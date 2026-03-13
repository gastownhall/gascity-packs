#!/bin/sh
set -eu

if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc rlm ask: missing Gas City pack context" >&2
  exit 1
fi

PYTHON="$GC_CITY_PATH/.gc/rlm/venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "gc rlm ask: runtime not installed; run 'gc rlm install' first" >&2
  exit 2
fi

exec "$PYTHON" "$GC_PACK_DIR/scripts/rlm_ask.py" "$@"
