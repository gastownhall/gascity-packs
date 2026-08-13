#!/usr/bin/env bash
# Decompose plan-review-approved PRECONDITION guard (canonical; platform bug dip-duj3e6).
#
# Makes CODED the fail-safe that was EMERGENT on 2026-08-03: the compound-build decompose step gated
# only on `needs=["plan-review"]` (step-DONE, not outcome) + a post-output build-artifact-valid.sh
# check on its OWN output — NO input-status gate. When the plan-review loop hard-failed (6/6 native
# cap, plan NOT approved) the decompose edge still released and a task-decomposer went active; only
# the decomposer AGENT's judgment refused. This makes it CODE: hard-refuse to decompose unless the
# plan-review terminated APPROVED on the workflow ROOT bead. Fail-CLOSED (default-deny).
#
# This is the check predicate for the `plan-review-approved-gate` operator step (build-base.formula.toml,
# build-from-plan-base.formula.toml). The GATE, not this script, owns the barrier: on a non-zero exit the
# gate step is left OPEN and BLOCKED (never closed), so the plain `blocks` edge to decompose never fires
# and the task-decomposer cannot activate on an unapproved plan. The proven DIP rig interim (dip-b78hkn)
# validated this exact mechanism; this is its canonical promotion.
#
# PREDICATE (pass iff BOTH hold):
#   1. gc.build.plan_review_status == "approved" on the workflow-ROOT bead, AND
#   2. no plan-review loop/finalize bead under that root recorded gc.outcome=fail.
# Any non-approved / MISSING / unreadable status, or a failing plan-review loop => hard refuse
# (exit non-zero). The gate operator interprets that exit and holds the gate blocked-open.
#
# SOURCE OF TRUTH: gc.build.plan_review_status on the workflow-ROOT bead, resolved via gc.root_bead_id
# on the running step (a bead with no gc.root_bead_id IS its own root). NEVER the per-iteration
# plan-review report artifact — mid-loop it reads draft/pass and is the stale-status trap.
#
# Mirror of design-review-approved.sh (which gates the plan-review LOOP by reading design_review.verdict);
# this gates the DECOMPOSE step by reading gc.build.plan_review_status on the workflow ROOT.
set -euo pipefail

fail() {
    # Machine-readable refusal on stderr; the dispatcher records it as attempt context.
    echo "decompose precondition FAILED: $*" >&2
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

# --- gate 1: AUTHORITATIVE plan-review status on the workflow root ------------
PLAN_REVIEW_STATUS=$(meta_field "$ROOT_JSON" "gc.build.plan_review_status")
[ -n "$PLAN_REVIEW_STATUS" ] || PLAN_REVIEW_STATUS="MISSING"
[ "$PLAN_REVIEW_STATUS" = "approved" ] \
    || fail "root=$ROOT_ID plan_review_status=$PLAN_REVIEW_STATUS, plan NOT approved — decompose refused, build halts at plan-review."

# --- gate 2 (hardening): refuse if a plan-review loop/finalize bead failed ----
# The plan-review finalize/loop beads carry gc.step_ref ending in ".plan-review" (the finalize, e.g.
# "compound-build.plan-review") or the "...plan-review...loop" scope (the loop bead); per-iteration and
# *.spec beads are excluded. If any recorded gc.outcome=fail the loop did not converge — refuse even if
# the status field somehow reads approved (defense-in-depth for the stale-status trap). Generalized
# across methodology packs (build-base / compound-build / ...), not pinned to one loop name.
LOOP_FAIL=$(bd list --all --metadata-field "gc.root_bead_id=$ROOT_ID" --json --limit=0 2>/dev/null \
    | jq -r '
        (if type == "array" then . else [.] end)
        | [ .[]
            | .metadata as $m
            | (($m["gc.step_ref"] // "")) as $sr
            | select(
                ($sr | endswith(".plan-review"))
                or ($sr == "plan-review")
                or ( ($sr | contains(".plan-review."))
                     and ($sr | contains("loop"))
                     and (($sr | contains("iteration")) | not)
                     and (($sr | endswith(".spec")) | not) )
              )
            | select((($m["gc.outcome"] // "")) == "fail")
            | .id
          ] | (first // "")
    ' 2>/dev/null || true)

[ -z "$LOOP_FAIL" ] \
    || fail "plan-review loop bead $LOOP_FAIL recorded gc.outcome=fail on root $ROOT_ID — plan-review did not converge, decompose refused, build halts at plan-review."

# --- SILENT-ON-APPROVED: happy path — decompose proceeds unchanged ------------
echo "decompose precondition OK: plan_review_status=approved on workflow root $ROOT_ID; no plan-review loop failure. Decompose may proceed."
exit 0
