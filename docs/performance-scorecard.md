# Measured optimization progression

The recorded two-request aggregate rate progressed from **32.3 to 168.6 to
292.9 output tokens/second**. That is a **9.07x observed start/end difference**
across configurations. The matched DSpark on/off comparison accounts for a
**1.74x aggregate gain**. These are different comparisons.

The absolute aggregate gains are **+136.25 tok/s** from eager to the graph-enabled
control, **+124.35 tok/s** from that control to DSpark, and **+260.59 tok/s**
across the historical start/end configurations.

| Recorded configuration | Window | Prose, one request | Code, one request | Reasoning, one request | Two requests, aggregate |
|---|---:|---:|---:|---:|---:|
| First working eager setup; compilation and graphs disabled, DSpark off | 32,768 | 16.35 tok/s | 16.31 tok/s | 16.33 tok/s | 32.31 tok/s |
| Compilation and target decode graphs enabled, DSpark off | 65,536 | 95.53 tok/s | 95.57 tok/s | 95.48 tok/s | 168.55 tok/s |
| Same graph-enabled profile with fixed-five-token DSpark | 65,536 | 209.43 tok/s | 190.15 tok/s | 173.99 tok/s | **292.90 tok/s** |

All three used the same short prompts: **30 prose, 39 code and 41 reasoning
input tokens**, with 256 output tokens, temperature zero and seed42. The
configured window is capacity, not the amount of text processed. Single-request
rates are medians of two measured repeats after one warmup per exact prompt.
Aggregate throughput is 512 output tokens divided by the elapsed time of one
concurrent prose/code pair. It is neither single-user speed nor the sum of
separately timed request rates. All rates include prefill and HTTP/stream time.

## What each improvement establishes

| Comparison and denominator | Prose gain | Code gain | Reasoning gain | Aggregate gain | Interpretation |
|---|---:|---:|---:|---:|---|
| Graph-enabled control / initial eager | 5.84x | 5.86x | 5.85x | 5.22x | Historical configuration difference |
| DSpark / graph-enabled control | 2.19x | 1.99x | 1.82x | 1.74x | Matched DSpark comparison |
| DSpark / initial eager | 12.81x | 11.66x | 10.65x | 9.07x | Historical start/end difference |

The eager-to-graph transition changes compilation, graph capture and the
configured window. The exact initial derivative image digest and competing-load
state were not preserved in the inspected evidence. Do not present that row as
a graph-only experiment or label the 9.07x start/end difference as DSpark's gain.
The later graph-enabled runs use the same patched preview image, with the source
build stopped during both runs. Table order represents configuration progression;
the DSpark graph run actually preceded its graph-enabled control measurement.

Throughput improved while first visible output took slightly longer: **69–70 ms
eager, 76–78 ms graph control, and 82–94 ms DSpark** in the measured single-request
trials. These are ranges from a small sample, not p95 guarantees. Warmup describes
the procedure; these historical files do not preserve prefix-hit counters, and
their inputs are smaller than one 256-token cache block.

## Configuration and evidence

All stages use the same pinned NVFP4 checkpoint, TP=2, two sequence slots, 95%
memory utilization, FP8 KV and main FlashInfer CUTLASS experts. The initial
eager log records batch2048, block256 and prefix caching. It reports 77.83 GiB
model memory and 11.82 GiB available KV on the reporting worker; those are startup values,
not measured benchmark peaks. The later DSpark profile uses a Marlin draft,
K=5 and FULL_DECODE_ONLY target graphs with maximum capture16. Its separate
experimental draft-forward graph remains disabled.

- [Initial eager observations](../results/baseline-benchmark.json)
- [Initial feature/configuration record](../results/baseline-features.json)
- [Selected eager startup evidence](../results/eager-baseline-startup-excerpt.txt)
- [Graph-enabled control](../results/control-graphs-benchmark.json)
- [Graph-enabled DSpark](../results/dspark-graphs-benchmark.json)
- [Matched configuration and proof limits](../results/graph-benchmark-comparison.json)
- [Unrounded scorecard and independently recalculated ratios](../results/historical-performance-scorecard.json)

