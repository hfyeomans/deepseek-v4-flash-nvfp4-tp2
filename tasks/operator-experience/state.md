# State

Implemented and locally verified on `recipe/operator-config`. Recovery point:
`1ed5bfa`. The GPU deployment is untouched; the owner will retest this launcher.
Independent fresh-machine qualification remains open.

Build and serve require `.env` (or `RECIPE_ENV_FILE`) and share `IMAGE`. Missing
files explain how to copy the example and set parameters. Missing settings
can't inherit old shell exports. The example uses adjustable 1M/96% defaults,
stable image/container/cache names and a configurable served model alias.

Normal logs stay at INFO. Request IDs/parameters, completed output summaries,
HTTP status and engine stats are visible. Prompt DEBUG is an explicit option.
Docker owns health probes and log rotation; launch output includes client,
status, log, stop and recovery commands. Restarting doesn't apply edited `.env`
settings; create a new container for those changes.

All 42 local tests passed, including 14 new operator tests. Both adversarial
findings were reproduced and fixed. See [verification](verification.md),
[design](plan.md) and [source findings](research.md).

## Owner's next test

Follow [the updated walkthrough](../../docs/first-run.md). Reuse/retag the
existing pinned patched image if its build succeeded; no Dockerfile or runtime
patch changed here. Check startup to healthy, normal INFO request/completion
logs, the served alias, all 19 API checks and a warmed restart. Save new logs
and results. Logging overhead and GPU behavior haven't been remeasured.

## Packaging follow-up

The setuptools warning is documented, not suppressed or fixed. Before changing
the pinned build toolchain, identify the package from the full step heading,
migrate direct wheel commands to a build frontend while preserving CUDA flags,
prebuilt artifacts and the ABI tag, then rebuild and run image/GPU acceptance.
The warning excerpt alone doesn't prove which package emitted it.
