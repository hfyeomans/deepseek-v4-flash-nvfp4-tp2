#!/usr/bin/env bash
# Source this from Bash; keep operator values in the selected env file.
RECIPE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
RECIPE_ENV_FILE=${RECIPE_ENV_FILE:-$RECIPE_DIR/.env}
if [[ ! -f "$RECIPE_ENV_FILE" ]]; then
  printf 'Missing config: %s\nCopy %s/example.env to %s, set the cache, network and profile parameters, then retry.\n' \
    "$RECIPE_ENV_FILE" "$RECIPE_DIR" "$RECIPE_ENV_FILE" >&2
  return 1
fi
# The example owns the setting names as well as their documented defaults.
# Clear those names so an incomplete file can't inherit an old image/profile.
while IFS='=' read -r config_key _config_default; do
  if [[ "$config_key" =~ ^[A-Z][A-Z_0-9]*$ ]]; then
    unset "$config_key"
  fi
done < "$RECIPE_DIR/example.env"
# shellcheck source=/dev/null
source "$RECIPE_ENV_FILE"

require_settings() {
  local setting
  for setting in "$@"; do
    if [[ -z ${!setting:-} ]]; then
      printf 'Missing %s in config. Compare your file with example.env.\n' "$setting" >&2
      return 1
    fi
  done
}

require_uints() {
  local setting
  for setting in "$@"; do
    if [[ ! ${!setting:-} =~ ^(0|[1-9][0-9]*)$ ]]; then
      printf '%s must be a nonnegative integer.\n' "$setting" >&2
      return 1
    fi
  done
}

require_switches() {
  local setting
  for setting in "$@"; do
    if [[ ${!setting:-} != 0 && ${!setting:-} != 1 ]]; then
      printf '%s must be 0 or 1.\n' "$setting" >&2
      return 1
    fi
  done
}

# Client origin for local checks. A wildcard bind isn't a client destination.
if [[ -n ${BIND_ADDRESS:-} && -n ${PORT:-} ]]; then
  CLIENT_HOST=$BIND_ADDRESS
  [[ "$CLIENT_HOST" != 0.0.0.0 ]] || CLIENT_HOST=127.0.0.1
  export BASE_URL="http://$CLIENT_HOST:$PORT"
fi
