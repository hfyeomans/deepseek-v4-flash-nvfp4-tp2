# Deployment design

## Objective

Serve the exact NVIDIA DeepSeek V4 Flash 0731 NVFP4 checkpoint using two RTX PRO
6000 Blackwell Max-Q GPUs with TP=2. Publish a recipe another owner can reproduce,
including the constraints found during testing. This is also a learning effort:
explicitly attempt 801K and 1M context windows, investigate what enables or blocks
them, and report the measured memory, correctness, and speed tradeoffs. The 64K
result is an intermediate milestone, not the context target.

## Selected approach

Use a standalone container recipe with one authoritative launch configuration,
environment-controlled host/cache settings, pinned runtime dependencies, and an
HTTP feature-validation command. Capture model/runtime revisions and test results
with each run. The final recipe must be runnable from public dependencies; an
unidentified local image is sufficient only for exploratory testing.

An upstream-only recipe would minimize maintenance, but must first pass the exact
SM120 and mixed NVFP4/MXFP4 draft checks. A full runtime fork would increase
maintenance substantially. Use a small attributed compatibility patch only when
a concrete failure establishes that a configuration or released fix is
insufficient.

## Deployment flow

1. Inspect idle GPUs, driver, memory, topology, cached weights, and installed image.
2. Establish an unmodified baseline on the exact NVIDIA model.
3. Enable the checkpoint's built-in DSpark and verify draft loading and acceptance.
4. Resolve evidenced failures one at a time; compare against the baseline.
5. Validate model features with and without DSpark, then at concurrency two.
6. Attempt 801,000- and 1,000,000-token context windows with DSpark. Record
   successful retrieval or exact startup/runtime failures. Distinguish configured
   window size from measured prompt length and reserve output tokens. The model
   ceiling is 1,048,576; explore it if useful. Use DSpark-off controls and bounded
   memory/offload experiments to explain limits and tradeoffs.
7. Rebuild/relaunch from the recipe and repeat the acceptance suite.

## Components

- Runtime definition: dependency pins, build provenance, and narrowly scoped patches.
- Launch configuration: TP=2, tested cache format, context/concurrency settings,
  DSV4 parsers, and DSpark settings; configurable host-specific values.
- Validation: deterministic synthetic facts, schema checks, tool round trips,
  streaming assembly, and measured speculation metrics.
- Results: sanitized version/hardware manifest and explicit pass/fail/untested
  statuses, with benchmark workload and timing methodology.
- Troubleshooting: only reproduced failures, causes, and verified remedies.

## Failure handling

Keep the existing host launcher intact until the new deployment passes. Stop only
containers created by this task. A failed DSpark or feature probe leaves that
capability unverified; it cannot be replaced by a successful health check.
Preserve failing outputs for diagnosis and keep private raw logs out of Git.

## Publication gate

The launch must be reproducible from recorded public source and dependency pins.
The final configuration must pass the required feature suite after restart.
Report unsupported or failed capabilities plainly. Review the complete repository
and sanitized results before making it public.

