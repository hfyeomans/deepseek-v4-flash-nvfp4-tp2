# Source-built image acceptance

The public-source image passed its 13 CPU regression methods, all 19 short API
checks over the LAN, and retrieval from **998,868 actual input tokens** in a
1,000,000-token window. Post-retrieval chat and a tool round trip also passed.
This establishes a working source-built candidate. Its matched DSpark control
is complete. The subsequent [interactive comparison](interactive-latency.md)
selects a 96% / batch2,048 / cap1,792 coding profile, with separate near-1M,
restart and final API evidence. The measurements below retain the original
96.5% candidate and its matched control.

After the control, the DSpark service restarted in 63.3 seconds of observation
using its existing kernel cache. All 19 LAN API checks passed again with the
corrected request recorder. See [restart evidence](../results/source-image-restart-api.json).

The tested settings are TP2, 96.5% memory utilization, batch2560, long-prefill
cap2304, two sequence slots, FP8 KV/block256, fixed-K5 DSpark with a Marlin
draft, main FlashInfer CUTLASS and FULL_DECODE_ONLY target graphs. Model revision
and image digests are preserved in the linked results.

## First startup and memory

With a newly created FlashInfer kernel-cache volume, startup reached readiness
after **519.5 seconds of observation**. Startup included kernel compilation,
profiling and autotuning; their individual durations were not measured. Both
ranks verified all 4,608 expert sources, 99 non-expert sources and 99 bindings.
Target graph capture completed using 0.10 GiB; reported KV availability was
6.30 GiB, with 1,122,401 reported cache tokens and 1.12x maximum-length capacity.
That does not establish two simultaneous 1M requests.

During draft preparation, 198 allocation warnings occurred before model loading
completed. Samples caught 7/12 MiB free; allocator messages reached 1/2 MiB.
Two later warnings occurred during FlashInfer gemm2 autotuning. Startup recovered,
but the early pressure occurs before the later KV report. Lowering the KV budget
alone does not establish safer weight preparation. Exact failing operators and
recovery mechanics were not traced.

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

The tiny reply is not a substitute for the tool measurement. The tool check
uses 295 input/54 output tokens, then 379 input/6 output tokens. Server activity
was one request before, two during, and one after the tool check, with no waiting
requests in those snapshots. Admission succeeds, but mixed-batch generation can
still be slow. These probes occurred at different points in the prefill; they
are not a matched latency comparison. Post-long cache conditions also differ.

The long test includes both the tiny chat and the additional tool round trip.
Global metrics therefore cover four API calls, totaling 999,555 input and 101
output tokens. Do not label their timing sums as isolated GPU compute time.
This is a small synthetic retrieval/feature test, not broad long-context quality.

See [19 LAN API checks](../results/source-image-lan-api.json),
[mixed near-1M test and recovery](../results/source-image-1m-mixed.json), and
[concurrent tool evidence](../results/source-image-concurrent-tool.json).

## Initial performance observations

Three short-input runs preserve their individual observations. Initial aggregate
throughput was **203.4 tok/s**, with roughly 671 ms to first output in the paired
requests. Subsequent paired trials reached **302.9 and 263.3 tok/s**. The logs
do not establish the cause of the initial delay. Keep all trials; do not promote
the fastest one to a general speed guarantee.

The frozen coding fixture contains 320 synthetic validator modules and measures
48,345 actual input tokens. With fresh per-request cache salts, three measured
512-token responses took 8.240–8.373 seconds, with first output at 6.239–6.364
seconds. Median end-to-end output rate was **61.50 tok/s**. Server counters
confirmed actual usage and zero cache hits. The separate paired trial combines
short prose with this long code, not two long code requests. Its prose request
took 10.012 seconds despite first output arriving in 86 ms.

The [exact synthetic fixture](../benchmarks/prompts/code-48k.txt) and its
[hash and reproduction notes](../benchmarks/prompts/README.md) are included.

These observations do not establish representative code quality or long-code-only
acceptance; speculative counters span warmups, every workload and the concurrent pair.

- [First short run](../results/final-dspark-short.json)
- [Second short run](../results/final-dspark-short-repeat2.json)
- [Third short run](../results/final-dspark-short-repeat3.json)
- [Frozen long-code input and measurements](../results/final-dspark-long-code.json)

The [historical scorecard](performance-scorecard.md) remains distinct from these
source-built 1M observations. The tool latency and narrow memory margin motivated
the completed [lower-memory profile comparison](interactive-latency.md).

## Matched DSpark control on the source image

The control uses the same image, 1M window, 96.5% memory budget, batch2560,
prefill cap2304, two slots and target graphs, with DSpark disabled. It passed
all 19 short API checks. Both configurations followed the same benchmark order:
first short run, frozen long code, then two further short runs. All runs are
preserved; no competing source build ran.

| Workload | DSpark off | DSpark on | Ratio |
|---|---:|---:|---:|
| Short prose, median of 9 requests | 93.66 tok/s | 192.32 tok/s | 2.05x |
| Short code, median of 9 requests | 93.60 tok/s | 187.42 tok/s | 2.00x |
| Short reasoning, median of 9 requests | 93.58 tok/s | 189.58 tok/s | 2.03x |
| Two short requests, median of all 3 paired trials | 163.96 tok/s | 263.31 tok/s | 1.61x |
| 48,345-token code input, median of 3 requests | 43.49 tok/s | 61.50 tok/s | 1.41x |

The control paired trials ranged from 163.93–164.28 tok/s; DSpark ranged from
203.38–302.92. Three pairs do not establish stable tail behavior. The long-code
median elapsed time fell from 11.772 to 8.325 seconds. First output ranges
overlapped around 6.3 seconds; time after first output was 5.440–5.441 seconds
without DSpark and 1.961–2.075 seconds with it. That interval includes stream
completion and multi-token bursts, so it is not isolated GPU decode time.

There is a capacity cost: reported KV availability fell from **11.84 to 6.30 GiB
per GPU**, and reported maximum-length cache concurrency from **2.11x to 1.12x**.
These are startup reports, not a test of two simultaneous full-1M requests.
Memory utilization is matched; actual allocations necessarily change with DSpark.

See [unrounded comparison and proof limits](../results/source-image-benchmark-comparison.json),
[control API checks](../results/source-image-control-api.json),
[control startup evidence](../results/source-image-control-startup-excerpt.txt),
[first control](../results/final-control-short.json),
[second control](../results/final-control-short-repeat2.json),
[third control](../results/final-control-short-repeat3.json), and
[long-code control](../results/final-control-long-code.json).

Historical tool request objects affected by the recorder's later-mutation bug
are marked in their observations. Responses, usage and timings remain valid;
see [the recording fix and regression](validation.md#historical-request-recording-limitation).
