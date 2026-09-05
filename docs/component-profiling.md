# Where the fixed-K5 runtime spends GPU work

Six diagnostic traces attribute all recorded kernels to their runner components.
Target forward is the largest category; the draft pipeline accounts for about
9.2–9.9% of summed kernel work in the generation-only windows. These percentages
are not achievable latency savings or a prediction of adaptive-verification ROI.

## Generation-only observations

Values are **sums of kernel durations in milliseconds**, including overlap.
Each rank is reported separately. Target forward includes attention/indexer,
MoE/linear work and collective kernels. Draft includes preparation, draft forward
and Markov sampling. Postprocess includes target logits projection.

| Case | Rank | Steps | Target forward | Postprocess | Target sampling | Draft pipeline | Other | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Short code C1 | 0 | 20 | 343.779 | 7.516 | 3.626 | 38.870 | 1.315 | 395.106 |
| Short code C1 | 1 | 20 | 343.950 | 7.510 | 3.600 | 38.953 | 1.305 | 395.317 |
| 48K code C1 | 0 | 20 | 373.730 | 7.518 | 3.608 | 39.214 | 1.394 | 425.465 |
| 48K code C1 | 1 | 20 | 374.159 | 7.526 | 3.578 | 39.215 | 1.383 | 425.861 |
| Short prose/code C2 | 0 | 19 | 402.408 | 7.693 | 3.448 | 44.134 | 1.276 | 458.959 |
| Short prose/code C2 | 1 | 19 | 398.795 | 7.682 | 3.403 | 44.075 | 1.279 | 455.234 |

Both C1 traces contain twenty `generation_1(6)` steps with no context requests.
C2 has a mixed first step (`context_1(39)_generation_1(6)`) and nineteen
`generation_2(12)` steps. That first step is excluded above: its kernel sums
were 107.732/32.969 ms on ranks 0/1. The trace does not establish the cause of the
asymmetry. It remains in the per-rank results rather than being discarded.

The named MQA-logits subset is 5.058/5.013 ms for short C1, 10.530/10.532 ms
for 48K C1 and 5.428/5.353 ms for the nineteen C2 steps. These values are already
inside target forward. They omit projections, compression, cache operations,
generic top-k and metadata; they are not total indexer cost.

## Why these numbers cannot be added into request latency

For short C1/rank 0, summed kernel work is 395.106 ms, but the union of occupied
kernel intervals is 306.771 ms and the first-to-last kernel span is 317.230 ms.
Streams overlap. The draft CPU scope totals 152.890 ms while its GPU kernels
sum 38.870 ms; CPU dispatch and GPU execution also overlap. Adding these numbers
would count overlapping work more than once. Summing both ranks would likewise
not produce request latency. Interval unions, spans, CPU scopes, memory activity
and per-step breakdowns remain separate in the published JSON.

The parser joins each kernel to exactly one CUDA runtime/driver launch through
its correlation ID, then uses the innermost runner scope on that CPU thread.
Graph nodes identify their particular `cudaGraphLaunch`; a reused graph ID alone
is insufficient. All six traces have 100% coarse kernel attribution, with no
ambiguous links or unpaired steps. Sample/draft scopes occur after the execute
annotation, so they are associated with the preceding execution on that thread.
Duplicate GPU annotation rollups are excluded. This is not a reconstructed
dependency critical path or full layer-level attribution.

## Profiler perturbation and cache conditions

Profiling used a separate container with the exact primary image/settings,
custom runner scopes enabled and the existing Torch profiler. Requests used
temperature 0, seed 42, thinking disabled, fixed output length and a warm-prefix
policy. Each case ran a same-concurrency warmup, an unprofiled bracket, the
profiled request(s), then another unprofiled bracket. It was separate from all
[matched controls](primary-control-screen.md).

| Case | Unprofiled before | Profiled request/batch | Unprofiled after |
|---|---:|---:|---:|
| Short code C1, 256 outputs | 1.390 s | 6.302 s | 1.497 s |
| Short prose/code C2, 256 outputs each | 2.385 s | 9.064 s | 1.764 s |
| 48,345-token code C1, 512 outputs | 7.313 s | 8.971 s | 2.640 s |

Perturbation is severe and the brackets are not stable, particularly for 48K.
There is no clean profiler-overhead ratio. Recorded kernel costs can guide
experiments but must not be treated as calibrated unprofiled cycle costs.
Full profiled-request cache hits/queries were 0/39, 0/69 and 48,128/48,345;
the long request still had 217 uncached prompt tokens. All metric windows had
zero preemptions. These full-request counters cannot normalize the shorter
trace window or establish per-step accepted-token yield.

## Reproducing the analysis

Add `VLLM_CUSTOM_SCOPES_FOR_PROFILING=1` to the **container environment** and
append this profiler configuration to a separate copy of the primary launch:

```json
{"profiler":"torch","torch_profiler_dir":"/experiment/traces","torch_profiler_with_stack":false,"torch_profiler_record_shapes":false,"ignore_frontend":true,"delay_iterations":2,"max_iterations":20}
```

Mount the trace output directory. Memory/stack/shape profiling was disabled.
Use the code and prose inputs in `benchmark.py` and the frozen 48K prompt. Each
case uses the warmup/bracket procedure above. POST `/start_profile`, submit the
case, then POST `/stop_profile`; require two actual trace files, not just 200
responses. The requested iteration cap was 20; the observed traces contain 20
execute steps. Request JSON is non-streaming for these diagnostic cases.
The public request records preserve hashes, counts and timing brackets.

Group copied `*.pt.trace.json.gz` files in one subdirectory per case, then run:

```bash
python3 -B -m unittest discover -s tests -p test_profile_trace_analysis.py
python3 -B experiments/profile_trace_analysis.py "$TRACE_ROOT" --output-dir "$ANALYSIS_OUTPUT"
```

The [parser](../experiments/profile_trace_analysis.py) and six regressions cover
asynchronous launches, reused graph IDs, ambiguous/missing links, thread
separation, overlap and mixed steps. Independent raw-event conservation checks
reconciled kernel plus memory activity with every profiler self-CUDA total
within 0.0005 ms of print rounding. A fresh publication reparse reproduced all
six result files exactly. Trace hashes are retained; raw trace files and local
host paths are excluded from the repository.

Evidence: [trace index](../results/component-profiles/index.json),
[verification](../results/component-profiles/verification.json),
[cache and traffic context](../results/component-profiles/traffic-context.json),
[short C1 requests](../results/profile-code-c1-requests.json),
[C2 requests](../results/profile-prose-code-c2-requests.json) and
[48K requests](../results/profile-code48k-c1-requests.json).

## How to use these measurements

These fixed-K5 profiles help explain where the accelerated recipe spends GPU
work. They do not predict the gain from removing a draft position or adding
confidence/compaction. Padding, overlap and instrumentation can change costs.
Use the unprofiled [matched controls](primary-control-screen.md) for measured
latency and throughput benefits. The same profile evidence serves as a baseline
in the [separate adaptive project](repository-boundaries.md); new optimization
claims require their own matched measurements.
