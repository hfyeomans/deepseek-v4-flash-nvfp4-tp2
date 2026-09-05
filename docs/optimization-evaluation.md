# Fixed-K5 acceleration measurement protocol

We needed a DSpark comparison at the settings we'd actually use. These primary
controls and diagnostic profiles are complete. Commit `e25dba7` and tag
`baseline-1m-k5` belong to the private development archive; see
[provenance](provenance.md). Use `recipe-1m-k5` for the clean recipe. Testing
finished with the selected service restored.

See [control results](primary-control-screen.md) and
[component profiles](component-profiling.md). The restored primary service
passed 19 API checks. The [adaptive project](repository-boundaries.md) retains
these fixed-K5 baselines too.

## Primary matched controls

Use the same image/checkpoint, TP2, 1M ceiling, 96% memory, two slots, batch 2,048,
cap 1,792, FP8 KV/block 256 and FULL_DECODE_ONLY target graphs capped at 16.
A enables K5 probabilistic DSpark/Marlin; B omits speculation. Record graph
sizes and available KV, which change when speculation is disabled.

The planned order was **A B / B A / A B**. Each block retained one warmup and
one measured short request per workload, one short C2 pair, one warmup and one
measured 48K code request, plus the long-code client's other workloads and
mixed C2 pair. It also retained one warmup and one measured 262K/tool probe.
Each mode therefore has three measured C1 observations per workload, three
short C2 pairs and three mixed probes. This is smaller than the five-block
finalist protocol and can't estimate p95.

The screen missed a separate C2 warmup. Keep its three trials and onset
variation. Before choosing a finalist, warm C2 explicitly, separate cold/warm
results and record clocks/throttling. Keep thermal/cache history more consistent
too: the first on container started cooler with resident KV.

Use matched versions of `benchmark.py`, `mixed_probe.py`, `verify.py` and frozen
`benchmarks/prompts/code-48k.txt`. Benchmarks use fresh salts, temperature 0,
seed 42 and 256 output tokens for short clients or 512 for long-code clients.
Reasoning stays fixed per workload. Mixed probes use fresh long prefixes,
delay 3 seconds and checked automatic tools. Their variable outputs and hits
prevent isolating scheduler cost.

Capture before/after metrics and both GPUs every two seconds. Reconcile tokens
including warmups/pairs, require zero hits for salted benchmarks and retain
failures. Run builds, kernel probes and profiling separately. Preserve and
restore the original primary container.

## Diagnostic component profiles

Profiling is separate diagnostic traffic. Kernel sums, CPU time and overlapping
request durations can't be added into an uninstrumented critical path or
adaptive speedup estimate. Fixed-mode API timings can't calibrate the unused
confidence head.

The [manifest](../benchmarks/optimization-manifest.json) pins historical client
hashes, settings, limitations and evidence, including service restoration. The
[private research repo](repository-boundaries.md) owns adaptive compatibility,
kernel changes and candidate tests.
