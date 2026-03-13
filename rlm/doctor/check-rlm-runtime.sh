#!/bin/sh
set -eu

if [ -z "${GC_CITY_PATH:-}" ]; then
  echo "missing GC_CITY_PATH"
  echo "Pack doctor checks run only inside a Gas City workspace."
  exit 2
fi

RUNTIME_DIR="$GC_CITY_PATH/.gc/rlm"
PYTHON="$RUNTIME_DIR/venv/bin/python"

if [ ! -f "$RUNTIME_DIR/config.toml" ] || [ ! -x "$PYTHON" ]; then
  echo "RLM runtime not installed"
  echo "Run gc rlm install to create .gc/rlm/ for this city."
  exit 1
fi

"$PYTHON" - <<'PY'
from importlib.metadata import version
print(f"rlms {version('rlms')} installed")
PY
