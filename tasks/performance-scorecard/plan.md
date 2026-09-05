# Before/after scorecard plan

1. Finish the current baseline and controlled final-image measurements. Preserve
   individual runs, failed attempts, and the preview's existing observations.
2. Reconcile each historical stage with its actual image/source, launch arguments,
   model revision, hardware, input/output counts, graph coverage, DSpark settings,
   context ceiling, cache state, concurrency, warmup and competing load.
3. Build a prominent numerical progression in the README and performance guide:
   first working eager setup, target decode graphs, fixed-K DSpark, selected
   context/batch recipe, then later adaptive verification if evaluated. Include
   only measured stages; mark unavailable values explicitly.
4. Show single-request latency/rates and two-request aggregate throughput in
   separate columns. Keep per-workload prose/code/reasoning values where a range
   would hide meaning. Include absolute gain, relative gain and the exact
   comparison denominator. Make the 32.3 -> 168.6 -> 292.9 tok/s aggregate
   progression easy to see, while preserving its historical/control boundaries.
5. Put matched comparisons beside the broader optimization history. Attribute
   DSpark-only gains to graphs-on controls and adaptive-only gains to adaptive
   off/on in the same candidate image. Separate engine-upgrade effects.
6. Add aligned long-input, mixed-request and memory tables: configured context,
   actual prompt/output tokens, prefill/TTFT, generation latency, aggregate rate,
   short/tool latency, observed headroom, errors/preemptions and retained features.
   Explain gains that cost context, memory margin or interactive responsiveness.
7. Link every numerical row to machine-readable evidence and exact reproduction
   settings. State repeats, variability, warm/cold/cache conditions and proof
   limits. A chart may help show progression, but axes and categories must not
   imply that different workloads are matched observations.
8. Independently verify arithmetic, links, labels and feature claims. Include
   neutral/negative optimizations and reasons for the chosen defaults. Update
   the scorecard after later phases rather than leaving stale headline numbers.

The final page should let a reader answer: what changed, how much did it help,
under which workload, what did it cost, and how can I reproduce the result?
