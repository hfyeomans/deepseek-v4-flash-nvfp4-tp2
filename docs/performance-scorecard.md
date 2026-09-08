# Measured optimization progression

I wanted the gains visible from the first working setup through the useful
recipe. Two-request aggregate throughput rose **32.3 → 168.6 → 292.9 output
tokens/second**, a **9.07x historical difference**. The matched DSpark on/off
test accounts for a **1.74x aggregate gain**; other configuration changes
contribute to the longer progression.

The absolute aggregate gains are **+136.25 tok/s** from eager to the graph-enabled
control, **+124.35 tok/s** from that control to DSpark, and **+260.59 tok/s**
across the historical start/end configurations.

| Recorded configuration | Window | Prose, one request | Code, one request | Reasoning, one request | Two requests, aggregate |
|---|---:|---:|---:|---:|---:|
| First working eager setup; compilation and graphs disabled, DSpark off | 32,768 | 16.35 tok/s | 16.31 tok/s | 16.33 tok/s | 32.31 tok/s |
| Compilation and target decode graphs enabled, DSpark off | 65,536 | 95.53 tok/s | 95.57 tok/s | 95.48 tok/s | 168.55 tok/s |
| Same graph-enabled profile with fixed-five-token DSpark | 65,536 | 209.43 tok/s | 190.15 tok/s | 173.99 tok/s | **292.90 tok/s** |

All stages used **30 prose, 39 code and 41 reasoning input tokens**, with
256-token outputs, temperature zero and seed 42. Single-request rates are medians
of two repeats after one warmup per exact prompt. Aggregate throughput is
512 output tokens divided by one concurrent prose/code pair's elapsed time.
It includes prefill and HTTP/stream time; it's not a single-user decode rate.
The larger configured windows don't change these short input lengths.

## What each improvement establishes

| Comparison and denominator | Prose gain | Code gain | Reasoning gain | Aggregate gain | Interpretation |
|---|---:|---:|---:|---:|---|
| Graph-enabled control / initial eager | 5.84x | 5.86x | 5.85x | 5.22x | Historical configuration difference |
| DSpark / graph-enabled control | 2.19x | 1.99x | 1.82x | 1.74x | Matched DSpark comparison |
| DSpark / initial eager | 12.81x | 11.66x | 10.65x | 9.07x | Historical start/end difference |

The eager-to-graph step changed compilation, graph capture and the context
ceiling. The initial derivative image digest and competing load weren't saved,
so that step can't isolate graphs or attribute the 9.07x difference to DSpark.
The later matched runs used the same patched preview with the source build
stopped. The table follows configuration progression; DSpark was actually
measured before its graph-enabled control.

First visible output took slightly longer: **69–70 ms eager, 76–78 ms graph
control and 82–94 ms DSpark**. These small-sample ranges aren't p95 estimates.
The historical files record warmups but lack prefix-hit counters; each input
is smaller than one 256-token cache block.

## Configuration and evidence

All stages use the pinned NVFP4 checkpoint, TP=2, two slots, 95% memory, FP8 KV
and FlashInfer CUTLASS target experts. The eager log records batch 2048, block 256
and prefix caching, with 77.83 GiB model memory and 11.82 GiB available KV on the
reporting worker at startup. The later DSpark profile uses Marlin, K=5 and
FULL_DECODE_ONLY target graphs capped at 16. Draft-forward graphs are disabled.

- [Initial eager observations](../results/baseline-benchmark.json)
- [Initial feature/configuration record](../results/baseline-features.json)
- [Selected eager startup evidence](../results/eager-baseline-startup-excerpt.txt)
- [Graph-enabled control](../results/control-graphs-benchmark.json)
- [Graph-enabled DSpark](../results/dspark-graphs-benchmark.json)
- [Matched configuration and proof limits](../results/graph-benchmark-comparison.json)
- [Unrounded scorecard and independently recalculated ratios](../results/historical-performance-scorecard.json)

## Source-built 1M candidate

This later candidate uses a 1M ceiling, 96.5% memory, batch 2560 and cap 2304.
Short rates pool nine requests per workload; aggregate rates are medians of
three paired trials. Those settings and sample counts differ from the preview
comparison above.

| Source-built configuration | Short prose | Short code | Short reasoning | Two short requests, aggregate median | 48,345-token code input |
|---|---:|---:|---:|---:|---:|
| Target graphs, DSpark off | 93.66 tok/s | 93.60 tok/s | 93.58 tok/s | 163.96 tok/s | 43.49 tok/s |
| Target graphs, DSpark on | 192.32 tok/s | 187.42 tok/s | 189.58 tok/s | 263.31 tok/s | 61.50 tok/s |
| DSpark/control | 2.05x | 2.00x | 2.03x | 1.61x | 1.41x |

