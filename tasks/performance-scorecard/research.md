# Before/after performance scorecard intake

The user requested a clear numerical progression from the first working setup
to the optimized recipe, including the approximately 292 tok/s two-request
aggregate result. This is a documentation phase alongside the planned testing;
it does not replace the current experiments.

## Existing evidence anchors

| Recorded stage | Single-request output rate | Two-request aggregate output rate | Evidence |
|---|---:|---:|---|
| First working eager baseline, DSpark off | 16.31–16.35 tok/s | 32.307 tok/s | [Baseline](../../results/baseline-benchmark.json) |
| Target decode graphs, DSpark off | About 95.5 tok/s | 168.553 tok/s | [Graphs control](../../results/control-graphs-benchmark.json) |
| Target decode graphs plus fixed-K DSpark | 173.995–209.432 tok/s | 292.901 tok/s | [DSpark](../../results/dspark-graphs-benchmark.json) |

The graphs-off/DSpark-off starting measurement is diagnostic history; its full
launch and competing-load conditions must be reconciled before making a matched
causal claim. The two graph-enabled stages already form a matched comparison.
Its single-request speedups are 1.82–2.19x and the aggregate two-request speedup
is about 1.74x. See [comparison](../../results/graph-benchmark-comparison.json).

The recorded start/end aggregate ratio is about 9.1x. If included, label it as
the observed progression across configurations, and enumerate the changed
conditions. Do not call that a DSpark-only gain. An original startup failure has
no measured throughput; do not invent a zero-rate baseline to exaggerate gains.

These short benchmarks use 30–41 input tokens and 256 output tokens per request,
with exact-prompt warmups. The 64K configured window is not a 64K input.
Current 128K-input pilots use a different workload and remain build-contended.
They belong in their own comparison with the same input/output counts.
