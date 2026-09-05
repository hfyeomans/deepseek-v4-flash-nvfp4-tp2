"""CPU regression for folded DSpark expert quantization in installed vLLM.

Run inside the vLLM environment against the pinned model's original config.json:

    DSPARK_TEST_MODEL_CONFIG=/checkpoint/config.json \
        python3 tests/test_quant_dispatch.py -v

This executes the installed DeepseekV4FP8Config.from_config, get_quant_method,
and is_mxfp4_quant. Only the two GPU quantization-method constructors are
mocked. The actual RoutedExperts type is allocated without its GPU setup;
the test covers dispatch, not weight loading, kernel arithmetic, or inference.

The mixed-format and malformed-scope cases intentionally fail on the unchanged
preview image. The native MXFP4 control removes NVIDIA's conversion metadata
from a copy of the fixture; it is a control, not a second downloaded checkpoint.
"""

from __future__ import annotations

import copy
import json
import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch.nn as nn

from vllm.config import set_current_vllm_config
from vllm.models.deepseek_v4.quant_config import DeepseekV4FP8Config, RoutedExperts


DEFAULT_CONFIG_PATH = 'config.json'
EXPECTED_TARGET_LAYERS = 43
EXPECTED_DRAFT_LAYERS = 3
CONFIG_PATH = Path(os.environ.get('DSPARK_TEST_MODEL_CONFIG', DEFAULT_CONFIG_PATH))
NVFP4_METHOD = object()
MXFP4_METHOD = object()


class QuantDispatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration = json.loads(CONFIG_PATH.read_text())
        cls.target_layers = cls.configuration['num_hidden_layers']
        cls.draft_layers = len(cls.configuration['dspark_target_layer_ids'])

    @contextmanager
    def dispatch_context(self, configuration: dict):
        hf_config = SimpleNamespace(**copy.deepcopy(configuration))
        model_config = SimpleNamespace(hf_config=hf_config)
        context = SimpleNamespace(
            model_config=model_config,
            speculative_config=SimpleNamespace(
                method='dspark',
                draft_model_config=model_config,
            ),
        )
        # Preserve the real type check without allocating expert weights or
        # initializing distributed/GPU execution. Dispatch only needs moe_config.
        layer = RoutedExperts.__new__(RoutedExperts)
        nn.Module.__init__(layer)
        layer.moe_config = SimpleNamespace()
        with (
            set_current_vllm_config(context),
            patch(
                'vllm.model_executor.layers.quantization.modelopt.'
                'ModelOptNvFp4FusedMoE',
                return_value=NVFP4_METHOD,
            ),
            patch(
                'vllm.models.deepseek_v4.quant_config.Mxfp4MoEMethod',
                return_value=MXFP4_METHOD,
            ),
        ):
            quant_config = DeepseekV4FP8Config.from_config(
                hf_config.quantization_config,
            )
            context.quant_config = quant_config
            yield quant_config, layer

    def assert_routing(
        self,
        quant_config: DeepseekV4FP8Config,
        layer: RoutedExperts,
        prefix: str,
        expected: str,
    ) -> None:
        selected = quant_config.get_quant_method(layer, prefix)
        selected_name = (
            'NVFP4' if selected is NVFP4_METHOD
            else 'MXFP4' if selected is MXFP4_METHOD
            else type(selected).__name__
        )
        actual = (selected_name, quant_config.is_mxfp4_quant(prefix, layer))
        self.assertEqual(actual, (expected, expected == 'MXFP4'), prefix)

    def test_pinned_fixture_declares_main_only_nvfp4_scope(self) -> None:
        self.assertEqual(self.target_layers, EXPECTED_TARGET_LAYERS)
        self.assertEqual(self.draft_layers, EXPECTED_DRAFT_LAYERS)
        self.assertEqual(self.configuration['expert_dtype'], 'fp4')
        quant = self.configuration['quantization_config']
        self.assertEqual(quant['moe_quant_algo'], 'NVFP4')
        self.assertIn('mtp.*', quant['ignore'])
        expected_keys = {
            f'layers.{index}.ffn.experts' for index in range(self.target_layers)
        }
        self.assertEqual(set(quant['quantized_layers']), expected_keys)
        for declaration in quant['quantized_layers'].values():
            self.assertEqual(declaration['quant_algo'], 'NVFP4')
            self.assertEqual(declaration['group_size'], 16)

    def test_target_boundary_prefixes_remain_nvfp4(self) -> None:
        with self.dispatch_context(self.configuration) as (quant_config, layer):
            for index in (0, self.target_layers - 1):
                for wrapper in ('', 'model.'):
                    prefix = f'{wrapper}layers.{index}.ffn.experts'
                    with self.subTest(prefix=prefix):
                        self.assert_routing(quant_config, layer, prefix, 'NVFP4')

    def test_all_draft_prefixes_use_mxfp4_after_target_dispatch(self) -> None:
        with self.dispatch_context(self.configuration) as (quant_config, layer):
            # Reuse the same instance, as folded draft layers do in this image.
            self.assert_routing(
                quant_config, layer, 'model.layers.0.ffn.experts', 'NVFP4',
            )
            for index in range(
                self.target_layers, self.target_layers + self.draft_layers,
            ):
                for wrapper in ('', 'model.'):
                    prefix = f'{wrapper}layers.{index}.ffn.experts'
                    with self.subTest(prefix=prefix):
                        self.assert_routing(quant_config, layer, prefix, 'MXFP4')

    def test_native_mxfp4_control_without_conversion_metadata(self) -> None:
        configuration = copy.deepcopy(self.configuration)
        original = configuration['quantization_config']
        configuration['quantization_config'] = {
            name: original[name]
            for name in (
                'activation_scheme', 'fmt', 'quant_method',
                'scale_fmt', 'weight_block_size',
            )
        }
        indices = (0, self.target_layers - 1, *range(
            self.target_layers, self.target_layers + self.draft_layers,
        ))
        with self.dispatch_context(configuration) as (quant_config, layer):
            for index in indices:
                for wrapper in ('', 'model.'):
                    prefix = f'{wrapper}layers.{index}.ffn.experts'
                    with self.subTest(prefix=prefix):
                        self.assert_routing(quant_config, layer, prefix, 'MXFP4')

    def test_malformed_explicit_scope_is_rejected_by_both_dispatch_apis(self) -> None:
        last_key = f'layers.{self.target_layers - 1}.ffn.experts'
        valid_scope = self.configuration['quantization_config']['quantized_layers']
        missing_main = copy.deepcopy(valid_scope)
        missing_main.pop(last_key)
        missing_algorithm = copy.deepcopy(valid_scope)
        missing_algorithm[last_key].pop('quant_algo')
        unknown_algorithm = copy.deepcopy(valid_scope)
        unknown_algorithm[last_key]['quant_algo'] = 'INVALID_FORMAT'
        cases = {
            'not_a_mapping': [],
            'empty_explicit_scope': {},
            'missing_main_layer': missing_main,
            'missing_layer_algorithm': missing_algorithm,
            'unknown_layer_algorithm': unknown_algorithm,
        }
        prefix = f'model.{last_key}'
        for case_name, scope in cases.items():
            configuration = copy.deepcopy(self.configuration)
            configuration['quantization_config']['quantized_layers'] = scope
            for api in ('get_quant_method', 'is_mxfp4_quant'):
                with self.subTest(case=case_name, api=api):
                    with self.assertRaises(ValueError):
                        with self.dispatch_context(configuration) as (quant, layer):
                            if api == 'get_quant_method':
                                quant.get_quant_method(layer, prefix)
                            else:
                                quant.is_mxfp4_quant(prefix, layer)


if __name__ == '__main__':
    unittest.main(verbosity=2)
