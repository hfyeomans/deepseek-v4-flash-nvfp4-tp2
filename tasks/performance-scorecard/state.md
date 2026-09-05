# Performance scorecard state

Historical progression, source-image controls, selected coding profile and
matched primary DSpark results are documented. Adaptive ROI is unmeasured.

The primary comparison records 93.66→200.64 tok/s short code, 164.59→226.03
aggregate, and 11.983→8.790 seconds for 48K code. Tools took 18.881→5.212 seconds
with variable outputs/hits. All C2 trials (226.03/204.43/296.16) remain, with
the missing C2 warmup and onset variation documented. See the
[control report](../../docs/primary-control-screen.md).

[Profiling](../../docs/component-profiling.md) is complete; the restored service
passed 19 APIs. The [private project](../../docs/repository-boundaries.md) owns
adaptive implementation and ROI. Shared metrics explain acceleration here.

The [scorecard](../../docs/performance-scorecard.md) reconciles eager, graphs
and DSpark from unrounded data. The eager 32K image digest/load remain unknown;
64K graphs-on stages are matched. The source 1M candidate measured about 2x
short throughput, 1.61x paired aggregate and 1.41x on 48,345-token code, retaining
the slow first pair and 37.9-second tool result. Selected cap 1792 measured
269.88 tok/s aggregate and 8.906 seconds on code versus cap 512's 260.03 and
12.205. Both passed near-1M; the selected profile passed restart/LAN checks.

Arithmetic, fixtures and counts were independently reviewed. The scorecard
keeps all pairs, costs, unrounded links and short/long distinctions. Adaptive
results require a compatible, measured implementation. The recipe is pushed
privately; see [publication status](../publication/state.md).

The everyday section also answers the baseline question: 11.92x short-code
rate and 8.35x aggregate versus eager, with historical differences explicit.
The separate 48K graph-enabled control shows 24.3% less time. No matched eager
48K or baseline tool measurement exists.

See [research](research.md), [plan](plan.md),
[hosting state](../hosting/state.md), and
[repository boundary](../../docs/repository-boundaries.md).
