#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "gstack-shared-worktree: $*" >&2
  exit 1
}

command -v gc >/dev/null 2>&1 || fail "gc is required on PATH"
command -v git >/dev/null 2>&1 || fail "git is required on PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 is required on PATH"

metadata_value() {
  printf '%s' "$1" | python3 -c '
import json
import sys

key = sys.argv[1]
data = json.load(sys.stdin)
if isinstance(data, list):
    data = data[0] if data else {}
metadata = data.get("metadata") if isinstance(data, dict) else {}
value = metadata.get(key, "") if isinstance(metadata, dict) else ""
print(value if isinstance(value, str) else "")
' "$2"
}

if [ "$#" -eq 0 ]; then
  BEAD_ID="${GC_BEAD_ID:-}"
  [ -n "$BEAD_ID" ] || fail "GC_BEAD_ID is required in formula-check mode"
  STEP_JSON="$(gc bd show "$BEAD_ID" --json 2>/dev/null)" || fail "gc bd show $BEAD_ID failed"
  ROOT_ID="$(metadata_value "$STEP_JSON" "gc.root_bead_id")"
  [ -n "$ROOT_ID" ] || fail "step $BEAD_ID is missing gc.root_bead_id"
  ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>/dev/null)" || fail "gc bd show $ROOT_ID failed"
  LAUNCHER_RAW="$(metadata_value "$ROOT_JSON" "gc.work_dir")"
  DRAIN_CONTROL_ID="$(metadata_value "$ROOT_JSON" "gc.drain_control_id")"
  SOURCE_ANCHOR_ID="$(metadata_value "$ROOT_JSON" "gc.drain_member_id")"
  DRAIN_INDEX="$(metadata_value "$ROOT_JSON" "gc.drain_index")"
  case "$DRAIN_INDEX" in
    "" | *[!0-9]*) fail "workflow root $ROOT_ID has invalid gc.drain_index: $DRAIN_INDEX" ;;
  esac
elif [ "$#" -eq 3 ]; then
  LAUNCHER_RAW="$1"
  DRAIN_CONTROL_ID="$2"
  SOURCE_ANCHOR_ID="$3"
else
  fail "usage: prepare-shared-worktree.sh [<launcher-root> <drain-control-id> <source-anchor-id>]"
fi

case "$DRAIN_CONTROL_ID" in
  "" | *[!A-Za-z0-9._-]*) fail "invalid drain control id: $DRAIN_CONTROL_ID" ;;
esac
case "$SOURCE_ANCHOR_ID" in
  "" | *[!A-Za-z0-9._-]*) fail "invalid source anchor id: $SOURCE_ANCHOR_ID" ;;
esac

WORK_DIR="$(cd "$LAUNCHER_RAW" 2>/dev/null && pwd -P)" || fail "workflow work dir does not exist: $LAUNCHER_RAW"
REPO_ROOT_RAW="$(git -C "$WORK_DIR" rev-parse --show-toplevel 2>/dev/null)" || fail "workflow work dir is not inside a git worktree: $WORK_DIR"
REPO_ROOT="$(cd "$REPO_ROOT_RAW" 2>/dev/null && pwd -P)" || fail "repository root does not exist: $REPO_ROOT_RAW"
LAUNCHER_ROOT="$REPO_ROOT"

canonical_common_dir() {
  repo="$1"
  raw="$(git -C "$repo" rev-parse --git-common-dir 2>/dev/null)" || return 1
  python3 - "$repo" "$raw" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1])
path = Path(sys.argv[2])
if not path.is_absolute():
    path = repo / path
print(path.resolve(strict=True))
PY
}

LAUNCHER_COMMON_DIR="$(canonical_common_dir "$LAUNCHER_ROOT")" || fail "cannot resolve launcher git common dir"
WORKTREE="$(dirname "$LAUNCHER_ROOT")/.$(basename "$LAUNCHER_ROOT")-gstack-worktrees/gstack-shared-$DRAIN_CONTROL_ID"

SHOW_JSON="$(gc bd show "$SOURCE_ANCHOR_ID" --json 2>/dev/null)" || fail "gc bd show $SOURCE_ANCHOR_ID failed"
CURRENT_WORK_DIR="$(printf '%s' "$SHOW_JSON" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
if isinstance(data, list):
    data = data[0] if data else {}
metadata = data.get("metadata") if isinstance(data, dict) else {}
value = metadata.get("work_dir", "") if isinstance(metadata, dict) else ""
print(value if isinstance(value, str) else "")
')"

if [ -n "$CURRENT_WORK_DIR" ]; then
  CURRENT_WORK_DIR="$(cd "$CURRENT_WORK_DIR" 2>/dev/null && pwd -P)" || fail "source anchor $SOURCE_ANCHOR_ID has a missing work_dir"
  [ "$CURRENT_WORK_DIR" = "$WORKTREE" ] || fail "source anchor $SOURCE_ANCHOR_ID points at a different worktree: $CURRENT_WORK_DIR"
fi

if [ ! -e "$WORKTREE" ]; then
  [ -z "$CURRENT_WORK_DIR" ] || fail "recorded shared worktree is missing: $WORKTREE"
  mkdir -p "$(dirname "$WORKTREE")"
  git -C "$LAUNCHER_ROOT" worktree add --detach "$WORKTREE" HEAD >/dev/null || fail "failed to create shared worktree: $WORKTREE"
fi

[ -d "$WORKTREE" ] || fail "shared worktree path is not a directory: $WORKTREE"
WORKTREE="$(cd "$WORKTREE" && pwd -P)"
[ "$WORKTREE" != "$LAUNCHER_ROOT" ] || fail "shared worktree must differ from launcher checkout"
INSIDE="$(git -C "$WORKTREE" rev-parse --is-inside-work-tree 2>/dev/null)" || fail "shared path is not a git worktree: $WORKTREE"
[ "$INSIDE" = "true" ] || fail "shared path is not a git worktree: $WORKTREE"
WORKTREE_ROOT_RAW="$(git -C "$WORKTREE" rev-parse --show-toplevel 2>/dev/null)" || fail "cannot resolve shared worktree root"
WORKTREE_ROOT="$(cd "$WORKTREE_ROOT_RAW" && pwd -P)"
[ "$WORKTREE_ROOT" = "$WORKTREE" ] || fail "shared path is not the worktree root: path=$WORKTREE root=$WORKTREE_ROOT"
WORKTREE_COMMON_DIR="$(canonical_common_dir "$WORKTREE")" || fail "cannot resolve shared worktree git common dir"
[ "$WORKTREE_COMMON_DIR" = "$LAUNCHER_COMMON_DIR" ] || fail "shared worktree belongs to a different repository"

gc bd update "$SOURCE_ANCHOR_ID" --set-metadata "work_dir=$WORKTREE" >/dev/null || fail "failed to persist work_dir on $SOURCE_ANCHOR_ID"
UPDATED_JSON="$(gc bd show "$SOURCE_ANCHOR_ID" --json 2>/dev/null)" || fail "failed to read back source anchor $SOURCE_ANCHOR_ID"
RECORDED_WORK_DIR="$(printf '%s' "$UPDATED_JSON" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
if isinstance(data, list):
    data = data[0] if data else {}
metadata = data.get("metadata") if isinstance(data, dict) else {}
value = metadata.get("work_dir", "") if isinstance(metadata, dict) else ""
print(value if isinstance(value, str) else "")
')"
[ "$RECORDED_WORK_DIR" = "$WORKTREE" ] || fail "source anchor $SOURCE_ANCHOR_ID did not retain the shared worktree"

printf '%s\n' "$WORKTREE"
