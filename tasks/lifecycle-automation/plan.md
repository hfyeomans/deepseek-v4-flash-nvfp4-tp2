# Automated recipe lifecycle implementation plan

Goal: `bash recipe.sh` applies the selected `.env` automatically. The owner
approved automatic apply; a separate `plan` action previews it without Docker
mutations. No image build or container change will run on the owner's GPU host
during development.

## Ownership and interface

`recipe.sh` loads the existing Bash config and exports only recipe settings to
`scripts/lifecycle.py`. The coordinator freezes those values for the child
scripts. `build.sh --print-spec` and `serve.sh --print-spec` expose their existing
validated inputs without Docker effects. Their normal commands stay available;
the coordinator uses the same serving spec to create candidates.

Actions: default/`apply`, `plan`, `build` (image only), `rebuild` (rerun the cached
build and apply), `stop`, and `status`. Invalid action/config fails before effects.
Stop/status only need the selected container name and Docker access.

Build identity covers effective build inputs, build scripts/Dockerfiles,
`.dockerignore`, patches and tests. Documentation and serving settings don't
invalidate it. Successful coordinated builds label the image with that digest.
Serving identity covers the rendered Docker/model arguments, exact image ID,
and logging configuration contents. Containers carry that digest and a recipe
ownership label; no full `.env` or secrets are stored in Docker labels.

## Apply sequence and recovery

1. Validate and freeze config; inspect Docker. List failures stop the operation.
2. Build if the image is absent, provenance differs or rebuild was requested.
   Preserve the current service on build failure. Use Docker's layer cache.
3. Compare desired serving identity with the current container. Leave an unchanged
   running container alone; start an unchanged stopped/created container.
4. For changes, create a stopped candidate using the exact inspected image ID.
   Catch Docker configuration/mount failures before stopping the old container.
5. Stop and rename the old recipe container to a unique backup name, then promote
   and start the candidate. Preserve old logs, image references and cache volumes.
   Use IDs for mutations, and print recovery commands if promotion/start fails.
6. Report starting/health state and client/log commands. Startup success means
   Docker started the process, not that model/API validation passed.

Recognize interrupted candidates on rerun, and refuse unrelated name collisions.
An existing pre-automation recipe container is identified by its recipe-specific
coverage environment flag and DeepSeek parser arguments; it is preserved during
migration. A filesystem lock serializes actions in this checkout. Docker remains
the source of truth; no separate current-deployment state file is maintained.

## Work and checks

- [ ] Add failing process-boundary tests for missing config, spec rendering,
  new build, unchanged running/stopped, bind-only changes, rebuild, failed build,
  failed candidate creation/start, daemon errors, migration and interrupted work.
- [ ] Add spec output to existing owners; implement the coordinator and labels.
  Keep existing launch arguments and image stages equivalent.
- [ ] Run existing local checks plus lifecycle regressions; review duplicate
  ownership, failure recovery and preservation of logs/caches.
- [ ] Update README, example.env and current usage docs to lead with `recipe.sh`.
  Keep low-level commands documented for diagnosis and frozen-tag recovery.
  Scan every Markdown document for stale current instructions; retain historical
  commands/results with their measurement context.
- [ ] Review prose with Humanizer, then Hank's technical voice. Validate links
  and unchanged historical evidence; record GPU qualification as pending.
- [ ] Commit and push the private recipe branch with a recovery checkpoint.

Rollback for this implementation: `a2a699b`. No serving defaults, model patches,
benchmark protocol or model-validation assertions are being changed.
