# Critical evaluation of 97% GPU memory utilization

I wanted to challenge whether 97% would buy us anything useful. It passed
startup, 19 API checks and near-1M retrieval with DSpark and graphs, but a short
request still timed out behind uncapped prefill. Both 96% and 97% recovered
three facts from 998,847 tokens in 509.7 and 508.1 seconds respectively; 96%
also passed 19 follow-up checks. Those unmatched timings don't establish a gain.

## What the percentage controls

`request_memory` multiplies CUDA-visible memory by `gpu_memory_utilization`.
The worker subtracts profiled non-KV allocations and estimated graph memory
to size the KV pool. This startup budget isn't a driver-enforced allocation
ceiling.

Sources: [requested-memory calculation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/worker/utils.py#L433),
[KV-budget calculation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/worker/gpu_worker.py#L464).

Each GPU reports about 95.01 GiB CUDA-visible memory. Moving from 96% to 97%
adds **0.95 GiB / 973 MiB per GPU** if the profile stays unchanged. TP requires
both ranks' pools; their budgets aren't independently additive.

## Evidence for and against 97%

| Observation | Implication |
|---|---|
| 1M/95% failed admission: 5.73 GiB needed, 4.98 GiB available | 95% is insufficient for this exact batch-2048 configuration |
| 1M/96% started: 5.93 GiB KV, reported 1.14x cache concurrency | 97% is unnecessary merely to start 1M |
| The 97% launch reported 6.88 GiB KV | More cache could help prefix retention or mixed request lengths |
| Reported cache concurrency at 97% is only about 1.32x | This does not establish two simultaneous full 1M requests |
| During 96% startup autotuning, the observed free memory was 657/622 MiB | An additional 973 MiB makes transient allocation failure plausible |
| During the early 96% long-input request, observed free memory was 1,535/1,500 MiB | Steady inference had more headroom than the sampled startup peak |

These snapshots can miss peaks. Driver-reserved memory explains the difference
between used-plus-free and displayed total; allocator reservations may be
reclaimable. The later 97% startup passed with **347/312 MiB minimum sampled
free memory**, followed by 19 API checks and near-1M retrieval. A separate
mixed probe timed out after 180 seconds. More cache didn't fix scheduling.
See [startup/API evidence](../results/dspark-1m-97-startup-api.json).

After warmup, the 96% log recommends 5.68 GiB KV but reports 5.93 GiB allocated.
The recommendation includes a 150 MiB buffer for profiling underestimates.
Likewise, 97% doesn't guarantee 3% free at runtime.

## Feature and performance consequences

Raising the percentage trades headroom for KV capacity. DSpark's five proposals,
model/KV precision, graphs, reasoning, tools, structured output, streaming and
prefix caching remain enabled.

It doesn't raise `max_model_len` or add sequence slots. Prompt, reasoning,
tool history and output still share the same token limit. Extra KV alone
promises no single-request speed gain.

Other memory-saving changes have separate costs. Fewer slots reduce concurrency;
disabling DSpark loses its measured short-input gain. Removing the roughly
0.10 GiB graph pool loses graph acceleration and still would not cover the
0.75 GiB admission shortfall at 95%. See
[vLLM's graph memory guide](https://docs.vllm.ai/en/latest/configuration/conserving_memory/#reduce-cuda-graphs).

The 97% experiment retained these features.

## How to choose the fastest practical profile

I'd use the lowest budget that fits the workload and delivers the measured
performance we need. Extra KV earns its memory cost when it enables useful
capacity or a faster batch. Check first output, generation and aggregate
throughput separately, including startup and inference failures.

Hold revision, quantization, DSpark, graphs and workloads fixed. Stop competing
builds. Warm kernels, then reset or separate prefixes for uncached tests. Check
actual tokens, retrieval answers, acceptance and per-rank memory during startup
and serving. Record cold and warm results separately.

Batch 2560/cap 2304 passed mixed near-1M retrieval at 97% and 96.5%, followed by
19 API checks. The [source-image comparison](interactive-latency.md) then tested
batch 2048 at 96%: cap 1792 favored foreground coding; cap 512 improved the 262K
tool median but slowed code. Near-1M serving minima were 1,099/1,064 MiB at
cap 1792 and 1,787/1,752 MiB at cap 512. Cap 1792 also passed a warmed restart and
19 post-long LAN checks. This supports the selected 96% profile. No measured
benefit justifies 97% for these workloads, though another workload may need
more cache. Startup headroom remains tighter than serving headroom.

## Startup and serving headroom are separate

Allocator logs caught startup pressure that periodic samples missed. Counts
below cover both ranks and count **allocation warnings, not failed requests**.
All four patched-preview launches reached readiness; source-image launches
are recorded separately.

| 1M launch | Draft post-load warnings | Later autotuning warnings |
|---|---:|---:|
| 96%, batch 2,048 | 0 | 2 |
| 97%, batch 2,048 | 0 | 4 |
| 97%, batch 2,560 | 198 | 4 |
| 96.5%, batch 2,560 | 191 | 2 |

Both batch 2560 launches reported **1–2 MiB free** during draft preparation,
before KV profiling. Sampled minima of 111/76 MiB at 97% and 19/36 MiB at
96.5% caught different phases and can't rank true startup minima.

At the same batch/cap, 96.5% reduced the packed KV pool by **486.5 MiB per GPU**
versus 97%. Post-ready sampled free memory rose from 1,395/1,360 to
1,953/1,918 MiB, partly affected by sampling and other allocations. Earlier
preparation pressure remained. The 96.5% retrieval passed at 998,871 input
tokens, with serving minima of 1,011/976 MiB versus 453/418 MiB at 97%.

Later 128K-input/512-output C1/C2 pilots at 96.5% sampled only 587/552 MiB
free. Output length, request mix and warm allocations can make a shorter
request use more memory. See [pilot measurements](../results/context-batch-pilot.json).

Weights are prepared before KV sizing. Utilization can't cap those earlier
allocations. Logs identify the phase but lack stacks needed to identify the
operation, recovery mechanism or skipped tactics. Readiness confirms recovery;
it doesn't establish comfortable startup headroom. See
[load/profiling order](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/worker/gpu_worker.py#L435)
and [warning analysis](../results/startup-allocation-review.json).

## Batching candidates from the pinned sizing code

At 1M context with asynchronous scheduling, five speculative tokens, and two
sequence slots, the conservative admission calculation predicts:

| Maximum batched tokens | Padded KV required | Margin against a hypothetical 6.88 GiB at 97% |
|---:|---:|---:|
| 1,024 | 4.880 GiB | 2.000 GiB |
| 2,048 | 5.732 GiB | 1.148 GiB |
| 2,560 | 6.158 GiB | 0.722 GiB |
| 3,072 | 6.584 GiB | 0.296 GiB |
| 4,096 | 7.436 GiB | -0.556 GiB |

Treat this table as an admission calculation. Larger workspaces can reduce
actual KV, so reprofile each batch. The reservation covers two asynchronous
batches; reducing slots from two to one doesn't shrink that term. It removes
concurrency and may save other buffers.

Use 2,048 as control and 2,560 as the first larger candidate; both passed
near-1M requests. Try 3,072 only with a measured reason and enough headroom.
Batch 1,024 may save memory but isn't presumed faster. These two-slot candidates
retain DSpark, graphs and APIs.

An untested option is batch 4,096 with synchronous scheduling. The pinned build
permits this with DSpark. One in-flight batch lowers admission to 5.732 GiB,
matching asynchronous batch 2,048. It keeps graphs and two-request batching but
loses scheduling overlap, which may hurt decode responsiveness. After the
97%/2,560 comparison, test actual activation memory, prefill and decode before
recommending it.

The [context/batch guide](context-batch.md) adds smaller-window candidates and
a matched-input protocol alongside the 801K/1M goals.
