#!/bin/sh
set -eu

exec python3 "$GC_PACK_DIR/scripts/github_intake_comment_issue.py" "$@"