## Source-built 1M candidate

This later comparison uses a 1M ceiling, 96.5% memory, batch2560 and prefill
cap2304. It is a tested candidate, not a confirmed optimal default. Single short
rates pool nine measured requests per workload; aggregate rates are medians of
all three paired trials. Its sample counts and configuration differ from the
historical preview table above.

| Source-built configuration | Short prose | Short code | Short reasoning | Two short requests, aggregate median | 48,345-token code input |
|---|---:|---:|---:|---:|---:|
| Target graphs, DSpark off | 93.66 tok/s | 93.60 tok/s | 93.58 tok/s | 163.96 tok/s | 43.49 tok/s |
| Target graphs, DSpark on | 192.32 tok/s | 187.42 tok/s | 189.58 tok/s | 263.31 tok/s | 61.50 tok/s |
| DSpark/control | 2.05x | 2.00x | 2.03x | 1.61x | 1.41x |

DSpark's three paired results were 203.4, 302.9 and 263.3 tok/s. Keep the slower
initial observation; its first-output delay was larger but its cause was not
established. The longer code input uses three measured 512-token responses,
identical prompt bytes and fresh salts with zero prefix hits. First-output time
remained around 6.3 seconds in both configurations. See the
[full protocol, memory cost and raw evidence](source-image-validation.md#matched-dspark-control-on-the-source-image).

During a separate near-1M prefill, a tiny reply completed in 2.1 seconds while a
two-call tool round trip took 37.9 seconds. Reported KV availability was 6.30 GiB
with DSpark versus 11.84 GiB without it. These costs matter when choosing the
interactive recipe. **Neither 292.9 nor 302.9 tok/s describes generation after
a 1M input.**

## Source-image profile tradeoffs

All rows below retain DSpark, TP2 and a 1M window. These are configuration
comparisons, not additional DSpark-on/off experiments.

| Memory / batch / prefill cap | Two short requests, aggregate median | 48K code HTTP median | Tool round trip during 262K input, median | Minimum sampled free memory during 262K tests, GPU0 / GPU1 |
|---|---:|---:|---:|---:|
| 96.5% / 2,560 / 2,304 | 263.31 tok/s | 8.325 s | 7.149 s | 607 / 570 MiB |
| 96% / 2,048 / 1,792 | 269.88 tok/s | 8.906 s | 6.808 s | 1,247 / 1,212 MiB |
| 96% / 2,048 / 512 | 260.03 tok/s | 12.205 s | 2.186 s | 2,125 / 2,090 MiB |

The smaller cap improves observed tool responsiveness during background prefill,
but its 48K foreground coding request takes about **37% longer** than at cap1,792.
Short-throughput differences do not establish a stable ranking. Each throughput
column uses all three paired trials; coding and tool columns use three measured
trials after warmups. Coding has identical input/output counts and zero prefix
hits. Tool outputs and cache hits vary, so the tool ratio is not an isolated
scheduling effect. All trials and proof limits appear in the
[interactive comparison](interactive-latency.md) and
[unrounded profile benchmark results](../results/source-image-profile-benchmarks.json).

## Primary everyday coding/tools profile

For everyday coding and tools with occasional very long inputs, the selected
profile uses **96% memory budget, a 1M context window, TP2, two sequence slots,
a 2,048-token batch budget and a 1,792-token long-prefill cap**. It retains
fixed-K5 DSpark with Markov correction and target decode graphs.

It passed 998,869-token retrieval and final LAN API checks.
Its near-1M tool round trip took 32.035 seconds, versus 18.113 seconds at cap512;
long HTTP times were 513.759 and 539.998 seconds. These single trials expose the
tradeoff without establishing a precise speedup or latency guarantee. See
[near-1M evidence and limits](interactive-latency.md#near-1m-and-coding-limits) and
[the runnable profile](running.md#recommended-coding-profile).

### Gain over the first working baseline

| Workload | First working eager baseline | Selected coding profile | Observed rate ratio |
|---|---:|---:|---:|
| Short coding prompt, one request | 16.31 tok/s | 194.47 tok/s | 11.92x |
| Two short requests, aggregate | 32.31 tok/s | 269.88 tok/s | 8.35x |

These are overall historical configuration gains, not DSpark-only gains or
predictions that everyday coding tasks finish twelve times faster. The initial
profile used a 32K ceiling, while the selected profile keeps 1M. Image,
compilation, graphs, speculation, memory budget, cache procedure and sample counts
also differ; the initial provenance limits above still apply. Short coding has
39 input / 256 output tokens. The baseline has two measured single-request
repeats and one pair; the selected profile has nine and three, respectively.

For the larger 48,345-token coding fixture, a different, graph-enabled source
control without DSpark took 11.772 seconds, versus 8.906 seconds for the selected
profile: **24.3% less elapsed time**, or **1.32x end-to-end output rate**. Both
generate 512 tokens with zero prefix hits. This compares the control at
96.5% / batch2,560 / cap2,304 with the selected 96% / batch2,048 / cap1,792,
so it also does not isolate DSpark alone. Those earlier records contain no
equivalent 48K eager-baseline or matched tool-roundtrip measurement. The new
exact-primary controls below close the DSpark comparison gap.

Sources: [initial baseline](../results/baseline-benchmark.json),
[selected profile](../results/source-image-profile-benchmarks.json), and
[48K graph-enabled control](../results/final-control-long-code.json).

### New matched DSpark comparison at the exact primary settings

The three-pair screen keeps the primary's 1M ceiling, 96% memory, batch2048 and
cap1792, and changes only the speculative configuration. All 132 requests
reconcile with server counters, and every salted benchmark has zero prefix hits.

| Everyday workload | DSpark off | DSpark on | Observed gain |
|---|---:|---:|---:|
| Short code, median completed-answer rate | 93.66 tok/s | 200.64 tok/s | **2.14x** |
| Two short requests, aggregate median | 164.59 tok/s | 226.03 tok/s | **1.37x** |
| 48,345-token code input, 512-token answer | 11.983 s | 8.790 s | **26.6% less time** |
| Checked tool roundtrip during roughly 262K input | 18.881 s | 5.212 s | **72.4% less time, observed** |

The C2 on trials were **226.03, 204.43 and 296.16 tok/s**. They had no separate
C2 warmup, and the first two incurred about 702 ms before first output versus
89 ms in the third. Keep the full spread; it does not invalidate the historical
292.90 observation or make that best result representative. Short-code first
output also rose from 75.7 to 84.4 ms despite faster completion. Mixed outputs
and cache hits vary, so its tool ratio is not isolated scheduler speed.
The measured long retrieval duration stayed around 55 seconds in both modes.

These are descriptive medians of three observations, not p95 or an optimum.
The [full control report](primary-control-screen.md) preserves warmups,
per-pair ratios, memory cost, startup warnings and the next measurement fixes;
[unrounded results](../results/primary-dspark-comparison.json) retain every trial.

### Community release qualification rerun

The September 5 source rebuild at the primary 1M/96% settings recorded
**201.36 tok/s** median short code and **265.95 tok/s** in one concurrent pair.
The 61,287-token synthetic retrieval check passed in **22.744 seconds**.
This was a functional qualification with warm-prefix short prompts, C1 warmups
and no independent C2 warmup or matched DSpark-off arm. It does not replace the
controlled comparison above or establish a new optimization gain. See
[all unrounded trials](../results/release-qualification/benchmark.json) and
[build, startup, feature and recovery evidence](../tasks/release-readiness/verification.md).

## Adaptive verification boundary

All acceleration in this scorecard comes from the recorded fixed-mode recipe
configurations. Adaptive-verification ROI remains unmeasured. The same baseline
numbers are retained in the [separate private research project](repository-boundaries.md)
for future comparisons; this scorecard will add gains or losses only after a
compatible candidate is qualified and measured. The repository split changes
documentation ownership, not the running profile or these results.
