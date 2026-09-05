# Fixed-K5 acceleration measurement protocol

Status: **exact-primary DSpark on/off controls and diagnostic profiles complete**.
The recipe keeps this protocol to explain its acceleration measurements and
their limits. Historical baseline protocol commit `e25dba7` and rollback tag
`baseline-1m-k5` refer to the private development archive; see
[provenance](provenance.md). The clean recipe checkpoint is `recipe-1m-k5`.
No serving profile changed during this screen.

Results: [exact-primary controls](primary-control-screen.md) and
[component profiling](component-profiling.md). The original primary service was
restored and passed 19 API checks. These fixed-K5 results are also preserved as
controls in the separate [adaptive research project](repository-boundaries.md).

## Primary matched controls

Compare the same source-built image and checkpoint at TP2, 1M maximum context,
96% memory budget, two request slots, batch 2,048, long-prefill cap 1,792,
FP8 KV/block256 and FULL_DECODE_ONLY target graphs with maximum capture size16.
Control A enables native K5 probabilistic DSpark/Marlin; control B omits
speculative configuration. Actual graph sizes and available KV memory can
change as a consequence of disabling speculation and must be recorded.

Predeclared screening order: **A B / B A / A B** across three paired blocks.
Every block retains one warmup and one measured short request per workload,
one short C2 pair, one warmup and one measured 48K code request plus the
existing client's other workloads and mixed short/long C2 pair. Each block
also retains one warmup and one measured 262K long-prefill/tool-roundtrip probe.
Thus each mode has three measured C1 observations per workload, three short
C2 pairs and three measured mixed probes, with warmups in every block.
This is a screen, not the five-block finalist protocol or a p95 estimate.

Observed measurement limitation: C1 warmups did not warm the same-concurrency
C2 case. Retain the three C2 trials and their onset variability. Before finalists,
add a separate C2 warmup and distinguish cold onset from steady measurements.
Record GPU clocks/throttling and more consistent cache/thermal history as well;
the initial preserved on container started cooler with resident KV.

Use unchanged `benchmark.py`, `mixed_probe.py`, `verify.py` and the frozen
`benchmarks/prompts/code-48k.txt`. Benchmark requests use fresh cache salts,
temperature0, seed42 and fixed 256 output tokens (short) or512 (long-code
client). Reasoning mode remains workload-specific and fixed across controls.
Mixed probes use independent fresh long prefixes, delay3 seconds and checked
automatic tools; retain output counts and cache-hit differences rather than
interpreting their timing as isolated scheduler cost.

Capture before/after server metrics and both GPUs at two-second intervals.
Reconcile all benchmark tokens including warmups/concurrent requests, require
zero prefix hits for salted benchmarks, and retain failures. No source builds,
kernel probes or profiling run alongside these measurements. The original
primary container is preserved and restored after switching controls.

## Diagnostic component profiles

Profiling ran as separate diagnostic traffic, excluded from control timings.
GPU kernel sums, CPU scheduling time and overlapping request-time sums are
distinct. The profiles locate work but do not measure an uninstrumented critical
path or predict an adaptive speedup. The inactive confidence head cannot be
calibrated from fixed-mode API timings.

The [manifest](../benchmarks/optimization-manifest.json) retains client hashes,
settings, measurement limitations and links to the raw controls and restoration
records. Additional adaptive compatibility, kernel work and candidate tests
are owned by the [private research repository](repository-boundaries.md).
