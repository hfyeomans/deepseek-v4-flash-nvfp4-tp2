# Recipe and adaptive development are separate projects

This repo owns the working fixed-K5 NVFP4 TP2 recipe: builds, patches, launch
profiles, checks, benchmarks and measured speed/memory/context tradeoffs.

The private adaptive project owns compatibility research and future experiments.
Both repos keep fixed-mode results: they explain acceleration here and serve
as controls there. Test and measure candidates before recommending them.

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
