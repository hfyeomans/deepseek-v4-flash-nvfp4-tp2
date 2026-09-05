# Interactive latency state

September 5, 2026: comparison complete; selected **1M/96%/batch 2,048/cap 1,792**.
The tool probe passed five regressions and independent review. Launcher defaults
stay unchanged; selection uses overrides.

Batch 2560/cap 2304 passed one warmup and three 262K repeats. Tool/long medians:
7.149/53.728 seconds; serving minima 607/570 MiB. Tool calls varied 45–54 tokens
then six-token answers, with 0 or 256 prefix hits. This is a fixed protocol,
not equal-length uncached generation.

The first lower-memory launch lacked `serve.sh` in the remote build directory.
Copying the reviewed launcher resolved this staging failure. The stopped
baseline remained available; this was not a GPU fit failure.

Cap 1792 passed startup and 19 APIs. Tool repeats:7.199/6.808/5.111 seconds; long
median 54.491 seconds; serving minima 1,247/1,212 MiB. Startup reported 5.93 GiB
KV/1.14x capacity. Two later autotuning warnings remained, with 137/102 MiB
sampled and 110 MiB allocator-reported free; no early warnings appeared.
Warmup took 14.272 seconds and is retained. One launch cannot rule out pressure.

Cap 512 passed startup,19 APIs, one warmup and three 262K repeats. Tool/long
medians:2.186/61.564 seconds; serving minima 2,125/2,090 MiB. All tool calls
generated 45 tokens then six-token answers. Cap 1792's matching-output trial
took 5.111 seconds; variable outputs prevent isolating scheduling from medians.

Both caps retrieved three facts near 1M and finished tools at delay 240 before
retrieval ended. Cap 512:998,866/35 tokens,539.998 seconds HTTP,18.113-second
tools. Cap 1792:998,869/35 tokens,513.759 seconds HTTP,32.035-second tools. Tools
generated 54+6 tokens. Server usage matched, hits/preemptions were zero, and
serving minima were 1,787/1,752 versus 1,099/1,064 MiB. Each has one trial; no
latency guarantee follows.

All profiles followed short/code/short/short. Paired medians were 263.31,269.88
and 260.03 tok/s for batch 2560/cap 2304, batch 2048/cap 1792 and cap 512. The 48,345
input/512 output fixture took 8.325,8.906 and 12.205 seconds respectively. Bytes,
settings, counts and zero hits/preemptions were checked independently. Cap 512
cost 37% more coding time than cap 1792; the selected cap costs 7% versus the
larger batch for more headroom. All trials remain saved.

Cap 1792 passed a 65.268-second warmed restart,19 pre-benchmark checks and 19
post-long LAN checks. It was left running with experiment containers saved.
Original preview, source and MXFP4 launcher remain preserved.

The fixture and hash are included for reproduction. Source audit found no
effective change from interactivity mode at these explicit settings, so no
redundant GPU test ran. Scheduler and DSpark algorithms stayed unchanged.

See [measurements](../../docs/interactive-latency.md),
[launch commands](../../docs/running.md#recommended-coding-profile),
[scorecard](../../docs/performance-scorecard.md) and
[acceptance](../../results/interactive-t1792-final-acceptance.json). Adaptive
verification and draft-forward graphs remain separate work.

Independent closeout reconciled 12 benchmark wrappers, near-1M counters/samples,
APIs, hashes and launch settings. All 69 JSON files parsed; links,17 shell
examples, private-identifier and whitespace checks passed. No runtime change
needed another regression run.
