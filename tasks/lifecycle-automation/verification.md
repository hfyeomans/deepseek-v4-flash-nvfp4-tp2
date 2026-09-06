# Lifecycle verification

All checks here are local. Stateful fake Docker and Git executables exercise
the real scripts; no image was built and no GPU-host container was changed.
The unchanged model/API/performance checks remain separate qualification steps.

## Behavior and review

The first lifecycle test failed before the new entrypoint existed. Later review
probes exposed these defects, each reproduced before its fix:

| Finding | Correction |
|---|---|
| Unrelated tests and patch prose triggered rebuilds | Hash actual Dockerfile COPY inputs, Dockerfiles and build specification |
| Invalid memory values could interrupt serving | Validate finite memory fraction, positive limits and port ranges in the shared serving path |
| A stopped container restarted during preparation escaped the stop step | Refresh the inspected state before deciding whether to stop |
| Printed stop command lost an alternate config selection | Preserve the selected config in printed status/stop commands |

Tests cover initial build/apply, unchanged running/stopped containers, bind-only
replacement, image changes, build-only and preview actions, failed build/create/
start, daemon errors, unrecognized containers, migration, interrupted candidates,
configuration edits during builds, local lock contention and alternate config
paths. Container and image IDs in the fake Docker remain unique across operations.
Direct-launch and printed-spec arguments match exactly. No benchmark request
format, model-validation assertion, serving default or model patch changed.

The independent lifecycle review reran 24 lifecycle tests and five focused
operator checks after confirming the first three fixes. It found no remaining
blocking issue. The alternate-config regression was added afterward. The final
local suite and documentation checks are recorded in [state](state.md).

## Documentation reconciliation

README, `example.env`, first deployment and running instructions now use
`recipe.sh`. Build-only qualification, controls and alternate profiles use its
actions without changing the measurements they run. Troubleshooting and
development explain migration, ownership and failure recovery. Operator, hosting,
release and publication state link to the new lifecycle qualification; the old
64K/95% default is explicitly historical.

The frozen `recipe-1m-k5` rollback keeps its original commands. Historical build
and measurement commands remain evidence, not current deployment instructions.
Measured tables, runtime patches, benchmark fixtures and saved results retain
their data. Updated prose received Humanizer and then Hank's technical-voice
passes; remaining low-level commands are for diagnosis or recovery.

## GPU walkthrough still required

On the owner's host: preview the first migration; build and run the existing
13 image checks; apply, wait for healthy and run the unchanged API checks.
Then verify stop/apply resumes without a build, a bind-only edit replaces
without a build, and the previous container/logs remain recoverable. No new
throughput, startup-time or model-quality result is claimed for this automation.
