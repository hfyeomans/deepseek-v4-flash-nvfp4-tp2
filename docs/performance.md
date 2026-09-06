# Performance observations

These preview-image measurements helped us choose the next experiments. They
use all three recipe patches. The source rebuild has
[its own CPU, API and near-1M results](source-image-validation.md).

## Matched short-prompt benchmark

Both modes use 64K, TP=2, two slots, FP8 KV, 95% memory and FULL_DECODE_ONLY
**target decode** graphs. Main experts use FlashInfer CUTLASS; DSpark uses
Marlin with five proposals. The source build was stopped. The optional DSpark
draft CUDA graph was disabled in these measurements.

Single-request rates are medians of two repeats after one warmup per prompt;
concurrency uses one paired trial per mode. Each response has 256 tokens.
Inputs are 30–41 tokens, so these end-to-end rates don't describe generation
after 64K, 801K or 1M inputs.

| Workload | Graphs, DSpark off | Graphs + DSpark | Ratio |
|---|---:|---:|---:|
| prose | 95.5 tok/s | 209.4 tok/s | 2.19x |
| code | 95.6 tok/s | 190.2 tok/s | 1.99x |
| reasoning | 95.5 tok/s | 174.0 tok/s | 1.82x |
| Two requests, aggregate | 168.6 tok/s | 292.9 tok/s | 1.74x |

Warm first output took 76–78 ms without DSpark and 82–94 ms with it. This small
synthetic test doesn't measure representative application speed or quality.

The early eager baseline of about 16.3 tok/s is diagnostic history; the
graph-enabled control isolates DSpark's gain.

See the raw [control](../results/control-graphs-benchmark.json),
[DSpark](../results/dspark-graphs-benchmark.json), and
[comparison](../results/graph-benchmark-comparison.json) files.

## Large-context learning targets

The original goal was to attempt 801,000- and 1,000,000-token windows with DSpark.
For each attempt, record settings, actual tokens, retrieval answers, prefill,
first output, generation, GPU/host memory and failures. Startup capacity alone
doesn't prove retrieval.

The owner reported 801K and possibly 1M on the earlier MXFP4 build. Cached
revision `7872f01b1d1fe23eabc4c98b48bffcef5a386062` has 166,886,535,336 bytes of
weights versus 175,550,788,904 for NVFP4, with the same compression ratios.
Disk size alone can't predict runtime or KV capacity.

## Avoiding a cached-input benchmark artifact

The pinned readiness check and warmups send the first workload prompt before
measurement, potentially populating its prefix cache. CLI defaults disable
readiness and warmups; the internal Python function has a different readiness
default. Check which entrypoint you use.

For uncached tests, check `/health` separately and use
`--ready-check-timeout-sec 0 --num-warmups 0`. Warm kernels with another seed,
then match measured seeds across modes. Use
`--random-prefix-len 0 --random-range-ratio 0`, record actual lengths and assign
a fresh `cache_salt` per run. Save salts and verify hit deltas. See the
[measurement audit](benchmark-measurement.md).

