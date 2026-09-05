# Recipe publication state

The `recipe-1m-k5` clean checkpoint contains usable fixed-K5 profiles and the
recorded acceleration findings. The release-readiness changes add client/build
hardening, a first-run guide and CPU CI. Historical measurement files and runtime
patch contents are unchanged. See [snapshot provenance](../../docs/provenance.md).

Original combined history, the prior research branch, split inventories and the
original rollback tag are maintained in the separate private adaptive repository.
History-separation administration is recorded there. The recipe GitHub repository
was replaced under the same name with clean refs; old research commit probes
return unavailable. A separate source rebuild and 13 image CPU checks passed.
GPU serving/restart/restoration qualification and CPU CI passed. The recipe
remains private until the pending visibility change and anonymous clone check. See
[current release state](../release-readiness/state.md) and
[qualification evidence](../release-readiness/verification.md).

See [repository boundaries](../../docs/repository-boundaries.md),
[recipe verification](../recipe-snapshot/verification.md), and
[primary performance findings](../../docs/performance-scorecard.md).
