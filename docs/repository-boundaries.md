# Recipe and adaptive development are separate projects

Use this repo to run fixed-K5 NVFP4 at TP2 and understand its measured tradeoffs.
It includes builds, patches, profiles, checks and benchmarks.

Keep adaptive compatibility research and adaptive experiments in the private
project. Both repos retain fixed-mode numbers: they explain this recipe's
gains and give adaptive work a baseline. Measure a candidate before
recommending it.

The clean `recipe-1m-k5` snapshot is a new checkpoint. Original combined
history, research branches, split inventories and the original rollback tag
remain in the private archive. See [provenance](provenance.md).

After research was saved locally, GitHub's recipe repo was replaced under the
same name. Probed old research commits were unavailable in the replacement.
See the [deployment qualification results](../results/release-qualification/summary.json).

Working notes in `tasks/` and the local `.gitignore` aren't published with the
current recipe. Earlier commits and retained branches still contain their
historical copies.

Start with [launching](running.md#recommended-coding-profile) and
[API checks](validation.md). The [everyday scorecard](performance-scorecard.md#primary-everyday-codingtools-profile)
shows measured outcomes.
