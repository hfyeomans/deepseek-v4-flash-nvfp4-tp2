# Your first deployment

Run these steps on the Linux GPU host. We tested two RTX PRO 6000 Blackwell
Max-Q cards, 96 GB each, at TP=2, with 246 GiB system RAM and driver 610.57.04.
RAM and driver values describe the test host; they are not minimum requirements.
Other GPU architectures are untested.

Weights occupy 175,550,788,904 bytes. Allow additional disk space for Docker
layers, source and kernel caches. Check free space on both the model and Docker
disks before starting.

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

You need Linux x86_64, Git, curl, Python 3.10+, Docker with BuildKit and permission
to run `docker` as your login user. Check GPU access inside Docker even if
`nvidia-smi` works on the host. If needed, follow the official
[Docker Engine installation](https://docs.docker.com/engine/install/) and
[NVIDIA Container Toolkit setup](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
with your administrator. Restarting Docker can interrupt other containers.

Verify Docker GPU visibility using the recipe's pinned CUDA base:

```bash
docker run --rm --gpus all \
  nvidia/cuda:13.0.3-base-ubuntu22.04@sha256:73ab6dfb3814a5097cd456736e70650ef9dc72343be4117d0400de78168760fe \
  nvidia-smi
```

Both cards should appear. Resolve access errors before building.

## 2. Get the recipe and checkpoint

```bash
git clone https://github.com/hfyeomans/deepseek-v4-flash-nvfp4-tp2.git
cd deepseek-v4-flash-nvfp4-tp2
mkdir -p results/raw
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'huggingface_hub==1.30.0'
hf --help
export MODEL=nvidia/DeepSeek-V4-Flash-0731-NVFP4
export REVISION=f1caa71142bd0be02f728c79f75042ac1e461579
export HF_CACHE="$HOME/.cache/huggingface"
hf download "$MODEL" --revision "$REVISION" --cache-dir "$HF_CACHE/hub"
```

If Ubuntu lacks `venv`, install `python3-venv`. The
[HF CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli) covers
installation and authentication; this rehearsal used package version 1.30.0.
Reuse a complete pinned cache if you have one. No GGUF conversion or separate
draft download is needed. `HF_CACHE` is the parent of `hub`; use the same value
for downloading and serving. Keep these exports in this terminal or set them
again after reconnecting.

## 3. Build and check the image

```bash
export FINAL_IMAGE=dsv4-nvfp4:first-run
bash build.sh > results/raw/build.log 2>&1
docker image inspect "$FINAL_IMAGE" --format '{{.Id}}'
```

Wait for a successful build exit. In another terminal, `tail -f
results/raw/build.log` shows progress. Defaults are 16 build jobs and 8 NVCC
threads; lower `BUILD_JOBS` and `NVCC_THREADS` to reduce compilation load. If
Ubuntu HTTP downloads stall, retry with
`APT_HTTPS_IPV4=1 BUILD_NETWORK=host bash build.sh` and a separate log. This
keeps the signed repositories; see [the diagnosed failure](troubleshooting.md#slow-ubuntu-package-downloads-during-the-public-rebuild).

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

All 13 methods must pass. They check patched CPU behavior and checkpoint
metadata; GPU validation comes next.

## 4. Launch your everyday coding/tools profile

Let existing requests finish, then stop the old model container. This recipe
needs both GPUs. Keep the old container and image for recovery.

```bash
IMAGE="$FINAL_IMAGE" CONTAINER_NAME=dsv4-first-run \
KERNEL_CACHE=dsv4-first-run-kernels \
MAX_MODEL_LEN=1000000 GPU_MEMORY_UTILIZATION=0.96 \
MAX_BATCHED_TOKENS=2048 MAX_NUM_SEQS=2 \
  bash serve.sh --long-prefill-token-threshold 1792
docker logs -f dsv4-first-run
```

Use a new kernel-volume name for first qualification, then keep it for
restarts. Wait for **Application startup complete**. Ctrl-C leaves the detached
server running. The fresh-cache rehearsal took about nine minutes to readiness;
some later request shapes still needed compilation. Busy CPU compilers with
low GPU use and periodic shared-memory wait messages do not, alone, indicate a
hang. See the [qualification timings](../tasks/release-readiness/verification.md).

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/v1/models
curl --fail http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"dsv4-nvfp4","messages":[{"role":"user","content":"Write a Python function that adds two numbers."}],"max_tokens":128,"chat_template_kwargs":{"thinking":false}}'
python3 verify.py --output results/raw/first-run-features.json
```

Health should return HTTP 200 with an empty body; `/v1/models` should list
`dsv4-nvfp4`. All 19 short feature checks should pass. They test APIs, including
reasoning, tools and streaming. Coding accuracy, 1M retrieval and DSpark speed
need separate measurements.

## 5. Reconnect, recover and choose the next check

After your test requests finish, verify a warmed restart:

```bash
docker restart dsv4-first-run
docker logs -f dsv4-first-run
```

Wait for startup, then repeat health and the feature suite with a new output
filename. Connect a local client to `http://127.0.0.1:8000/v1` with model
`dsv4-nvfp4`. For another machine, follow the
[LAN binding instructions](running.md#start-the-server).

The coding profile is ready to use. The [running guide](running.md) covers
benchmarks, DSpark counters, 801K/1M probes and the secondary profile. Budget
time for large probes: the measured near-1M mixed run took about 514 seconds.
Two full-window requests have not been qualified. For recovery, use the
[saved container or tagged rebuild](running.md#preserved-baseline-and-rollback).

The [release record](../tasks/release-readiness/verification.md) identifies the
steps rehearsed on the existing host. An independent fresh-machine installation
and the owner's first walkthrough remain untested.
