# Deployment configuration and visibility

Authorized scope: the user's concrete configuration, naming, logging, model
identity and stop-command requests. Keep the live GPU host untouched while
the owner tests. Preserve recovery commit `1ed5bfa` and work on a new branch.

## Design decision

`example.env` owns operator defaults. Build and serve require a copied `.env`,
or a file selected with `RECIPE_ENV_FILE`. Clear recipe-owned ambient values
before loading the file. Reject launcher arguments so they can't bypass the
settings used by Docker, health checks or client instructions.
Use `IMAGE` for both build and launch. The selected 1M/96% profile is the example.

The shared loader owns the missing-config safety check and required-setting
validation. Build owns image creation; serve owns the single GPU launch. Docker
owns health state and lifecycle. This small shared safety boundary prevents
building one image and accidentally serving another. No lifecycle wrapper,
request middleware or duplicate defaults are needed. Stop the extraction if
it starts managing model state or interpreting arbitrary dotenv syntax.

Runtime pins and supported architecture constraints stay fixed; adjustable
build, serving and logging settings move to the example. Keep a whitelist of
container environment variables. Normal logging stays at INFO. Prompt DEBUG
is an explicit opt-in with bounded excerpts; outputs are logged at completion,
without per-token deltas. Retain API access
and aggregate engine logs, with bounded Docker log retention.

## Work and verification

1. Add failing process-boundary tests for missing config, custom paths, image
   agreement, defaults, explicit logging/health options and Docker failures.
2. Add the loader, example and logging configuration; update build and serve.
3. Update current deployment instructions and profile switches. Keep historical
   measurements, visuals and frozen rollback syntax. Review with humanizer,
   then Hank's technical voice.
4. Run local checks, validate the health command against a local HTTP stub and
   audit the final diff. Record that a full build/GPU retest is pending.
5. Commit and push the private branch with exact retest instructions.

Rollback: return to `1ed5bfa` for code; the existing GPU container and image
remain available. Do not claim new performance numbers from CPU checks.
