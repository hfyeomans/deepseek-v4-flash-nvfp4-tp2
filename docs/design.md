# Deployment design

## Objective

I wanted a working recipe for the exact NVIDIA DeepSeek V4 Flash 0731 NVFP4
checkpoint on two RTX PRO 6000 Blackwell Max-Q GPUs at TP=2, with enough detail
to learn from the process. The goal was to attempt 801K and 1M and explain the
memory, correctness and speed limits we found.64K was a step along the way.

## Selected approach

Use a container recipe with one launch configuration, configurable host/cache
paths, pinned dependencies and HTTP feature checks. Record model/runtime
revisions with results. The final build must use public dependencies; an
unidentified local image is useful only for exploration.

I'd keep this upstream if it passes the SM120 and mixed NVFP4/MXFP4 checks.
When a reproduced failure needs a patch, keep it small and attributed. A full
fork adds maintenance; configuration or a released fix may already solve it.

## Deployment flow

1. Inspect idle GPUs, driver, memory, topology, cached weights and image.
2. Establish an unmodified baseline on the exact NVIDIA model.
3. Enable embedded DSpark; check loading and accepted tokens.
4. Fix reproduced failures individually and compare against baseline.
5. Check APIs with DSpark on/off and two concurrent requests.
6. Attempt 801,000- and 1,000,000-token windows. Save retrieval results or failures,
   actual prompt lengths and output headroom. Test the model's 1,048,576 ceiling
   separately if useful. Use DSpark-off and bounded memory/offload experiments
   to investigate limits.
7. Rebuild, restart and repeat acceptance.

## Components

- Runtime: pinned dependencies, build provenance and small patches.
- Launch: TP=2, tested KV, context/slots, DSV4 parsers and DSpark, with configurable
  host-specific values.
- Validation: synthetic facts, schemas, tool roundtrips, streams and speculation.
- Results: sanitized manifests, pass/fail/untested labels and benchmark methods.
- Troubleshooting: reproduced failures and verified fixes.

## Failure handling

Keep the existing launcher until validation passes. Stop only this task's
containers. A healthy endpoint can't replace a failed feature check. Save
failures for diagnosis and keep raw host logs out of Git.

## Publication gate

Rebuild from pinned public source, pass features after restart and document
failed or unsupported capabilities. Review the full repo and sanitized results
before publication.
