#!/usr/bin/env bash
# Deterministic Graph-v2 completion for Gastown polecat workflow stages.
#
# Agent prose must not reconstruct step identity or provenance. This command
# resolves exactly one current-session step, proves its workflow root and input
# convoy, records gc.outcome=pass, and verifies the durable result.

set -u -o pipefail

EXIT_USAGE=2
EXIT_INDETERMINATE=75

ACTION=${1:-}
if [[ -n "$ACTION" ]]; then
    shift
fi

CONVOY_ID=""
STEP_REF=""

usage() {
    cat >&2 <<'EOF'
Usage:
  gc gastown polecat-step complete \
    --convoy ID --step-ref mol-polecat-work.STEP
EOF
}

while (($#)); do
    case "$1" in
        --convoy)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            CONVOY_ID=$2
            shift 2
            ;;
        --step-ref)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            STEP_REF=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "polecat-step: unknown argument: $1" >&2
            usage
            exit "$EXIT_USAGE"
            ;;
    esac
done

if (($#)) || [[ "$ACTION" != "complete" ]] ||
   [[ -z "$CONVOY_ID" || -z "$STEP_REF" ]]; then
    usage
    exit "$EXIT_USAGE"
fi

safe_atom() {
    local value=$1
    [[ -n "$value" ]] || return 1
    [[ "$value" != *$'\n'* && "$value" != *$'\r'* &&
       "$value" != *$'\t'* ]]
}

safe_atom "$CONVOY_ID" && safe_atom "$STEP_REF" || {
    echo "polecat-step: unsafe empty/control-character argument" >&2
    exit "$EXIT_USAGE"
}

case "$STEP_REF" in
    mol-polecat-work.load-context|\
    mol-polecat-work.workspace-setup|\
    mol-polecat-work.preflight-tests|\
    mol-polecat-work.implement|\
    mol-polecat-work.self-review)
        ;;
    *)
        echo "polecat-step: unsupported workflow step: $STEP_REF" >&2
        exit "$EXIT_USAGE"
        ;;
esac

GC_CMD=${GC_BIN:-}
if [[ -z "$GC_CMD" ]]; then
    GC_CMD=$(command -v gc 2>/dev/null || true)
fi
if [[ -z "$GC_CMD" || ! -x "$GC_CMD" ]]; then
    echo "polecat-step: the invoking gc executable is unavailable" >&2
    exit "$EXIT_INDETERMINATE"
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "polecat-step: jq is required" >&2
    exit "$EXIT_INDETERMINATE"
fi

run_gc_bd() {
    local command=("$GC_CMD" "bd")
    "${command[@]}" "$@"
}

indeterminate() {
    echo "POLECAT_STEP_INDETERMINATE: $*" >&2
    echo "The workflow step was not intentionally advanced; inspect and retry." >&2
    exit "$EXIT_INDETERMINATE"
}

ACTOR=${BEADS_ACTOR:-${GC_SESSION_NAME:-${GC_SESSION_ID:-${GC_ALIAS:-${GC_AGENT:-}}}}}
safe_atom "$ACTOR" ||
    indeterminate "the current session assignee is unavailable or unsafe"

classify_root() {
    local root_id=$1 root_json classification
    safe_atom "$root_id" || return 2
    root_json=$(run_gc_bd show "$root_id" --json 2>/dev/null) || return 2
    classification=$(printf '%s' "$root_json" | jq -er \
        --arg id "$root_id" --arg convoy "$CONVOY_ID" '
        if type != "array" or length != 1 or .[0].id != $id or
           .[0].metadata["gc.kind"] != "workflow" or
           .[0].metadata["gc.formula_contract"] != "graph.v2" or
           ((.[0].metadata | has("gc.formula_name")) and
            .[0].metadata["gc.formula_name"] != "mol-polecat-work") or
           (.[0].metadata["gc.input_convoy_id"] | type) != "string" or
           (.[0].metadata["gc.input_convoy_id"] | length) == 0
        then error("root identity or Graph-v2 provenance mismatch")
        elif .[0].metadata["gc.input_convoy_id"] == $convoy
        then "match"
        else "other"
        end' 2>/dev/null) || return 2
    case "$classification" in
        match) return 0 ;;
        other) return 1 ;;
        *) return 2 ;;
    esac
}

validate_step() {
    local step_json=$1 expected_status=$2 expected_outcome=$3
    printf '%s' "$step_json" | jq -er \
        --arg actor "$ACTOR" --arg ref "$STEP_REF" \
        --arg status "$expected_status" --arg outcome "$expected_outcome" '
        if type == "array" and length == 1 and
           (.[0].id | type) == "string" and (.[0].id | length) > 0 and
           .[0].status == $status and .[0].assignee == $actor and
           .[0].metadata["gc.step_ref"] == $ref and
           (.[0].metadata["gc.root_bead_id"] | type) == "string" and
           (.[0].metadata["gc.root_bead_id"] | length) > 0 and
           (($outcome == "__empty__" and
             (((.[0].metadata | has("gc.outcome")) | not) or
              .[0].metadata["gc.outcome"] == "")) or
            ($outcome != "__empty__" and
             .[0].metadata["gc.outcome"] == $outcome))
        then [.[0].id, .[0].metadata["gc.root_bead_id"]] | @tsv
        else error("step identity/state mismatch")
        end' 2>/dev/null
}

