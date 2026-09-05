# Clean recipe snapshot verification

September 5, 2026: all 14 existing local client/profile tests passed: two
benchmark-input, five mixed-probe, one request-observation and six trace-analysis
checks. Shell syntax, JSON decoding, documentation links and manifest input/result
paths passed. These checks do not exercise GPUs.

All 122 serving/build, client, fixture, patch, test and measured result files
match the prior validated recipe bytes. The acceleration scorecard and unrounded
measurements remain unchanged. Documentation now separates recipe provenance
from private research administration. No new performance or model-quality result
was generated during this history operation.

The clean snapshot has independent Git ancestry. Original history and the
original rollback tag remain in the private adaptive archive. New clones should
use this recipe history; do not merge old combined branches back into it.
The clean recipe checkpoint is `recipe-1m-k5`.
