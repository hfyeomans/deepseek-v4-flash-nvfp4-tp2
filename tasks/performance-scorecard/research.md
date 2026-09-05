# Before/after performance scorecard intake

Make the gains visible from the first working setup through roughly 292 tok/s
two-request aggregate. Keep this documentation alongside the experiments.

## Existing evidence anchors

| Recorded stage | Single-request output rate | Two-request aggregate output rate | Evidence |
|---|---:|---:|---|
| First working eager baseline, DSpark off | 16.31–16.35 tok/s | 32.307 tok/s | [Baseline](../../results/baseline-benchmark.json) |
| Target decode graphs, DSpark off | About 95.5 tok/s | 168.553 tok/s | [Graphs control](../../results/control-graphs-benchmark.json) |
| Target decode graphs plus fixed-K DSpark | 173.995–209.432 tok/s | 292.901 tok/s | [DSpark](../../results/dspark-graphs-benchmark.json) |

The eager start is diagnostic history with incomplete launch/load provenance.
The graph-enabled on/off stages are matched: 1.82–2.19x single-request and
1.74x aggregate gains. See [comparison](../../results/graph-benchmark-comparison.json).

The roughly 9.1x start/end ratio combines configuration changes. Identify them
instead of attributing everything to DSpark. Startup failures have no throughput
measurement; assigning zero would exaggerate gains.

Short tests use 30–41 input/256 output tokens with exact-prompt warmups. The
64K setting is capacity. The build-contended 128K pilots use different workloads
and need separate matched-input comparisons.
