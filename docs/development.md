# Changing and checking the recipe

Keep serving code, small verification clients and measured evidence separate.
The clients use Python's standard library; this repository does not need a
package framework. Adaptive implementation belongs in the private research repo.

## Fast local checks

Install Python 3.10 or newer, Bash, ShellCheck and `patch`. On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install python3 shellcheck patch
bash scripts/check-local.sh
```

This is also the CPU CI entry point. It exercises outgoing benchmark requests,
stream termination and diagnostics, mixed-request overlap, profiler attribution
and patch direction. It makes no requests to a model server and requires no GPU.
It does not replace the [13 image tests or GPU acceptance](running.md).

## Make a bounded change

1. Branch from the current recipe. Record the failure and intended change in
   `tasks/<slug>/`; use a failing regression for behavior changes.
2. Fix the demonstrated cause. Keep request observations in the API client;
   keep feature assertions in their checks. Do not merge different timing
   semantics merely because both clients parse streamed responses.
3. Run the local checks. For image or launcher changes, use a separate image
   and container, run the image tests, and complete GPU acceptance and recovery.
4. Review the diff for correctness, duplicated state/side effects, stale
   instructions, undocumented prerequisites and unnecessary abstractions.
5. Record what passed, what failed and what remains untested. Commit a recovery
   point before another experiment; keep the previous working container.

Never edit old result JSON to make it match changed clients. The
`recipe-1m-k5` tag preserves the original clients referred to by historical input
hashes. New measurements need new filenames, client hashes, image identities,
settings and warmup/cache details. Keep raw host logs and credentials out of Git.

The [release review](../tasks/release-readiness/review.md) records the first
adversarial and duplication review, its fixes and the boundaries of validation.
