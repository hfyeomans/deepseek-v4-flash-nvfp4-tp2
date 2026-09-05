# Changing and checking the recipe

Keep serving code, verification clients and evidence separate. Standard-library
Python is enough for these clients. Adaptive implementation belongs in the
private research repo.

## Fast local checks

Install Python 3.10 or newer, Bash, ShellCheck and `patch`. On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install python3 shellcheck patch
bash scripts/check-local.sh
```

This is also the CPU CI entrypoint. It checks benchmark requests, stream endings
and diagnostics, mixed-request overlap, profiling and patch direction without
a GPU or model server. Run [image/GPU checks](running.md) separately.

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

Keep old result JSON intact. Historical client hashes refer to `recipe-1m-k5`.
New measurements need new filenames, client/image hashes, settings and
warmup/cache details. Keep raw host logs and credentials out of Git.

The [release review](../tasks/release-readiness/review.md) records adversarial
and duplication findings, fixes and validation limits.
