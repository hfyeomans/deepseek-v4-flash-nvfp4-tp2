# Recipe snapshot provenance and rollback

Use `recipe-1m-k5` when you need to get back to the clean tested snapshot.
Runtime/build files, patches, clients, fixtures, tests and results kept their
original bytes at that tag. Docs and repo administration were split from research.

The later [release review](../tasks/release-readiness/review.md) fixed benchmark
termination, stream records, report paths and patch direction, and added
onboarding/CPU CI. Historical results, fixtures and runtime patches stayed
unchanged. Old manifests identify tagged clients; later
[GPU checks](../tasks/release-readiness/verification.md) have separate records.

## Reproduce the runtime

The checkpoint remains `f1caa71142bd0be02f728c79f75042ac1e461579`; the vLLM
source remains `0f59188db1504b042ce621842bdde6c0fe862df6` plus the
[three recipe patches](../patches/README.md). See
[original build provenance](../results/original-build-provenance.json) and
[source-image provenance](../results/source-build-provenance.json).
Model weights aren't included. Apache-2.0 source attribution is preserved.

## Kernel sources and local changes

We adapted the kernel build and runtime integration for two RTX PRO 6000
Blackwell Max-Q cards. We reused upstream kernel implementations, compiled
relevant parts for SM120 and fixed the compatibility failures we encountered.
Our recipe patches change Python integration code; they don't rewrite CUDA
arithmetic kernels or PTX instructions.

These GPUs have [compute capability 12.0](https://developer.nvidia.com/cuda/gpus).
[build.sh](../build.sh) selects `torch_cuda_arch_list=12.0` with CUDA 13.0.3.
That targets their SM120 architecture. `TENSOR_PARALLEL_SIZE=2` separately tells
the server to split model computation across the two GPUs.

| Component | What we did |
|---|---|
| vLLM foundation | Rebuilt the pinned `jasl/vllm` community fork, which already contained SM120 and DeepSeek support. |
| Main NVFP4 computation | Used upstream FlashInfer/CUTLASS implementations. |
| FlashInfer kernel cache | Removed the incompatible precompiled JIT cache so affected kernels compile against the installed runtime. This accounts for some first-start compilation; other packaged binaries remain in the stack. |
| DSpark draft computation | Used the existing Marlin implementation for its MXFP4 weights after the inherited CUTLASS draft path failed during SM120 GEMM1 profiling. |
| Our patches | Corrected quantization selection, reasoning encoding and draft-weight coverage checks in Python. These fix integration and validation around the existing kernels. |

[Dockerfile.experimental](../Dockerfile.experimental) removes
`flashinfer-jit-cache`, exposes the installed NVRTC headers and adds the missing
`libnvrtc.so` linker name. This lets compilation use the installed TVM FFI/NVRTC
runtime after the bundled cache failed symbol resolution. The
[ABI diagnosis](troubleshooting.md#flashinfer-cache-and-tvm-abi) and
[patch inventory](../patches/README.md) explain the failures and fixes.
Keep the [named kernel cache](running.md#first-launch-and-kernel-cache) to reuse
compatible compiled kernels on later starts.

The [measured gains](performance-scorecard.md) come from comparisons of serving
configurations: DSpark, CUDA graphs, memory allocation, batching and prefill
scheduling. They don't measure gains from a new kernel implementation. Building
for SM120 establishes the architecture target; it doesn't establish the fastest
possible kernels for these Max-Q cards. The
[future kernel experiments](../tasks/kernel-experiments/state.md) track that
question separately from the tested recipe.

## Checkpoints and historical records

Use `recipe-1m-k5` for this recipe's recovery point. The original
`baseline-1m-k5` Git tag and combined history remain in the private adaptive
archive. Old IDs in results identify the measurement environment; they are
not available refs in this clean repo. Keep those records unchanged.

The local Docker tag `dsv4-nvfp4:baseline-1m-k5` names image
`sha256:1f0776d3ac4a990186899d122ebee81e5ad0bcdf1dbb95ebccb30d5f94c6908e`
on the test host, independently of Git tags. It wasn't uploaded to a registry.
See [recovery instructions](running.md#preserved-baseline-and-rollback).

## Working copies after the history change

Start with a clean clone. Merging an old combined branch would bring research
history back into this repo. Keep research private, and label new measurements
with their own image/settings instead of rewriting historical results.
