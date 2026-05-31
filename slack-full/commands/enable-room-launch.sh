#!/bin/sh
set -eu

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc slack enable-room-launch: missing Gas City pack context" >&2
  exit 1
fi

exec "$GC_PACK_DIR/cli/gc-slack-cli" enable-room-launch "$@"
