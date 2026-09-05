#!/usr/bin/env bash
# Experimental launch under validation; see README.md for current limitations.
set -euo pipefail

IMAGE=${IMAGE:-dsv4-nvfp4:recipe}
MODEL=${MODEL:-nvidia/DeepSeek-V4-Flash-0731-NVFP4}
REVISION=${REVISION:-f1caa71142bd0be02f728c79f75042ac1e461579}
HF_CACHE=${HF_CACHE:-${HOME}/.cache/huggingface}
KERNEL_CACHE=${KERNEL_CACHE:-codex-dsv4-kernel-cache}
CONTAINER_NAME=${CONTAINER_NAME:-dsv4-nvfp4}
BIND_ADDRESS=${BIND_ADDRESS:-127.0.0.1}
PORT=${PORT:-8000}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-65536}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-2}
MAX_BATCHED_TOKENS=${MAX_BATCHED_TOKENS:-2048}
GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.95}
OFFLINE=${OFFLINE:-1}
DSPARK=${DSPARK:-1}
EAGER=${EAGER:-0}

[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'REVISION must be a full pinned Hugging Face commit SHA.' >&2
  exit 1
}

extra_args=()
if [[ "$EAGER" == 1 ]]; then
  extra_args+=(--enforce-eager)
else
  extra_args+=(--compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY","max_cudagraph_capture_size":16}')
fi
if [[ "$DSPARK" == 1 ]]; then
  printf -v speculative_config '{"method":"dspark","num_speculative_tokens":5,"draft_sample_method":"probabilistic","moe_backend":"marlin","revision":"%s"}' "$REVISION"
  extra_args+=(--speculative-config "$speculative_config")
fi

exec docker run -d --name "$CONTAINER_NAME" --gpus all --ipc=host \
  -p "$BIND_ADDRESS:$PORT:8000" \
  -e HF_HUB_OFFLINE="$OFFLINE" -e HF_DATASETS_OFFLINE="$OFFLINE" \
  -e MAX_JOBS="${MAX_JOBS:-8}" \
  -e DSPARK_VERIFY_WEIGHT_COVERAGE=1 \
  -v "$HF_CACHE:/root/.cache/huggingface" \
  -v "$KERNEL_CACHE:/root/.cache/flashinfer" \
  "$IMAGE" "$MODEL" \
  --revision "$REVISION" --tokenizer-revision "$REVISION" \
  --trust-remote-code --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 --tensor-parallel-size 2 \
  --kv-cache-dtype fp8 --block-size 256 --moe-backend flashinfer_cutlass \
  --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS" \
  --max-num-batched-tokens "$MAX_BATCHED_TOKENS" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --enable-prefix-caching --served-model-name dsv4-nvfp4 \
  "${extra_args[@]}" "$@"
