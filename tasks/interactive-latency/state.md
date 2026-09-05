# Interactive latency state

September 5, 2026: **bounded configuration comparison complete; coding profile
selected at 1M / 96% / batch2,048 / cap1,792.** The optional tool probe passed
five regressions and independent review. Generic launcher defaults remain
unchanged; the selected profile uses documented overrides.

The batch2560/cap2304 baseline completed one retained warmup and three measured
262K probes. All retrievals and tool round trips passed. Median tool round trip
was 7.149 seconds; long completion HTTP median was 53.728 seconds. Tool outputs
varied between 45 and 54 tokens before the six-token final reply. Prefix-hit
deltas were 0 or 256, so this is a matched functional protocol, not equal-length
uncached generation. Sampled free memory was 607/570 MiB.

The first lower-memory launch attempt found `serve.sh` absent from the remote
build-only directory after stopping the saved baseline. The reviewed launch
script was copied there and the candidate launched. This was a host staging
failure, not a GPU fit failure. The saved baseline remains available for rollback.

The 1M/96%/batch2048/cap1792 candidate passed startup and all 19 API checks.
Its three measured tool round trips were 7.199, 6.808 and 5.111 seconds; the
long HTTP median was 54.491 seconds. Minimum sampled serving free memory was
1,247/1,212 MiB. It reported 5.93 GiB KV and 1.14x maximum-length capacity.
Startup had two later autotuning allocation warnings, with 137/102 MiB sampled
free and 110 MiB minimum allocator-reported free; no early preparation warnings
were recorded in this startup. This does not establish that startup pressure
is eliminated. Warmup took 14.272 seconds for tools and is preserved separately.

The cap512 candidate passed startup, all 19 APIs, one retained warmup and three
measured 262K trials. Median tool latency was 2.186 seconds; long HTTP median
61.564 seconds, with 2,125/2,090 MiB minimum sampled serving free memory. All
three tool calls generated 45 tokens before the six-token final reply. The raw
median ratio against cap1792 is not an isolated scheduling effect because the
latter also generated 54-token calls. The same-output cap1792 trial took 5.111 s.

Both caps completed near-1M retrieval with all three facts correct. Cap512 used
998,866 input / 35 output tokens, took 539.998 seconds over HTTP, and completed
the tool round trip at delay240 in 18.113 seconds. Cap1792 used 998,869 / 35,
took 513.759 seconds over HTTP, and completed the tool round trip in 32.035
seconds. Both tool checks generated 54 + 6 tokens and finished before their long
request. Server usage counters match all three calls, with zero prefix hits and
preemptions. Minimum sampled serving free memory was 1,787/1,752 MiB at cap512
and 1,099/1,064 MiB at cap1792. These are single observations, not a latency SLO
or a steady-state speedup estimate.

The three profiles completed identical short/code/short/short benchmark sequences.
All short paired trials are retained; their medians were 263.31, 269.88 and
260.03 tok/s for batch2560/cap2304, batch2048/cap1792 and batch2048/cap512.
The 48,345-token fixture with 512-token responses measured 8.325, 8.906 and
12.205 seconds median, respectively. Counts, exact prompt bytes/settings and
zero prefix hits/preemptions were independently verified. Cap512's 37% coding
penalty versus cap1792 justifies selecting cap1792 for the user's primary coding
workload; the smaller cap remains an option for concurrent tool responsiveness.
The selected profile's roughly 7% coding cost versus the larger batch buys more
sampled serving headroom. Neither is a universal optimum.

Cap1792 passed a warmed restart in 65.268 seconds, all 19 API checks before
benchmarking, then all 19 again over LAN after its near-1M test. It is left
running; previous experiment containers remain saved for rollback. Original
preview image, source and MXFP4 launcher are preserved.

The exact synthetic coding fixture is now public with its hash, closing a
reproduction gap. The pinned performance-mode interactivity flag was audited
and adds no effective behavior under this recipe's explicit graph/batch settings;
no redundant GPU experiment was run. No scheduler or DSpark algorithm changed.

See [measurements and proof limits](../../docs/interactive-latency.md),
[selected commands](../../docs/running.md#recommended-coding-profile),
[scorecard](../../docs/performance-scorecard.md), and
[final acceptance](../../results/interactive-t1792-final-acceptance.json).
Adaptive verification and experimental draft-forward graphs remain separate phases.

Closeout verification: independent review reconciled all 12 source-profile
benchmark wrappers, the final near-1M raw counters/samples, API evidence, hashes
and recommended launch. All 69 public JSON files parsed; local documentation
links and 17 shell examples passed checks. The private-identifier scan found no
matches and the Git whitespace check passed. No runtime code changed in this
closeout; the already passing client regressions remain the applicable checks.
