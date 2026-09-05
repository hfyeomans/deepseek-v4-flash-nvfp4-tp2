# State

Implemented and locally verified on `recipe/operator-config`. Recovery point:
`1ed5bfa`. The owner's GPU walkthrough is in progress; host checks have been read-only.
Independent fresh-machine qualification remains open.

Build and serve require `.env` (or `RECIPE_ENV_FILE`) and share `IMAGE`. Missing
files explain how to copy the example and set parameters. Missing settings
can't inherit old shell exports. The example uses adjustable 1M/96% defaults,
stable image/container/cache names and a configurable served model alias.
`TENSOR_PARALLEL_SIZE=2` is now explicit in the example and launch output. It
replaces the hardcoded `--tensor-parallel-size 2`, preserving the tested default.
Existing `.env` files need the new line; other TP values haven't been qualified.
The bind default remains `127.0.0.1`. The example and guides now explain that
using a LAN IP or `0.0.0.0` exposes the unauthenticated API to reachable clients;
change it only with an understood and restricted network exposure.

Normal logs stay at INFO. Request IDs/parameters, completed output summaries,
HTTP status and engine stats are visible. Prompt DEBUG is an explicit option.
Docker owns health probes and log rotation; launch output includes client,
status, log, stop and recovery commands. Restarting doesn't apply edited `.env`
settings; create a new container for those changes.

All 44 local tests passed, including 16 operator tests. Both adversarial
findings were reproduced and fixed. See [verification](verification.md),
[design](plan.md) and [source findings](research.md).

## Owner's next test

During the owner's first launch, the new `dsv4-nvfp4-kernels` volume was created
with the container. Inspection showed active CUDA compiler processes while
GPU use was low, VRAM was around 85 GiB per card and health was `starting`.
TP2, 1M context and 96% memory were confirmed in the container arguments.
The walkthrough now sets this expectation before launch and links to compiler
checks and cache-reuse guidance. This observation isn't a completed startup
timing or a new performance result.

The owner reported `No such image` from a manual command after copying `.env`.
Read-only inspection on the GPU host confirmed `dsv4-nvfp4:recipe` exists
(`07e2c6886e38`) and direct inspection succeeds. An unset or stale interactive
`IMAGE` value is consistent with the error; that terminal's value wasn't observed.
The walkthrough now sources config in each image-check block and guards against
an empty image name. No rebuild, retag or container change was needed.

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
