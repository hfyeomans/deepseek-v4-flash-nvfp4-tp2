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
checks the real build/serve entrypoints and automated lifecycle against fake
Docker/Git executables, config loading and health probes against a temporary
localhost HTTP server. Lifecycle regressions cover replacement order, failures,
migration, interrupted updates and configuration changes during a build.
No GPU or model server is needed. Run [image/GPU checks](running.md) separately.

## Make a bounded change

1. Branch from `main` and record the problem in your local `tasks/<slug>/`.
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

Task notes and `.gitignore` stay local. Set up local ignore rules for settings,
logs and working files before staging changes. The [deployment results](../results/release-qualification/summary.json)
record the earlier GPU checks; the [automated lifecycle](running.md#stop-resume-and-apply-settings)
still needs its GPU walkthrough.

## Build and lifecycle ownership

`recipe.sh` loads the trusted Bash config once; `scripts/lifecycle.py` coordinates
Docker phases using those captured values. `build.sh --print-spec` owns build
inputs and `serve.sh --print-spec` owns validation and launch arguments. Normal
low-level builds/launches and automated candidate creation use these same owners.

Docker image/container labels store input digests and ownership, not full `.env`
values. `work/lifecycle/` holds the per-checkout lock and temporary config snapshots;
there's no separate current-deployment database. New Dockerfile inputs must be
tracked before apply: the current scanner supports literal single-file `COPY`
instructions and rejects unsupported forms. Add support with a regression when
changing that syntax. Docs and unrelated tests must not invalidate the image.

## Future kernel experiments

Further kernel experiments are planned but haven't started. They cover profiling
and testing further SM120 improvements against the current recipe.
Start with the existing component traces; preserve
the working image and require measured gains, correctness and memory checks
before adopting a change. Adaptive-verification work stays in its own repo.
