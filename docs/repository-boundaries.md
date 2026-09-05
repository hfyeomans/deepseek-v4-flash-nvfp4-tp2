# Recipe and adaptive development are separate projects

This repository owns the tested fixed-K5 NVFP4 TP2 recipe: build provenance,
runtime patches, launch profiles, API checks, benchmarks, performance scorecard,
component profiles and measured memory/context tradeoffs.

Adaptive research, compatibility engineering and future experiments belong in
the separate private adaptive project. Shared fixed-mode measurements remain
here to explain acceleration benefits and costs. The research project retains
the same observations as controls. A future candidate must be qualified and
measured before its gains or losses become recipe recommendations.

The recipe uses a clean snapshot history. Its original combined ancestry,
research branch, split inventories and original rollback tag are archived in
the private adaptive repository. The new `recipe-1m-k5` tag is a distinct recipe
checkpoint, not a renamed historical experiment. See [provenance](provenance.md).

Both repositories remain private. Clean Git refs and a clean clone do not prove
that GitHub has removed every cached old commit. Publication requires a separate
check of that boundary; no public release or live server change is implied here.

For use now, follow [build and launch](running.md#recommended-coding-profile),
then [API validation](validation.md). For measured outcomes, see the
[everyday coding scorecard](performance-scorecard.md#primary-everyday-codingtools-profile).
