# Where the fixed-K5 runtime spends GPU work

We profiled the recipe to see where GPU work goes. Six traces show target
forward dominating, with the draft pipeline taking 9.2–9.9% of summed kernel
time in generation-only windows. Don't read that as time we can simply remove
or as an adaptive-verification gain.

## Generation-only observations

Values sum kernel durations in milliseconds, including overlap, separately
per rank. Target forward includes attention/indexer, MoE/linear and collectives.
Draft includes preparation, forward and Markov sampling. Postprocess includes
target logits projection.

| Case | Rank | Steps | Target forward | Postprocess | Target sampling | Draft pipeline | Other | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Short code C1 | 0 | 20 | 343.779 | 7.516 | 3.626 | 38.870 | 1.315 | 395.106 |
| Short code C1 | 1 | 20 | 343.950 | 7.510 | 3.600 | 38.953 | 1.305 | 395.317 |
| 48K code C1 | 0 | 20 | 373.730 | 7.518 | 3.608 | 39.214 | 1.394 | 425.465 |
| 48K code C1 | 1 | 20 | 374.159 | 7.526 | 3.578 | 39.215 | 1.383 | 425.861 |
| Short prose/code C2 | 0 | 19 | 402.408 | 7.693 | 3.448 | 44.134 | 1.276 | 458.959 |
| Short prose/code C2 | 1 | 19 | 398.795 | 7.682 | 3.403 | 44.075 | 1.279 | 455.234 |

C1 traces contain twenty `generation_1(6)` steps. C2 starts with
`context_1(39)_generation_1(6)`, followed by nineteen `generation_2(12)` steps.
The mixed first step is excluded above but retained in results: 107.732/32.969 ms
on ranks 0/1. The cause of that asymmetry is unknown.

Named MQA-logits kernels sum to 5.058/5.013 ms for short C1, 10.530/10.532 ms
for 48K C1 and 5.428/5.353 ms for nineteen C2 steps. They are already included
in target forward. Total indexer cost also includes projections, compression,
cache work, generic top-k and metadata that this subset omits.

## Why these numbers cannot be added into request latency

Short C1/rank 0 sums to 395.106 ms of kernels, but their occupied-interval union
is 306.771 ms and first-to-last span is 317.230 ms. Streams overlap. The draft
CPU scope totals 152.890 ms while draft GPU kernels sum to 38.870 ms; these
also overlap. Adding CPU/GPU times or both ranks would double-count work.
The JSON reports unions, spans, scopes, memory activity and steps separately.

The parser links each kernel to one CUDA launch by correlation ID and the
innermost runner scope on that CPU thread. Graph nodes link to their specific
`cudaGraphLaunch`, not just a reused graph ID. All six traces have 100% coarse
attribution, no ambiguous links and no unpaired steps. Sample/draft scopes
follow execute and attach to that thread's preceding execution. Duplicate GPU
annotation summaries are excluded. This maps components, not a full dependency
critical path or every layer.

## Profiler perturbation and cache conditions

A separate container used the primary image/settings, custom runner scopes
and Torch profiler. Requests used temperature 0, seed 42, thinking off, fixed
output length and warm prefixes. Each case ran a same-concurrency warmup, an
unprofiled request, the profiled request(s), then another unprofiled request.
None overlapped the [matched controls](primary-control-screen.md).

| Case | Unprofiled before | Profiled request/batch | Unprofiled after |
|---|---:|---:|---:|
| Short code C1, 256 outputs | 1.390 s | 6.302 s | 1.497 s |
| Short prose/code C2, 256 outputs each | 2.385 s | 9.064 s | 1.764 s |
| 48,345-token code C1, 512 outputs | 7.313 s | 8.971 s | 2.640 s |

The profiler changes timing substantially, especially at 48K. Even the
surrounding unprofiled requests vary too much for a clean overhead ratio.
Use these traces to choose experiments. Full-request cache hits/queries were
0/39, 0/69 and 48,128/48,345, leaving 217 uncached long-prompt tokens. All windows
had zero preemptions. Those full-request counters can't normalize the shorter
trace or show accepted tokens per step.

## Reproducing the analysis

Add `VLLM_CUSTOM_SCOPES_FOR_PROFILING=1` to the **container environment** and
append this profiler configuration to a separate copy of the primary launch:

```json
{"profiler":"torch","torch_profiler_dir":"/experiment/traces","torch_profiler_with_stack":false,"torch_profiler_record_shapes":false,"ignore_frontend":true,"delay_iterations":2,"max_iterations":20}
```

Mount the output directory. Disable memory/stack/shape profiling. Use
`benchmark.py` code/prose inputs and the frozen 48K fixture with the warmup and
bracket procedure above. POST `/start_profile`, submit the case, then POST
`/stop_profile`. Require two trace files, not only HTTP 200. The cap was 20
iterations; traces contain 20 execute steps. These diagnostic requests are
non-streaming. Published records retain hashes, counts and timing brackets.

Group copied `*.pt.trace.json.gz` files in one subdirectory per case, then run:

```bash
python3 -B -m unittest discover -s tests -p test_profile_trace_analysis.py
python3 -B experiments/profile_trace_analysis.py "$TRACE_ROOT" --output-dir "$ANALYSIS_OUTPUT"
```

The [parser](../experiments/profile_trace_analysis.py) has regressions for
asynchronous launches, reused graph IDs, ambiguous/missing links, threads,
overlap and mixed steps. Independent raw-event checks reconciled kernel plus
memory activity with profiler self-CUDA totals within 0.0005 ms of rounding.
Reparsing reproduced all six published result files exactly. Trace hashes are
retained; raw traces and local host paths stay outside the repo.

Evidence: [trace index](../results/component-profiles/index.json),
[verification](../results/component-profiles/verification.json),
[cache and traffic context](../results/component-profiles/traffic-context.json),
[short C1 requests](../results/profile-code-c1-requests.json),
[C2 requests](../results/profile-prose-code-c2-requests.json) and
[48K requests](../results/profile-code48k-c1-requests.json).

## How to use these measurements

Use these profiles to find work worth investigating, then measure gains with
unprofiled [controls](primary-control-screen.md). Padding and overlap matter,
and instrumentation changes costs. The [adaptive project](repository-boundaries.md)
shares these baselines; any new claim needs its own matched measurements.
The [future kernel experiments](development.md#future-kernel-experiments) use the same
evidence to investigate SM120 improvements beyond the current recipe.
