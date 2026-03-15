#!/bin/sh
set -eu

exec python3 "$GC_PACK_DIR/scripts/github_intake_create_pr.py" "$@"
