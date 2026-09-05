# Before/after scorecard plan

1. Finish controlled final-image measurements; keep all runs, failures and
   preview observations.
2. Reconcile each stage's image/source, launch settings, model/hardware, token
   counts, graphs, DSpark, window, cache, concurrency, warmups and competing load.
3. Show measured progression: eager, target graphs, fixed-K DSpark, selected
   context/batch, then adaptive only if measured. Mark missing values.
4. Separate single-request latency/rates from aggregate throughput. Keep workload
   columns and exact denominators. Show the 32.3 -> 168.6 -> 292.9 tok/s history
   with absolute/relative gains and its comparison limits.
5. Put matched controls beside history. Isolate DSpark with graphs-on controls
   and adaptive with on/off in the same image; separate engine upgrades.
6. Add long-input, mixed-load and memory tables with actual tokens, timings,
   errors, preemptions and features. Explain costs in context or responsiveness.
7. Link rows to raw results and settings. Record repeats, variation and cache
   conditions. Any chart must distinguish unmatched workloads.
8. Independently check arithmetic, links and claims. Retain regressions and
   neutral results, explain defaults and update after later experiments.

Readers should understand what changed, its measured gain and cost, and how
to reproduce it.
