# Recipe publication state

`main` consolidates the recipe branches. The original branches and recovery tag
are retained; see [branch integration](../main-integration/state.md). This does
not change repository visibility or the pending GPU qualification.

`recipe-1m-k5` preserves tested profiles and findings. Later release fixes add
client/build hardening, onboarding and CPU CI. Historical results and runtime
patches remain unchanged. See [provenance](../../docs/provenance.md).

The private adaptive repo keeps original history, research branches, inventories
and rollback tags. The replacement recipe has clean refs; old research commits
checked against it are unavailable. Rebuild, 13 image CPU methods, GPU serving,
restart/recovery and CPU CI passed for the recorded release. The new
[lifecycle automation](../lifecycle-automation/state.md) still needs its GPU
walkthrough. Keep publication paused while the owner reviews and tests the
recipe. Visibility approval and an anonymous clone check still follow.
See [release state](../release-readiness/state.md) and
[qualification](../release-readiness/verification.md).

See [repository boundaries](../../docs/repository-boundaries.md),
[recipe verification](../recipe-snapshot/verification.md), and
[primary performance findings](../../docs/performance-scorecard.md).
