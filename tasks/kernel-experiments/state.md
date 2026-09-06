# Further kernel experiments on SM120

Status: future task, not started. No kernel changes or new gains are claimed.
The owner requested this follow-up while documenting how the recipe adapts
upstream kernels. See [sources and local changes](../../docs/provenance.md#kernel-sources-and-local-changes).

## Question to test

Can changes to kernel selection, launch configuration or an upstream kernel
implementation improve everyday coding/tools on two RTX PRO 6000 Blackwell
Max-Q GPUs at TP2, while preserving stability, correctness and the long-input
option? Compilation for SM120 alone doesn't answer this.

## Starting evidence and proposed work

1. Preserve the current image and configuration as the control. Record source,
   checkpoint and image revisions, cache conditions, GPU clocks and power limits.
   Use the [primary controls](../../docs/primary-control-screen.md) and
   [scorecard](../../docs/performance-scorecard.md) as comparison references.
2. Use the [component profiles](../../docs/component-profiling.md) to choose a
   bottleneck, then profile the relevant kernels. Separate compute, memory and
   communication costs. Summed kernel durations include overlap and aren't
   request latency; confirm where a change could reduce elapsed time.
3. Test one justified change in a separate image or container. Record whether
   it changes upstream source, compiler settings or runtime selection. Establish
   numerical checks appropriate to that change before benchmarking it.
4. Run repeated, matched measurements without the profiler: first-token latency,
   time per output token, completion time, single-request and aggregate throughput,
   peak VRAM and errors. Keep cold compilation separate from warmed serving.
   Cover short coding/tools, the existing 48K fixture, concurrent requests and
   long prefill. Recheck 801K/near-1M retrieval and recovery for a candidate.
5. Repeat image CPU and API checks, including reasoning, tools, streaming,
   cancellation and DSpark acceptance. Include coding-output correctness checks;
   valid API responses and faster generation alone don't establish accuracy.

## Decision and handoff

Publish positive and negative results with the exact candidate/control settings
and observed variation. Adopt a change only when repeatable gains justify its
memory, latency and maintenance costs. Retain the current recipe when results
are inconclusive or the candidate regresses required behavior.

Before implementation, write `research.md` and a bounded `plan.md` here from the
profiling evidence. Changes that require adaptive verification belong in the
[private adaptive project](../../docs/repository-boundaries.md). This task records
future work; it doesn't schedule experiments or change the serving defaults.
