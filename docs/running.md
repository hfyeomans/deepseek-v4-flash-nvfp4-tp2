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
it for your host. Build and serve require that file and use the same `IMAGE`.
The example contains the selected 1M/96% profile. File assignments win over
ambient shell exports; change `.env` instead of adding inline launch overrides.
Source the loader for manual download, Docker and benchmark commands:

```bash
cp example.env .env  # Once; don't overwrite an existing configuration.
source scripts/config.sh
```

For a separate profile or a config outside the repository:

```bash
export RECIPE_ENV_FILE=/absolute/path/to/profile.env
bash serve.sh
```

Use `unset RECIPE_ENV_FILE` to return to the repo's `.env`. Each selected file
must be a complete copy of the example. `$RECIPE_DIR` in that file resolves to
the recipe checkout, even when you launch from another directory. Keep the file
private; it's sourced as trusted Bash. `serve.sh` rejects command-line overrides
so Docker ports, health probes and the printed model name use the same settings.

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

Check Docker GPU access and Git first. `build.sh` checks out the pinned source
into `work/vllm-source`, recreates the SM120 build, fixes the FlashInfer cache
ABI issue and applies three runtime patches.

```bash
bash build.sh
```

If Ubuntu HTTP downloads stall, set `APT_HTTPS_IPV4=1` and `BUILD_NETWORK=host`
in `.env`, then rerun `bash build.sh`. This passed the stalled stage on the test
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

These are CPU tests. For the first GPU launch, use a new `KERNEL_CACHE` volume
to test compilation without existing FlashInfer cache files. Keep it for warmed
restarts.

## Start the server

```bash
bash serve.sh
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
| Target decode CUDA graphs | FULL_DECODE_ONLY, maximum capture size 16; experimental draft-forward graph disabled |
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
docker stop "$CONTAINER_NAME"
docker start "$CONTAINER_NAME"
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

Apply changed settings by creating a new container. `docker restart` reuses the
old settings; changing `.env` or retagging an image doesn't update that container.
Stop it after requests finish, set a new `CONTAINER_NAME` in `.env`, then run
`bash serve.sh`. Keep the old container for recovery. If you choose to reuse a
name, save its logs and remove the stopped container with
`docker rm <container-name>` first; that removes the container and its logs,
not the named kernel cache or image.

## Recommended coding profile

I'd start with the values in `example.env`. They keep the long-input option
without taking the larger batch's memory cost. After configuring `.env`, launch
with `bash serve.sh`; no profile overrides are needed.

The prefill cap limits how much of a long input gets processed per scheduling
step; it doesn't shorten the 1M window. This profile passed near-1M retrieval,
concurrent tools, a warmed restart and 19 LAN checks. The 48K coding fixture
took a median 8.906 seconds. One tool roundtrip during near-1M prefill took
32.035 seconds, so leave time for very large inputs.

If tools responding during background prefill matter more, change
`LONG_PREFILL_TOKEN_THRESHOLD` to `512` and `CONTAINER_NAME` to
`dsv4-nvfp4-concurrent-tools` in `.env`. Stop the primary container with
`docker stop dsv4-nvfp4`, then run `bash serve.sh`. Leave the other settings fixed.

Cap 512 reduced the tool median to 2.186 seconds during repeated 262K inputs
and took 18.113 seconds in one near-1M trial. The coding fixture slowed to
12.205 seconds. Both profiles keep fixed-K5 DSpark, Markov correction and target
decode graphs. Adaptive verification and optional draft-forward graphs are
disabled. See [measurements and startup limits](interactive-latency.md).

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
set `DSPARK=0` and `CONTAINER_NAME=dsv4-nvfp4-control`. Keep other settings,
including logging, identical. Save results before stopping the primary container:

```bash
docker stop dsv4-nvfp4
RECIPE_ENV_FILE="$PWD/.env.control" bash serve.sh
# Wait for application startup, then run the same benchmark.
python3 benchmark.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" --label graphs-control-primary \
  --output results/raw/benchmark-control-primary.json
# Restore the saved DSpark container after recording the control results.
docker stop dsv4-nvfp4-control
docker start dsv4-nvfp4
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
that ceiling, copy `.env` to `.env.801k`, change `MAX_MODEL_LEN` to `801000` and
`CONTAINER_NAME` to `dsv4-nvfp4-801k`, then launch after stopping the primary:

```bash
docker stop dsv4-nvfp4
RECIPE_ENV_FILE="$PWD/.env.801k" bash serve.sh
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
values and `CONTAINER_NAME=dsv4-nvfp4-1m-candidate`, then stop the active container
and run `RECIPE_ENV_FILE="$PWD/.env.candidate" bash serve.sh`.

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
