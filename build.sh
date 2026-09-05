#!/usr/bin/env bash
# Recreate the recovered public-source build, then apply the tested fixes.
set -euo pipefail
RECIPE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SOURCE_DIR=${SOURCE_DIR:-$RECIPE_DIR/work/vllm-source}
SOURCE_URL=https://github.com/jasl/vllm.git
SOURCE_TAG=sm120-pr-41834-stable-preview-20260804
SOURCE_REVISION=0f59188db1504b042ce621842bdde6c0fe862df6
BASE_IMAGE=${BASE_IMAGE:-dsv4-sm120:source-20260804}
ABI_IMAGE=${ABI_IMAGE:-dsv4-sm120:kernel-fix}
FINAL_IMAGE=${FINAL_IMAGE:-dsv4-nvfp4:recipe}
BUILD_JOBS=${BUILD_JOBS:-16}
NVCC_THREADS=${NVCC_THREADS:-8}
BUILD_NETWORK=${BUILD_NETWORK:-default}
APT_HTTPS_IPV4=${APT_HTTPS_IPV4:-0}
CUDA_BUILD_IMAGE=nvidia/cuda:13.0.3-devel-ubuntu22.04@sha256:3869b846a8cc495ce11c172d87cfc0da8874b910d14a9810bec6b6182e9ee9f8
CUDA_FINAL_IMAGE=nvidia/cuda:13.0.3-base-ubuntu22.04@sha256:73ab6dfb3814a5097cd456736e70650ef9dc72343be4117d0400de78168760fe

if [[ ! -e "$SOURCE_DIR" ]]; then
  git clone --depth 1 --branch "$SOURCE_TAG" "$SOURCE_URL" "$SOURCE_DIR"
fi
[[ $(git -C "$SOURCE_DIR" rev-parse HEAD) == "$SOURCE_REVISION" ]] || {
  echo 'Source checkout is not the pinned revision.' >&2
  exit 1
}
[[ -z $(git -C "$SOURCE_DIR" status --porcelain) ]] || {
  echo 'Source checkout has changes; use a clean source directory.' >&2
  exit 1
}

# Digests are the exact linux/amd64 CUDA materials from the retained build record.
# On the test host, HTTP mirror downloads stalled. This optional preparation
# keeps the same signed Ubuntu repositories, using HTTPS and IPv4 transport.
if [[ "$APT_HTTPS_IPV4" == 1 ]]; then
  docker build --network "$BUILD_NETWORK" --build-arg BASE_IMAGE="$CUDA_BUILD_IMAGE" \
    -f "$RECIPE_DIR/Dockerfile.network" -t dsv4-sm120:cuda-devel-https "$RECIPE_DIR"
  docker build --network "$BUILD_NETWORK" --build-arg BASE_IMAGE="$CUDA_FINAL_IMAGE" \
    -f "$RECIPE_DIR/Dockerfile.network" -t dsv4-sm120:cuda-base-https "$RECIPE_DIR"
  CUDA_BUILD_IMAGE=dsv4-sm120:cuda-devel-https
  CUDA_FINAL_IMAGE=dsv4-sm120:cuda-base-https
fi
docker build --network "$BUILD_NETWORK" --target vllm-openai -f "$SOURCE_DIR/docker/Dockerfile" \
  --build-arg max_jobs="$BUILD_JOBS" --build-arg nvcc_threads="$NVCC_THREADS" \
  --build-arg torch_cuda_arch_list=12.0 \
  --build-arg BUILD_BASE_IMAGE="$CUDA_BUILD_IMAGE" \
  --build-arg FINAL_BASE_IMAGE="$CUDA_FINAL_IMAGE" \
  -t "$BASE_IMAGE" "$SOURCE_DIR"
docker build --network none --build-arg BASE_IMAGE="$BASE_IMAGE" \
  -f "$RECIPE_DIR/Dockerfile.experimental" -t "$ABI_IMAGE" "$RECIPE_DIR"
docker build --network none --build-arg BASE_IMAGE="$ABI_IMAGE" \
  -f "$RECIPE_DIR/Dockerfile.dspark" -t "$FINAL_IMAGE" "$RECIPE_DIR"
printf 'Built %s\n' "$FINAL_IMAGE"
