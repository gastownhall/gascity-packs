#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.com
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.com

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

REPO="$TEST_ROOT/repo"
WT="$TEST_ROOT/worktree"
SCRIPT="$ROOT/gastown/assets/scripts/worktree-setup.sh"

git init -q "$REPO"
printf 'node_modules/\n' > "$REPO/.gitignore"
git -C "$REPO" add .gitignore
git -C "$REPO" commit -qm initial

sh "$SCRIPT" "$REPO" "$WT" worker
mkdir -p "$WT/.gc"
printf '{}\n' > "$WT/.gc/runtime.json"

status=$(git -C "$WT" status --porcelain)
[[ -z "$status" ]] || fail "runtime artifacts dirty the worktree: $status"
cmp "$REPO/.gitignore" "$WT/.gitignore" || fail "tracked .gitignore changed"

EXCLUDE=$(git -C "$WT" rev-parse --git-path info/exclude)
case "$EXCLUDE" in
    /*) ;;
    *) EXCLUDE="$WT/$EXCLUDE" ;;
esac
[[ $(grep -cxF '.gc/' "$EXCLUDE") -eq 1 ]] || fail "missing local .gc/ exclude"
cp "$EXCLUDE" "$TEST_ROOT/exclude-before"

sh "$SCRIPT" "$REPO" "$WT" worker
cmp "$TEST_ROOT/exclude-before" "$EXCLUDE" || fail "excludes changed on rerun"
status=$(git -C "$WT" status --porcelain)
[[ -z "$status" ]] || fail "setup rerun dirtied the worktree: $status"

printf 'user work\n' > "$WT/user.txt"
status=$(git -C "$WT" status --porcelain)
[[ "$status" == '?? user.txt' ]] || fail "user work must remain visible: $status"

echo "PASS: worktree runtime excludes are local and idempotent"
