# Build, serve, and reproduce the checks

Run these commands from the recipe repository on the Linux GPU host.
If this is your first deployment, follow the [ordered walkthrough](first-run.md)
for clone, prerequisite checks, CLI installation and expected results.
The measured hardware is two RTX PRO 6000 Blackwell Max-Q GPUs at TP=2.
The tested driver is 610.57.04. The recipe targets SM120 and the pinned preview
source; it has not been validated on other architectures or a stock vLLM image.

The existing preview image plus these patches has passed the recorded checks.
The public-source rebuild completed and passed all 13 CPU regression methods,
19 LAN API checks and near-1M retrieval. See [source-image acceptance](source-image-validation.md)
for its settings and limits, and the [profile comparison](interactive-latency.md)
for the selected coding configuration.

## Obtain the pinned checkpoint

Install the Hugging Face `hf` CLI if needed, then download the pinned snapshot:

```bash
export MODEL=nvidia/DeepSeek-V4-Flash-0731-NVFP4
export REVISION=f1caa71142bd0be02f728c79f75042ac1e461579
hf download "$MODEL" --revision "$REVISION"
```

The weight shards total 175,550,788,904 bytes. Allow additional space for source,
Docker layers, build caches, and compiled kernels. `serve.sh` defaults to offline
use of `$HOME/.cache/huggingface`; set `HF_CACHE` if your cache lives elsewhere.
The draft layers are already in this snapshot. No GGUF conversion or separate
draft checkpoint is needed for this vLLM recipe.

## Build the runtime

Docker with NVIDIA GPU access and Git must work on the host. `build.sh` checks out
the pinned public source into `work/vllm-source`, reconstructs the recorded SM120
build, fixes the FlashInfer cache ABI issue, and applies the three runtime patches.

```bash
bash build.sh
```

On the test host, Ubuntu HTTP downloads stalled. The following transport
workaround passed that stage while keeping the same signed repositories and
pinned CUDA base images:

```bash
APT_HTTPS_IPV4=1 BUILD_NETWORK=host bash build.sh
```

The resulting image name is `dsv4-nvfp4:recipe`. Defaults use 16 build jobs and
8 NVCC threads; `BUILD_JOBS` and `NVCC_THREADS` override them. See
[source/build provenance](../results/original-build-provenance.json) and
[the diagnosed compatibility failures](troubleshooting.md).

The completed build's [image digests, dependency versions and CPU results](../results/source-build-provenance.json)
are recorded separately from the original image. That JSON preserves the
build-stage snapshot, whose GPU acceptance was still pending at collection;
[subsequent GPU acceptance](source-image-validation.md) completed. This was a source rebuild on
the same host with reusable base/download layers, not a clean-machine test or
a claim of bit-for-bit reproducibility.

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

These tests do not exercise GPUs. Use a previously unused `KERNEL_CACHE` volume
name on the first GPU acceptance launch to check kernel compilation independently
of existing FlashInfer cache files. Retain that volume for warmed restarts.

## Start the server

```bash
bash serve.sh
docker logs -f dsv4-nvfp4
```

Wait for application startup to complete. The initial launch compiles kernels;
model weights loading successfully is only one startup stage. The launcher binds
to loopback by default and uses the following settings:

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

For the tested two-GPU host and interactive coding with occasional very long
inputs, use these explicit overrides. Stop the earlier recipe container first;
use a new name to preserve its logs. The generic launcher defaults above remain
64K at 95%.

```bash
CONTAINER_NAME=dsv4-nvfp4-coding \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.96 \
MAX_BATCHED_TOKENS=2048 MAX_NUM_SEQS=2 \
  bash serve.sh --long-prefill-token-threshold 1792
```

This profile passed near-1M retrieval, concurrent tools, a warmed restart and all
19 short API checks over the LAN afterward. The cap limits long-prefill work
per scheduling step; it does not shorten the 1M context window. In the tested
48K coding fixture, median completion time was 8.906 seconds. A tool round trip
during the near-1M prefill took 32.035 seconds, so capacity does not imply instant
responses while a very long input is processing.

If tool responsiveness during background prefill matters more, choose cap512
instead, after stopping the active recipe container:

```bash
CONTAINER_NAME=dsv4-nvfp4-concurrent-tools \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.96 \
MAX_BATCHED_TOKENS=2048 MAX_NUM_SEQS=2 \
  bash serve.sh --long-prefill-token-threshold 512
```

Cap512 measured a 2.186-second tool median during the repeated 262K input test
and 18.113 seconds in one near-1M test. The coding fixture slowed to 12.205
seconds. Both profiles retain fixed-K5 DSpark, Markov correction and target
decode graphs; neither enables adaptive verification or the optional draft
forward graph. See [all profile measurements and startup limits](interactive-latency.md).

## Run the API checks

The test clients require Python 3 and its standard library only. They send
synthetic requests to the running server and exit nonzero on a failed check.

```bash
mkdir -p results/raw
python3 verify.py --long-context-tokens 61440 \
  --output results/raw/features-64k.json
python3 benchmark.py --label dspark-graphs-64k \
  --output results/raw/benchmark-64k.json
```

