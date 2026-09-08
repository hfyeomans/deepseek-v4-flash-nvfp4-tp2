# Build, serve, and reproduce the checks

Use this guide to run the tested profiles and repeat the measurements. If
you're deploying for the first time, start with the
[walkthrough](first-run.md). Run commands from the recipe directory on the
Linux GPU host. The tested pair is RTX PRO 6000 Blackwell Max-Q at TP=2 with
driver 610.57.04. Other architectures and stock vLLM images haven't been
qualified for this SM120 recipe.

The patched preview and public-source rebuild passed their recorded checks.
The rebuild passed 13 CPU methods, 19 LAN API checks and near-1M retrieval.
See [source-image acceptance](source-image-validation.md) and the
[selected profile comparison](interactive-latency.md).

## Configuration

Run commands in Bash. Copy [example.env](../example.env) to `.env`, then edit
it for your host. `recipe.sh` requires that file and uses the same `IMAGE` for
building and serving.
The example contains the selected 1M/96% profile. File assignments win over
ambient shell exports; change `.env` instead of adding inline launch overrides.
Copying the file or running `recipe.sh` doesn't set variables in your terminal.
Source the loader for manual download, Docker and benchmark commands:

```bash
cp example.env .env  # Once; don't overwrite an existing configuration.
source scripts/config.sh
```

For a separate profile or a config outside the repository:

```bash
export RECIPE_ENV_FILE=/absolute/path/to/profile.env
bash recipe.sh
```

Use `unset RECIPE_ENV_FILE` to return to the repo's `.env`. Each selected file
must be a complete copy of the example. `$RECIPE_DIR` in that file resolves to
the recipe checkout, even when you launch from another directory. Keep the file
private; it's sourced as trusted Bash. The script uses a snapshot of its effective
settings for each operation. Edits made during a build apply on the next run.
Use `.env` for parameters and the commands below for lifecycle actions.

| What you want to do | Action |
|---|---|
| Resume a stopped model with the same settings | `bash recipe.sh` |
| Apply serving changes in `.env`, including `BIND_ADDRESS` | `bash recipe.sh`; it replaces the container and reuses the image |
| Build initially or apply changed image inputs | `bash recipe.sh`; it builds before replacing the container |
| Build the image without starting a model | `bash recipe.sh build` |
| Rerun the build and apply its result, retaining Docker's build cache | `bash recipe.sh rebuild` |
| Preview the required actions | `bash recipe.sh plan` |
| Stop and unload the model | `bash recipe.sh stop` |
| Show container and health state | `bash recipe.sh status` |

An unchanged running container is left alone. A replacement can interrupt active
requests, so apply changes when you're ready for that interruption.

## Obtain the pinned checkpoint

Install the Hugging Face `hf` CLI if needed, then use the configured cache:

```bash
source scripts/config.sh
hf download "$MODEL" --revision "$REVISION" --cache-dir "$HF_CACHE/hub"
```

Weight shards total 175,550,788,904 bytes. Allow extra space for source, Docker
layers and caches. `OFFLINE=1` uses the downloaded snapshot when serving. It
includes draft layers; no GGUF conversion or separate draft download is needed.

## Build the runtime

For everyday changes, use `bash recipe.sh`; it decides whether a build is needed.
Use the build-only phase below when you want to run the image tests before launch.

