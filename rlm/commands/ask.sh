#!/bin/sh
set -eu

if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc rlm ask: missing Gas City pack context" >&2
  exit 1
fi

RUNTIME_DIR="${GC_PACK_STATE_DIR:-${GC_CITY_RUNTIME_DIR:-$GC_CITY_PATH/.gc/runtime}/packs/rlm}"
if [ ! -x "$RUNTIME_DIR/venv/bin/python" ] && [ -x "$GC_CITY_PATH/.gc/rlm/venv/bin/python" ]; then
  RUNTIME_DIR="$GC_CITY_PATH/.gc/rlm"
fi
PYTHON="$RUNTIME_DIR/venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "gc rlm ask: runtime not installed; run 'gc rlm install' first" >&2
  exit 2
fi

exec "$PYTHON" "$GC_PACK_DIR/scripts/rlm_ask.py" "$@"
