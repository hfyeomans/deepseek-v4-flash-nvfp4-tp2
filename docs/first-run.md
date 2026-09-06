# Your first deployment

I wanted to keep the settings in one place and see what the server was doing.
This walkthrough gets the image built, the endpoint checked and your coding
agent connected. Run these commands in Bash on the Linux GPU host.

We tested two RTX PRO 6000 Blackwell Max-Q cards, 96 GB each, at TP=2, with
246 GiB RAM and driver 610.57.04. RAM and driver describe that machine, not
minimum requirements. Other GPU architectures haven't been tested. Weights
alone use 175,550,788,904 bytes; allow more for Docker layers and caches.

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
to run Docker as your login user. If needed, follow the official
[Docker installation](https://docs.docker.com/engine/install/) and
[NVIDIA Container Toolkit setup](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
Restarting Docker can interrupt other containers.

Check GPU access inside Docker before spending time on a build:

```bash
docker run --rm --gpus all \
  nvidia/cuda:13.0.3-base-ubuntu22.04@sha256:73ab6dfb3814a5097cd456736e70650ef9dc72343be4117d0400de78168760fe \
  nvidia-smi
```

You should see both cards. Check space on the model-cache and Docker disks.

## 2. Configure and download

```bash
git clone https://github.com/hfyeomans/deepseek-v4-flash-nvfp4-tp2.git
cd deepseek-v4-flash-nvfp4-tp2
cp example.env .env
```

Edit `.env` before continuing. It contains the tested everyday profile:
**1,000,000 tokens, 96% memory, two slots, batch 2,048, prefill cap 1,792 and
fixed-K5 DSpark**. These are defaults you can change; other values need testing.
Set `HF_CACHE` to your weight-cache location. Keep `BIND_ADDRESS=127.0.0.1`
for access from this host only. Before enabling access from other machines,
read [the network exposure guidance](running.md#start-the-server).

Build and serve load `.env` themselves and fail if it's missing. These are
trusted Bash assignments; file values win over old shell exports. The shared
loader also makes the same settings available to the commands below:

```bash
source scripts/config.sh
mkdir -p results/raw
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'huggingface_hub==1.30.0'
hf download "$MODEL" --revision "$REVISION" --cache-dir "$HF_CACHE/hub"
```

If Ubuntu lacks `venv`, install `python3-venv`. The
[HF CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli) covers
installation and authentication. Reuse a complete pinned cache if you have one.
`HF_CACHE` is the parent of `hub`; no GGUF conversion or separate draft download
is needed. After editing `.env` or reconnecting, source the loader again for
manual commands. [Alternate config files](running.md#configuration) work too.

## 3. Build and check the image

Already built the image and only changed a serving setting in `.env`? Skip the
build and [replace the container](running.md#stop-resume-and-apply-settings).
Rebuilding won't update the saved container or resolve a name conflict. The
[action table](running.md#configuration) explains when each command is needed.

```bash
source scripts/config.sh
mkdir -p results/raw
bash build.sh > results/raw/build.log 2>&1 &&
  docker image inspect "${IMAGE:?Load scripts/config.sh first}" --format '{{.Id}}'
```

Copying `.env` doesn't load it into your terminal. `build.sh` loads it in its
own process, so source the loader above before using variables in manual
commands. To inspect an image you've already built, skip the build and run:

```bash
source scripts/config.sh
docker image inspect "${IMAGE:?Load scripts/config.sh first}" --format '{{.Id}}'
```

Wait for a successful build exit. In another terminal, `tail -f
results/raw/build.log` shows progress. The default image tag is
`dsv4-nvfp4:recipe`; Docker may display `docker.io/library/` in front of it.
That display doesn't mean the image was uploaded.

Already built this pinned, patched image under an older name? These launcher
changes don't require recompiling it. Give it the stable tag with
`docker tag <existing-image-tag-or-id> dsv4-nvfp4:recipe`, then run the image
checks below. Tagging keeps the same bytes and leaves the old tag available.

Lower `BUILD_JOBS` and `NVCC_THREADS` in `.env` if compilation uses too much RAM.
If Ubuntu HTTP downloads stall, set `APT_HTTPS_IPV4=1` and `BUILD_NETWORK=host`
in `.env`, then rerun the build with a new log filename. See
[the network diagnosis](troubleshooting.md#slow-ubuntu-package-downloads-during-the-public-rebuild).
A [setup.py deprecation warning](troubleshooting.md#python-packaging-deprecation-warning)
alone isn't a failed build; retain the log and check the final exit status.

Check the patches and checkpoint metadata inside the image before loading GPUs:

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

All 13 methods must pass. These check CPU behavior and metadata; the next step
checks the running model.

## 4. Start and watch the server

Both GPUs must be available. Let the old model finish its requests, then stop
its container. This stops that container, not the Docker service or its image:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker stop <old-container-name>
```

Replace the placeholder with the name from the list. Keep that container for
recovery. With the default name in `.env`, launch and follow logs:

**Allow several minutes for the first launch with a new kernel cache.** Kernels
compile after the weights load. The earlier rehearsal reached readiness in
about nine minutes, including service shutdown, loading and compilation;
that isn't a fixed startup time. Keep the `KERNEL_CACHE` volume
(`dsv4-nvfp4-kernels` by default) so later starts can reuse compiled kernels.

```bash
bash serve.sh
docker logs --timestamps -f dsv4-nvfp4
```

The launcher prints your configured client URL, model name, health and stop
commands. Ctrl-C exits the log viewer and leaves the server running. During
compilation, GPU activity can be low and VRAM can sit below its final footprint.
Repeated `No available shared memory broadcast block found in 60 seconds`
messages can mean workers are still compiling; they don't prove a hang.
Check [compiler activity](running.md#first-launch-and-kernel-cache) before
restarting. Wait for **Application startup complete** and a healthy status:

```bash
source scripts/config.sh
docker inspect --format '{{.State.Status}} / {{.State.Health.Status}}' "$CONTAINER_NAME"
curl --fail "$BASE_URL/health"
curl --fail "$BASE_URL/v1/models"
python3 verify.py --base-url "$BASE_URL" --model "$SERVED_MODEL_NAME" \
  --output results/raw/features.json
```

Health returns HTTP 200 with an empty body. `/v1/models` lists your served alias.
All 19 short feature checks should pass. These cover tools, reasoning, streaming
and other APIs; coding accuracy, 1M retrieval and speed need separate tests.

The [startup record](../tasks/release-readiness/verification.md) separates the
first launch from the warmed restart. New request shapes can still need compilation.

## 5. Connect your coding agent

Choose an OpenAI-compatible provider. With the default settings, use:

| Client setting | Value |
|---|---|
| Base URL, on the GPU host | `http://127.0.0.1:8000/v1` |
| Base URL, on another machine | `http://<gpu-host-LAN-address>:8000/v1` after changing `BIND_ADDRESS` |
| Model name | `dsv4-nvfp4` (the `SERVED_MODEL_NAME` value) |
| API key | A nonempty placeholder if your client requires one; this recipe doesn't configure server authentication |

The client sends the served alias as its model name. The Hugging Face path
identifies the download; the Docker tag identifies the runtime image.

## 6. Stop, restart and change settings

Stopping frees the model's GPU memory once its processes exit, but keeps the
container and its name. With the default name, stop and later resume it with:

```bash
docker stop dsv4-nvfp4
docker start dsv4-nvfp4
docker logs --timestamps -f dsv4-nvfp4
```

`bash serve.sh` creates a new container; an existing name blocks creation even
when stopped. **Restarting keeps the container's original settings.** Serving
changes in `.env` need a new container, not an image rebuild. Follow
[apply settings](running.md#stop-resume-and-apply-settings) to preserve the old
container or save its logs and replace it. Wait for healthy, then repeat the
feature suite with a new output filename.

The [release record](../tasks/release-readiness/verification.md) covers the
rehearsal on the existing host. The owner's walkthrough is in progress;
an independent fresh-machine install remains unqualified.
