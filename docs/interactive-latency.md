# Tool responsiveness during long prefill

The model passed API checks, but one tool roundtrip still took 37.9 seconds
during near-1M prefill. We wanted a more useful everyday profile. This test
changes batch and prefill caps while keeping 1M, K5, Markov correction, target
graphs, FP8 KV, TP2 and two slots.

**For coding, I'd start with 96% memory, batch 2,048, cap 1,792 and 1M context.**
It keeps most larger-batch speed with more serving headroom. Cap 512 is useful
when tools during long prefill matter more, but neither profile gave subsecond
tools near 1M. See [launch commands](running.md#recommended-coding-profile).

## Repeated 262K protocol

Each profile has one saved warmup and three repeats, without a competing build.
Retrieval requests 262,000 tokens with a fresh prefix and must return three facts.
Three seconds after the long call starts, an independent client checks a tool roundtrip:
function, arguments, return value and final answer. Both calls must finish before
the long request. Each trial saves server counters and two-second GPU samples.

| Profile, all with 1M window | Tool round-trip median | Long HTTP median | Minimum sampled serving free memory, GPU0 / GPU1 |
|---|---:|---:|---:|
| 96.5%, batch2560, cap2304 | 7.149 s | 53.728 s | 607 / 570 MiB |
| 96%, batch2048, cap1792 | 6.808 s | 54.491 s | 1,247 / 1,212 MiB |
| 96%, batch2048, cap512 | **2.186 s** | 61.564 s | **2,125 / 2,090 MiB** |

The smaller batch/budget gave more headroom with similar timing. Changing only
cap 1792 to 512 reduced tool median by 68% while lengthening retrieval by 13%.
Both caps later passed near-1M mixed retrieval. These 262K trials can't be
compared as a speedup over the earlier near-1M probe: length, submission point
and workload differ.

The first tool input has 295 tokens, but its 45- or 54-token output changes the
second input to 370 or 379 tokens; the final answer is six tokens. Prefix-hit
deltas were 0/256/256 in both earlier profiles and 256 in every cap 512 trial;
global counters can't assign hits to a call. Cap 512 always generated 45 tokens
for the call. The one cap 1792 trial with that length took 5.111 seconds versus
2.155–2.330 seconds across cap 512 trials. That single match can't isolate the
effect precisely. Long inputs ranged 261,865–261,872 tokens. Usage matched server
counters, with zero preemptions.

Keep per-trial outputs and cache hits beside the medians. Three workload
comparisons can't establish an isolated scheduler gain, tail latency or broad
tool accuracy.

Tool warmups took 7.216, 14.272 and 22.376 seconds, respectively. They remain in
the evidence but are excluded from medians under the planned protocol. These
are warmed results, not first-request guarantees.

DSpark was active throughout. Cap 1792 accepted 188/370 proposed tokens and
cap 512 accepted 156/425 across measured mixed runs. Those global counters combine
retrieval and tools; they can't isolate tool acceptance or DSpark's speed benefit.

## Memory and startup

Batch 2048/cap 1792 reported 5.93 GiB KV and 1.14x maximum-length capacity versus
6.30 GiB/1.12x at batch 2560/cap 2304. Smaller batches reduce in-flight reservation.
Capacity arithmetic doesn't test two simultaneous full-1M requests.

Cap 1792 reached readiness in 124.4 seconds with the existing FlashInfer cache
and passed 19 API checks. No early draft-preparation warnings appeared; two
later autotuning warnings remained. Samples reached 137/102 MiB free and
allocator logs 110 MiB. One startup can't establish a consistent margin.

Cap 512 passed 19 API checks with the same 5.93 GiB KV/1.14x capacity. Readiness
took 124.5 seconds. It had no early preparation warnings and two later autotuning
warnings. Startup minima were 173/138 MiB sampled and 146 MiB allocator-reported.

## Near-1M and coding limits

Cap 512 retrieved all three facts from **998,866 input tokens**, producing 35
tokens in 539.998 seconds over HTTP (541.811 for the whole probe). At delay 240
seconds, tools passed in 18.113 seconds: 6.784 for the 54-token call and 11.329 for
the six-token answer, finishing 281.877 seconds before the long request. Totals
of 999,540 input/95 output matched server counters, with zero hits/preemptions.
Minimum free memory across 267 samples was 1,787/1,752 MiB.

This single later-prefill trial can't guarantee 18-second latency or isolate
a gain over the earlier 37.9-second test. The 2.2-second median at 262K doesn't
predict near-1M latency. See [the full record](../results/interactive-b2048-t512-1m.json).

Cap 1792 retrieved all three facts from **998,869 input tokens**, producing 35
tokens in 513.759 seconds over HTTP (515.623 for the probe). At the same 240-second
delay, tools took **32.035 seconds**: 25.045 for the 54-token call and 6.990 for the
six-token answer, finishing 241.716 seconds before retrieval. Totals of 999,543
input/95 output matched server counters, with zero hits/preemptions. Minimum
free memory across 254 samples was 1,099/1,064 MiB.

| Near-1M profile, both at 96% / batch2,048 | Actual long input / output | Long HTTP | Tool round trip at 240 s | Minimum sampled free memory, GPU0 / GPU1 |
|---|---:|---:|---:|---:|
| Cap1,792 | 998,869 / 35 | 513.759 s | 32.035 s | 1,099 / 1,064 MiB |
| Cap512 | 998,866 / 35 | 539.998 s | 18.113 s | 1,787 / 1,752 MiB |

Each cap has one trial with matched requested length, delay and tool-output
lengths. Run order, prefixes and cache histories differ. Accepted/proposed tokens
were 64/132 at cap 1792 and 67/129 at cap 512, pooled across retrieval and tools.
These runs don't isolate DSpark, establish sustained speed or compare broad
accuracy.

Cap 1792 restarted warm in 65.268 seconds and passed 19 API checks before
benchmarking, then 19 LAN checks after near-1M retrieval. See the
[retrieval record](../results/interactive-b2048-t1792-1m.json) and
[restart/API results](../results/interactive-t1792-final-acceptance.json).

The 48K coding fixture changed the choice. Cap 512 took 12.205 seconds median
at 41.95 output tok/s versus 8.325 seconds at 61.50 tok/s for batch 2560/cap 2304.
First output rose from about 6.3 to 9.5 seconds. Cap 1792 took 8.906 seconds. For
everyday coding, I'd accept somewhat slower background tools to keep the
foreground request moving.

| Source-image profile | Short prose | Short code | Short reasoning | Two short requests, aggregate | 48K code, elapsed / output rate |
|---|---:|---:|---:|---:|---:|
| 96.5%, batch2560, cap2304 | 192.32 tok/s | 187.42 tok/s | 189.58 tok/s | 263.31 tok/s | 8.325 s / 61.50 tok/s |
| 96%, batch2048, cap1792 | 191.46 tok/s | 194.47 tok/s | 182.19 tok/s | 269.88 tok/s | 8.906 s / 57.49 tok/s |
| 96%, batch2048, cap512 | 198.85 tok/s | 183.16 tok/s | 180.29 tok/s | 260.03 tok/s | 12.205 s / 41.95 tok/s |

Short rates pool nine requests per workload; paired rates use all three trials.
Code uses three 512-token responses to identical 48,345-token inputs with unique
salts. All benchmarks had zero hits/preemptions and followed short/code/short/short
order; earlier mixed workloads and cache histories differ. Small short-input
differences can't rank profiles reliably. Code ranges don't overlap between
caps: 8.625–8.925 versus 12.022–12.230 seconds.

That's why cap 1792 is the coding default and cap 512 is the concurrent-tools
option. Both passed near-1M retrieval with the same DSpark/API features. The
selected cap costs about 7% coding time versus batch 2560/cap 2304 for more
headroom. See [all trials](../results/source-image-profile-benchmarks.json).

## A flag that does not add a gain here

`--performance-mode interactivity` leaves this recipe's effective graphs
unchanged. Balanced starts at `[1,2,4,8,16]`, interactivity at `[1…16]`; K5
alignment makes both `[6,12]` at capture 16. The pinned CUTLASS and Marlin paths
don't consume this mode. Its other branch only changes unspecified batch
defaults in throughput mode. With these explicit settings, another trial would
repeat the same configuration. See
[defaults](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/vllm.py#L1897),
[alignment](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/compilation.py#L1518)
and [throughput defaults](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/engine/arg_utils.py#L2733).

## Evidence and reproduction

- [Unrounded comparison and individual trial summaries](../results/interactive-latency-comparison.json)
- [Baseline warmup](../results/interactive-b2560-t2304-warmup.json), [trial 1](../results/interactive-b2560-t2304-1.json), [trial 2](../results/interactive-b2560-t2304-2.json), [trial 3](../results/interactive-b2560-t2304-3.json)
- [Lower-memory warmup](../results/interactive-b2048-t1792-warmup.json), [trial 1](../results/interactive-b2048-t1792-1.json), [trial 2](../results/interactive-b2048-t1792-2.json), [trial 3](../results/interactive-b2048-t1792-3.json)
- [Lower-memory startup and API acceptance](../results/interactive-b2048-t1792-acceptance.json), [startup excerpt](../results/interactive-b2048-t1792-startup-excerpt.txt)
- [Cap 512 warmup](../results/interactive-b2048-t512-warmup.json), [trial 1](../results/interactive-b2048-t512-1.json), [trial 2](../results/interactive-b2048-t512-2.json), [trial 3](../results/interactive-b2048-t512-3.json)
- [Cap 512 startup and API acceptance](../results/interactive-b2048-t512-acceptance.json), [startup excerpt](../results/interactive-b2048-t512-startup-excerpt.txt)
- [Probe commands](running.md#check-responsiveness-during-a-long-input), [measurement regressions](validation.md#mixed-tool-responsiveness)

Published results replace large prompts with character counts and SHA256 hashes.
The generator, prefixes, settings and usage remain recorded; full raw inputs
and resource samples are retained privately.
