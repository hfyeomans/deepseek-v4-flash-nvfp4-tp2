# Reproduced failures

These observations apply to the tested image and exact model revision. A proposed
remedy remains experimental until the GPU/API validation confirms it.

## FlashInfer cache and TVM ABI

The original image loads the main model at 77.83 GiB per GPU, then both workers
exit while loading `flashinfer_jit_cache/.../fused_moe_120.so`:

```text
undefined symbol: TVMFFIGetCustomAllocator
```

The cache is FlashInfer 0.6.16+cu130, commit
`8da13a29c85f7e5b1c81878d933f84ae9fc4afa9`. The installed
`apache-tvm-ffi==0.1.11` shared library does not export that symbol. The Python
FlashInfer package's version matches the cache; checking version strings alone
does not establish ABI compatibility.

`Dockerfile.experimental` removes the precompiled cache in a derivative image,
allowing FlashInfer to compile against its installed headers and runtime.
The first rebuild failed because `nvrtc.h` was outside the compiler's search
path. The header already exists in the Python CUDA package; the Dockerfile adds
that directory through `CPLUS_INCLUDE_PATH`. The final link also required an
unversioned `libnvrtc.so` link to the existing `libnvrtc.so.13`; this is created
inside the derivative image. No host toolkit was changed.

The rebuilt `fused_moe_120.so` then linked and loaded successfully with
`LD_BIND_NOW=1`, which resolves symbols eagerly. Complete serving is a separate
validation step.

The kernel cache volume preserves completed compilation across test launches.
First-start compilation can take several minutes. Shared-memory timeout notices
during active compiler work do not themselves prove a deadlock; inspect the
actual worker error and compiler processes.

## NVFP4 target with MXFP4 DSpark draft

The checkpoint's `quantized_layers` declares main expert layers 0–42 as NVFP4.
Its `mtp.*` draft experts retain group-32 MXFP4 scales. The installed vLLM dispatch
ignores this scope and selects NVFP4 for folded draft runtime layers 43–45.

Patch 0001 adds one per-layer resolver shared by quantizer selection and the
MXFP4 predicate. It keeps target experts NVFP4, maps the explicitly excluded
DSpark experts to MXFP4, and rejects invalid or unknown explicit coverage. It
does not rewrite weights or alter generic speculative-model ownership.

The [CPU regression](../tests/test_quant_dispatch.py) fails before the patch and
passes after it. This proves format dispatch only. Complete draft loading,
correct GPU output, and positive accepted-draft-token metrics are separate gates.

## Reasoning-effort prompts changed in 0731

The installed encoder uses the older two-level convention: `high` has no prefix,
and `max` uses the prefix now assigned to `high`. The pinned 0731 encoder defines
three levels: `low` has no prefix, `high` uses “Absolute maximum”, and `max` uses
“Beyond maximum”.

Patch 0002 updates only these prefixes and the tokenizer's `low` mapping.
[Tests](../tests/test_reasoning_encoding.py) compare complete rendered prompts
against the pinned checkpoint's own encoder, including disabled thinking, the
default, and the `xhigh` alias. All four test methods pass after the patch;
three assertions failed before it. API-level reasoning remains separately tested.

Source: [pinned model encoding reference](https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4/blob/f1caa71142bd0be02f728c79f75042ac1e461579/encoding/README.md).

## Draft CUTLASS MXFP4/MXFP8 kernel fails on SM120

After patch 0001, the draft selects `FLASHINFER_CUTLASS_MXFP4_MXFP8` when it
inherits the target's `flashinfer_cutlass` setting. Draft loading completes, but
warm-up fails during FlashInfer autotuning. The initial asynchronous CUDA error
appears at allocation of a random test tensor, with additional TMA descriptor
errors. That allocation is not the origin of the kernel fault.

A repeat with `CUDA_LAUNCH_BLOCKING=1` locates the failure in the draft GEMM1
profiler's generated `cutlass_kernel_file_gemm_grouped_sm120_M128_BS_group8`
kernel, for FP8 activations, FP4 weights, and BF16 output. The error is
`Failed to run cutlass TMA WS grouped gemm. Error: Error Internal`, followed by
CUDA illegal instruction during cleanup. This reproduces on both TP workers.

The next experiment uses `"moe_backend":"marlin"` inside the speculative
configuration. This pinned runtime's V1 draft configuration applies that option
independently of the target backend. The main NVFP4 model continues using
FlashInfer CUTLASS. This configuration resolved serving. All 20 synthetic API checks passed with
DSpark at 64K using CUDA graphs, and accepted draft token counters increased.

## Slow Ubuntu package downloads during the public rebuild

On the test host, the original HTTP package-index fetch remained stalled after
more than ten minutes. Small container probes reproduced timeouts. A 64 KiB
HTTPS/IPv4 probe over host networking completed in 0.14 seconds.

The optional build profile `APT_HTTPS_IPV4=1 BUILD_NETWORK=host` prepares the same
pinned CUDA parent images with HTTPS URLs for the same Ubuntu repositories and
forces IPv4 for APT. It does not disable package-signature verification. This
profile passed the stalled index-fetch stage and proceeded to dependency
installation; complete public-image acceptance remains pending. The normal
build profile retains the upstream network configuration.
