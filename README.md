# DeepSeek V4 Flash NVFP4 on two RTX PRO 6000 Max-Q GPUs

A tested vLLM recipe for `nvidia/DeepSeek-V4-Flash-0731-NVFP4` on two NVIDIA
RTX PRO 6000 Blackwell Max-Q GPUs, 96 GB each, at tensor parallelism 2.
The repository contains build inputs, runtime patches, launch instructions,
benchmark clients and measured findings. Model weights are not included.

**Selected everyday coding/tools profile: 1,000,000-token ceiling, 96% memory,
batch budget 2,048, prefill cap 1,792, two request slots and fixed-K5 DSpark.**
It passed near-1M synthetic retrieval, a warmed restart and 19 short API checks.
Long-input retrieval and short API checks are separate evidence; neither is a
broad coding-quality evaluation or proof of two simultaneous 1M requests.

## Build and use it

Start with [your first deployment](docs/first-run.md), an ordered walkthrough
from machine prerequisites to a working coding/tools endpoint. The
[full running guide](docs/running.md) adds profile choices and experiments.
Completing the walkthrough leaves the selected coding/tools profile running;
you can connect your client immediately.

The generic launcher defaults remain 64K / 95%; use the explicit overrides for
the selected profile. For tools sharing very long inputs, the secondary profile
uses cap512 with the same other limits. It improved concurrent-tool latency in
our tests at the cost of slower long coding requests. See the
[profile comparison and both launch commands](docs/running.md#recommended-coding-profile).

## Acceleration benefits and costs

The [performance scorecard](docs/performance-scorecard.md) keeps the historical
progression and a dedicated primary everyday coding/tools section. The latest
[exact-primary DSpark on/off screen](docs/primary-control-screen.md) holds the
image, checkpoint and primary settings fixed:

| Workload | DSpark off | DSpark on | Observed benefit |
|---|---:|---:|---|
| Short code, one request | 93.66 tok/s | 200.64 tok/s | 2.14× throughput |
| Two short requests, aggregate median | 164.59 tok/s | 226.03 tok/s | 1.37× throughput |
| 48,345-token code input, 512-token answer | 11.983 s | 8.790 s | 26.6% less elapsed time |

These are three-observation medians, not p95 or an established optimum. The
three DSpark-on concurrent trials were 226.03 / 204.43 / 296.16 tok/s; that
screen lacked an independent C2 warmup. Short-code first output increased from
75.7 to 84.4 ms despite faster completion. DSpark also consumes memory: the
reporting worker's available KV budget fell from 11.43 to 5.93 GiB.

The earlier matched 64K short-prompt comparison measured about **95.5 tok/s
with graphs alone and 174–209 with DSpark**, a **1.8–2.2×** gain. Its single
two-request trial reached **292.90 tok/s**, versus 168.55 without DSpark. These
30–41-token prompts do not establish long-context speed. The scorecard preserves
the initial eager → graphs → DSpark progression, configuration differences,
all trials and links to unrounded evidence; it does not substitute the best
historical observation for the latest matched median.

For learning how the gains arise, see [DSpark activity and capabilities](docs/dspark-evaluation.md),
[why the recipe uses K5](docs/dspark-k-and-verification.md),
[diagnostic component profiles](docs/component-profiling.md), and
[the matched measurement protocol](docs/optimization-evaluation.md).

## Context, memory and feature findings

Both 801K and near-1M retrieval goals were reached. The selected profile's
998,869-token prompt completed in 513.759 seconds in a single mixed test;
the overlapping tool roundtrip took 32.035 seconds. Cap512 recorded 539.998
seconds and 18.113 seconds respectively. These are synthetic observations,
not general long-context quality or steady-state throughput estimates.

- [Profile tradeoffs](docs/interactive-latency.md): everyday coding versus tools
  overlapping long prefill, with all measured repeats.
- [Memory review](docs/memory-utilization-review.md): why 96% was selected,
  what 95% and 97% attempts showed, and startup versus serving headroom.
- [Context and batch](docs/context-batch.md): limits, concurrency and the
  measurements needed before choosing a larger batch.
- [Source-image validation](docs/source-image-validation.md) and
  [feature requirements](docs/validation.md): reasoning, tools, streaming,
  structured output, cancellation, concurrency and proof boundaries.

Target decode graphs, parallel drafting, Markov correction and target
verification are active. The learned confidence head is loaded but unused by
this pinned inference chain. Adaptive verification and optional draft-forward
graphs have no measured benefit claimed here.

## Provenance and repository boundary

Checkpoint: `f1caa71142bd0be02f728c79f75042ac1e461579`; public-source fork:
`0f59188db1504b042ce621842bdde6c0fe862df6`, plus the
[three documented runtime patches](patches/README.md). The main experts are
NVFP4; embedded DSpark experts retain MXFP4 and use Marlin. The source-built
image passed its 13 runtime CPU tests. Local client/profile checks and recorded
GPU results are separate from those image tests.

For changes, use the [local checks and development workflow](docs/development.md).

This recipe and its findings remain in
[deepseek-v4-flash-nvfp4-tp2](https://github.com/hfyeomans/deepseek-v4-flash-nvfp4-tp2).
Adaptive research, compatibility work and future experiments now belong in the
separate private [adaptive-verification repository](https://github.com/hfyeomans/deepseek-v4-flash-adaptive-verification).
Shared measurements explain acceleration here and provide comparison controls
there. No adaptive speedup is inferred from fixed-K5 results.

This repository starts from a clean recipe snapshot. Original combined history
and its rollback reference are retained in the private research archive. The
clean recipe checkpoint is `recipe-1m-k5`. See [provenance and rollback](docs/provenance.md)
and [repository boundaries](docs/repository-boundaries.md). The repository
remains private pending publication checks. Recipe code and vLLM modifications
use Apache-2.0; model weights retain their own license.
