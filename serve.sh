#!/usr/bin/env bash
# Launch the profile in .env; see docs/running.md for checks and recovery.
set -euo pipefail

RECIPE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/config.sh
source "$RECIPE_DIR/scripts/config.sh"
if (( $# > 1 )) || { (( $# == 1 )) && [[ "$1" != --print-spec ]]; }; then
  echo 'Change .env or select a file with RECIPE_ENV_FILE; --print-spec only prints validated launch settings.' >&2
  exit 1
fi
require_settings IMAGE MODEL REVISION HF_CACHE KERNEL_CACHE CONTAINER_NAME \
  BIND_ADDRESS PORT SERVER_PORT SERVED_MODEL_NAME TENSOR_PARALLEL_SIZE MAX_MODEL_LEN MAX_NUM_SEQS \
  MAX_BATCHED_TOKENS LONG_PREFILL_TOKEN_THRESHOLD GPU_MEMORY_UTILIZATION \
  MAX_CUDAGRAPH_CAPTURE_SIZE MAX_JOBS LOGGING_CONFIG DOCKER_LOG_MAX_SIZE \
  DOCKER_LOG_MAX_FILES HEALTH_INTERVAL HEALTH_TIMEOUT_SECONDS HEALTH_START_PERIOD HEALTH_RETRIES
require_uints PORT SERVER_PORT TENSOR_PARALLEL_SIZE MAX_MODEL_LEN MAX_NUM_SEQS MAX_BATCHED_TOKENS \
  LONG_PREFILL_TOKEN_THRESHOLD MAX_CUDAGRAPH_CAPTURE_SIZE MAX_JOBS MAX_LOG_LEN \
  DOCKER_LOG_MAX_FILES HEALTH_TIMEOUT_SECONDS HEALTH_RETRIES
require_switches OFFLINE DSPARK EAGER LOG_REQUESTS LOG_OUTPUTS
[[ "$TENSOR_PARALLEL_SIZE" != 0 ]] || { echo 'TENSOR_PARALLEL_SIZE must be a positive integer.' >&2; exit 1; }
for setting in MAX_MODEL_LEN MAX_NUM_SEQS MAX_BATCHED_TOKENS MAX_JOBS HEALTH_TIMEOUT_SECONDS HEALTH_RETRIES DOCKER_LOG_MAX_FILES; do
  [[ ${!setting} != 0 ]] || { printf '%s must be positive.\n' "$setting" >&2; exit 1; }
done
python3 - "$GPU_MEMORY_UTILIZATION" "$PORT" "$SERVER_PORT" <<'PY'
import math
import sys
try:
    fraction = float(sys.argv[1])
except ValueError:
    fraction = float('nan')
if not math.isfinite(fraction) or not 0 < fraction <= 1:
    sys.exit('GPU_MEMORY_UTILIZATION must be a finite number greater than 0 and at most 1.')
if any(not 1 <= int(port) <= 65535 for port in sys.argv[2:]):
    sys.exit('PORT and SERVER_PORT must be between 1 and 65535.')
PY
[[ -f "$LOGGING_CONFIG" ]] || { echo 'LOGGING_CONFIG must name an existing file.' >&2; exit 1; }

[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'REVISION must be a full pinned Hugging Face commit SHA.' >&2
  exit 1
}

extra_args=()
if [[ "$EAGER" == 1 ]]; then
  extra_args+=(--enforce-eager)
else
  printf -v compilation_config '{"cudagraph_mode":"FULL_DECODE_ONLY","max_cudagraph_capture_size":%s}' "$MAX_CUDAGRAPH_CAPTURE_SIZE"
  extra_args+=(--compilation-config "$compilation_config")
fi
if [[ "$DSPARK" == 1 ]]; then
  printf -v speculative_config '{"method":"dspark","num_speculative_tokens":5,"draft_sample_method":"probabilistic","moe_backend":"marlin","revision":"%s"}' "$REVISION"
  extra_args+=(--speculative-config "$speculative_config")
fi
if [[ "$LOG_REQUESTS" == 1 ]]; then
  extra_args+=(--enable-log-requests --max-log-len "$MAX_LOG_LEN")
  if [[ "$LOG_OUTPUTS" == 1 ]]; then
    extra_args+=(--enable-log-outputs --no-enable-log-deltas)
  fi
fi
printf -v health_cmd "python3 -c 'import sys, urllib.request; r = urllib.request.urlopen(\"http://127.0.0.1:%s/health\", timeout=%s); sys.exit(0 if r.status == 200 else 1)'" \
  "$SERVER_PORT" "$HEALTH_TIMEOUT_SECONDS"

docker_options=(--name "$CONTAINER_NAME" --gpus all --ipc=host \
  -p "$BIND_ADDRESS:$PORT:$SERVER_PORT" \
  --log-driver json-file --log-opt "max-size=$DOCKER_LOG_MAX_SIZE" --log-opt "max-file=$DOCKER_LOG_MAX_FILES" \
  --health-cmd "$health_cmd" --health-interval "$HEALTH_INTERVAL" \
  --health-timeout "${HEALTH_TIMEOUT_SECONDS}s" --health-start-period "$HEALTH_START_PERIOD" \
  --health-retries "$HEALTH_RETRIES" \
  -e HF_HUB_OFFLINE="$OFFLINE" -e HF_DATASETS_OFFLINE="$OFFLINE" \
  -e MAX_JOBS="$MAX_JOBS" \
  -e VLLM_LOGGING_CONFIG_PATH=/etc/vllm/logging.json \
  -e DSPARK_VERIFY_WEIGHT_COVERAGE=1 \
  --mount "type=bind,source=$LOGGING_CONFIG,target=/etc/vllm/logging.json,readonly" \
  -v "$HF_CACHE:/root/.cache/huggingface" \
  -v "$KERNEL_CACHE:/root/.cache/flashinfer")
model_args=("$MODEL" \
  --host 0.0.0.0 --port "$SERVER_PORT" \
  --revision "$REVISION" --tokenizer-revision "$REVISION" \
  --trust-remote-code --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
  --kv-cache-dtype fp8 --block-size 256 --moe-backend flashinfer_cutlass \
  --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS" \
  --max-num-batched-tokens "$MAX_BATCHED_TOKENS" \
  --long-prefill-token-threshold "$LONG_PREFILL_TOKEN_THRESHOLD" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --enable-prefix-caching --served-model-name "$SERVED_MODEL_NAME" \
  "${extra_args[@]}")

if [[ ${1:-} == --print-spec ]]; then
  python3 -c 'import json, sys; n = int(sys.argv[1]); print(json.dumps({"docker_options": sys.argv[2:2+n], "image": sys.argv[2+n], "model_args": sys.argv[3+n:]}))' \
    "${#docker_options[@]}" "${docker_options[@]}" "$IMAGE" "${model_args[@]}"
  exit 0
fi

if container_state=$(docker container inspect --format '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null); then
  {
    printf 'Container %s already exists (%s). serve.sh creates a new container.\n' "$CONTAINER_NAME" "$container_state"
    case "$container_state" in
      exited|created) printf 'Resume with its original settings: docker start %q\n' "$CONTAINER_NAME" ;;
    esac
    printf 'Logs: docker logs --timestamps -f %q\n' "$CONTAINER_NAME"
    printf "Status: docker container inspect --format '{{.State.Status}}' %q\n" "$CONTAINER_NAME"
    printf 'Serving changes in .env require a new container, not an image rebuild.\n'
    printf 'Apply automatically: bash %q\n' "$RECIPE_DIR/recipe.sh"
  } >&2
  exit 1
fi

container_id=$(docker run -d "${docker_options[@]}" "$IMAGE" "${model_args[@]}")

printf 'Created %s (%s). Starting; wait for healthy before sending requests.\n' "$CONTAINER_NAME" "$container_id"
printf 'Config: %s\nImage: %s\nTensor parallelism: %s\nClient base URL: %s/v1\nModel: %s\n' \
  "$RECIPE_ENV_FILE" "$IMAGE" "$TENSOR_PARALLEL_SIZE" "$BASE_URL" "$SERVED_MODEL_NAME"
[[ "$BIND_ADDRESS" != 0.0.0.0 ]] || echo 'For LAN clients, replace 127.0.0.1 with the GPU host address.'
printf 'Logs:   docker logs --timestamps -f %q\n' "$CONTAINER_NAME"
printf "Status: docker inspect --format '{{.State.Status}} / {{.State.Health.Status}}' %q\n" "$CONTAINER_NAME"
printf 'Stop:   docker stop %q\nRestart saved container: docker start %q\n' "$CONTAINER_NAME" "$CONTAINER_NAME"
