# Research and observed runtime behavior

## Checkpoint

The exact [NVIDIA revision](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/tree/f1caa71142bd0be02f728c79f75042ac1e461579)
contains 43 main transformer layers and three DSpark draft layers. The main
experts use NVFP4 with group-16 scales; the draft retains MXFP4 with group-32
scales. The five-token DSpark block and 1,048,576 model context ceiling are
checkpoint properties, not proof of hardware support or practical context.
NVIDIA explicitly did not validate speculative decoding for this release.

The official 0731 encoder distinguishes low, high, and max reasoning. The
installed preview encoder retained an older convention. CPU comparisons against
the pinned checkpoint reproduced and then verified the corrected prompts.

## Runtime provenance

The user's exact image is `vllm-sm120-dsv4:preview-20260804`. Docker Buildx history
identifies [jasl/vllm revision 0f59188](https://github.com/jasl/vllm/tree/0f59188db1504b042ce621842bdde6c0fe862df6),
target `vllm-openai`, CUDA 13.0.3 base images, SM12.0, 16 build jobs, and eight
NVCC threads. Sanitized original provenance is in `results/`.

The image's runtime is vLLM 20260804, Torch 2.13.0+cu130, Transformers 5.16.1,
FlashInfer 0.6.16, and TVM FFI 0.1.11. Python source comparison found 2,175 exact
matches with the source checkout; compiled binaries were not compared.

## Reproduced compatibility gaps

1. The precompiled FlashInfer cache references an absent TVM allocator symbol.
   Rebuilding against the installed runtime works after exposing existing NVRTC
   headers and providing the existing runtime library's development link.
2. Global quantization dispatch incorrectly routes draft experts as NVFP4.
   Scoped dispatch keeps target NVFP4 and draft MXFP4.
3. The preview tokenizer's high/max reasoning prefixes differ from 0731.
4. Draft CUTLASS MXFP4/MXFP8 grouped GEMM fails on SM120. Explicit Marlin draft
   selection resolves serving; target CUTLASS NVFP4 remains unchanged.
5. A fused parameter count alone can conceal missing expert tensors or missing
   companion projection shards. The opt-in diagnostic checks finer-grained loads.

See `docs/troubleshooting.md` for exact symptoms and proof boundaries. These
findings apply to the pinned revision and hardware; they are not claims about
all current vLLM versions or GPU architectures.

## User-reported MXFP4 comparison

The user reports that the earlier MXFP4 build reached 801K and possibly 1M
context on this machine. Treat this as a user-observed reference point;
that run has not been reproduced in this investigation. Compare actual NVFP4
weight/draft/KV allocations and launch settings before explaining any gap.
