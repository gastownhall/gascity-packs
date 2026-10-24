#!/bin/sh
set -eu

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc slack events-health: missing Gas City pack context" >&2
  exit 2
fi

exec python3 "$GC_PACK_DIR/scripts/slack_events_health.py" "$@"