This controls measurement; prefix caching stays enabled. Label cached-prefix
benchmarks separately. See [readiness/warmup code](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/benchmarks/serve.py#L826).

## Observed mixed-request scheduling limit

At 97%, a short request waited behind uncapped near-1M prefill for 180 seconds
and timed out. We had a second slot and only 61–68% KV occupancy, but metrics
showed one running and one waiting request. Free cache wasn't enough.
[Failure record](../results/dspark-1m-97-concurrent-short-timeout.json).

The scheduler serves running requests first. With a zero threshold, long
prefill can consume the step's whole token budget, leaving none for waiting
requests. Lowering `long_prefill_token_threshold` reserves room for short work.
Batch 2560/cap 2304 then passed mixed retrieval with DSpark, graphs and two slots.
See [running budgets](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/sched/scheduler.py#L488)
and [waiting admission](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/sched/scheduler.py#L690).

Five proposals and two slots reserve eight batch tokens. Budget 2,560 therefore
schedules 2,552: cap 2,304 leaves 248 for other work; cap 2,048 leaves 504. At
budget 2,048, cap 2,048 leaves nothing because only 2,040 tokens are schedulable.
These caps keep DSpark, graphs, asynchronous scheduling and two slots.

At 97% / batch 2560 / cap 2304, short replies passed in 4.720 and 3.242 seconds
while long retrieval continued. The second had one running request before and
after. Retrieval returned correctly from 998,847 input/35 output tokens in
525.519 seconds total (523.662 HTTP). All 19 later API checks passed. Sampled
free-memory minima were 111/76 MiB at startup and 453/418 MiB during inference.
This confirms responsiveness, not a controlled speed gain.
[Mixed trial](../results/dspark-1m-97-b2560-t2304-mixed.json).

The original probe timed overlap from prompt preparation, making its claim
too broad. Server activity and fresh-container/cache logs independently support
this result. The corrected probe uses completion-call boundaries and a unique
prefix; three regressions failed before the fix and passed after it. Admission
and prefill still require server metrics.

For the next comparison, see [context versus batch measurements](context-batch.md).

The same batch/cap passed at **96.5%** with 998,871 input/35 output tokens in
525.619 seconds total (523.813 HTTP). Short replies took 4.199 and 2.252 seconds;
the second had one running request before/after. All 19 API checks passed.
Serving minima were 1,011/976 MiB versus 453/418 MiB at 97%. First-use compilation,
a competing build and unique prefixes prevent a matched timing comparison.
[96.5% evidence](../results/dspark-1m-965-b2560-t2304-mixed.json).

## Matched-input pilot: concurrency at 1M

These pilots ran on the patched preview during a source build. They test the
harness and suggest candidates; controlled source-image repeats are needed
for recommendations. Each uses seed 101, two 131,072-token inputs/512-token
outputs, fresh salts, 1M, 96.5%, batch 2560, cap 2304, K5 and target graphs.

| Client concurrency | Aggregate output rate, including prefill | Individual TTFTs | Median per-request TPOT | Draft acceptance fraction |
|---:|---:|---|---:|---:|
| 1 | 20.531 tok/s | 20.403 s, 20.851 s | 8.436 ms | 20.51% |
| 2 | 21.312 tok/s | 22.779 s, 42.571 s | 29.752 ms | 19.69% |

C2 produced 3.8% more aggregate output with worse generation delay/token. Two
requests per case can't establish a repeatable gain or tail latency. Server
counts matched 262,144 input/1,024 output tokens with zero hits/preemptions.
Overlapping request durations can't be summed as GPU time, and random inputs
don't represent coding quality or natural-code acceptance.

Both pilots sampled 587/552 MiB free, below the earlier near-1M trial. Workload
and warm allocations affect headroom; 96.5% doesn't guarantee a gigabyte free.
See [pilots](../results/context-batch-pilot.json) and
[measurement definitions](benchmark-measurement.md).

Reducing only the ceiling to **524,288**, at 96.5% / batch 2560 / cap 2304, completed
both salted cases. C1 measured 20.054 tok/s, TTFT 21.171/21.453 seconds and median
TPOT 8.256 ms. C2 measured 21.169 tok/s, TTFT 23.158/43.146 seconds and TPOT 29.349 ms.
Counts matched 262,144 input/1,024 output with zero hits/preemptions. Startup KV
rose from 6.30 to 6.88 GiB; serving minima were 739/704 MiB. These small differences
under build contention don't establish a benefit from shortening context.

At 96.5%, **524,288/batch 4096/cap 3840** started with 6.60 GiB KV and 1.31x
calculated capacity. Counts matched with zero hits/preemptions. C1 measured
18.920 tok/s and TTFT 25.394/20.528 seconds; a saved repeat reached 21.084 tok/s
and 19.919/20.414 seconds. C2 measured 21.966 tok/s, TTFT 21.795/41.139 seconds and
median TPOT 28.857 ms. Serving minima were 407/372 MiB.

Keep the slow first C1 pair alongside its repeat. It followed a C2 warmup,
which doesn't guarantee warm C1 shapes, but the logs don't prove compilation
caused the delay. Warm both in the next comparison. These variable,
build-contended pilots don't justify giving up context or choosing a batch.

The last pilot used **1M/batch 2048/cap 1792** at 96.5%, with separate C1/C2
warmups. C1 measured 18.804 tok/s, TTFT 21.904/22.154 seconds and TPOT 10.173 ms;
C2 measured 19.996 tok/s, TTFT 45.116/25.191 seconds and TPOT 28.973 ms. Counts
matched, with zero hits/preemptions and 795/760 MiB minimum free memory. Startup
reported 6.41 GiB KV and 1,226,192-token capacity. Acceptance varied from 13.71%
at C1 to 19.57% at C2. That variation and the active source build prevent
attributing speed solely to batch size. All nine measured pilot cases remain
in the evidence.
