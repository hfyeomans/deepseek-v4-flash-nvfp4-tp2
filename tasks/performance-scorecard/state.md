# Performance scorecard state

Status: **historical progression, matched source-image comparison and selected
coding-profile stage and exact-primary control screen documented.** Adaptive
runtime performance remains unmeasured.

The latest exact-primary screen is recorded in the dedicated everyday-coding
section: short code 93.66→200.64 tok/s, short C2 aggregate 164.59→226.03 tok/s,
48K code 11.983→8.790 seconds. Mixed tool 18.881→5.212 seconds is an observed
outcome with varying outputs/cache hits. All three C2 on trials are retained
(226.03/204.43/296.16), together with the missing C2 warmup and onset variability.
These add a matched-primary comparison rather than replacing the historical
selected-profile observations below. See the [control report](../../docs/primary-control-screen.md).

Diagnostic [component profiling](../../docs/component-profiling.md) is complete.
The original service was restored and passed 19 API checks. Adaptive integration,
kernel research and quality/ROI work now belong in the
[separate private project](../../docs/repository-boundaries.md). Shared metrics
remain here to explain the measured acceleration benefit and its costs.

The [historical scorecard](../../docs/performance-scorecard.md) now reconciles
the eager, graph-enabled control and DSpark observations. Ratios were independently
recomputed from unrounded results. Initial eager used 32K and disabled compilation
as well as graphs; its exact derivative digest and competing-load state remain
unknown. Later stages use 64K and have a matched graph-enabled control.
The source-built 1M candidate now has a matched DSpark comparison: about 2x short
single-request throughput, 1.61x median paired aggregate across all three trials,
and 1.41x on the 48,345-token synthetic code input. Evidence includes the slower
first paired observation and the 37.9-second concurrent tool limitation.
The bounded profile comparison is complete. The selected 1M/96%/batch2048/
cap1792 coding profile measured 269.88 tok/s median short paired aggregate and
8.906 seconds on the 48K coding fixture. Cap512 measured 260.03 tok/s and
12.205 seconds, with better concurrent tool latency. Both passed near-1M
retrieval; the selected profile passed restart and final LAN API checks.

The scorecard includes absolute/relative gains, all three paired trials per
source profile, memory/latency costs and links to unrounded evidence. Arithmetic
and fixture/count consistency were independently reviewed. No throughput claim
equates short prompts with a near-1M input. Add adaptive results only if a
compatible implementation is established and measured; keep its ROI unmeasured
until then. The repository has now been pushed privately; see
[publication state](../publication/state.md). No public release has been made.

The user's direct baseline question is now documented: the selected profile
measured 11.92x short coding rate and 8.35x paired aggregate versus the initial
eager setup. These historical ratios were recalculated from unrounded records.
The separate 48K graph-enabled/no-DSpark control comparison shows 24.3% less
elapsed time for the selected profile, with configuration differences explicit.
No matched eager 48K or baseline tool-roundtrip result is claimed.
These settings, gains and tool-latency limits now have a dedicated
"Primary everyday coding/tools profile" section in the scorecard.

See [research](research.md), [plan](plan.md),
[hosting state](../hosting/state.md), and
[repository boundary](../../docs/repository-boundaries.md).
