#!/bin/sh
set -eu

if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc rlm uninstall: missing Gas City pack context" >&2
  exit 1
fi

PYTHON="$GC_CITY_PATH/.gc/rlm/venv/bin/python"
if [ -x "$PYTHON" ]; then
  exec "$PYTHON" "$GC_PACK_DIR/scripts/rlm_uninstall.py" "$@"
fi

exec python3 "$GC_PACK_DIR/scripts/rlm_uninstall.py" "$@"
