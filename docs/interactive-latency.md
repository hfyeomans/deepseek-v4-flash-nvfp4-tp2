# Tool responsiveness during long prefill

The source-built candidate passed API checks but took 37.9 seconds for one tool
round trip during a near-1M input. Admission alone did not establish responsive
tool use. This experiment compares feasible batch and prefill-cap settings while
retaining the 1M window, fixed-K5 DSpark, Markov correction, target decode graphs,
FP8 KV, TP2 and two sequence slots.

**Recommended coding profile among those tested: 96% memory, batch2,048,
prefill cap1,792, 1M window.** It preserves most of the larger-batch coding
performance while giving more sampled serving headroom. Cap512 is an alternative
when tools sharing a long prefill matter more than foreground coding speed.
Neither profile gives subsecond tool latency during the near-1M probe.
See [launch commands](running.md#recommended-coding-profile).

## Repeated 262K protocol

Each profile runs one retained warmup and three measured repeats, with no source
build running. The long retrieval requests 262,000 tokens, gets a fresh prefix,
and must return three correct facts. Three seconds after its completion call
starts, an independent client runs the same automatic-tool check. It verifies
the function name, arguments, returned value and final answer. Both tool calls
must finish before the long request. Separate server metrics and two-second GPU
samples accompany every trial.

| Profile, all with 1M window | Tool round-trip median | Long HTTP median | Minimum sampled serving free memory, GPU0 / GPU1 |
|---|---:|---:|---:|
| 96.5%, batch2560, cap2304 | 7.149 s | 53.728 s | 607 / 570 MiB |
| 96%, batch2048, cap1792 | 6.808 s | 54.491 s | 1,247 / 1,212 MiB |
| 96%, batch2048, cap512 | **2.186 s** | 61.564 s | **2,125 / 2,090 MiB** |

The lower batch/budget gives more serving headroom with similar timing in this
small comparison. Reducing only its cap from 1792 to 512 lowers the observed tool
median by 68%, while the long request takes 13% longer. Both caps subsequently
passed near-1M retrieval with a concurrent tool round trip.
These 262K results must not be presented as a speedup over the
earlier near-1M tool observation: context, submission point and workload differ.

The first tool request is fixed at 295 input tokens. Its generated call contains
45 or 54 output tokens, so the second request has 370 or 379 input tokens and
returns six tokens. Initial prompts and protocol are fixed; the entire second
payload is not. Measured total prefix-hit deltas are 0, 256 and 256 in both
earlier profiles, versus 256 in every cap512 trial; aggregate counters cannot
identify which individual call benefited. Every cap512 tool call generated 45
tokens before the six-token final answer. The cap1792 trial with that same output
length took 5.111 seconds, compared with 2.155–2.330 seconds across cap512's three
trials; the single comparison trial does not establish a precise isolated effect.
Actual long inputs range from 261,865 to 261,872 tokens across the three profiles.
All client usage totals match the server counters; no preemptions occurred.

Consequently, these are functional workload comparisons, not proof that every
millisecond of difference comes from the scheduling change. Show the individual
trials, output lengths and cache hits alongside medians. Three measured trials
do not establish tail-latency guarantees or broad tool-use quality.

The retained warmups took 7.216, 14.272 and 22.376 seconds for tools, respectively;
they are excluded by the predeclared protocol, not removed from the evidence.
The measured improvement is a warmed result, not a first-request guarantee.

DSpark remains active in every profile, but a higher acceptance fraction is not
the same as a faster response. Across the three measured mixed runs, cap1792
accepted 188 of 370 proposed tokens, while cap512 accepted 156 of 425. These global
counters include both the long retrieval and tools. They do not measure tool-only
draft quality or isolate DSpark's benefit from a DSpark-off control at this cap.

## Memory and startup

The batch2048/cap1792 startup reports 5.93 GiB available KV and 1.14x
maximum-length cache capacity, versus 6.30 GiB and 1.12x for batch2560/cap2304.
The smaller batch reduces the admission reservation for work in flight. Reported
capacity is arithmetic, not a test of two simultaneous full-1M requests.

The lower-memory candidate reached readiness after 124.4 seconds of observation
with the existing FlashInfer cache. It passed all 19 short API checks. Its startup
record contains no early draft-preparation warnings, but two later autotuning
allocation warnings remain. Samples reached 137/102 MiB free; allocator messages
reported a minimum of 110 MiB. This single startup does not establish that
preparation pressure is eliminated or that every launch has the same margin.

Cap512 also passed all 19 short API checks. It reported the same 5.93 GiB KV and
1.14x capacity, reached readiness after 124.5 seconds, and recorded two later
autotuning warnings. Its sampled startup minimum was 173/138 MiB and minimum
allocator-reported free memory 146 MiB; no early preparation warnings were recorded.

## Near-1M and coding limits

Cap512 retrieved all three facts from **998,866 input tokens**, with 35 output
tokens. Its long completion took 539.998 seconds over HTTP, 541.811 seconds for
the whole probe. A tool round trip submitted 240 seconds after that completion
call started passed in 18.113 seconds: 6.784 seconds for the 54-token call and
11.329 seconds for the six-token final response. It finished 281.877 seconds
before the long request. The three calls totaled 999,540 input and 95 output
tokens, matching server counters; prefix hits and preemptions were zero.
Minimum sampled serving free memory was 1,787/1,752 MiB across 267 samples.

This is one later-prefill observation, not a guarantee of 18-second latency or a
matched speedup over the earlier 37.9-second test. The 2.2-second 262K median does
not establish near-1M responsiveness. See [the complete near-1M record](../results/interactive-b2048-t512-1m.json).

Cap1792 subsequently retrieved all three facts from **998,869 input tokens**,
also with 35 output tokens. Long HTTP time was 513.759 seconds, with 515.623 seconds
for the complete retrieval probe. The tool check at the same 240-second delay
took **32.035 seconds**: 25.045 seconds for the 54-token call and 6.990 seconds
for the six-token final response. It finished 241.716 seconds before the long
request. All three calls totaled 999,543 input / 95 output tokens, exactly
matching server deltas, with zero prefix hits and preemptions. Minimum sampled
serving free memory was 1,099/1,064 MiB across 254 samples.

| Near-1M profile, both at 96% / batch2,048 | Actual long input / output | Long HTTP | Tool round trip at 240 s | Minimum sampled free memory, GPU0 / GPU1 |
|---|---:|---:|---:|---:|
| Cap1,792 | 998,869 / 35 | 513.759 s | 32.035 s | 1,099 / 1,064 MiB |
| Cap512 | 998,866 / 35 | 539.998 s | 18.113 s | 1,787 / 1,752 MiB |

These are one observation per cap, with the same requested length, submission
delay and tool output lengths. Separate run order, slightly different long
prefixes and prior cache histories remain; this is not a steady-state speedup
estimate. Global speculative counters confirm accepted tokens in both runs
(64/132 proposed at cap1792, 67/129 at cap512), but combine retrieval and tools.
They do not isolate DSpark's benefit or establish equivalent general accuracy.

The cap1792 container also passed a warmed restart in 65.268 seconds and all
19 short API checks before benchmarking, then all 19 again over the LAN after
this near-1M run. It remains the selected coding service. See the
[near-1M record](../results/interactive-b2048-t1792-1m.json) and
[restart and final API acceptance](../results/interactive-t1792-final-acceptance.json).

The frozen 48K coding benchmark also exposes a cost that the padding-based
retrieval test alone misses. Cap512 measured 41.95 output tok/s end to end and
12.205 seconds median, versus 61.50 tok/s and 8.325 seconds in the earlier
batch2560/cap2304 profile. First output moved from roughly 6.3 to 9.5 seconds.
The lower-memory cap1792 profile then measured 8.906 seconds on the same code
fixture, much closer to the earlier profile. A responsiveness gain during a
background prefill should not hide slower foreground coding.

| Source-image profile | Short prose | Short code | Short reasoning | Two short requests, aggregate | 48K code, elapsed / output rate |
|---|---:|---:|---:|---:|---:|
| 96.5%, batch2560, cap2304 | 192.32 tok/s | 187.42 tok/s | 189.58 tok/s | 263.31 tok/s | 8.325 s / 61.50 tok/s |
| 96%, batch2048, cap1792 | 191.46 tok/s | 194.47 tok/s | 182.19 tok/s | 269.88 tok/s | 8.906 s / 57.49 tok/s |
| 96%, batch2048, cap512 | 198.85 tok/s | 183.16 tok/s | 180.29 tok/s | 260.03 tok/s | 12.205 s / 41.95 tok/s |

Short columns pool nine measured requests per workload; paired columns are
medians of all three trials. Coding uses three measured 512-token responses to
identical 48,345-token inputs with unique cache salts. Zero prefix hits and
preemptions were verified in every benchmark. All profiles followed the same
short/code/short/short order, but prior mixed workloads and cache histories differ.
Small short-prompt differences do not establish a stable ranking. The coding
time ranges do not overlap between the two caps: 8.625–8.925 versus 12.022–12.230 s.

This supports choosing cap1792 for coding and offering cap512 when concurrent
tool responsiveness matters more. Both passed near-1M retrieval and retain the
same configured DSpark/API features. The selected cap1792 code median is about
7% slower than batch2560/cap2304, a measured cost accepted for more serving
headroom. These are workload-specific choices, not a universal optimum.
See [unrounded profile comparisons and all benchmark files](../results/source-image-profile-benchmarks.json).

## A flag that does not add a gain here

The pinned `--performance-mode interactivity` does not change this recipe's
effective graph sizes. Balanced starts with `[1,2,4,8,16]`; interactivity starts
with `[1…16]`. Fixed-K5 alignment reduces both to `[6,12]` at maximum capture16,
covering the same two request counts. The pinned source has no CUTLASS or Marlin
consumer of this mode. The other behavioral branch changes unspecified batch
defaults only for throughput mode. An extra GPU trial for the interactivity flag
would therefore repeat the same configuration here. This is specific to these
explicit settings, not a general claim about the flag in every deployment.
See [graph defaults](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/vllm.py#L1897),
[speculative alignment](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/config/compilation.py#L1518),
and [throughput defaults](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/engine/arg_utils.py#L2733).

## Evidence and reproduction

- [Unrounded comparison and individual trial summaries](../results/interactive-latency-comparison.json)
- [Baseline warmup](../results/interactive-b2560-t2304-warmup.json), [trial 1](../results/interactive-b2560-t2304-1.json), [trial 2](../results/interactive-b2560-t2304-2.json), [trial 3](../results/interactive-b2560-t2304-3.json)
- [Lower-memory warmup](../results/interactive-b2048-t1792-warmup.json), [trial 1](../results/interactive-b2048-t1792-1.json), [trial 2](../results/interactive-b2048-t1792-2.json), [trial 3](../results/interactive-b2048-t1792-3.json)
- [Lower-memory startup and API acceptance](../results/interactive-b2048-t1792-acceptance.json), [startup excerpt](../results/interactive-b2048-t1792-startup-excerpt.txt)
- [Cap512 warmup](../results/interactive-b2048-t512-warmup.json), [trial 1](../results/interactive-b2048-t512-1.json), [trial 2](../results/interactive-b2048-t512-2.json), [trial 3](../results/interactive-b2048-t512-3.json)
- [Cap512 startup and API acceptance](../results/interactive-b2048-t512-acceptance.json), [startup excerpt](../results/interactive-b2048-t512-startup-excerpt.txt)
- [Probe commands](running.md#check-responsiveness-during-a-long-input), [measurement regressions](validation.md#mixed-tool-responsiveness), [experiment plan](../tasks/interactive-latency/plan.md)

Large synthetic prompts are replaced in public results by character counts and
SHA256 hashes. Their generator, unique prefixes, settings and actual usage remain
recorded. Complete raw inputs and resource samples are retained privately.