find_replay() {
    local closed_json matches candidate_id candidate_root candidate_json
    local validated candidate_count=0

    closed_json=$(run_gc_bd list --assignee "$ACTOR" --status=closed \
        --limit=0 --json 2>/dev/null) || return 1
    matches=$(printf '%s' "$closed_json" | jq -ce \
        --arg actor "$ACTOR" --arg ref "$STEP_REF" '
        if type == "array"
        then [.[] |
          select(.status == "closed" and .assignee == $actor and
                 .metadata["gc.step_ref"] == $ref and
                 .metadata["gc.outcome"] == "pass" and
                 (.id | type) == "string" and (.id | length) > 0 and
                 (.metadata["gc.root_bead_id"] | type) == "string" and
                 (.metadata["gc.root_bead_id"] | length) > 0)]
        else error("closed step list is not an array")
        end' 2>/dev/null) || return 1

    while IFS=$'\t' read -r candidate_id candidate_root; do
        [[ -n "$candidate_id" && -n "$candidate_root" ]] || continue
        candidate_json=$(run_gc_bd show "$candidate_id" --json 2>/dev/null) ||
            return 1
        validated=$(validate_step "$candidate_json" "closed" "pass") ||
            return 1
        [[ "$validated" == "$candidate_id"$'\t'"$candidate_root" ]] ||
            return 1
        classify_root "$candidate_root"
        case $? in
            0)
                candidate_count=$((candidate_count + 1))
                STEP_BEAD_ID=$candidate_id
                ROOT_BEAD_ID=$candidate_root
                ;;
            1)
                # A canonically verified root for another input convoy is not
                # this invocation's replay candidate.
                ;;
            *)
                # Unreadable, malformed, or wrong-formula roots make the
                # replay set indeterminate; they must not be silently ignored.
                return 1
                ;;
        esac
    done < <(printf '%s' "$matches" | jq -r '
        .[] | [.id, .metadata["gc.root_bead_id"]] | @tsv')

    [[ "$candidate_count" -eq 1 ]]
}

STEP_LIST_JSON=$(run_gc_bd list --assignee "$ACTOR" --status=in_progress \
    --limit=0 --json 2>/dev/null) ||
    indeterminate "could not list the current session's in-progress steps"
STEP_MATCHES=$(printf '%s' "$STEP_LIST_JSON" | jq -ce \
    --arg actor "$ACTOR" --arg ref "$STEP_REF" '
    if type == "array"
    then [.[] |
      select(.status == "in_progress" and .assignee == $actor and
             .metadata["gc.step_ref"] == $ref)]
    else error("step list is not an array")
    end' 2>/dev/null) ||
    indeterminate "the current session's step list was malformed"
STEP_COUNT=$(printf '%s' "$STEP_MATCHES" | jq -er 'length' 2>/dev/null) ||
    indeterminate "could not count matching workflow steps"

if [[ "$STEP_COUNT" == "0" ]]; then
    find_replay ||
        indeterminate "no unique closed/pass replay matches this step and convoy"
    printf 'POLECAT_STEP_COMPLETE step=%s ref=%s root=%s convoy=%s replay=true\n' \
        "$STEP_BEAD_ID" "$STEP_REF" "$ROOT_BEAD_ID" "$CONVOY_ID"
    exit 0
fi
if [[ "$STEP_COUNT" != "1" ]]; then
    indeterminate "expected one claimed step, found $STEP_COUNT"
fi

STEP_BEAD_ID=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].id' 2>/dev/null) ||
    indeterminate "the claimed step has no exact id"
safe_atom "$STEP_BEAD_ID" ||
    indeterminate "the claimed step id is unsafe"
STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not read the exact claimed step"
VALIDATED=$(validate_step "$STEP_JSON" "in_progress" "__empty__") ||
    indeterminate "claimed step identity, ownership, or state did not verify"
IFS=$'\t' read -r VERIFIED_STEP_ID ROOT_BEAD_ID <<<"$VALIDATED"
[[ "$VERIFIED_STEP_ID" == "$STEP_BEAD_ID" ]] ||
    indeterminate "claimed step id changed during verification"
classify_root "$ROOT_BEAD_ID"
[[ $? -eq 0 ]] ||
    indeterminate "workflow root or input-convoy provenance did not verify"

if ! run_gc_bd update "$STEP_BEAD_ID" \
     --set-metadata gc.outcome=pass \
     --status=closed \
     --append-notes "Completed through validated Gastown polecat-step protocol: $STEP_REF"; then
    indeterminate "could not persist closed/pass on the exact claimed step"
fi

VERIFY_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not read back the completed step"
VERIFY_RESULT=$(validate_step "$VERIFY_JSON" "closed" "pass") ||
    indeterminate "completed step did not read back as exact closed/pass"
[[ "$VERIFY_RESULT" == "$STEP_BEAD_ID"$'\t'"$ROOT_BEAD_ID" ]] ||
    indeterminate "completed step provenance changed during readback"
classify_root "$ROOT_BEAD_ID"
[[ $? -eq 0 ]] ||
    indeterminate "workflow root changed during completion readback"

printf 'POLECAT_STEP_COMPLETE step=%s ref=%s root=%s convoy=%s replay=false\n' \
    "$STEP_BEAD_ID" "$STEP_REF" "$ROOT_BEAD_ID" "$CONVOY_ID"
