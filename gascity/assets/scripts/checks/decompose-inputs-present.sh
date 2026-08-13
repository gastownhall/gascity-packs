#!/usr/bin/env bash
# Decompose-inputs-present FAIL-LOUD guard (canonical; platform bug dip-5hkepo).
#
# The compound-build/build-from-plan decompose (and prepare-decompose) step beads render their
# descriptions at INSTANTIATION (frozen, one pass) — before plan/plan-review produce their artifacts.
# When plan_path / plan_review_path default to "" and are never promoted to the workflow root, the
# frozen render carries an EMPTY path and decompose silently proceeds on empty inputs. The real fix is
# runtime-read (decompose.md/prepare-decompose.md read the root var store) + promotion (plan-review
# records gc.build.plan_review_path on root). This guard is the no-silent-failure backstop: it asserts
# BOTH paths are present+non-empty on the workflow ROOT before decompose proceeds, and exits non-zero
# with a clear single-line diagnostic otherwise. Fail-CLOSED (default-deny).
#
# The prepare-decompose OPERATOR step runs this guard and, on a non-zero exit, leaves prepare-decompose
# OPEN and BLOCKED (never closed) — because decompose depends on it, the task-decomposer never activates.
# That blocked-open barrier (not a plain [steps.check], which would close-fail and release on close) is
# what turns a silent empty-decompose into a loud halt.
#
# PREDICATE (pass iff BOTH hold), each key resolved as gc.build.<k> with fallback gc.var.<k>:
#   1. plan_path        is present and non-empty on the workflow-ROOT bead, AND
#   2. plan_review_path is present and non-empty on the workflow-ROOT bead.
# The gc.build/gc.var fallback matches build-artifact-valid.sh and covers both flows: build-from-plan
# promotes gc.build.plan_review_path via the plan-review stage, while a directly-launched
# build-from-decompose supplies the paths as gc.var.* launch vars.
#
# SOURCE OF TRUTH: the workflow-ROOT bead, resolved via gc.root_bead_id on the running step (a bead with
# no gc.root_bead_id IS its own root). Pattern mirrors plan-review-approved.sh.
set -euo pipefail

fail() {
    # Machine-readable refusal on stderr; the operator records it as the halt diagnostic.
    echo "decompose inputs unresolved: $*" >&2
    exit 1
}

BEAD_ID="${GC_BEAD_ID:-}"
[ -n "$BEAD_ID" ] || fail "GC_BEAD_ID not set — cannot resolve workflow root (fail-closed)"
command -v bd >/dev/null 2>&1 || fail "bd not on PATH (fail-closed)"
command -v jq >/dev/null 2>&1 || fail "jq not on PATH (fail-closed)"

meta_field() {
    # meta_field <json> <key> -> metadata[key] or empty (handles array-or-object `bd show` output)
    printf '%s\n' "$1" | jq -r --arg k "$2" '
        (if type == "array" then (.[0] // {}) else . end) | (.metadata[$k] // "")
    ' 2>/dev/null || true
}

# --- resolve the workflow ROOT bead ------------------------------------------
BEAD_JSON=$(bd show "$BEAD_ID" --json 2>/dev/null || true)
[ -n "$BEAD_JSON" ] || fail "bd show $BEAD_ID returned nothing — bead unreadable (fail-closed)"
ROOT_ID=$(meta_field "$BEAD_JSON" "gc.root_bead_id")
[ -n "$ROOT_ID" ] || ROOT_ID="$BEAD_ID"   # no root ref => the bead is its own workflow root

if [ "$ROOT_ID" = "$BEAD_ID" ]; then
    ROOT_JSON="$BEAD_JSON"
else
    ROOT_JSON=$(bd show "$ROOT_ID" --json 2>/dev/null || true)
    [ -n "$ROOT_JSON" ] || fail "bd show root $ROOT_ID returned nothing — workflow root unreadable (fail-closed)"
fi

# --- assert BOTH decompose inputs are present + non-empty on the root ---------
# Each key: gc.build.<k> is authoritative; fall back to gc.var.<k> (launch var).
PLAN_PATH=$(meta_field "$ROOT_JSON" "gc.build.plan_path")
[ -n "$PLAN_PATH" ] || PLAN_PATH=$(meta_field "$ROOT_JSON" "gc.var.plan_path")
PLAN_REVIEW_PATH=$(meta_field "$ROOT_JSON" "gc.build.plan_review_path")
[ -n "$PLAN_REVIEW_PATH" ] || PLAN_REVIEW_PATH=$(meta_field "$ROOT_JSON" "gc.var.plan_review_path")

MISSING=""
[ -n "$PLAN_PATH" ] || MISSING="plan_path"
if [ -z "$PLAN_REVIEW_PATH" ]; then
    [ -z "$MISSING" ] && MISSING="plan_review_path" || MISSING="$MISSING, plan_review_path"
fi

[ -z "$MISSING" ] \
    || fail "root=$ROOT_ID missing/empty: $MISSING (plan_path='$PLAN_PATH' plan_review_path='$PLAN_REVIEW_PATH'); decompose halts — its inputs were never promoted to the workflow root."

# --- happy path — decompose inputs resolved ----------------------------------
echo "decompose inputs present on workflow root $ROOT_ID: plan_path=$PLAN_PATH plan_review_path=$PLAN_REVIEW_PATH. Decompose may proceed."
exit 0
