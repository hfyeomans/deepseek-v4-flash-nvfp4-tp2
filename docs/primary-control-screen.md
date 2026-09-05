# Exact-primary DSpark controls

We already had gains from earlier profiles. This test asks what DSpark adds
at the everyday settings: **2.14x short-code throughput** and **26.6% less time
on the 48K fixture**. First output didn't improve on every workload. Three
pairs can't establish an optimum or p95 latency.

## What stayed fixed

Both modes use the same image and NVFP4 checkpoint, TP2, a 1,000,000-token
ceiling, 96% memory, two slots, batch 2048, cap 1792, FP8 KV/block 256, prefix
caching, FlashInfer CUTLASS target experts and FULL_DECODE_ONLY target graphs
capped at 16. The off control removes only K5 probabilistic DSpark/Marlin.
Image, environment, entrypoint, GPU requests and cache mounts match.

The planned order was **on/off, off/on, on/off**, using unchanged clients,
C1 warmups, fresh salts and saved concurrent requests. Mixed probes had separate
warmups. The [manifest](../benchmarks/optimization-manifest.json) pins settings,
hardware and client hashes; the [protocol](optimization-evaluation.md) defines
the runs. Profiling and kernel tests ran separately. Each mode has three
measured observations below.

## Completed-answer speed and first output

| Workload | DSpark off median | DSpark on median | Comparison |
|---|---:|---:|---:|
| Short prose, one request | 93.73 tok/s | 201.49 tok/s | 2.15x throughput |
| Short code, one request | 93.66 tok/s | 200.64 tok/s | 2.14x throughput |
| Short reasoning, one request | 93.63 tok/s | 192.25 tok/s | 2.05x throughput |
| Two short requests, aggregate | 164.59 tok/s | 226.03 tok/s | 1.37x throughput |
| 48,345-token code input, 512-token answer | 11.983 s | 8.790 s | 26.6% less elapsed time |
| Same 48K code request, first output | 6.546 s | 6.636 s | 1.4% more time |
| Short code, first output | 75.7 ms | 84.4 ms | 11.5% more time |

Prose/code/reasoning inputs contain 30/39/41 tokens, with 256-token outputs,
temperature 0 and seed 42. Rates include prefill and HTTP streaming. The 1M
ceiling doesn't make these long-input tests. Aggregate rate is 512 output
tokens divided by the concurrent pair's elapsed time. The long-code client
also runs short prose/reasoning and a short-prose/long-code pair; those requests
remain in the evidence.

### Concurrency onset is an unresolved cost

| Pair | Off aggregate tok/s | On aggregate tok/s | On first output, prose/code |
|---|---:|---:|---:|
| 1 | 164.34 | 226.03 | 703/703 ms |
| 2 | 165.01 | 204.43 | 702/701 ms |
| 3 | 164.59 | 296.16 | 89/89 ms |

The client warmed C1 but **not C2**. Pair2-on restarted the container; pair3-on
continued without restarting. A cold-versus-warm effect is plausible but
unconfirmed. Keep all three trials. The earlier 269.88 median and historical
292.90 observation use different procedures. Follow-up testing must warm each
concurrency/workload and record cold onset separately.

## Tools during a long prefill

| Checked mixed workload | Off median | On median | Observed change |
|---|---:|---:|---:|
| Two-call automatic-tool roundtrip during a roughly 262K input | 18.881 s | 5.212 s | 72.4% less elapsed time |
| Long retrieval probe, including preparation | 54.555 s | 54.970 s | 0.8% more time |
| Long completion call alone | 54.174 s | 54.595 s | 0.8% more time |

All twelve mixed probes, including warmups, passed retrieval and tools; the
short operation finished before the long call. Long prompts contain
262,007–262,011 tokens. Measured long answers vary from 25 to 35 tokens and tool
calls from 45 to 54, changing follow-up inputs. Requests are unseeded with no
fixed minimum output and 256–512 prefix hits per run. The tool ratio therefore
describes this workload, not an isolated scheduling gain. These checks don't
establish broad coding/tool accuracy or equivalent long-request speed.

## Memory, accounting and remaining uncertainty

On the reporting worker, DSpark raises startup model memory from 77.83 to
83.21 GiB and reduces available KV from **11.43 to 5.93 GiB**. Calculated cache
capacity falls from 2,187,600 to 1,135,251 tokens; neither figure tests two
full-1M requests. Graph pools use 0.09/0.10 GiB, with the largest graph growing
from 2 to 12 rows. DSpark reserves part of batch 2048, leaving 2040 scheduled
tokens.

All **132 requests** match server totals: **4,025,096 prompt** and **37,873
generated tokens**. The 96 benchmark salts are unique, with zero prefix hits.
All 24 measurement windows show zero errors, aborts and preemptions. Across
537 two-GPU samples at roughly two-second intervals, minimum free memory was
1,097/1,062 MiB with DSpark and 1,251/1,214 MiB without it.

The first on block started cooler with resident KV; later thermal/cache histories
differ. Peak sampled temperature was 89 C; clocks and throttling weren't
recorded. Each of three startup segments recovered from two allocator OOM
warnings during autotuning. Clean request counters don't erase startup
warnings or establish long-term stability. Periodic samples can miss memory
peaks, and the cause of timing variance remains unknown.

## What this says about K5

The three on-short clients, including warmups and C2, recorded 1,924 rounds,
9,620 proposals and 4,233 accepted draft tokens. Positions 1–5 survived
1,533/1,111/741/511/337 times. The fifth survived **17.5% of all rounds**, or
337/511 = **65.95%** when the first four survived. These pooled counters can't
be assigned to one C1 workload. See [K5 and acceptance denominators](dspark-k-and-verification.md).

Dropping proposal five would reduce advancement from 3.200 to 3.025 tokens
per round if acceptance stayed fixed. We'd need more than 5.5% lower cycle
cost just to break even, before adaptive overhead. That's a useful estimate
for planning a test. It isn't an L4 result: shorter prefixes change future
proposals, and graph padding may keep verification cost. We still need a
supported prefix path, measured cycle costs and calibrated confidence.

Evidence: [all control rows, counters and resources](../results/primary-dspark-controls.json),
[independently recomputed comparisons and every trial](../results/primary-dspark-comparison.json),
[overall scorecard](performance-scorecard.md).
