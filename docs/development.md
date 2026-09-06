# Changing and checking the recipe

Keep this repo easy to build, inspect and rerun. Small standard-library Python
clients are enough; serving code and measured evidence have separate jobs.
Adaptive implementation stays in the private research repo.

## Fast local checks

Install Python 3.10 or newer, Bash, ShellCheck and `patch`. On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install python3 shellcheck patch
bash scripts/check-local.sh
```

This is also the CPU CI entrypoint. It checks benchmark requests, stream endings
and diagnostics, mixed-request overlap, profiling and patch direction. It also
checks the real build/serve entrypoints against fake Docker/Git executables,
config loading and health probes against a temporary localhost HTTP server.
No GPU or model server is needed. Run [image/GPU checks](running.md) separately.

## Make a bounded change

1. Branch from the current recipe and record the problem in `tasks/<slug>/`.
   Add a failing regression for behavior changes.
2. Fix the cause. Keep request records in the API client and feature assertions
   in their checks. Clients with different timing definitions need separate logic.
3. Run local checks. Image/launcher changes also need a separate image/container,
   image tests, GPU acceptance and recovery.
4. Review correctness, duplicate state or side effects, stale instructions,
   missing prerequisites and unnecessary abstractions.
5. Save results and untested limits. Commit before the next experiment and keep
   the working container.

Don't rewrite an old result to match a new client. Historical hashes refer to
`recipe-1m-k5`. Give new measurements new filenames and record client/image
hashes, settings and warmup/cache details. Keep host logs and credentials private.

The [release review](../tasks/release-readiness/review.md) records adversarial
and duplication findings, fixes and validation limits. The
[operator update](../tasks/operator-experience/state.md) tracks config/logging
changes and the owner's pending GPU retest.

## Future kernel experiments

The [kernel experiment task](../tasks/kernel-experiments/state.md) is recorded
but hasn't started. It covers profiling and testing further SM120 improvements
against the current recipe. Start with the existing component traces; preserve
the working image and require measured gains, correctness and memory checks
before adopting a change. Adaptive-verification work stays in its own repo.