`verify.py` adds `/v1` itself: its `--base-url` is the server origin, such as
`http://127.0.0.1:8000`. It covers chat, reasoning, tools and their round trips,
structured output, streaming, concurrency, prefix reuse, cancellation recovery,
and optional long-context retrieval. See [pass conditions](validation.md).

For a matched DSpark comparison, save the first results, stop this recipe's
container, and use a **different container name** for `DSPARK=0`, keeping all
other settings identical. A stopped container retains its name; running another
container with that name fails. For the default names/settings above:

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

Keep other workloads idle. The benchmark warms every exact
prompt, generates 256 tokens per request, and records two measured repeats plus
one pair of concurrent requests. It measures short inputs even on a large window.

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

Record later short runs under distinct output names to preserve all trials.
The [fixture description and hash](../benchmarks/prompts/README.md) identify the
exact bytes. The code override replaces only the code workload: its concurrent
pair remains short prose plus long code, not two long code requests. Uncached
mode gives every request a fresh cache salt; still verify server hit counters.

## Attempt large context

The 801K configuration has passed a single 799,847-token retrieval request on the
patched preview image. Stop the earlier recipe container before changing its
window. Use a new name to preserve its logs:

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

The 1M experiment uses `MAX_MODEL_LEN=1000000` and
`--long-context-tokens 999000` and `GPU_MEMORY_UTILIZATION=0.96`. This passed
998,847-token retrieval and all 19 follow-up API checks on the patched preview;
95% failed the startup memory check. The public rebuild subsequently passed at
96.5% with the larger batch below and at 96% with both recommended-profile caps.
The model window includes
prompt and completion tokens; these probes reserve output room and report the
actual tokenizer count. A successful single request does not establish two
simultaneous full-window requests or broad retrieval quality.

The initial source-built 1M candidate used the following overrides, after stopping the
previous recipe container:

```bash
CONTAINER_NAME=dsv4-nvfp4-1m-candidate \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.965 \
MAX_BATCHED_TOKENS=2560 \
  bash serve.sh --long-prefill-token-threshold 2304
```

This is a measured candidate, not the selected interactive default. Retrieval
and short API checks passed, but a concurrent tool round trip took 37.9 seconds
and sampled serving free memory fell to 507/472 MiB. See
[the complete source-image report](source-image-validation.md).

For each attempt, preserve launch settings, startup memory logs, actual token
counts, outputs, and elapsed times. Keep first-use compilation and concurrent
build activity separate from steady-state performance. The cache token count
printed at startup is context-dependent arithmetic; see
[the memory explanation](context-memory.md).

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

Warm the same protocol before measured repeats and retain the warmup result.
The long prompt gets a fresh prefix each run; the tool prompt is unchanged and
may reuse cache blocks, including between its two calls. Record cache-hit deltas
instead of describing this entire workload as uncached. Record actual prompt and
completion counts, both tool-call times, long duration and sampled resources.

This prepares the prompt, starts the long completion call, and submits a short
exact-answer request 30 seconds after that call begins. Each run records a new
unique prefix near the start of the long prompt. Passing requires both answers
to be correct and the short response to finish at least one second before the
long completion call returns. If the long request finishes before the probe,
the result is inconclusive. The output preserves failures, completion-call
boundaries, the prefix, and raw synthetic requests. Use server metrics to verify
admission and prefill activity; client overlap alone does not establish them.

The uncapped 97% profile exposed a 180-second short-request timeout.
`MAX_BATCHED_TOKENS=2560` with `--long-prefill-token-threshold 2304` subsequently
passed mixed near-1M retrieval and all 19 follow-up API checks. Source-image
acceptance and controlled benchmarks have since completed; the
[interactive comparison](interactive-latency.md) records lower-memory alternatives. See
[the scheduling evidence](performance.md#observed-mixed-request-scheduling-limit).

For a controlled context/batch comparison with vLLM's benchmark and saved
latencies, follow [the measurement guide](context-batch.md).

## Preserved baseline and rollback

Git tag `recipe-1m-k5` preserves this clean recipe's tested source/build/launch
files. Use it in a separate checkout to recover the recipe without discarding
newer work. The original `baseline-1m-k5` Git tag is retained in the private
adaptive archive; [provenance](provenance.md) explains historical references.
The selected host's exact tested image is also tagged
`dsv4-nvfp4:baseline-1m-k5`; its identity is recorded in
[snapshot provenance](provenance.md). This image tag is local to
that host and is not a registry upload.

After an experiment, let active requests finish and stop its container before
restoring the saved baseline container with `docker start <saved-container>`.
On the original host, the local image tag above is also available for a new
container. Keep a distinct name and retain previous logs.

On another host, build an explicitly named recovery image from a separate
checkout; the default build does not create the original host's baseline tag:

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

The pinned checkpoint must still be present in the configured `HF_CACHE`.
Wait for application startup, check `/health` and `/v1/models`, then rerun
`verify.py` under a new output filename. Recovering code alone does not prove
the running service was rolled back.
