#!/usr/bin/env bash
set -euo pipefail

# Plan-review approval gate for the build graphs.
#
# `decompose` (and through it the implementation drain) only `needs` the
# plan-review stage, and a `needs` edge is satisfied by closure alone. Without
# this gate a plan-review closed with `changes_required` released
# decomposition and worktree creation exactly as an approved one did. The
# compiler rejects drain combined with gate, so the enforcement sits on the
# plan-review step itself as a [steps.check], like the producer-stage
# build-artifact-valid.sh gates beside it.
#
# The reviewer records the verdict on the workflow root bead as
#   gc.build.plan_review_status=<approved|questions|changes_required|blocked>
# (the same root key the superpowers and compound-engineering plan-review
# expansions already stamp). Only `approved` passes. Any other value, or a
# missing value, fails closed: the check loop re-dispatches the review within
# max_attempts, and exhaustion closes the stage with gc.outcome=fail.
#
# Reads only `gc bd show` on ids it already holds ($GC_BEAD_ID, then its
# gc.root_bead_id), so it works on a city that relocates the graph class
# without a collection query. Failures print one machine-readable line on
# stderr; the dispatcher records it in gc.attempt_log for the next attempt.
# This gate never prompts.

fail() {
  echo "plan-review-check: $*" >&2
  exit 1
}

BEAD_ID="${GC_BEAD_ID:-}"
[ -n "$BEAD_ID" ] || fail "GC_BEAD_ID is required"
command -v gc >/dev/null 2>&1 || fail "gc is required on PATH"
command -v jq >/dev/null 2>&1 || fail "jq is required on PATH"

metadata_value() {
  # metadata_value <json> <key> -> prints metadata[key] or empty
  printf '%s\n' "$1" | jq -r --arg key "$2" '
    (if type == "array" then (.[0] // {}) else . end)
    | .metadata[$key] // empty
  ' 2>/dev/null || true
}

SHOW_JSON="$(gc bd show "$BEAD_ID" --json 2>/dev/null)" || fail "gc bd show $BEAD_ID failed"

ROOT_ID="$(metadata_value "$SHOW_JSON" "gc.root_bead_id")"
ROOT_JSON="$SHOW_JSON"
if [ -n "$ROOT_ID" ] && [ "$ROOT_ID" != "$BEAD_ID" ]; then
  ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>/dev/null)" || fail "gc bd show $ROOT_ID failed"
fi
ROOT_ID="${ROOT_ID:-$BEAD_ID}"

STATUS="$(metadata_value "$ROOT_JSON" "gc.build.plan_review_status")"

case "$STATUS" in
  approved)
    echo "Plan review approved: gc.build.plan_review_status=approved on workflow root $ROOT_ID"
    exit 0
    ;;
  "")
    fail "no plan-review verdict recorded: gc.build.plan_review_status is missing on workflow root $ROOT_ID. The plan-review stage must record approved on the workflow root before it can close; decomposition stays blocked until it does."
    ;;
  *)
    fail "plan review not approved: gc.build.plan_review_status=$STATUS on workflow root $ROOT_ID. Decomposition stays blocked until the plan-review stage records approved."
    ;;
esac
