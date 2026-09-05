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

## Obtain the pinned checkpoint

Install the Hugging Face `hf` CLI if needed, then download the pinned snapshot:

```bash
export MODEL=nvidia/DeepSeek-V4-Flash-0731-NVFP4
export REVISION=f1caa71142bd0be02f728c79f75042ac1e461579
hf download "$MODEL" --revision "$REVISION"
```

Weight shards total 175,550,788,904 bytes. Allow extra space for source, Docker
layers and build/kernel caches. `serve.sh` uses `$HOME/.cache/huggingface`
offline by default; set `HF_CACHE` for another location. This snapshot includes
the draft layers, so no GGUF conversion or separate draft download is needed.

## Build the runtime

Check Docker GPU access and Git first. `build.sh` checks out the pinned source
into `work/vllm-source`, recreates the SM120 build, fixes the FlashInfer cache
ABI issue and applies three runtime patches.

```bash
bash build.sh
```

Ubuntu HTTP downloads stalled on the test host. This workaround passed that
stage with the same signed repositories and pinned CUDA base images:

```bash
APT_HTTPS_IPV4=1 BUILD_NETWORK=host bash build.sh
```

The image is named `dsv4-nvfp4:recipe`. Override the defaults of 16 build jobs
and 8 NVCC threads with `BUILD_JOBS` and `NVCC_THREADS`. See
[build provenance](../results/original-build-provenance.json) and
[compatibility fixes](troubleshooting.md).

The [build record](../results/source-build-provenance.json) contains image
digests, dependencies and CPU results. GPU acceptance was pending when that
record was saved; [later tests passed](source-image-validation.md). This build
reused base/download layers on the existing host. It doesn't establish a
fresh-machine build or bit-for-bit reproducibility.

Run the 13 CPU regression methods against the pinned checkpoint metadata:

```bash
export CHECK_MODEL_DIR="/root/.cache/huggingface/hub/models--nvidia--DeepSeek-V4-Flash-0731-NVFP4/snapshots/$REVISION"
docker run --rm --entrypoint bash \
  -e HF_HUB_OFFLINE=1 -e CUDA_VISIBLE_DEVICES=-1 \
  -e "DSPARK_TEST_MODEL_CONFIG=$CHECK_MODEL_DIR/config.json" \
  -e "DSPARK_TEST_MODEL_DIR=$CHECK_MODEL_DIR" \
  -v "${HF_CACHE:-$HOME/.cache/huggingface}:/root/.cache/huggingface:ro" \
  dsv4-nvfp4:recipe -c 'set -e
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
docker logs -f dsv4-nvfp4
```

Wait for application startup to complete, including initial kernel compilation.
The launcher binds to loopback and defaults to:

| Setting | Default |
|---|---|
| Tensor parallelism | 2 |
| Model alias | `dsv4-nvfp4` |
| Maximum model length | 65,536 total tokens |
| GPU memory utilization | 0.95 |
| Main expert backend | FlashInfer CUTLASS, NVFP4 |
| DSpark draft | Marlin, original MXFP4, five speculative tokens |
| KV cache | FP8, block size 256, prefix caching enabled |
| Target decode CUDA graphs | FULL_DECODE_ONLY, maximum capture size 16; experimental draft-forward graph disabled |
| Sequence slots / batched tokens | 2 / 2,048 |
| Tokenizer, reasoning, tool parser | `deepseek_v4` |

`MAX_MODEL_LEN`, `GPU_MEMORY_UTILIZATION`, `MAX_NUM_SEQS`, and
`MAX_BATCHED_TOKENS` override the corresponding settings. `DSPARK=0` disables
speculation; `EAGER=1` disables CUDA graphs for diagnostics. `IMAGE`,
`CONTAINER_NAME`, `BIND_ADDRESS`, and `PORT` configure deployment placement.
Additional vLLM options can be passed after `serve.sh`.

For LAN clients, set `BIND_ADDRESS` to the GPU host's LAN address when launching.
Use `http://<gpu-host>:8000/v1` as the OpenAI-compatible base URL and
`dsv4-nvfp4` as the model name. With the default loopback binding, use
`http://127.0.0.1:8000/v1` on the GPU host.

## Recommended coding profile

I'd start everyday coding with these settings. They keep the long-input option
without taking the larger batch's memory cost. Stop the earlier recipe
container and use a new name to keep its logs. The launcher itself still
defaults to 64K at 95%.

