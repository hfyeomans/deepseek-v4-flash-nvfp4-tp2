# Clean recipe snapshot verification

September 5, 2026: 14 local methods passed (two benchmark, five mixed-probe,
one observation, six trace-analysis), plus shell syntax, JSON, links and
manifest paths. No GPUs were exercised.

All 122 serving/build, client, fixture, patch, test and result files match the
validated bytes. The scorecard and raw measurements stayed intact; docs now
separate recipe provenance from research administration. This history operation
created no performance or quality result.

Use `recipe-1m-k5` for the clean snapshot. It has independent ancestry; original
history and rollback tags remain private. Start with a new clone and don't
merge old combined branches into it.
