# DeepSeek V4 Flash NVFP4 on two RTX PRO 6000 Max-Q GPUs

I wanted this model for everyday coding and tools, with room for very long
inputs. I also wanted to understand what it took to reach 801K and 1M context
on two GPUs. This repo turns that work into a recipe you can run and learn from:
`nvidia/DeepSeek-V4-Flash-0731-NVFP4` on two NVIDIA RTX PRO 6000 Blackwell Max-Q
GPUs, 96 GB each, at tensor parallelism 2. Build inputs, patches, clients and
measurements are included; download the weights separately.

**For everyday coding/tools, start with the tested 1,000,000-token ceiling,
96% memory, batch budget 2,048, prefill cap 1,792, two slots and fixed-K5 DSpark.**
DSpark proposes draft tokens for the main model to verify. This profile passed
near-1M synthetic retrieval, a warmed restart and 19 short API checks. Broad
coding accuracy and two simultaneous 1M requests still need testing.

## Build and use it

Follow [your first deployment](docs/first-run.md) to prepare the host, build
and check the image, then connect a client. Use the
[running guide](docs/running.md) when you're ready to compare profiles or
repeat the experiments.

Copy [example.env](example.env) to `.env` and edit it for your host. Both build
and serve require it. The example uses the selected 1M/96% profile; change the
prefill cap to 512 for the secondary profile. That improved tool latency during
long inputs at the cost of slower foreground coding. See
[configuration and the tradeoff](docs/running.md#recommended-coding-profile).

## Acceleration benefits and costs

The [scorecard](docs/performance-scorecard.md) shows what each optimization
actually bought us. For the selected profile, this
[DSpark on/off test](docs/primary-control-screen.md) keeps the image, checkpoint
and other settings fixed:

| Workload | DSpark off | DSpark on | Observed benefit |
|---|---:|---:|---|
| Short code, one request | 93.66 tok/s | 200.64 tok/s | 2.14× throughput |
| Two short requests, aggregate median | 164.59 tok/s | 226.03 tok/s | 1.37× throughput |
| 48,345-token code input, 512-token answer | 11.983 s | 8.790 s | 26.6% less elapsed time |

These are medians of three observations. Concurrent DSpark-on trials ranged
from 204.43 to 296.16 tok/s, with a median of 226.03 and no separate C2 warmup.
Short-code first output rose from 75.7 to 84.4 ms despite faster completion.
DSpark reduced the reporting worker's available KV budget from 11.43 to
5.93 GiB. This sample can't establish p95 latency or an optimum.

The earlier matched 64K comparison measured about **95.5 tok/s with graphs
alone and 174–209 with DSpark**, a **1.8–2.2×** gain. One two-request trial
reached **292.90 tok/s**, versus 168.55 without DSpark. Those 30–41-token
prompts tell us about short-input speed. The scorecard keeps these historical
results separate from the latest matched medians.

To understand where the gains come from, read
[how we check DSpark](docs/dspark-evaluation.md),
[why K5 is fixed](docs/dspark-k-and-verification.md),
[where GPU time goes](docs/component-profiling.md) and
[how to measure a fair comparison](docs/optimization-evaluation.md).

## Context, memory and feature findings

We reached both synthetic retrieval goals. In one mixed test, the selected
profile completed a 998,869-token prompt in 513.759 seconds and an overlapping
tool roundtrip in 32.035 seconds. Cap 512 took 539.998 and 18.113 seconds.
That's useful capacity, but tools can still take tens of seconds during a huge
input. These single trials don't establish general long-context accuracy or
sustained throughput.

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
verification are active. The confidence head is loaded but unused. Adaptive
verification and optional draft-forward graphs have no measured gain here.

## Provenance and repository boundary

Checkpoint: `f1caa71142bd0be02f728c79f75042ac1e461579`; source fork:
`0f59188db1504b042ce621842bdde6c0fe862df6`, with
[three runtime patches](patches/README.md). Main experts use NVFP4; embedded
DSpark experts use MXFP4 with Marlin. The source image passed 13 runtime CPU
tests; client checks and GPU measurements are recorded separately.

The [kernel sources and local changes](docs/provenance.md#kernel-sources-and-local-changes)
table explains what we rebuilt for SM120, which upstream implementations we
reused and how we fixed their integration. Further kernel experiments are planned;
the current gains measure serving configurations.

For changes, use the [local checks and development workflow](docs/development.md).

Deployment code and findings live in
[deepseek-v4-flash-nvfp4-tp2](https://github.com/hfyeomans/deepseek-v4-flash-nvfp4-tp2).
The private [adaptive-verification repository](https://github.com/hfyeomans/deepseek-v4-flash-adaptive-verification)
owns adaptive compatibility research and adaptive experiments. It shares these baseline
measurements; adaptive speedup remains unmeasured.

The clean recipe checkpoint is `recipe-1m-k5`. Original combined history and
rollback references remain in the private research archive. See
[provenance and rollback](docs/provenance.md),
[repository boundaries](docs/repository-boundaries.md) and
[release status](tasks/publication/state.md). Recipe code and vLLM modifications
use Apache-2.0; model weights retain their own license.
