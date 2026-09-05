# Exact-primary DSpark controls

The primary coding profile's matched engine comparison shows **2.14x short-code
throughput** and **26.6% less elapsed time for the 48K coding fixture** with
DSpark. First-output latency does not improve with every workload. This is a
three-pair operational screen, not a claim of optimality or a p95 estimate.

## What stayed fixed

Both controls use the same source-built image and pinned NVFP4 checkpoint,
TP2, a 1,000,000-token ceiling, 96% memory budget, two request slots,
batch 2048, long-prefill cap 1792, FP8 KV/block 256, prefix caching, FlashInfer
CUTLASS target experts and FULL_DECODE_ONLY target graphs capped at 16.
The only engine command difference is removal of the K5 probabilistic
DSpark/Marlin configuration in the off control. The image, environment,
entrypoint, GPU device requests and cache mounts were checked for equality.

The predeclared order was **on/off, off/on, on/off**. Every block ran the
unchanged benchmark clients, with C1 warmups, fresh cache salts and retained
measured/concurrent requests. The mixed probes had their own warmups.
The [manifest](../benchmarks/optimization-manifest.json) pins configuration,
hardware and client hashes; the [protocol](optimization-evaluation.md)
defines the procedure. Measurements were serialized with profiling and kernel
tests. All numbers below use three measured observations per mode.

## Completed-answer speed and first output

| Workload | DSpark off median | DSpark on median | Comparison |
|---|---:|---:|---:|
| Short prose, one request | 93.73 tok/s | 201.49 tok/s | 2.15x throughput |
| Short code, one request | 93.66 tok/s | 200.64 tok/s | 2.14x throughput |
| Short reasoning, one request | 93.63 tok/s | 192.25 tok/s | 2.05x throughput |
| Two short requests, aggregate | 164.59 tok/s | 226.03 tok/s | 1.37x throughput |
| 48,345-token code input, 512-token answer | 11.983 s | 8.790 s | 26.6% less elapsed time |
| Same 48K code request, first output | 6.546 s | 6.636 s | 1.4% more time |
| Short code, first output | 75.7 ms | 84.4 ms | 11.5% more time |

Short inputs are 30/39/41 tokens for prose/code/reasoning, with 256-token
outputs. Temperature 0 and seed 42 are fixed. Rates include prefill and HTTP
streaming time; these are not isolated decode rates. A configured 1M ceiling
does not make these 1M-input measurements. Aggregate rate is 512 output tokens
divided by the elapsed time of the concurrent pair, not the sum of C1 rates.
The longer code client also runs short prose/reasoning and a short-prose/long-code
pair; all of those requests remain in the evidence.

### Concurrency onset is an unresolved cost

| Pair | Off aggregate tok/s | On aggregate tok/s | On first output, prose/code |
|---|---:|---:|---:|
| 1 | 164.34 | 226.03 | 703/703 ms |
| 2 | 165.01 | 204.43 | 702/701 ms |
| 3 | 164.59 | 296.16 | 89/89 ms |

The client warmed C1 workloads, but did **not** separately warm C2. Pair2-on
restarted the serving container; pair3-on continued without a restart. The
history allows a possible cold-versus-steady effect, but does not identify its
cause. Keep all three trials. The older 269.88 median and 292.90 historical
observation remain valid records of their own procedures; they do not replace
this screen's lower median. Finalist testing must separately record cold onset
and warm every concurrency/workload before measuring it.

## Tools during a long prefill

| Checked mixed workload | Off median | On median | Observed change |
|---|---:|---:|---:|
| Two-call automatic-tool roundtrip during a roughly 262K input | 18.881 s | 5.212 s | 72.4% less elapsed time |
| Long retrieval probe, including preparation | 54.555 s | 54.970 s | 0.8% more time |
| Long completion call alone | 54.174 s | 54.595 s | 0.8% more time |

All twelve mixed probes, including warmups, passed retrieval and tool checks;
the short operation completed before the long call. Actual long prompts range
262,007–262,011 tokens. Long answers vary from 25 to 35 tokens in measured trials;
tool-call outputs vary from 45 to 54 tokens, changing the follow-up prompt.
Mixed requests are unseeded, have no fixed minimum output, and record 256–512
prefix hits per run. These differences make the tool ratio an observed workload
outcome, not isolated scheduler speed. Similar long times do not prove
equivalence. These synthetic checks are not broad coding/tool-quality scores.

## Memory, accounting and remaining uncertainty

Startup reports 77.83 GiB model memory without DSpark and 83.21 GiB with it on
the reporting worker. Available KV falls from **11.43 to 5.93 GiB**, with calculated
capacity 2,187,600 versus 1,135,251 tokens. Those are capacity estimates, not tests
of two simultaneous 1M requests. Graph pool measurements are 0.09/0.10 GiB; the
largest profiled graph changes from 2 to 12 rows. The DSpark scheduler reports an
effective 2040 scheduled-token limit from the configured 2048 budget.

All **132 requests** reconcile exactly: **4,025,096 prompt tokens** and
**37,873 generated tokens**. All 96 benchmark salts are unique, and every salted
benchmark has zero prefix hits. All 24 measurement windows have zero errors,
aborts and preemptions. There are 537 samples covering both GPUs at about
two-second intervals. Minimum sampled free memory is 1,097/1,062 MiB with
DSpark and 1,251/1,214 MiB without it, across the full client runs.

The first on block starts cooler and with resident KV from previous use; later
blocks have different thermal/cache history. Peak sampled temperature is 89 C,
and clock/throttling telemetry was not recorded. No cause for timing variance
is established. Each of the three recorded startup segments has two recovered
allocator OOM warnings during autotuning before reaching readiness. Clean
measurement counters do not make startup OOM-free or establish long-term
stability. Sampled memory minima are not continuous peaks.

## What this says about K5

Across the three complete on-short clients, including warmups and C2, there
were 1,924 draft rounds, 9,620 proposals and 4,233 accepted draft tokens. Acceptance
at positions 1–5 was 1,533/1,111/741/511/337: the fifth position survived in
**17.5% of rounds**. These counters cannot be assigned to one C1 workload.
Conditional on the first four positions surviving, the fifth survived
337/511 = **65.95%**. The denominator matters: this is not a 17.5% conditional
acceptance probability. See [K5 and accepted-prefix metrics](dspark-k-and-verification.md)
for the distinction between configuration, acceptance and useful acceleration.

That does not prove the fifth proposal is wasteful. As a rough counterfactual
holding acceptance behavior fixed, removing it reduces estimated tokens advanced
per round from 3.200 to 3.025. Total cycle cost would need to fall by more than
5.5% just to break even, before added adaptive overhead. Actual prefix changes
also change future proposal histories, so this is a teaching example, not a
measured L4 result or adaptive ROI estimate. Graph padding may preserve much
of the verification cost. A supported prefix implementation, measured cycle
costs and calibrated per-request confidence are still needed.

Evidence: [all control rows, counters and resources](../results/primary-dspark-controls.json),
[independently recomputed comparisons and every trial](../results/primary-dspark-comparison.json),
[overall scorecard](performance-scorecard.md).
