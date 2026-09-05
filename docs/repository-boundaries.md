# Recipe and adaptive development are separate projects

Use this repo to run fixed-K5 NVFP4 at TP2 and understand its measured tradeoffs.
It includes builds, patches, profiles, checks and benchmarks.

Keep adaptive compatibility research and future experiments in the private
project. Both repos retain fixed-mode numbers: they explain this recipe's
gains and give adaptive work a baseline. Measure a candidate before
recommending it.

The clean `recipe-1m-k5` snapshot is a new checkpoint. Original combined
history, research branches, split inventories and the original rollback tag
remain in the private archive. See [provenance](provenance.md).

After research was saved locally, GitHub's recipe repo was replaced under the
same name. Probed old research commits were unavailable in the replacement.
See [visibility status](../tasks/publication/state.md) and
[live qualification](../tasks/release-readiness/verification.md).

Start with [launching](running.md#recommended-coding-profile) and
[API checks](validation.md). The [everyday scorecard](performance-scorecard.md#primary-everyday-codingtools-profile)
shows measured outcomes.
