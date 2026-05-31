#!/bin/sh
set -eu

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc slack publish-to-channel: missing Gas City pack context" >&2
  exit 1
fi

exec python3 "$GC_PACK_DIR/scripts/slack_chat_publish_to_channel.py" "$@"
