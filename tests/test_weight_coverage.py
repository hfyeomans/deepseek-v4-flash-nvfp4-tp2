"""Exercise the real DSpark loader's opt-in coverage diagnostic on the CPU.

Run in the patched vLLM environment: python3 tests/test_weight_coverage.py -v

The fixture uses the pinned 0731 checkpoint's source names: three draft layers,
256 experts, 4,608 expert tensors, 99 non-expert tensors, and 99 fused parameter
bindings. Values and parameter shapes are deliberately tiny synthetic CPU data.
Parallel-rank discovery and expert mapping are replaced with fixture equivalents;
parameter callbacks copy CPU values and report success. The installed load_weights
method, its name remapping, and its coverage checks execute unchanged.

This tests coverage bookkeeping and rejection of missing source shards. It does
not validate production tensor shapes, numerical values, kernels, or inference.
"""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
import vllm.models.deepseek_v4.nvidia.dspark as dspark


DRAFT_LAYERS = 3
ROUTED_EXPERTS = 256
ATTENTION_HEADS = 64
TP_SIZE = 2
EXPERT_TENSOR_COUNT = DRAFT_LAYERS * ROUTED_EXPERTS * 3 * 2

LAYER_SOURCES = (
    'attn.attn_sink', 'attn.kv_norm.weight', 'attn.q_norm.weight',
    'attn.wkv.scale', 'attn.wkv.weight',
    'attn.wo_a.scale', 'attn.wo_a.weight',
    'attn.wo_b.scale', 'attn.wo_b.weight',
    'attn.wq_a.scale', 'attn.wq_a.weight',
    'attn.wq_b.scale', 'attn.wq_b.weight',
    'attn_norm.weight', 'ffn.gate.bias', 'ffn.gate.weight',
    'ffn.shared_experts.w1.scale', 'ffn.shared_experts.w1.weight',
    'ffn.shared_experts.w2.scale', 'ffn.shared_experts.w2.weight',
    'ffn.shared_experts.w3.scale', 'ffn.shared_experts.w3.weight',
    'ffn_norm.weight', 'hc_attn_base', 'hc_attn_fn', 'hc_attn_scale',
    'hc_ffn_base', 'hc_ffn_fn', 'hc_ffn_scale',
)
LAYER_PARAMETERS = (
    'attn.attn_sink', 'attn.kv_norm.weight', 'attn.q_norm.weight',
    'attn.fused_wqa_wkv.weight', 'attn.fused_wqa_wkv.weight_scale_inv',
    'attn.wo_a.weight', 'attn.wo_a.weight_scale_inv',
    'attn.wo_b.weight', 'attn.wo_b.weight_scale_inv',
    'attn.wq_b.weight', 'attn.wq_b.weight_scale_inv',
    'attn_norm.weight', 'ffn.gate.e_score_correction_bias', 'ffn.gate.weight',
    'ffn.shared_experts.gate_up_proj.weight',
    'ffn.shared_experts.gate_up_proj.weight_scale_inv',
    'ffn.shared_experts.down_proj.weight',
    'ffn.shared_experts.down_proj.weight_scale_inv',
    'ffn_norm.weight', 'hc_attn_base', 'hc_attn_fn', 'hc_attn_scale',
    'hc_ffn_base', 'hc_ffn_fn', 'hc_ffn_scale',
    'ffn.experts.w13_weight', 'ffn.experts.w13_weight_scale',
    'ffn.experts.w2_weight', 'ffn.experts.w2_weight_scale',
)
TOP_SOURCES = (
    'embed.weight', 'head.weight',
    'mtp.0.main_proj.weight', 'mtp.0.main_proj.scale', 'mtp.0.main_norm.weight',
    'mtp.2.norm.weight', 'mtp.2.hc_head_fn',
    'mtp.2.hc_head_base', 'mtp.2.hc_head_scale',
    'mtp.2.markov_head.markov_w1.weight', 'mtp.2.markov_head.markov_w2.weight',
    'mtp.2.confidence_head.proj.weight',
)
TOP_PARAMETERS = (
    'embed_tokens.weight', 'head.weight',
    'main_proj.weight', 'main_proj.weight_scale_inv', 'main_norm.weight',
    'norm.weight', 'hc_head_fn', 'hc_head_base', 'hc_head_scale',
    'markov_w1.weight', 'markov_w2.weight', 'confidence_head.weight',
)


def copy_fixture_weight(param, loaded_weight, *_args, **kwargs):
    param.data.copy_(loaded_weight)
    return True if kwargs.get('return_success') else None


