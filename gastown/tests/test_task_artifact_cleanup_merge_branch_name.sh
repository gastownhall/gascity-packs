#!/usr/bin/env bash
set -euo pipefail

# Pins GH#553: task-artifact-cleanup's direct-merge branch-name gate used to
# require $BRANCH == "polecat/$WORK" exactly, refusing a legitimate no-force
# rework name (polecat/<item>-r<N>) before the script ever asked the remote
# anything. The fix (valid_direct_merge_branch, extracted from the real
# script below so this test cannot drift from what actually ships) accepts
# the exact name or a nonempty-all-digits -r<N> suffix, re-checks the
# candidate against the recorded metadata.branch verbatim (command
# substitution must not be able to normalize it), and still only ever
# matches THIS work item's name.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPT="$ROOT/gastown/assets/scripts/task-artifact-cleanup.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# Extract just the self-contained helper functions the gate needs, between
# the two markers below, rather than copying their bodies by hand: a test
# that duplicated the logic could pass while the shipped function drifted.
FRAGMENT=$(sed -n '/^artifact_git_common_dir() {/,/^task_artifact_path_shape() {/p' "$SCRIPT" | \
    sed '$d')
if ! printf '%s\n' "$FRAGMENT" | grep -q '^valid_direct_merge_branch() {'; then
    fail "valid_direct_merge_branch is not defined in $SCRIPT: the fix for GH#553 is missing or the extraction markers drifted"
fi
eval "$FRAGMENT"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
RIG_ROOT="$tmp/rig"
mkdir -p "$RIG_ROOT"
git -C "$RIG_ROOT" init -q

WORK="item-123"

check() {
    local label="$1" branch="$2" meta_branch="$3" want="$4"
    META=$(printf '{"branch":"%s"}' "$meta_branch")
    if valid_direct_merge_branch "$branch"; then
        got=accept
    else
        got=reject
    fi
    [ "$got" = "$want" ] || fail "$label: valid_direct_merge_branch($branch) = $got, want $want"
}

# The exact name, unchanged behavior.
check "exact name"                  "polecat/item-123"      "polecat/item-123"      accept

# Revision names the issue asks to accept.
check "revision -r1"                "polecat/item-123-r1"   "polecat/item-123-r1"   accept
check "revision -r12"                "polecat/item-123-r12"  "polecat/item-123-r12"  accept
check "revision -r0"                "polecat/item-123-r0"   "polecat/item-123-r0"   accept
check "revision -r001 (leading zero)" "polecat/item-123-r001" "polecat/item-123-r001" accept

# Malformed revision suffixes must still be refused.
check "empty suffix (-r alone)"     "polecat/item-123-r"    "polecat/item-123-r"    reject
check "non-numeric suffix"          "polecat/item-123-rabc" "polecat/item-123-rabc" reject
check "signed suffix"               "polecat/item-123-r-1"  "polecat/item-123-r-1"  reject

# An unrelated item's branch, with or without a revision suffix, must stay
# refused — the fix narrows what one specific item's name may look like, it
# does not loosen the match to any polecat/* branch.
check "unrelated item"              "polecat/item-999"      "polecat/item-999"      reject
check "unrelated item, revision"    "polecat/item-999-r1"   "polecat/item-999-r1"   reject

# A dot in the item id must not let a glob-like match slip through on a
# different but visually similar name.
check "item with a dot, mismatched" "polecat/item.123"      "polecat/item.123"      reject

# Defense-in-depth: the candidate must match what the metadata actually
# recorded, not just look right syntactically (guards command-substitution
# normalization of the recorded value).
check "candidate disagrees with metadata" "polecat/item-123-r1" "polecat/item-123-r2" reject

echo "PASS: all task-artifact-cleanup direct-merge branch-name cases behaved as expected"
