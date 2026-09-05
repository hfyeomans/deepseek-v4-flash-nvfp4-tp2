# Fixed-K5 acceleration measurement protocol

The primary DSpark controls and diagnostic profiles are complete. This is the
protocol behind their acceleration measurements. Commit `e25dba7` and tag
`baseline-1m-k5` refer to the private development archive; see
[provenance](provenance.md). The clean checkpoint is `recipe-1m-k5`. The selected
profile stayed unchanged after testing.

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
finalist protocol and cannot estimate p95.

C1 warmups did not separately warm C2. Keep all three C2 trials and their
onset variation. Finalist tests need C2 warmups, separate cold/warm records,
clock/throttling telemetry and more consistent thermal/cache history. The first
on container started cooler with resident KV.

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
request durations cannot be added into an uninstrumented critical path or
adaptive speedup estimate. Fixed-mode API timings cannot calibrate the unused
confidence head.

The [manifest](../benchmarks/optimization-manifest.json) pins historical client
hashes, settings, limitations and evidence, including service restoration. The
[private research repo](repository-boundaries.md) owns adaptive compatibility,
kernel changes and candidate tests.