def expert_mapping(_model, *, num_experts: int, **_kwargs):
    return [
        (f'experts.{fused}_', f'experts.{expert}.{projection}.', expert, projection)
        for expert in range(num_experts)
        for projection, fused in (('w1', 'w13'), ('w2', 'w2'), ('w3', 'w13'))
    ]


class LoaderFixture:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            n_routed_experts=ROUTED_EXPERTS,
            num_attention_heads=ATTENTION_HEADS,
            expert_dtype='fp4',
        )
        self.num_dspark_layers = DRAFT_LAYERS
        self.pad_shared_expert = False
        self.layers = OrderedDict(
            (str(index), SimpleNamespace(ffn=SimpleNamespace(use_mega_moe=False)))
            for index in range(DRAFT_LAYERS)
        )
        names = list(TOP_PARAMETERS) + [
            f'layers.{index}.{suffix}'
            for index in range(DRAFT_LAYERS)
            for suffix in LAYER_PARAMETERS
        ]
        self.parameters = {}
        for name in names:
            size = ATTENTION_HEADS // TP_SIZE if name.endswith('attn_sink') else 1
            param = torch.nn.Parameter(torch.zeros(size), requires_grad=False)
            param.weight_loader = copy_fixture_weight
            self.parameters[name] = param

    def named_parameters(self):
        return iter(self.parameters.items())

    def finalize_mega_moe_weights(self) -> None:
        pass

    def weights(self, omitted: str | None = None):
        names = list(TOP_SOURCES) + [
            f'mtp.{index}.{suffix}'
            for index in range(DRAFT_LAYERS)
            for suffix in LAYER_SOURCES
        ] + [
            f'mtp.{index}.ffn.experts.{expert}.{projection}.{suffix}'
            for index in range(DRAFT_LAYERS)
            for expert in range(ROUTED_EXPERTS)
            for projection in ('w1', 'w2', 'w3')
            for suffix in ('weight', 'scale')
        ]
        for name in names:
            if name != omitted:
                size = ATTENTION_HEADS if name.endswith('attn_sink') else 1
                yield name, torch.ones(size)


class WeightCoverageTest(unittest.TestCase):
    def run_loader(self, omitted: str | None = None, rank: int = 0, enabled=True):
        fixture = LoaderFixture()
        with (
            patch.dict('os.environ', {'DSPARK_VERIFY_WEIGHT_COVERAGE': '1' if enabled else '0'}),
            patch.object(dspark, 'get_tensor_model_parallel_world_size', return_value=TP_SIZE),
            patch.object(dspark, 'get_tensor_model_parallel_rank', return_value=rank),
            patch.object(dspark, 'fused_moe_make_expert_params_mapping', expert_mapping),
        ):
            loaded = dspark.DSparkDeepseekV4ForCausalLM.load_weights(
                fixture, fixture.weights(omitted),
            )
        return fixture, loaded

    def test_complete_fixture_passes_on_both_tp_ranks(self) -> None:
        fixture = LoaderFixture()
        names = [name for name, _weight in fixture.weights()]
        self.assertEqual(len([name for name in names if '.ffn.experts.' in name]), EXPERT_TENSOR_COUNT)
        self.assertEqual(len(names) - EXPERT_TENSOR_COUNT, 99)
        for rank in range(TP_SIZE):
            with self.subTest(rank=rank):
                fixture, loaded = self.run_loader(rank=rank)
                self.assertEqual(loaded, set(fixture.parameters))
                self.assertEqual(len(loaded), 99)

    def test_missing_fused_companion_is_rejected(self) -> None:
        for projection in ('attn.wkv', 'ffn.shared_experts.w3'):
            for suffix in ('weight', 'scale'):
                omitted = f'mtp.0.{projection}.{suffix}'
                with self.subTest(omitted=omitted):
                    with self.assertRaisesRegex(ValueError, 'missing fused sources'):
                        self.run_loader(omitted=omitted)

    def test_missing_expert_tensor_is_still_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, 'missing experts'):
            self.run_loader(omitted='mtp.0.ffn.experts.0.w1.weight')

    def test_disabled_diagnostic_preserves_loader_behavior(self) -> None:
        fixture, loaded = self.run_loader(
            omitted='mtp.0.attn.wkv.weight', enabled=False,
        )
        self.assertEqual(loaded, set(fixture.parameters))


if __name__ == '__main__':
    unittest.main(verbosity=2)
