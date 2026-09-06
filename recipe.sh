#!/usr/bin/env bash
# Apply the selected .env through the existing build and serving specifications.
set -euo pipefail
RECIPE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/config.sh
source "$RECIPE_DIR/scripts/config.sh"
while IFS='=' read -r config_key _config_default; do
  if [[ "$config_key" =~ ^[A-Z][A-Z_0-9]*$ && -v "$config_key" ]]; then
    export "${config_key?}"
  fi
done < "$RECIPE_DIR/example.env"
export RECIPE_DIR RECIPE_ENV_FILE
exec python3 "$RECIPE_DIR/scripts/lifecycle.py" "$@"