DSpark paired trials measured 203.4, 302.9 and 263.3 tok/s. The initial delay
has no established cause; all three trials count. Long code uses identical
inputs, three 512-token responses and fresh salts, with zero prefix hits.
First output stayed around 6.3 seconds in both modes. See
[protocol, memory cost and evidence](source-image-validation.md#matched-dspark-control-on-the-source-image).

During a separate near-1M prefill, a tiny reply took 2.1 seconds and a two-call
tool roundtrip took 37.9 seconds. Available KV was 6.30 GiB with DSpark versus
11.84 GiB without it. **Neither 292.9 nor 302.9 tok/s describes generation
after a 1M input.**

## Source-image profile tradeoffs

These profiles all retain DSpark, TP2 and a 1M window.

| Memory / batch / prefill cap | Two short requests, aggregate median | 48K code HTTP median | Tool round trip during 262K input, median | Minimum sampled free memory during 262K tests, GPU0 / GPU1 |
|---|---:|---:|---:|---:|
| 96.5% / 2,560 / 2,304 | 263.31 tok/s | 8.325 s | 7.149 s | 607 / 570 MiB |
| 96% / 2,048 / 1,792 | 269.88 tok/s | 8.906 s | 6.808 s | 1,247 / 1,212 MiB |
| 96% / 2,048 / 512 | 260.03 tok/s | 12.205 s | 2.186 s | 2,125 / 2,090 MiB |

Cap 512 helps tools during background prefill, but its 48K coding request takes
about **37% longer** than cap 1,792. That's the tradeoff behind the two profiles.
Each column uses three measured trials after warmups. Coding counts match with
zero hits; tool outputs/hits vary, so their ratio can't isolate scheduling.
Small short-throughput differences don't establish a ranking. See
[trial details](interactive-latency.md) and
[unrounded benchmarks](../results/source-image-profile-benchmarks.json).

## Primary everyday coding/tools profile

For everyday coding and tools, I'd start with **96% memory, a 1M window, TP2,
two slots, batch 2,048 and cap 1,792**. It keeps fixed-K5 DSpark, Markov correction
and target decode graphs.

It passed 998,869-token retrieval and final LAN API checks. One near-1M tool
roundtrip took 32.035 seconds versus 18.113 at cap 512; long HTTP times were
513.759 and 539.998 seconds. These single trials show the tradeoff without
establishing a repeatable latency gain. See
[near-1M evidence](interactive-latency.md#near-1m-and-coding-limits) and
[launch commands](running.md#recommended-coding-profile).

### Gain over the first working baseline

| Workload | First working eager baseline | Selected coding profile | Observed rate ratio |
|---|---:|---:|---:|
| Short coding prompt, one request | 16.31 tok/s | 194.47 tok/s | 11.92x |
| Two short requests, aggregate | 32.31 tok/s | 269.88 tok/s | 8.35x |

These ratios show what changed over the project. They don't mean everyday
coding will finish twelve times faster. Image, compilation, graphs, speculation,
memory, cache procedure and sample counts changed, and the ceiling grew from
32K to 1M. The coding test itself stayed at 39 input/256 output tokens. Eager
has two repeats and one pair; the selected profile has nine and three. The
initial provenance limits above still apply.

For 48,345-token code, a graph-enabled source control without DSpark took
11.772 seconds versus 8.906 for the selected profile: **24.3% less time**, or
**1.32x output rate**. Both generated 512 tokens with zero prefix hits. The
control used 96.5% / batch 2,560 / cap 2,304 versus 96% / batch 2,048 / cap 1,792,
so this also combines configuration changes. No equivalent 48K eager or matched
tool baseline was recorded. The next comparison isolates DSpark at the primary
settings.

Sources: [initial baseline](../results/baseline-benchmark.json),
[selected profile](../results/source-image-profile-benchmarks.json), and
[48K graph-enabled control](../results/final-control-long-code.json).

### New matched DSpark comparison at the exact primary settings

This three-pair comparison changes only speculation at the primary 1M / 96% /
batch 2048 / cap 1792 settings. All 132 requests match server token counters;
every salted benchmark has zero prefix hits.

| Everyday workload | DSpark off | DSpark on | Observed gain |
|---|---:|---:|---:|
| Short code, median completed-answer rate | 93.66 tok/s | 200.64 tok/s | **2.14x** |
| Two short requests, aggregate median | 164.59 tok/s | 226.03 tok/s | **1.37x** |
| 48,345-token code input, 512-token answer | 11.983 s | 8.790 s | **26.6% less time** |
| Checked tool roundtrip during roughly 262K input | 18.881 s | 5.212 s | **72.4% less time, observed** |

C2 DSpark-on trials measured **226.03, 204.43 and 296.16 tok/s**, without a
separate C2 warmup. First output took about 702 ms in the first two and 89 ms
in the third. Use the full spread; the historical 292.90 result belongs to
its own procedure. Short-code first output rose from 75.7 to 84.4 ms. Mixed
outputs and cache hits vary, so the tool ratio can't isolate scheduler speed.
Long retrieval stayed around 55 seconds in both modes.

Keep all three observations when quoting the median. They can't establish
p95 or an optimum. The [control report](primary-control-screen.md) explains
warmups, per-pair ratios, memory and startup warnings; the
[raw comparison](../results/primary-dspark-comparison.json) retains every trial.

### Community release qualification rerun

The September 5 rebuild at 1M/96% recorded **201.36 tok/s** median short code,
**265.95 tok/s** in one concurrent pair and a passing 61,287-token retrieval in
**22.744 seconds**. This checked functionality using warm-prefix prompts and
C1 warmups. It had no separate C2 warmup or DSpark-off control, so it establishes
no new optimization gain. See [trials](../results/release-qualification/benchmark.json)
and [build, startup, API and recovery checks](../results/release-qualification/summary.json).

## Adaptive verification boundary

Adaptive-verification ROI is unmeasured. The
[private research project](repository-boundaries.md) retains these fixed-mode
baselines for future comparisons. Add adaptive gains or losses here only after
a compatible implementation is tested and measured.
