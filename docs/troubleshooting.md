# Reproduced failures

These are the failures we reproduced and the fixes we checked. Use the symptoms
to find the relevant case, then validate your own GPU/API behavior if the image
or model revision differs.

## Python packaging deprecation warning

`SetuptoolsDeprecationWarning: setup.py install is deprecated` is a maintenance
warning. It doesn't by itself fail the build or show a runtime/DSpark defect.
Keep the full log, including the step heading above the warning, and check the
build's exit status. An image with the same tag may be left from an older build.

The pinned upstream [Dockerfile](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/docker/Dockerfile#L575)
invokes `setup.py bdist_wheel`, which can reach the deprecated install machinery
while assembling a wheel. The reported step `#57` alone doesn't identify the
emitting package. [PyPA's guidance](https://packaging.python.org/en/latest/discussions/setup-py-deprecated/)
is to use a build frontend such as `python -m build`; setuptools and `setup.py`
as configuration remain supported.

This needs follow-up before updating the build toolchain. Migrate the upstream
wheel steps, preserve their CUDA/build flags and Python ABI tag, then run a full
build, the 13 image CPU tests and GPU/API checks. We haven't made that packaging
change or suppressed the warning. Track it in the
[operator test record](../tasks/operator-experience/state.md).

## FlashInfer cache and TVM ABI

The original image loads the main model at 77.83 GiB per GPU, then both workers
exit while loading `flashinfer_jit_cache/.../fused_moe_120.so`:

```text
undefined symbol: TVMFFIGetCustomAllocator
```

The FlashInfer cache is 0.6.16+cu130, commit
`8da13a29c85f7e5b1c81878d933f84ae9fc4afa9`. Its version matches the Python
package, but `apache-tvm-ffi==0.1.11` doesn't export the required symbol.
Matching version strings didn't guarantee ABI compatibility.

`Dockerfile.experimental` removes the precompiled cache so FlashInfer builds
against the installed runtime. The first rebuild could not find `nvrtc.h`,
which already existed in the Python CUDA package. The Dockerfile adds its
directory to `CPLUS_INCLUDE_PATH` and creates the required unversioned
`libnvrtc.so` link to `libnvrtc.so.13` inside the image. The host toolkit stays
unchanged.

The rebuilt `fused_moe_120.so` linked and loaded with `LD_BIND_NOW=1` to check
symbol resolution. Serving still required a separate test.

Keep the kernel-cache volume so restarts reuse compiled kernels. First startup
can take minutes. Check worker errors and compiler activity before assuming
shared-memory timeout messages mean a deadlock.

## NVFP4 target with MXFP4 DSpark draft

The checkpoint's `quantized_layers` declares main expert layers 0–42 as NVFP4.
Its `mtp.*` draft experts retain group-32 MXFP4 scales. The installed vLLM dispatch
ignores this scope and selects NVFP4 for folded draft runtime layers 43–45.

Patch 0001 shares a per-layer resolver between quantizer selection and the
MXFP4 predicate. It keeps target experts NVFP4, selects MXFP4 for the excluded
DSpark experts and rejects unknown or invalid explicit coverage. Weight bytes
and generic speculative-model ownership stay unchanged.

The [CPU regression](../tests/test_quant_dispatch.py) failed before the patch
and passed afterward. That checks dispatch. GPU loading, output and accepted
draft tokens require separate validation.

## Reasoning-effort prompts changed in 0731

The installed encoder uses the older two-level convention: `high` has no prefix,
and `max` uses the prefix now assigned to `high`. The pinned 0731 encoder defines
three levels: `low` has no prefix, `high` uses “Absolute maximum”, and `max` uses
“Beyond maximum”.

Patch 0002 corrects the prefixes and tokenizer `low` mapping.
[Tests](../tests/test_reasoning_encoding.py) compare full rendered prompts with
the checkpoint encoder, covering disabled thinking, the default and `xhigh`.
All four methods pass; three assertions failed before the patch. API reasoning
is tested separately.

Source: [pinned model encoding reference](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/blob/f1caa71142bd0be02f728c79f75042ac1e461579/encoding/README.md).

## Draft CUTLASS MXFP4/MXFP8 kernel fails on SM120

After patch 0001, the draft inherits `flashinfer_cutlass` and selects
`FLASHINFER_CUTLASS_MXFP4_MXFP8`. Loading succeeds, but FlashInfer autotuning
fails. The asynchronous error appears during random test-tensor allocation
alongside TMA descriptor errors; that location obscures the kernel fault.

A repeat with `CUDA_LAUNCH_BLOCKING=1` locates the failure in the draft GEMM1
profiler's generated `cutlass_kernel_file_gemm_grouped_sm120_M128_BS_group8`
kernel, for FP8 activations, FP4 weights, and BF16 output. The error is
`Failed to run cutlass TMA WS grouped gemm. Error: Error Internal`, followed by
CUDA illegal instruction during cleanup. This reproduces on both TP workers.

Setting `"moe_backend":"marlin"` in the speculative configuration resolved
serving. V1 applies it independently of the target's FlashInfer CUTLASS backend.
All 20 synthetic API checks passed at 64K with DSpark and CUDA graphs, and
accepted draft-token counters increased.

## Slow Ubuntu package downloads during the public rebuild

On the test host, the original HTTP package-index fetch remained stalled after
more than ten minutes. Small container probes reproduced timeouts. A 64 KiB
HTTPS/IPv4 probe over host networking completed in 0.14 seconds.

Setting `APT_HTTPS_IPV4=1` and `BUILD_NETWORK=host` in `.env` switches the pinned CUDA parents to HTTPS
for the same Ubuntu repositories and forces APT to use IPv4. Package signatures
remain verified. It passed the stalled fetch, completed the build and passed
[source-image acceptance](source-image-validation.md). The default build keeps
upstream networking.
