# Research and observed runtime behavior

## Checkpoint

The [pinned NVIDIA model](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/tree/f1caa71142bd0be02f728c79f75042ac1e461579)
has 43 main layers and three DSpark layers. Target experts use group-16 NVFP4;
drafts retain group-32 MXFP4. Five draft positions and the 1,048,576 ceiling
describe the checkpoint, not hardware validation. NVIDIA didn't test
speculation for this release.

The installed encoder used older reasoning prefixes. CPU comparisons against
the 0731 low/high/max encoder reproduced the mismatch and verified the fix.

## Runtime provenance

Buildx history identifies `vllm-sm120-dsv4:preview-20260804` as
[jasl/vllm revision 0f59188](https://github.com/jasl/vllm/tree/0f59188db1504b042ce621842bdde6c0fe862df6),
target `vllm-openai`, CUDA 13.0.3, SM12.0, 16 build jobs and eight NVCC threads.
Sanitized provenance is in `results/`.

Runtime versions: vLLM 20260804, Torch 2.13.0+cu130, Transformers 5.16.1,
FlashInfer 0.6.16 and TVM FFI 0.1.11. All 2,175 shared Python files matched source;
compiled binaries weren't compared.

## Reproduced compatibility gaps

1. FlashInfer's precompiled cache needs an absent TVM symbol. Rebuilding works
   with existing NVRTC headers and the missing development-library link.
2. Global dispatch treats draft experts as NVFP4; scoped dispatch restores MXFP4.
3. Preview high/max reasoning prefixes differ from 0731.
4. Draft CUTLASS MXFP4/MXFP8 GEMM fails on SM120; Marlin works while target
   CUTLASS NVFP4 stays unchanged.
5. Fused parameter counts can hide missing tensors/shards; the opt-in diagnostic
   checks individual sources and bindings.

`docs/troubleshooting.md` records symptoms and validation limits for this
pinned model/runtime/hardware.

## User-reported MXFP4 comparison

The earlier MXFP4 run is a useful reference: the owner reported 801K and
possibly 1M. We haven't reproduced it here. Check actual allocations and launch
settings before explaining any difference.