Check Docker GPU access and Git first. `build.sh` checks out the pinned source
into `work/vllm-source`, recreates the SM120 build, fixes the FlashInfer cache
ABI issue and applies three runtime patches.
See [kernel sources and local changes](provenance.md#kernel-sources-and-local-changes)
for what compiles for SM120 and what we changed.

```bash
bash recipe.sh build
```

If Ubuntu HTTP downloads stall, set `APT_HTTPS_IPV4=1` and `BUILD_NETWORK=host`
in `.env`, then rerun `bash recipe.sh build`. This passed the stalled stage on the test
host with the same signed repositories and pinned CUDA base images.

The image is named `dsv4-nvfp4:recipe`. Set `BUILD_JOBS` and `NVCC_THREADS` in
`.env` to change the defaults of 16 and 8. See
[build provenance](../results/original-build-provenance.json) and
[compatibility fixes](troubleshooting.md).

The [build record](../results/source-build-provenance.json) contains image
digests, dependencies and CPU results. GPU acceptance was pending when that
record was saved; [later tests passed](source-image-validation.md). This build
reused base/download layers on the existing host. It doesn't establish a
fresh-machine build or bit-for-bit reproducibility.

Run the 13 CPU regression methods against the pinned checkpoint metadata:

```bash
source scripts/config.sh
CHECK_MODEL_DIR="/root/.cache/huggingface/hub/models--nvidia--DeepSeek-V4-Flash-0731-NVFP4/snapshots/$REVISION"
docker run --rm --entrypoint bash \
  -e HF_HUB_OFFLINE=1 -e CUDA_VISIBLE_DEVICES=-1 \
  -e "DSPARK_TEST_MODEL_CONFIG=$CHECK_MODEL_DIR/config.json" \
  -e "DSPARK_TEST_MODEL_DIR=$CHECK_MODEL_DIR" \
  -v "$HF_CACHE:/root/.cache/huggingface:ro" \
  "$IMAGE" -c 'set -e
    for check_test in /opt/recipe-tests/test_*.py; do
      python3 "$check_test"
    done'
```

These are CPU tests. Use a new `KERNEL_CACHE` volume to test startup without
existing FlashInfer cache files. This adds a [compilation delay](#first-launch-and-kernel-cache);
keep the volume for warmed restarts.

## Start the server

```bash
bash recipe.sh
docker logs --timestamps -f dsv4-nvfp4
```

Wait for application startup to complete, including initial kernel compilation.
The example binds to loopback and starts with:

| Setting | Default |
|---|---|
| Tensor parallelism | `TENSOR_PARALLEL_SIZE=2` |
| Model alias | `dsv4-nvfp4` |
| Maximum model length | 1,000,000 total tokens |
| GPU memory utilization | 0.96 |
| Main expert backend | FlashInfer CUTLASS, NVFP4 |
| DSpark draft | Marlin, original MXFP4, five speculative tokens |
| KV cache | FP8, block size 256, prefix caching enabled |
| Target decode CUDA graphs | Enabled with FULL_DECODE_ONLY, maximum capture size 16 |
| Optional DSpark draft CUDA graph | Disabled pending testing on this hardware; DSpark drafting remains enabled |
| Sequence slots / batched tokens | 2 / 2,048 |
| Tokenizer, reasoning, tool parser | `deepseek_v4` |

Change `MAX_MODEL_LEN`, `GPU_MEMORY_UTILIZATION`, `MAX_NUM_SEQS`,
`MAX_BATCHED_TOKENS` and `LONG_PREFILL_TOKEN_THRESHOLD` in `.env` to compare
profiles. `DSPARK=0` disables speculation; `EAGER=1` disables CUDA graphs.
`TENSOR_PARALLEL_SIZE=2` splits model computation across the two GPUs; all
reported GPU results used TP2. Other values need separate hardware and runtime
validation. If you copied `.env` before this parameter was added, add that line
to your existing file. FP8 KV, parser/backend choices, source and CUDA pins
remain fixed in code. K5 is a checkpoint constraint.

Keep `BIND_ADDRESS=127.0.0.1` for access from the GPU host only. Change it only
if you understand the exposure and have restricted network access. The host's
LAN IPv4 address binds the published port to that address; `0.0.0.0` binds it
to every IPv4 interface. This recipe doesn't configure API authentication:
any client that can reach the published port can submit requests. Reachability
depends on routing and firewall rules. Use Docker Engine 28 or newer: older
versions can expose localhost-published ports to the same network segment.
See [Docker's port-publishing guidance](https://docs.docker.com/engine/network/port-publishing/).

For LAN clients, use `http://<gpu-host>:8000/v1`, replacing the host and port
with your settings. `0.0.0.0` is a bind address, not a client destination.
With loopback binding, use `http://127.0.0.1:8000/v1` on the GPU host. The model
name is `SERVED_MODEL_NAME` (default `dsv4-nvfp4`); `/v1/models` confirms it.

## Logs and health

Normal runs use INFO: request IDs and parameters, bounded completed responses,
HTTP paths/status codes and vLLM's periodic engine statistics. Streaming deltas
are disabled to avoid per-token noise. The pinned logger may
report a streaming token-count summary instead of the full response text.
`LOG_OUTPUTS=0` removes response text; `LOG_REQUESTS=0` disables request/output
logging while keeping HTTP access and engine statistics.

Docker calls `/health` every 30 seconds. Those calls appear in access logs once
the API is listening. During early compilation, the socket isn't available yet;
Docker stores connection failures in its health history. A 15-minute startup
grace period accommodates compilation. A successful probe can mark it healthy
sooner; an unhealthy status doesn't automatically restart it.

```bash
source scripts/config.sh
docker logs --timestamps -f "$CONTAINER_NAME"
# Run status/history commands in another terminal, or exit the log viewer first.
docker inspect --format '{{.State.Status}} / {{.State.Health.Status}}' "$CONTAINER_NAME"
docker inspect --format '{{json .State.Health}}' "$CONTAINER_NAME"
```

An HTTP 200 on a streaming request means headers were sent, not that generation
finished. Check the final response log and your client's completed stream.
I use health checks to confirm availability. Coding accuracy and DSpark
acceptance need their own tests. Container logs rotate at 10 MB per file, with three files retained.
Save a separate log before a long experiment if you need its full history.

Prompt text is DEBUG-only in this pinned vLLM build. To inspect it, create
`work/` if needed and copy `config/logging.json` to `work/logging-prompts.json`.
Change only the `vllm.entrypoints.serve.utils.request_logger` level to `DEBUG`, and point
`LOGGING_CONFIG` in your `.env` to that file's absolute path. Keep `LOG_REQUESTS=1`.
`MAX_LOG_LEN=256` bounds text and token-ID excerpts. This is an explicit
troubleshooting mode; the engine stays at INFO. Return `LOGGING_CONFIG` to its
example value for normal runs. Logs can contain supplied code and model output.

### First launch and kernel cache

A fresh cache adds CPU compilation work after model loading. The GPUs can be
mostly idle while `nvcc`, `cicc` or `cc1plus` use CPU cores. VRAM may plateau
before KV-cache and graph allocation; it isn't the final serving footprint yet.
The engine can print `No available shared memory broadcast block found in 60 seconds`
while waiting for its workers. That message alone doesn't distinguish compilation
from a stalled worker.

Check activity without interrupting startup:

```bash
source scripts/config.sh
docker top "$CONTAINER_NAME" -eo pid,ppid,comm,pcpu,etime
docker logs --timestamps --tail 60 "$CONTAINER_NAME"
docker inspect --format '{{.State.Status}} / {{.State.Health.Status}}' "$CONTAINER_NAME"
```

Busy compiler processes, changing compiler PIDs or new kernel messages are
evidence of work. If those stop and startup stays unchanged, inspect errors and
resource pressure; don't assume every wait message is harmless. Docker can remain
`starting` during its configured grace period. Wait for application startup and
`healthy` before using the endpoint.

Keep the named `KERNEL_CACHE` volume to reuse compatible FlashInfer kernels.
Changing to a new volume name or deleting it loses that reuse. Model loading
and other initialization still run; new images or request shapes can require
more compilation. See the [first-launch and restart record](source-image-validation.md)
for measured timings and their limits.

## Stop, resume and apply settings

Use the same script after editing `.env`. Keep `CONTAINER_NAME` stable to update
that deployment. Changing the name selects a different container; the script
doesn't stop other deployments or unrelated GPU services.

```bash
bash recipe.sh plan    # Optional preview; no Docker mutations.
bash recipe.sh         # Apply the selected configuration.
bash recipe.sh status
```

The script reports these phases:

1. Load and validate `.env`, then inspect the image and container.
2. Reuse or build the image while the current container stays in place.
3. Resume/keep an unchanged container, or prepare a stopped replacement.
4. Stop the previous recipe container and retain it under a unique
   `<name>-previous-...` name with its logs and image reference.
5. Promote and start the replacement. Wait for healthy before using the endpoint.

Serving changes, including bind address, context, memory and batch settings,
don't rebuild the image. Build decisions use the effective build inputs,
Dockerfiles and files copied into the image. Comments in `.env`, unrelated tests
and documentation don't trigger a rebuild. Logging-file content is a serving
change. An image from before this automation has no build record, so the first
automated run performs a cached build and preserves the old container on migration.
Layer reuse depends on Docker's available cache.

A failed build or failed candidate creation leaves the current container in place.
Docker creation catches mount/configuration errors; GPU memory fit and successful
model initialization still require startup. Failed promotion/start prints recovery
commands. An interrupted prepared candidate can be reused on the next apply.
Only one operation can run at a time from this checkout. Use one checkout to
manage a deployment, and avoid concurrent manual Docker changes.

To stop and later resume:

```bash
bash recipe.sh stop
bash recipe.sh
```

Stop frees GPU memory once the server processes exit. Containers, images, logs,
model downloads and named kernel caches remain. Previous containers accumulate
until you choose to remove them. List them with `docker ps -a`; save any logs you
need with `docker logs --timestamps <name> > saved.log 2>&1` before removal.

For manual recovery, stop the failed/new container, rename it to a spare name,
rename the selected previous container to `CONTAINER_NAME`, and start that saved
container. Use the exact IDs printed by the script. Direct `docker start` uses
saved settings; `recipe.sh` applies the current `.env`, so fix/revert that file
before the next automated apply.

Low-level `build.sh` and `serve.sh` remain available for diagnosis. The former
builds only; the latter creates a container and will report a name conflict.
Their `--print-spec` option exposes validated inputs without Docker effects.
Use `recipe.sh` for normal operation. The coordinator doesn't run or replace the
image, API, accuracy or performance checks below.

## Recommended coding profile

I'd start with the values in `example.env`. They keep the long-input option
without taking the larger batch's memory cost. After configuring `.env`, launch
with `bash recipe.sh`; no profile overrides are needed.

The prefill cap limits how much of a long input gets processed per scheduling
step; it doesn't shorten the 1M window. This profile passed near-1M retrieval,
concurrent tools, a warmed restart and 19 LAN checks. The 48K coding fixture
took a median 8.906 seconds. One tool roundtrip during near-1M prefill took
32.035 seconds, so leave time for very large inputs.

If tools responding during background prefill matter more, change
`LONG_PREFILL_TOKEN_THRESHOLD` to `512` in `.env`, then run `bash recipe.sh`.
Keep `CONTAINER_NAME` and all other settings fixed.

Cap 512 reduced the tool median to 2.186 seconds during repeated 262K inputs
and took 18.113 seconds in one near-1M trial. The coding fixture slowed to
12.205 seconds. Both profiles keep fixed-K5 DSpark, Markov correction and target
decode graphs. The optional draft CUDA graph remains disabled pending testing
on this hardware. Adaptive verification is not implemented in this pinned
proposer. See [measurements and startup limits](interactive-latency.md).

## Run the API checks

The clients use Python 3 and its standard library. They send synthetic requests
and exit nonzero if a check fails.

```bash
source scripts/config.sh
mkdir -p results/raw
python3 verify.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --long-context-tokens 61440 \
  --output results/raw/features-61k-probe.json
python3 benchmark.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --label dspark-graphs-primary \
  --output results/raw/benchmark-primary.json
```

`verify.py` adds `/v1`, so pass the server origin to `--base-url`, for example
`http://127.0.0.1:8000`. It checks chat, reasoning, tools, structured output,
streaming, concurrency, prefix reuse and cancellation recovery, with optional
long retrieval. See [pass conditions](validation.md).

For a matched DSpark comparison, copy `.env` to `.env.control`. In that copy,
set `DSPARK=0`. Keep all other settings, including container name and logging,
identical. Save results before switching the primary container:

```bash
RECIPE_ENV_FILE="$PWD/.env.control" bash recipe.sh
# Wait for application startup, then run the same benchmark.
python3 benchmark.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --label graphs-control-primary \
  --output results/raw/benchmark-control-primary.json
# Reapply the primary configuration after recording the control results.
RECIPE_ENV_FILE="$PWD/.env" bash recipe.sh
```

Keep other workloads idle. The benchmark warms each exact prompt, generates
256 tokens per request and records two repeats plus one concurrent pair. Its
inputs remain short regardless of the configured window.

The source-image comparison used three measured repeats per workload and three
separate short runs, with the frozen coding run between the first and second.
The exact project-generated coding fixture is included in the repository:

```bash
python3 benchmark.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --label your-profile-short --tokens 256 --repeats 3 \
  --output results/raw/your-profile-short.json
python3 benchmark.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --label your-profile-code --tokens 512 --repeats 3 \
  --code-prompt-file benchmarks/prompts/code-48k.txt --cache-mode uncached \
  --output results/raw/your-profile-code.json
```

Use distinct filenames for later runs. The
[fixture description](../benchmarks/prompts/README.md) records its exact hash.
The override replaces the code workload; the concurrent pair is short prose
plus long code. Uncached mode assigns each request a fresh salt; verify server
cache-hit counters too.

## Attempt large context

The patched preview passed one 799,847-token retrieval at 801K. To repeat at
that ceiling, copy `.env` to `.env.801k` and change `MAX_MODEL_LEN` to `801000`.
Keep the container name, then apply:

```bash
RECIPE_ENV_FILE="$PWD/.env.801k" bash recipe.sh
```

After startup completes:

```bash
python3 verify.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --only identity,long_context,chat \
  --long-context-tokens 800000 --timeout 1800 \
  --output results/raw/features-801k.json
```

The 1M experiment uses `MAX_MODEL_LEN=1000000`,
`--long-context-tokens 999000` and `GPU_MEMORY_UTILIZATION=0.96`. The patched
preview passed 998,847-token retrieval and 19 follow-up API checks; 95% failed
startup admission. The source rebuild passed at 96.5% with the larger batch
below and at 96% with both recommended caps. Probes reserve output space within
the window and report actual token counts. These single requests don't test
two full windows or broad retrieval accuracy.

The initial source-built candidate used memory `0.965`, batch `2560` and
prefill cap `2304`. To reproduce it, copy `.env` to `.env.candidate`, set those
values, keep the container name, and run
`RECIPE_ENV_FILE="$PWD/.env.candidate" bash recipe.sh`.

This earlier candidate passed retrieval and short API checks. A concurrent
tool roundtrip took 37.9 seconds, and sampled serving free memory fell to
507/472 MiB. It's not the selected default. See the
[source-image report](source-image-validation.md).

Save settings, logs, actual tokens, outputs and timings for every attempt,
including failures. Separate first-use compilation and competing builds from
warmed measurements. Read the [memory guide](context-memory.md) before treating
startup's calculated cache-token count as a limit.

## Check responsiveness during a long input

Run on the otherwise idle recipe server:

```bash
python3 mixed_probe.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --label your-profile --prompt-tokens 999000 \
  --delay 30 --short-timeout 180 \
  --output results/raw/mixed-profile.json
```

To measure a checked automatic tool round trip instead of the tiny reply, add
`--short-check tools_auto`. Both tool calls must finish while the long completion
is still active. The two final near-1M cap comparisons used `--delay 240` with
`--prompt-tokens 999000 --short-check tools_auto`. For a shorter repeated
configuration comparison:

```bash
python3 mixed_probe.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --label your-profile-tools --prompt-tokens 262000 \
  --delay 3 --short-check tools_auto \
  --output results/raw/mixed-tools.json
```

Warm this protocol and retain the warmup result before measured repeats. Each
long prompt has a fresh prefix; the fixed tool prompt can reuse cache blocks,
even between its two calls. Record hit deltas, actual tokens, both tool-call
times, long duration and sampled resources.

The first example submits a short exact-answer request 30 seconds after the
long completion call starts. Every long prompt has a unique prefix. Both answers
must be correct, and the short response must finish at least one second before
the long call returns. If the long request finishes before the probe, the result
is inconclusive. Output retains failures, call boundaries, prefixes and raw
requests. Use server metrics to confirm admission and prefill activity; client
overlap alone can't show them.

An uncapped 97% profile timed out a short request after 180 seconds.
`MAX_BATCHED_TOKENS=2560` with `--long-prefill-token-threshold 2304` then passed
mixed near-1M retrieval and 19 API checks. See the
[later source-image profile comparison](interactive-latency.md) and
[scheduler explanation](performance.md#observed-mixed-request-scheduling-limit).

For a controlled context/batch comparison with vLLM's benchmark and saved
latencies, follow [the measurement guide](context-batch.md).

## Preserved baseline and rollback

Tag `recipe-1m-k5` preserves the tested source/build/launch files. Use a separate
checkout for recovery. The original `baseline-1m-k5` Git tag remains in the
private adaptive archive; see [historical provenance](provenance.md). On the
original host, image tag `dsv4-nvfp4:baseline-1m-k5` also preserves the tested
image. Its [identity is recorded](provenance.md); it hasn't been uploaded to
a registry.

Let experiment requests finish, use `docker stop <experiment-container>`, then
restore the saved container with `docker start <saved-container>`. On the
original host, you can also launch the local baseline image under a new name.
Retain previous logs.

On another host, build an explicitly named recovery image from a separate
checkout. The following commands intentionally use the frozen tag's older
`FINAL_IMAGE` and inline overrides; that checkout predates `.env` support:

```bash
git worktree add --detach ../dsv4-recipe-rollback recipe-1m-k5
cd ../dsv4-recipe-rollback
FINAL_IMAGE=dsv4-nvfp4:rollback bash build.sh
# Stop the experimental container after its requests finish, then launch:
IMAGE=dsv4-nvfp4:rollback CONTAINER_NAME=dsv4-recovery \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.96 \
MAX_BATCHED_TOKENS=2048 MAX_NUM_SEQS=2 \
  bash serve.sh --long-prefill-token-threshold 1792
```

Keep the checkpoint in `HF_CACHE`. After startup, check `/health` and
`/v1/models`, then run `verify.py` with a new output filename. That's how you
confirm the restored service works.
