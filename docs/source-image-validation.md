# Source-built image acceptance

The source-built image passed 13 CPU methods, 19 LAN API checks and retrieval
from **998,868 input tokens** in a 1,000,000-token window. Post-retrieval chat
and tools also passed. This page records the original 96.5% candidate and its
matched DSpark control. The later [profile comparison](interactive-latency.md)
selected 96% / batch 2,048 / cap 1,792 and records its near-1M, restart and API
checks separately.

After the control, DSpark restarted in 63.3 seconds with the existing kernel
cache. All 19 LAN API checks passed with the corrected request recorder.
See [restart evidence](../results/source-image-restart-api.json).

The tested settings are TP2, 96.5% memory utilization, batch 2560, long-prefill
cap 2304, two sequence slots, FP8 KV/block 256, fixed-K5 DSpark with a Marlin
draft, main FlashInfer CUTLASS and FULL_DECODE_ONLY target graphs. Model revision
and image digests are preserved in the linked results.

## First startup and memory

With a new FlashInfer kernel-cache volume, startup took **519.5 seconds of
observation**, including compilation, profiling and autotuning. Those stages
were not timed separately. Both ranks verified 4,608 expert sources,
99 non-expert sources and 99 bindings. Target graphs used 0.10 GiB. Reported
KV was 6.30 GiB, or 1,122,401 cache tokens and 1.12x maximum-length capacity;
this does not test two simultaneous 1M requests.

Draft preparation logged 198 allocation warnings before model loading finished.
Samples caught 7/12 MiB free; allocator messages reached 1/2 MiB. FlashInfer
gemm2 autotuning later logged two warnings. Startup recovered, but lowering
the later KV budget cannot be assumed to fix earlier preparation pressure.
The exact failing operators and recovery path were not traced.

See [build and CPU evidence](../results/source-build-provenance.json),
[startup measurements](../results/source-image-startup.json), and
[selected startup log lines](../results/source-image-startup-excerpt.txt).

## Long input, chat and tools

| Observation | Result |
|---|---|
| Near-1M retrieval | 998,868 input / 35 output tokens; all three facts correct |
| Long completion HTTP time | 511.394 seconds; 513.165 seconds including preparation |
| Tiny concurrent chat | Correct in 2.095 seconds, while the long request continued |
| Automatic tool round trip during the long prefill | Correct in 37.941 seconds: 28.971 seconds for the tool call, then 8.970 seconds for the tool-result response |
| Post-long tool check | Correct in 0.416 seconds |
| Sampled minimum serving free memory | 507/472 MiB per GPU |
| Prefix hits / preemptions during mixed test | Zero / zero |

The tool check uses 295 input/54 output tokens, then 379 input/6 output tokens.
Server snapshots showed one request before, two during and one after, with
none waiting. Admission worked, but generation was still slow. The tiny reply
and tool check occurred at different prefill points, and post-long cache state
also differs. Their latencies are not a matched comparison.

The long test, tiny chat and tool roundtrip total four API calls, 999,555 input
and 101 output tokens. Global timing sums include overlapping work. This
synthetic test does not establish broad long-context accuracy.

See [19 LAN API checks](../results/source-image-lan-api.json),
[mixed near-1M test and recovery](../results/source-image-1m-mixed.json), and
[concurrent tool evidence](../results/source-image-concurrent-tool.json).

## Initial performance observations

Three short-input runs measured **203.4, 302.9 and 263.3 tok/s** aggregate.
The first pair took roughly 671 ms to first output; logs do not explain why.
Keep all three trials when comparing speed.

The frozen fixture has 320 synthetic validators and 48,345 input tokens. With
fresh salts, three 512-token responses took 8.240–8.373 seconds, with first
output at 6.239–6.364 seconds and median end-to-end rate **61.50 tok/s**. Server
counters confirmed usage and zero hits. A separate pair combines short prose
with long code; its prose response took 10.012 seconds despite first output
arriving in 86 ms.

The [exact synthetic fixture](../benchmarks/prompts/code-48k.txt) and its
[hash and reproduction notes](../benchmarks/prompts/README.md) are included.

Speculative counters combine warmups, workloads and the concurrent pair. They
cannot isolate long-code acceptance or establish representative coding accuracy.

- [First short run](../results/final-dspark-short.json)
- [Second short run](../results/final-dspark-short-repeat2.json)
- [Third short run](../results/final-dspark-short-repeat3.json)
- [Frozen long-code input and measurements](../results/final-dspark-long-code.json)

The [scorecard](performance-scorecard.md) separates historical preview results
from these source-image measurements. Slow tools and narrow memory margins
led to the [lower-memory comparison](interactive-latency.md).

## Matched DSpark control on the source image

The DSpark-off control keeps the same image, 1M window, 96.5% memory, batch 2560,
cap 2304, two slots and target graphs. It passed 19 API checks. Both modes ran
short, long code, then two more short runs without a competing build. All runs
are retained.

| Workload | DSpark off | DSpark on | Ratio |
|---|---:|---:|---:|
| Short prose, median of 9 requests | 93.66 tok/s | 192.32 tok/s | 2.05x |
| Short code, median of 9 requests | 93.60 tok/s | 187.42 tok/s | 2.00x |
| Short reasoning, median of 9 requests | 93.58 tok/s | 189.58 tok/s | 2.03x |
| Two short requests, median of all 3 paired trials | 163.96 tok/s | 263.31 tok/s | 1.61x |
| 48,345-token code input, median of 3 requests | 43.49 tok/s | 61.50 tok/s | 1.41x |

Control pairs ranged 163.93–164.28 tok/s; DSpark pairs ranged 203.38–302.92.
Three pairs cannot establish tail latency. Long-code median time fell from
11.772 to 8.325 seconds, while first-output ranges overlapped around 6.3 seconds.
After first output, the control took 5.440–5.441 seconds and DSpark
1.961–2.075 seconds. Those intervals include stream completion and multi-token
bursts, not just GPU decode.

DSpark reduced available KV from **11.84 to 6.30 GiB per GPU** and calculated
maximum-length cache concurrency from **2.11x to 1.12x**. These startup estimates
do not test two full-1M requests. The memory percentage is matched; allocations
change with speculation.

See [unrounded comparison and proof limits](../results/source-image-benchmark-comparison.json),
[control API checks](../results/source-image-control-api.json),
[control startup evidence](../results/source-image-control-startup-excerpt.txt),
[first control](../results/final-control-short.json),
[second control](../results/final-control-short-repeat2.json),
[third control](../results/final-control-short-repeat3.json), and
[long-code control](../results/final-control-long-code.json).

Historical request objects affected by the later-mutation bug are marked in
the results. Responses, usage and timings remain valid. See the
[recorder fix and regression](validation.md#historical-request-recording-limitation).