```bash
CONTAINER_NAME=dsv4-nvfp4-coding \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.96 \
MAX_BATCHED_TOKENS=2048 MAX_NUM_SEQS=2 \
  bash serve.sh --long-prefill-token-threshold 1792
```

The prefill cap limits how much of a long input gets processed per scheduling
step; it doesn't shorten the 1M window. This profile passed near-1M retrieval,
concurrent tools, a warmed restart and 19 LAN checks. The 48K coding fixture
took a median 8.906 seconds. One tool roundtrip during near-1M prefill took
32.035 seconds, so leave time for very large inputs.

If you care more about tools responding during background prefill, try cap 512.
Stop the active recipe container first:

```bash
CONTAINER_NAME=dsv4-nvfp4-concurrent-tools \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.96 \
MAX_BATCHED_TOKENS=2048 MAX_NUM_SEQS=2 \
  bash serve.sh --long-prefill-token-threshold 512
```

Cap 512 reduced the tool median to 2.186 seconds during repeated 262K inputs
and took 18.113 seconds in one near-1M trial. The coding fixture slowed to
12.205 seconds. Both profiles keep fixed-K5 DSpark, Markov correction and target
decode graphs. Adaptive verification and optional draft-forward graphs are
disabled. See [measurements and startup limits](interactive-latency.md).

## Run the API checks

The clients use Python 3 and its standard library. They send synthetic requests
and exit nonzero if a check fails.

```bash
mkdir -p results/raw
python3 verify.py --long-context-tokens 61440 \
  --output results/raw/features-64k.json
python3 benchmark.py --label dspark-graphs-64k \
  --output results/raw/benchmark-64k.json
```

`verify.py` adds `/v1`, so pass the server origin to `--base-url`, for example
`http://127.0.0.1:8000`. It checks chat, reasoning, tools, structured output,
streaming, concurrency, prefix reuse and cancellation recovery, with optional
long retrieval. See [pass conditions](validation.md).

For a matched DSpark comparison, save the results, stop the recipe container
and launch `DSPARK=0` with identical other settings. Use a **different container
name**: stopped containers still hold their names. With the defaults above:

```bash
docker stop dsv4-nvfp4
DSPARK=0 CONTAINER_NAME=dsv4-nvfp4-control bash serve.sh
# Wait for application startup, then run the same benchmark.
python3 benchmark.py --label graphs-control-64k \
  --output results/raw/benchmark-control-64k.json
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
python3 benchmark.py --label your-profile-short --tokens 256 --repeats 3 \
  --output results/raw/your-profile-short.json
python3 benchmark.py --label your-profile-code --tokens 512 --repeats 3 \
  --code-prompt-file benchmarks/prompts/code-48k.txt --cache-mode uncached \
  --output results/raw/your-profile-code.json
```

Use distinct filenames for later runs. The
[fixture description](../benchmarks/prompts/README.md) records its exact hash.
The override replaces the code workload; the concurrent pair is short prose
plus long code. Uncached mode assigns each request a fresh salt; verify server
cache-hit counters too.

## Attempt large context

The patched preview passed one 799,847-token retrieval at 801K. Stop the earlier
container before changing the window; use a new name to keep its logs:

```bash
docker stop dsv4-nvfp4
CONTAINER_NAME=dsv4-nvfp4-801k MAX_MODEL_LEN=801000 bash serve.sh
```

After startup completes:

```bash
python3 verify.py --only identity,long_context,chat \
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

The initial source-built 1M candidate used the following overrides, after stopping the
previous recipe container:

```bash
CONTAINER_NAME=dsv4-nvfp4-1m-candidate \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.965 \
MAX_BATCHED_TOKENS=2560 \
  bash serve.sh --long-prefill-token-threshold 2304
```

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
python3 mixed_probe.py --label your-profile --prompt-tokens 999000 \
  --delay 30 --short-timeout 180 \
  --output results/raw/mixed-profile.json
```

To measure a checked automatic tool round trip instead of the tiny reply, add
`--short-check tools_auto`. Both tool calls must finish while the long completion
is still active. The two final near-1M cap comparisons used `--delay 240` with
`--prompt-tokens 999000 --short-check tools_auto`. For a shorter repeated
configuration comparison:

```bash
python3 mixed_probe.py --label your-profile-tools --prompt-tokens 262000 \
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

Let experiment requests finish, stop its container, then restore the saved
container with `docker start <saved-container>`. On the original host, you can
also launch the local baseline image under a new name. Retain previous logs.

On another host, build an explicitly named recovery image from a separate
checkout; the default build doesn't create the original host's baseline tag:

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
