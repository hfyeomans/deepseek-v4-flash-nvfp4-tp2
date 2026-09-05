# Your first deployment

Run these steps in a terminal on the Linux GPU host. This recipe was tested on
two RTX PRO 6000 Blackwell Max-Q cards, 96 GB each, at TP=2. The measured host had
246 GiB system RAM and driver 610.57.04; these observations are not minimum
requirements for every compatible machine. Other GPU architectures are untested.

The source build and model download are substantial. Weights alone occupy
175,550,788,904 bytes; allow more space for Docker layers, source and kernel
caches. Check both the model disk and Docker's disk before starting.

## 1. Check the machine

```bash
nvidia-smi
docker version
docker buildx version
docker ps
git --version
python3 --version
curl --version
df -h
```

You need Linux x86_64, Git, curl, Python 3.10+, Docker with BuildKit and permission to
run `docker` as your login user. Seeing both GPUs in `nvidia-smi` does not prove
Docker can use them. If Docker or GPU access is missing, complete the official
[Docker Engine installation](https://docs.docker.com/engine/install/) and
[NVIDIA Container Toolkit setup](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
with your administrator. Do not restart a working Docker daemon as a routine
recipe step; that can interrupt other containers.

Verify Docker GPU visibility using the recipe's pinned CUDA base:

```bash
docker run --rm --gpus all \
  nvidia/cuda:13.0.3-base-ubuntu22.04@sha256:73ab6dfb3814a5097cd456736e70650ef9dc72343be4117d0400de78168760fe \
  nvidia-smi
```

Both cards should appear. Stop here and resolve access errors before building.

## 2. Get the recipe and checkpoint

```bash
git clone https://github.com/hfyeomans/deepseek-v4-flash-nvfp4-tp2.git
cd deepseek-v4-flash-nvfp4-tp2
mkdir -p results/raw
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade huggingface_hub
hf --help
export MODEL=nvidia/DeepSeek-V4-Flash-0731-NVFP4
export REVISION=f1caa71142bd0be02f728c79f75042ac1e461579
export HF_CACHE="$HOME/.cache/huggingface"
hf download "$MODEL" --revision "$REVISION" --cache-dir "$HF_CACHE/hub"
```

If Ubuntu reports that `venv` is unavailable, install `python3-venv` first.
The [official HF CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli)
describes installation and authentication. An existing complete pinned cache
can be reused; no GGUF conversion or second draft download is required.
`HF_CACHE` names the parent of `hub`, which the launcher mounts into Docker.
Set it consistently when downloading and serving. Keep these exports in the
same terminal, or set them again after reconnecting.

## 3. Build and check the image

```bash
export FINAL_IMAGE=dsv4-nvfp4:first-run
bash build.sh > results/raw/build.log 2>&1
docker image inspect "$FINAL_IMAGE" --format '{{.Id}}'
```

The build must exit successfully. In another terminal, `tail -f
results/raw/build.log` shows progress. The default is 16 build jobs and 8 NVCC
threads; reduce `BUILD_JOBS` and `NVCC_THREADS` if your machine needs less
parallel compilation. If Ubuntu HTTP downloads stall as they did on the test
host, retry with `APT_HTTPS_IPV4=1 BUILD_NETWORK=host bash build.sh`, saving a
separate log. This retains the signed repositories; see
[the diagnosed failure](troubleshooting.md#slow-ubuntu-package-downloads-during-the-public-rebuild).

Run the CPU tests inside your newly built image before using its GPUs:

```bash
export CHECK_MODEL_DIR="/root/.cache/huggingface/hub/models--nvidia--DeepSeek-V4-Flash-0731-NVFP4/snapshots/$REVISION"
docker run --rm --entrypoint bash \
  -e HF_HUB_OFFLINE=1 -e CUDA_VISIBLE_DEVICES=-1 \
  -e "DSPARK_TEST_MODEL_CONFIG=$CHECK_MODEL_DIR/config.json" \
  -e "DSPARK_TEST_MODEL_DIR=$CHECK_MODEL_DIR" \
  -v "$HF_CACHE:/root/.cache/huggingface:ro" \
  "$FINAL_IMAGE" -c 'set -e
    for check_test in /opt/recipe-tests/test_*.py; do
      python3 "$check_test"
    done'
```

All 13 methods must pass. These validate patched CPU behavior and checkpoint
metadata, not GPU inference.

## 4. Launch your everyday coding/tools profile

Let any existing requests finish and stop the old model container first. Both
GPUs are needed; do not start a second copy alongside a model using their memory.
Keep the old container and image so you can restart them if needed.

```bash
IMAGE="$FINAL_IMAGE" CONTAINER_NAME=dsv4-first-run \
KERNEL_CACHE=dsv4-first-run-kernels \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.96 \
MAX_BATCHED_TOKENS=2048 MAX_NUM_SEQS=2 \
  bash serve.sh --long-prefill-token-threshold 1792
docker logs -f dsv4-first-run
```

Use a previously unused kernel-volume name for your first qualification. Keep
it for subsequent restarts. Wait for **Application startup complete**; weight
loading alone is insufficient. Ctrl-C leaves the detached server running.

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/v1/models
curl --fail http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"dsv4-nvfp4","messages":[{"role":"user","content":"Write a Python function that adds two numbers."}],"max_tokens":128,"chat_template_kwargs":{"thinking":false}}'
python3 verify.py --output results/raw/first-run-features.json
```

Health returns HTTP 200 with an empty body; `/v1/models` lists `dsv4-nvfp4`.
The short feature suite should pass all 19 checks. It covers reasoning, tools,
streaming and other APIs, but does not establish broad coding accuracy, 1M
retrieval or DSpark acceleration by itself.

## 5. Reconnect, recover and choose the next check

After your test requests finish, verify a warmed restart:

```bash
docker restart dsv4-first-run
docker logs -f dsv4-first-run
```

Wait for startup again, then repeat health and the feature suite with a new
output filename. A client on this host uses `http://127.0.0.1:8000/v1` and model
`dsv4-nvfp4`. For a client on another machine, configure the LAN binding using
[the server instructions](running.md#start-the-server).

You can now use the coding profile. The [full running guide](running.md) adds
benchmark comparisons, DSpark counters, optional 801K/1M probes and the
secondary profile for tools during long input processing. A 1M configured limit
does not prove two simultaneous full-window requests will fit. The measured
near-1M mixed run took about 514 seconds, so start large-input experiments only
when you can let them finish. For rollback, use the
[saved-container or explicitly tagged rebuild instructions](running.md#preserved-baseline-and-rollback).

Our [release validation record](../tasks/release-readiness/verification.md)
states which steps were rehearsed on the existing host. An independent fresh
machine installation and your own first-person walkthrough are separate checks.
