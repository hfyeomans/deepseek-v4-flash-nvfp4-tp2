#!/usr/bin/env bash
# Fast checks for recipe clients and build commands; no GPU or model required.
set -euo pipefail
RECIPE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-python3}
cd "$RECIPE_DIR"
command -v "$PYTHON" >/dev/null
command -v shellcheck >/dev/null
command -v patch >/dev/null
bash -n recipe.sh build.sh serve.sh scripts/check-local.sh scripts/config.sh example.env
shellcheck -x recipe.sh build.sh serve.sh scripts/check-local.sh scripts/config.sh
for check_test in test_benchmark_inputs.py test_mixed_probe.py \
  test_verify_observations.py test_profile_trace_analysis.py \
  test_patch_direction.py test_operator_config.py test_lifecycle.py; do
  "$PYTHON" -m unittest discover -s tests -p "$check_test"
done
