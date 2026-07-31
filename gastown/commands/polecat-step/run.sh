#!/usr/bin/env bash
# Deterministic Graph-v2 execution and completion for Gastown polecat stages.
#
# Agent prose must not reconstruct step identity, provenance, or task-artifact
# ownership. This command resolves exactly one current-session step and proves
# its workflow root and input convoy. The read-only exec action additionally
# proves the convoy's sole source and exact artifact worktree before replacing
# itself with caller-supplied argv there. The complete action records
# gc.outcome=pass and verifies the durable result.

set -u -o pipefail

# Repository-selection overrides are unsafe here: they can make validation
# inspect one repository while argv later operates on another. Keep normal Git
# transport/credential configuration, but remove every inherited repo-local
# selector before the first Git probe and leave it absent for the child.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_NAMESPACE
unset GIT_CONFIG GIT_CONFIG_SYSTEM GIT_CONFIG_GLOBAL GIT_CONFIG_NOSYSTEM
unset GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT
unset GIT_IMPLICIT_WORK_TREE GIT_GRAFT_FILE GIT_NO_REPLACE_OBJECTS
unset GIT_REPLACE_REF_BASE GIT_PREFIX GIT_INTERNAL_SUPER_PREFIX GIT_SUPER_PREFIX
unset GIT_SHALLOW_FILE GIT_QUARANTINE_PATH
unset GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
for git_config_name in "${!GIT_CONFIG_KEY_@}" "${!GIT_CONFIG_VALUE_@}"; do
    unset "$git_config_name"
done
unset git_config_name

# These names are command-owned outputs, never trusted inputs from a provider
# or a previous process generation.
unset GC_POLECAT_SOURCE_ID GC_POLECAT_SOURCE_BRANCH
unset GC_POLECAT_ARTIFACT_DIR GC_POLECAT_CONVOY_ID

EXIT_USAGE=2
EXIT_INDETERMINATE=75

ACTION=${1:-}
if [[ -n "$ACTION" ]]; then
    shift
fi

CONVOY_ID=""
STEP_REF=""
BLOCK_CODE=""
BLOCK_REASON=""
CONFLICT_STAGE_EXEC=false
declare -a EXEC_ARGV=()

usage() {
    cat >&2 <<'EOF'
Usage:
  gc gastown polecat-step exec \
    --convoy ID --step-ref mol-polecat-work.STEP -- COMMAND [ARG...]
  gc gastown polecat-step block \
    --convoy ID --step-ref mol-polecat-work.STEP \
    --code MACHINE_CODE --reason TEXT
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
        --reason)
            [[ $# -ge 2 && -z "$BLOCK_REASON" ]] || {
                usage
                exit "$EXIT_USAGE"
            }
            BLOCK_REASON=$2
            shift 2
            ;;
        --code)
            [[ $# -ge 2 && -z "$BLOCK_CODE" ]] || {
                usage
                exit "$EXIT_USAGE"
            }
            BLOCK_CODE=$2
            shift 2
            ;;
        --)
            shift
            EXEC_ARGV=("$@")
            set --
            break
            ;;
        *)
            echo "polecat-step: unknown argument: $1" >&2
            usage
            exit "$EXIT_USAGE"
            ;;
    esac
done

if (($#)) || [[ -z "$CONVOY_ID" || -z "$STEP_REF" ]]; then
    usage
    exit "$EXIT_USAGE"
fi
case "$ACTION" in
    complete)
        if ((${#EXEC_ARGV[@]})) ||
           [[ -n "$BLOCK_CODE" || -n "$BLOCK_REASON" ]]; then
            usage
            exit "$EXIT_USAGE"
        fi
        ;;
    exec)
        if ((${#EXEC_ARGV[@]} == 0)) ||
           [[ -n "$BLOCK_CODE" || -n "$BLOCK_REASON" ]]; then
            usage
            exit "$EXIT_USAGE"
        fi
        ;;
    block)
        if ((${#EXEC_ARGV[@]})) ||
           [[ -z "$BLOCK_CODE" || -z "$BLOCK_REASON" ]] ||
           ((${#BLOCK_CODE} > 128)) || ((${#BLOCK_REASON} > 2048)); then
            usage
            exit "$EXIT_USAGE"
        fi
        ;;
    *)
        usage
        exit "$EXIT_USAGE"
        ;;
esac

safe_atom() {
    local value=$1
    local LC_ALL=C
    [[ -n "$value" ]] || return 1
    [[ "$value" != *[[:cntrl:]]* ]]
}

safe_atom "$CONVOY_ID" && safe_atom "$STEP_REF" || {
    echo "polecat-step: unsafe empty/control-character argument" >&2
    exit "$EXIT_USAGE"
}
if [[ "$ACTION" == "block" ]]; then
    safe_atom "$BLOCK_CODE" && safe_atom "$BLOCK_REASON" || {
        echo "polecat-step: unsafe empty/control-character block code or reason" >&2
        exit "$EXIT_USAGE"
    }
    case "$BLOCK_CODE" in
        *[!A-Za-z0-9._:-]*)
            echo "polecat-step: unsafe block code" >&2
            exit "$EXIT_USAGE"
            ;;
    esac
fi

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
if [[ "$ACTION" == "exec" &&
      "$STEP_REF" == "mol-polecat-work.load-context" ]]; then
    echo "polecat-step: load-context has no task artifact to execute in" >&2
    exit "$EXIT_USAGE"
fi
if [[ "$ACTION" == "exec" &&
      "$STEP_REF" == "mol-polecat-work.workspace-setup" ]]; then
    if [[ "${#EXEC_ARGV[@]}" -eq 4 &&
          "${EXEC_ARGV[0]}" == "gc" &&
          "${EXEC_ARGV[1]}" == "gastown" &&
          "${EXEC_ARGV[2]}" == "polecat-conflict" &&
          "${EXEC_ARGV[3]}" == "stage" ]]; then
        CONFLICT_STAGE_EXEC=true
    else
        echo "polecat-step: workspace-setup exec accepts only exact polecat-conflict stage" >&2
        exit "$EXIT_USAGE"
    fi
fi

[[ -n "${GC_CITY_PATH:-}" && -n "${GC_RIG:-}" &&
   -n "${GC_RIG_ROOT:-}" ]] || {
    echo "polecat-step: GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required" >&2
    exit "$EXIT_INDETERMINATE"
}
case "$GC_RIG" in
    ""|"."|".."|*[!A-Za-z0-9._-]*)
        echo "polecat-step: the runtime rig name is unsafe" >&2
        exit "$EXIT_INDETERMINATE"
        ;;
esac
RUNTIME_RIG=$GC_RIG
CITY_ROOT=$(CDPATH= cd -- "$GC_CITY_PATH" 2>/dev/null && pwd -P) || {
    echo "polecat-step: could not canonicalize the city root" >&2
    exit "$EXIT_INDETERMINATE"
}
RIG_ROOT=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) || {
    echo "polecat-step: could not canonicalize the rig root" >&2
    exit "$EXIT_INDETERMINATE"
}

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
    local command=("$GC_CMD" "bd" "--rig" "$RUNTIME_RIG")
    GC_NO_API=1 \
    GC_CITY="$CITY_ROOT" \
    GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" \
    GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$RIG_ROOT" \
    GC_STORE_SCOPE=rig \
        "${command[@]}" "$@"
}

run_gc_convoy() {
    local command=("$GC_CMD" "convoy")
    GC_NO_API=1 \
    GC_CITY="$CITY_ROOT" \
    GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" \
    GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$RIG_ROOT" \
    GC_STORE_SCOPE=rig \
        "${command[@]}" "$@"
}

indeterminate() {
    echo "POLECAT_STEP_INDETERMINATE: $*" >&2
    echo "The workflow step was not intentionally advanced; inspect and retry." >&2
    exit "$EXIT_INDETERMINATE"
}

declare -a ACTORS=()

add_actor() {
    local value=$1 existing
    [[ -n "$value" ]] || return 0
    safe_atom "$value" || return 1
    for existing in "${ACTORS[@]}"; do
        [[ "$existing" != "$value" ]] || return 0
    done
    ACTORS+=("$value")
}

for identity in \
    "${BEADS_ACTOR:-}" \
    "${GC_SESSION_NAME:-}" \
    "${GC_SESSION_ID:-}" \
    "${GC_ALIAS:-}" \
    "${GC_AGENT:-}"; do
    add_actor "$identity" ||
        indeterminate "a current session assignee identity is unsafe"
done
[[ "${#ACTORS[@]}" -gt 0 ]] ||
    indeterminate "the current session assignee identities are unavailable"

COLLECTED_STEPS='[]'
COLLECT_FAILURE=''

collect_steps() {
    local status=$1 outcome=$2 actor listed matches
    COLLECTED_STEPS='[]'
    COLLECT_FAILURE=''

    for actor in "${ACTORS[@]}"; do
        listed=$(run_gc_bd list --assignee "$actor" --status="$status" \
            --limit=0 --json 2>/dev/null) || {
            COLLECT_FAILURE="could not list $status steps for identity $actor"
            return 1
        }
        matches=$(printf '%s' "$listed" | jq -ce \
            --arg actor "$actor" --arg ref "$STEP_REF" \
            --arg status "$status" --arg outcome "$outcome" '
            if type == "array" and
               all(.[]; type == "object" and
                        .status == $status and .assignee == $actor)
            then [.[] |
              select(.status == $status and .assignee == $actor and
                     .metadata["gc.step_ref"] == $ref and
                     ($outcome == "__any__" or
                      .metadata["gc.outcome"] == $outcome))]
            else error("step list contradicted the requested status or assignee")
            end' 2>/dev/null) || {
            COLLECT_FAILURE="the $status step list for identity $actor was malformed"
            return 1
        }
        COLLECTED_STEPS=$(jq -cn \
            --argjson accumulated "$COLLECTED_STEPS" \
            --argjson matches "$matches" \
            '$accumulated + $matches') || {
            COLLECT_FAILURE="could not aggregate $status step lists"
            return 1
        }
    done

    printf '%s' "$COLLECTED_STEPS" | jq -e '
        all(.[];
            (.id | type) == "string" and (.id | length) > 0 and
            (.assignee | type) == "string" and (.assignee | length) > 0) and
        (([.[].id] | length) == ([.[].id] | unique | length))
    ' >/dev/null 2>&1 || {
        COLLECT_FAILURE="$status step aggregation contained malformed or duplicate ids"
        return 1
    }
}

classify_root() {
    local root_id=$1 mode=$2 root_json classification
    case "$mode" in
        live|replay) ;;
        *) return 2 ;;
    esac
    safe_atom "$root_id" || return 2
    root_json=$(run_gc_bd show "$root_id" --json 2>/dev/null) || return 2
    classification=$(printf '%s' "$root_json" | jq -er \
        --arg id "$root_id" --arg convoy "$CONVOY_ID" \
        --arg rig "$RUNTIME_RIG" --arg mode "$mode" '
        if type != "array" or length != 1 or .[0].id != $id or
           (.[0].metadata | type) != "object" or
           .[0].metadata["gc.kind"] != "workflow" or
           .[0].metadata["gc.formula_contract"] != "graph.v2" or
           .[0].metadata["gc.var.rig_name"] != $rig or
           ((.[0].metadata | has("gc.formula_name")) and
            .[0].metadata["gc.formula_name"] != "mol-polecat-work") or
           (.[0].metadata["gc.input_convoy_id"] | type) != "string" or
           (.[0].metadata["gc.input_convoy_id"] | length) == 0
        then error("root identity or Graph-v2 provenance mismatch")
        elif .[0].metadata["gc.input_convoy_id"] != $convoy
        then "other"
        elif $mode == "live" and
             (.[0].status != "in_progress" or
              ((.[0].metadata | has("gc.outcome")) and
               .[0].metadata["gc.outcome"] != ""))
        then error("target workflow root is not active")
        elif $mode == "replay" and
             (((.[0].status == "in_progress") and
               (((.[0].metadata | has("gc.outcome")) | not) or
                .[0].metadata["gc.outcome"] == "")) or
              ((.[0].status == "closed") and
               ((.[0].metadata["gc.outcome"] == "pass") or
                (.[0].metadata["gc.outcome"] == "fail"))))
        then "match"
        elif $mode == "replay"
        then error("target workflow root is incoherent for replay")
        else "match"
        end' 2>/dev/null) || return 2
    case "$classification" in
        match) return 0 ;;
        other) return 1 ;;
        *) return 2 ;;
    esac
}

validate_step() {
    local step_json=$1 expected_assignee=$2 expected_status=$3 expected_outcome=$4
    printf '%s' "$step_json" | jq -er \
        --arg actor "$expected_assignee" --arg ref "$STEP_REF" \
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
    local matches candidate_id candidate_assignee candidate_root candidate_json
    local validated candidate_count=0

    collect_steps "closed" "pass" || return 1
    matches=$(printf '%s' "$COLLECTED_STEPS" | jq -ce '
        if all(.[];
               (.metadata["gc.root_bead_id"] | type) == "string" and
               (.metadata["gc.root_bead_id"] | length) > 0)
        then .
        else error("closed/pass replay candidate is malformed")
        end' 2>/dev/null) || return 1

    while IFS=$'\t' read -r \
        candidate_id candidate_assignee candidate_root; do
        [[ -n "$candidate_id" && -n "$candidate_assignee" &&
           -n "$candidate_root" ]] || continue
        safe_atom "$candidate_id" && safe_atom "$candidate_assignee" &&
            safe_atom "$candidate_root" || return 1
        candidate_json=$(run_gc_bd show "$candidate_id" --json 2>/dev/null) ||
            return 1
        validated=$(validate_step "$candidate_json" "$candidate_assignee" \
            "closed" "pass") ||
            return 1
        [[ "$validated" == "$candidate_id"$'\t'"$candidate_root" ]] ||
            return 1
        classify_root "$candidate_root" replay
        case $? in
            0)
                candidate_count=$((candidate_count + 1))
                STEP_BEAD_ID=$candidate_id
                STEP_ASSIGNEE=$candidate_assignee
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
        .[] | [.id, .assignee, .metadata["gc.root_bead_id"]] | @tsv')

    [[ "$candidate_count" -eq 1 ]]
}

find_blocked_step() {
    local matches candidate_id candidate_assignee candidate_root candidate_json
    local validated candidate_count=0

    collect_steps "blocked" "__any__" || return 1
    matches=$(printf '%s' "$COLLECTED_STEPS" | jq -ce '
        if all(.[];
               (.metadata["gc.root_bead_id"] | type) == "string" and
               (.metadata["gc.root_bead_id"] | length) > 0)
        then .
        else error("blocked replay candidate is malformed")
        end' 2>/dev/null) || return 1

    while IFS=$'\t' read -r \
        candidate_id candidate_assignee candidate_root; do
        [[ -n "$candidate_id" && -n "$candidate_assignee" &&
           -n "$candidate_root" ]] || continue
        safe_atom "$candidate_id" && safe_atom "$candidate_assignee" &&
            safe_atom "$candidate_root" || return 1
        candidate_json=$(run_gc_bd show "$candidate_id" --json 2>/dev/null) ||
            return 1
        validated=$(validate_step "$candidate_json" "$candidate_assignee" \
            "blocked" "__empty__") ||
            return 1
        [[ "$validated" == "$candidate_id"$'\t'"$candidate_root" ]] ||
            return 1
        classify_root "$candidate_root" live
        case $? in
            0)
                candidate_count=$((candidate_count + 1))
                STEP_BEAD_ID=$candidate_id
                STEP_ASSIGNEE=$candidate_assignee
                ROOT_BEAD_ID=$candidate_root
                ;;
            1)
                # A canonically verified root for another input convoy is not
                # this invocation's blocked replay candidate.
                ;;
            *)
                return 1
                ;;
        esac
    done < <(printf '%s' "$matches" | jq -r '
        .[] | [.id, .assignee, .metadata["gc.root_bead_id"]] | @tsv')

    [[ "$candidate_count" -eq 1 ]]
}

BLOCK_REPLAY=false
collect_steps "in_progress" "__any__" ||
    indeterminate "${COLLECT_FAILURE:-could not resolve in-progress steps}"
STEP_MATCHES=$COLLECTED_STEPS
STEP_COUNT=$(printf '%s' "$STEP_MATCHES" | jq -er 'length' 2>/dev/null) ||
    indeterminate "could not count matching workflow steps"

if [[ "$STEP_COUNT" == "0" ]]; then
    case "$ACTION" in
        exec)
            indeterminate "no unique live step matches this exec request"
            ;;
        block)
            find_blocked_step ||
                indeterminate "no unique exact blocked replay matches this step and convoy"
            BLOCK_REPLAY=true
            ;;
        complete)
            find_replay ||
                indeterminate "no unique closed/pass replay matches this step and convoy"
            printf 'POLECAT_STEP_COMPLETE step=%s ref=%s root=%s convoy=%s replay=true\n' \
                "$STEP_BEAD_ID" "$STEP_REF" "$ROOT_BEAD_ID" "$CONVOY_ID"
            exit 0
            ;;
    esac
fi
if [[ "$STEP_COUNT" != "1" && "$BLOCK_REPLAY" != "true" ]]; then
    indeterminate "expected one claimed step, found $STEP_COUNT"
fi

if [[ "$BLOCK_REPLAY" != "true" ]]; then
    STEP_BEAD_ID=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].id' 2>/dev/null) ||
        indeterminate "the claimed step has no exact id"
    STEP_ASSIGNEE=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].assignee' 2>/dev/null) ||
        indeterminate "the claimed step has no exact assignee"
    safe_atom "$STEP_BEAD_ID" ||
        indeterminate "the claimed step id is unsafe"
    safe_atom "$STEP_ASSIGNEE" ||
        indeterminate "the claimed step assignee is unsafe"
    STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not read the exact claimed step"
    VALIDATED=$(validate_step "$STEP_JSON" "$STEP_ASSIGNEE" \
        "in_progress" "__empty__") ||
        indeterminate "claimed step identity, ownership, or state did not verify"
    IFS=$'\t' read -r VERIFIED_STEP_ID ROOT_BEAD_ID <<<"$VALIDATED"
    [[ "$VERIFIED_STEP_ID" == "$STEP_BEAD_ID" ]] ||
        indeterminate "claimed step id changed during verification"
    classify_root "$ROOT_BEAD_ID" live
    [[ $? -eq 0 ]] ||
        indeterminate "workflow root or input-convoy provenance did not verify"
fi

if [[ "$ACTION" == "block" ]]; then
    block_convoy_source_id() {
        local convoy_json=$1
        printf '%s' "$convoy_json" | jq -er --arg convoy "$CONVOY_ID" '
            if type == "object" and .schema_version == "1" and
               (.convoy | type) == "object" and .convoy.id == $convoy and
               (.children | type) == "array" and
               (.children | length) == 1 and
               (.children[0].id | type) == "string" and
               (.children[0].id | length) > 0
            then .children[0].id
            else error("convoy identity/schema/source mismatch")
            end' 2>/dev/null
    }

    block_source_contract_ok() {
        local source_json=$1 required_status=$2
        printf '%s' "$source_json" | jq -e \
            --arg id "$BLOCK_SOURCE_ID" \
            --arg status "$required_status" \
            --arg code "$BLOCK_CODE" \
            --arg reason "$BLOCK_REASON" \
            --arg step "$STEP_REF" \
            --arg step_id "$STEP_BEAD_ID" \
            --arg root "$ROOT_BEAD_ID" \
            --arg previous_route "$BLOCK_PREVIOUS_ROUTE" \
            --arg convoy "$CONVOY_ID" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == $status and ((.[0].assignee // "") == "") and
            ((.[0].metadata // {}) | type) == "object" and
            .[0].metadata["gc.routed_to"] == "human" and
            .[0].metadata.blocked_reason == $reason and
            .[0].metadata["gc.polecat_block_code"] == $code and
            (.[0].metadata["gc.polecat_block_version"] | tostring) == "1" and
            .[0].metadata["gc.polecat_block_step_ref"] == $step and
            .[0].metadata["gc.polecat_block_step_id"] == $step_id and
            .[0].metadata["gc.polecat_block_root"] == $root and
            .[0].metadata["gc.polecat_block_previous_route"] ==
              $previous_route and
            .[0].metadata["gc.polecat_block_convoy"] == $convoy' \
            >/dev/null 2>&1
    }

    block_source_precondition_ok() {
        local source_json=$1
        printf '%s' "$source_json" | jq -e \
            --arg id "$BLOCK_SOURCE_ID" \
            --arg code "$BLOCK_CODE" \
            --arg reason "$BLOCK_REASON" \
            --arg step "$STEP_REF" \
            --arg step_id "$STEP_BEAD_ID" \
            --arg root "$ROOT_BEAD_ID" \
            --arg previous_route "$BLOCK_PREVIOUS_ROUTE" \
            --arg convoy "$CONVOY_ID" '
            def empty_or_exact($expected):
              . == null or . == "" or . == $expected;
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == "open" and ((.[0].assignee // "") == "") and
            ((.[0].metadata // {}) | type) == "object" and
            (((.[0].metadata["gc.routed_to"] // "") == $previous_route and
              (.[0].metadata["gc.polecat_block_previous_route"] |
               empty_or_exact($previous_route))) or
             (.[0].metadata["gc.routed_to"] == "human" and
              .[0].metadata["gc.polecat_block_previous_route"] ==
                $previous_route)) and
            (.[0].metadata.blocked_reason | empty_or_exact($reason)) and
            (.[0].metadata["gc.polecat_block_code"] |
             empty_or_exact($code)) and
            ((.[0].metadata["gc.polecat_block_version"] == null) or
             (.[0].metadata["gc.polecat_block_version"] == "") or
             ((.[0].metadata["gc.polecat_block_version"] | tostring) == "1")) and
            (.[0].metadata["gc.polecat_block_step_ref"] |
             empty_or_exact($step)) and
            (.[0].metadata["gc.polecat_block_step_id"] |
             empty_or_exact($step_id)) and
            (.[0].metadata["gc.polecat_block_root"] |
             empty_or_exact($root)) and
            (.[0].metadata["gc.polecat_block_previous_route"] |
             empty_or_exact($previous_route)) and
            (.[0].metadata["gc.polecat_block_convoy"] |
             empty_or_exact($convoy))' >/dev/null 2>&1
    }

    block_step_contract_ok() {
        local step_json=$1 required_status=$2
        printf '%s' "$step_json" | jq -e \
            --arg id "$STEP_BEAD_ID" \
            --arg actor "$STEP_ASSIGNEE" \
            --arg status "$required_status" \
            --arg ref "$STEP_REF" \
            --arg root "$ROOT_BEAD_ID" \
            --arg source "$BLOCK_SOURCE_ID" \
            --arg code "$BLOCK_CODE" \
            --arg reason "$BLOCK_REASON" \
            --arg convoy "$CONVOY_ID" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == $status and .[0].assignee == $actor and
            .[0].metadata["gc.step_ref"] == $ref and
            .[0].metadata["gc.root_bead_id"] == $root and
            (((.[0].metadata | has("gc.outcome")) | not) or
             .[0].metadata["gc.outcome"] == "") and
            .[0].metadata["gc.blocked_reason"] == $reason and
            .[0].metadata["gc.polecat_block_code"] == $code and
            (.[0].metadata["gc.polecat_block_version"] | tostring) == "1" and
            .[0].metadata["gc.polecat_block_source"] == $source and
            .[0].metadata["gc.polecat_block_convoy"] == $convoy' \
            >/dev/null 2>&1
    }

    block_step_precondition_ok() {
        local step_json=$1
        printf '%s' "$step_json" | jq -e \
            --arg id "$STEP_BEAD_ID" \
            --arg actor "$STEP_ASSIGNEE" \
            --arg ref "$STEP_REF" \
            --arg root "$ROOT_BEAD_ID" \
            --arg source "$BLOCK_SOURCE_ID" \
            --arg code "$BLOCK_CODE" \
            --arg reason "$BLOCK_REASON" \
            --arg convoy "$CONVOY_ID" '
            def empty_or_exact($expected):
              . == null or . == "" or . == $expected;
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == "in_progress" and .[0].assignee == $actor and
            .[0].metadata["gc.step_ref"] == $ref and
            .[0].metadata["gc.root_bead_id"] == $root and
            (((.[0].metadata | has("gc.outcome")) | not) or
             .[0].metadata["gc.outcome"] == "") and
            (.[0].metadata["gc.blocked_reason"] |
             empty_or_exact($reason)) and
            (.[0].metadata["gc.polecat_block_code"] |
             empty_or_exact($code)) and
            ((.[0].metadata["gc.polecat_block_version"] == null) or
             (.[0].metadata["gc.polecat_block_version"] == "") or
             ((.[0].metadata["gc.polecat_block_version"] | tostring) == "1")) and
            (.[0].metadata["gc.polecat_block_source"] |
             empty_or_exact($source)) and
            (.[0].metadata["gc.polecat_block_convoy"] |
             empty_or_exact($convoy))' >/dev/null 2>&1
    }

    block_incomplete() {
        echo "POLECAT_STEP_BLOCK_INDETERMINATE: $*" >&2
        echo "A durable block may be partially or fully present; inspect and retry this exact block command." >&2
        exit "$EXIT_INDETERMINATE"
    }

    revalidate_block_snapshot() {
        local required_source_status=$1 required_step_status=$2
        local convoy_json source_id source_json step_json

        convoy_json=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
            return 1
        source_id=$(block_convoy_source_id "$convoy_json") || return 1
        [[ "$source_id" == "$BLOCK_SOURCE_ID" ]] || return 1
        classify_root "$ROOT_BEAD_ID" live || return 1
        source_json=$(run_gc_bd show "$BLOCK_SOURCE_ID" --json 2>/dev/null) ||
            return 1
        block_source_contract_ok "$source_json" "$required_source_status" ||
            return 1
        step_json=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
            return 1
        block_step_contract_ok "$step_json" "$required_step_status"
    }

    BLOCK_CONVOY_JSON=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
        indeterminate "could not read the exact input convoy before blocking"
    BLOCK_SOURCE_ID=$(block_convoy_source_id "$BLOCK_CONVOY_JSON") ||
        indeterminate "input convoy identity/schema or sole source did not verify before blocking"
    case "$BLOCK_SOURCE_ID" in
        ""|"."|".."|*[!A-Za-z0-9._-]*)
            indeterminate "the input convoy source id is unsafe"
            ;;
    esac

    BLOCK_SOURCE_JSON=$(run_gc_bd show "$BLOCK_SOURCE_ID" --json 2>/dev/null) ||
        indeterminate "could not read the exact source before blocking"
    BLOCK_PREVIOUS_ROUTE=$(printf '%s' "$BLOCK_SOURCE_JSON" | jq -er \
        --arg id "$BLOCK_SOURCE_ID" '
        if type != "array" or length != 1 or .[0].id != $id or
           ((.[0].metadata // {}) | type) != "object"
        then error("source identity/metadata mismatch")
        elif (.[0].metadata["gc.routed_to"] // "") == "human"
        then
          if (.[0].metadata | has("gc.polecat_block_previous_route")) and
             (.[0].metadata["gc.polecat_block_previous_route"] | type) ==
               "string"
          then .[0].metadata["gc.polecat_block_previous_route"]
          else error("human-routed source lacks prior route provenance")
          end
        elif ((.[0].metadata["gc.routed_to"] // "") | type) == "string"
        then .[0].metadata["gc.routed_to"] // ""
        else error("source route is malformed")
        end' 2>/dev/null) ||
        indeterminate "source route or prior-route provenance is malformed"
    if ((${#BLOCK_PREVIOUS_ROUTE} > 512)) ||
       [[ "$BLOCK_PREVIOUS_ROUTE" == *$'\n'* ||
          "$BLOCK_PREVIOUS_ROUTE" == *$'\r'* ||
          "$BLOCK_PREVIOUS_ROUTE" == *$'\t'* ]]; then
        indeterminate "source prior route is unsafe"
    fi
    BLOCK_SOURCE_STATUS=$(printf '%s' "$BLOCK_SOURCE_JSON" | jq -er \
        --arg id "$BLOCK_SOURCE_ID" '
        if type == "array" and length == 1 and .[0].id == $id and
           ((.[0].assignee // "") == "") and
           ((.[0].metadata // {}) | type) == "object" and
           (.[0].status == "open" or .[0].status == "blocked")
        then .[0].status
        else error("source state is not safely blockable")
        end' 2>/dev/null) ||
        indeterminate "source identity/state or prior blocker conflicts"

    if [[ "$BLOCK_SOURCE_STATUS" == "blocked" ]]; then
        block_source_contract_ok "$BLOCK_SOURCE_JSON" "blocked" ||
            indeterminate "blocked source lacks this exact durable block contract"
    elif ! block_source_contract_ok "$BLOCK_SOURCE_JSON" "open"; then
        block_source_precondition_ok "$BLOCK_SOURCE_JSON" ||
            indeterminate "source carries a conflicting durable block signature"
        run_gc_bd update "$BLOCK_SOURCE_ID" \
            --set-metadata "gc.routed_to=human" \
            --set-metadata "blocked_reason=$BLOCK_REASON" \
            --set-metadata "gc.polecat_block_code=$BLOCK_CODE" \
            --set-metadata "gc.polecat_block_version=1" \
            --set-metadata "gc.polecat_block_step_ref=$STEP_REF" \
            --set-metadata "gc.polecat_block_step_id=$STEP_BEAD_ID" \
            --set-metadata "gc.polecat_block_root=$ROOT_BEAD_ID" \
            --set-metadata "gc.polecat_block_previous_route=$BLOCK_PREVIOUS_ROUTE" \
            --set-metadata "gc.polecat_block_convoy=$CONVOY_ID" \
            --append-notes "BLOCKED [$BLOCK_CODE] [$STEP_REF]: $BLOCK_REASON" ||
            block_incomplete "could not persist the source blocker"
        BLOCK_SOURCE_JSON=$(run_gc_bd show "$BLOCK_SOURCE_ID" --json 2>/dev/null) ||
            block_incomplete "could not read back the source blocker"
        block_source_contract_ok "$BLOCK_SOURCE_JSON" "open" ||
            block_incomplete "source blocker did not read back exactly"
    fi

    BLOCK_STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        block_incomplete "could not re-read the current step before blocking"
    if [[ "$BLOCK_REPLAY" == "true" ]]; then
        block_step_contract_ok "$BLOCK_STEP_JSON" "blocked" ||
            block_incomplete "blocked step lacks this exact durable block contract"
        [[ "$BLOCK_SOURCE_STATUS" == "blocked" ]] ||
            block_incomplete "blocked step has no matching blocked source"
    elif ! block_step_contract_ok "$BLOCK_STEP_JSON" "in_progress"; then
        block_step_precondition_ok "$BLOCK_STEP_JSON" ||
            block_incomplete "workflow step carries a conflicting durable block signature"
        run_gc_bd update "$STEP_BEAD_ID" \
            --set-metadata "gc.blocked_reason=$BLOCK_REASON" \
            --set-metadata "gc.polecat_block_code=$BLOCK_CODE" \
            --set-metadata "gc.polecat_block_version=1" \
            --set-metadata "gc.polecat_block_source=$BLOCK_SOURCE_ID" \
            --set-metadata "gc.polecat_block_convoy=$CONVOY_ID" ||
            block_incomplete "could not persist the workflow-step blocker"
        BLOCK_STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
            block_incomplete "could not read back the workflow-step blocker"
        block_step_contract_ok "$BLOCK_STEP_JSON" "in_progress" ||
            block_incomplete "workflow-step blocker did not read back exactly"
    fi

    if [[ "$BLOCK_REPLAY" == "true" ]]; then
        revalidate_block_snapshot "blocked" "blocked" ||
            block_incomplete "blocked replay authority changed before drain acknowledgement"
        "$GC_CMD" runtime drain-ack ||
            block_incomplete "durable block replay verified but drain acknowledgement failed"
        printf 'POLECAT_STEP_BLOCKED step=%s ref=%s root=%s convoy=%s source=%s code=%s replay=true\n' \
            "$STEP_BEAD_ID" "$STEP_REF" "$ROOT_BEAD_ID" "$CONVOY_ID" \
            "$BLOCK_SOURCE_ID" "$BLOCK_CODE"
        exit 0
    fi

    revalidate_block_snapshot "$BLOCK_SOURCE_STATUS" "in_progress" ||
        block_incomplete "block authority changed before status transitions"

    if [[ "$BLOCK_SOURCE_STATUS" == "open" ]]; then
        run_gc_bd update "$BLOCK_SOURCE_ID" --status=blocked ||
            block_incomplete "could not mark the source blocked"
    fi
    BLOCK_SOURCE_JSON=$(run_gc_bd show "$BLOCK_SOURCE_ID" --json 2>/dev/null) ||
        block_incomplete "could not read back blocked source status"
    block_source_contract_ok "$BLOCK_SOURCE_JSON" "blocked" ||
        block_incomplete "source blocked status or reason did not read back exactly"

    revalidate_block_snapshot "blocked" "in_progress" ||
        block_incomplete "block authority changed after source status transition"
    run_gc_bd update "$STEP_BEAD_ID" --status=blocked ||
        block_incomplete "could not mark the workflow step blocked"
    BLOCK_STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        block_incomplete "could not read back blocked workflow-step status"
    block_step_contract_ok "$BLOCK_STEP_JSON" "blocked" ||
        block_incomplete "workflow-step blocked status or reason did not read back exactly"

    revalidate_block_snapshot "blocked" "blocked" ||
        block_incomplete "final durable block snapshot did not verify"

    "$GC_CMD" runtime drain-ack ||
        block_incomplete "durable block succeeded but drain acknowledgement failed"
    printf 'POLECAT_STEP_BLOCKED step=%s ref=%s root=%s convoy=%s source=%s code=%s replay=false\n' \
        "$STEP_BEAD_ID" "$STEP_REF" "$ROOT_BEAD_ID" "$CONVOY_ID" \
        "$BLOCK_SOURCE_ID" "$BLOCK_CODE"
    exit 0
fi

if [[ "$ACTION" == "exec" ]]; then
    GIT_CMD=$(command -v git 2>/dev/null || true)
    [[ -n "$GIT_CMD" && -x "$GIT_CMD" ]] ||
        indeterminate "git is required for artifact execution"

    convoy_source_id() {
        local convoy_json=$1
        printf '%s' "$convoy_json" | jq -er --arg convoy "$CONVOY_ID" '
            if type == "object" and .schema_version == "1" and
               (.convoy | type) == "object" and
               .convoy.id == $convoy and
               (.children | type) == "array" and
               (.children | length) == 1 and
               (.children[0].id | type) == "string" and
               (.children[0].id | length) > 0
            then .children[0].id
            else error("convoy identity/schema/source mismatch")
            end' 2>/dev/null
    }

    source_context() {
        local source_json=$1
        printf '%s' "$source_json" | jq -cer --arg id "$SOURCE_ID" '
            if type == "array" and length == 1 and .[0].id == $id and
               .[0].status == "open" and
               ((.[0].assignee // "") == "") and
               ((.[0].metadata // {}) | type) == "object" and
               (.[0].metadata.artifact_dir | type) == "string" and
               (.[0].metadata.artifact_dir | length) > 0 and
               (((.[0].metadata | has("branch")) | not) or
                (.[0].metadata.branch | type) == "string")
            then {
              artifact: .[0].metadata.artifact_dir,
              branch: (.[0].metadata.branch // "")
            }
            else error("source identity/state/artifact mismatch")
            end' 2>/dev/null
    }

    ONE_LINE=""
    read_one_line_file() {
        local file=$1 line count=0
        ONE_LINE=""
        [[ -f "$file" && ! -L "$file" ]] || return 1
        while IFS= read -r line || [[ -n "$line" ]]; do
            count=$((count + 1))
            [[ "$count" -eq 1 ]] || return 1
            ONE_LINE=$line
        done <"$file"
        [[ "$count" -eq 1 ]] && safe_atom "$ONE_LINE"
    }

    resolve_dir_ref() {
        local base=$1 ref=$2 candidate
        case "$ref" in
            /*) candidate=$ref ;;
            *) candidate="$base/$ref" ;;
        esac
        CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P
    }

    resolve_file_ref() {
        local base=$1 ref=$2 candidate parent parent_real
        case "$ref" in
            /*) candidate=$ref ;;
            *) candidate="$base/$ref" ;;
        esac
        parent=$(dirname -- "$candidate") || return 1
        parent_real=$(CDPATH= cd -- "$parent" 2>/dev/null && pwd -P) ||
            return 1
        printf '%s/%s\n' "$parent_real" "$(basename -- "$candidate")"
    }

    ARTIFACT_VALIDATION_FAILURE=""
    validate_artifact_context() {
        local candidate=$1 artifact_real rig_namespace rig_namespace_real
        local canonical_artifact worktrees_parent provider_home provider_root
        local provider_name artifact_top artifact_common artifact_git_dir
        local admin_ref admin_real admin_backref admin_backreal
        local admin_common_ref admin_common_real current_branch
        local listed registered_count=0

        ARTIFACT_VALIDATION_FAILURE=""
        artifact_real=$(CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P) || {
            ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir is unavailable"
            return 1
        }
        [[ "$artifact_real" == "$ARTIFACT_REAL" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir is redirected"
            return 1
        }
        [[ "$(basename -- "$artifact_real")" == "$SOURCE_ID" &&
           "$(basename -- "$(dirname -- "$artifact_real")")" == "worktrees" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir is not bead-scoped"
            return 1
        }

        rig_namespace="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG"
        rig_namespace_real=$(CDPATH= cd -- "$rig_namespace" 2>/dev/null &&
            pwd -P) || {
            ARTIFACT_VALIDATION_FAILURE="could not resolve the city/rig worktree namespace"
            return 1
        }
        [[ "$rig_namespace_real" == "$rig_namespace" ]] || {
            ARTIFACT_VALIDATION_FAILURE="the city/rig worktree namespace is redirected"
            return 1
        }
        canonical_artifact="$rig_namespace_real/artifacts/worktrees/$SOURCE_ID"
        if [[ "$artifact_real" != "$canonical_artifact" ]]; then
            worktrees_parent=$(dirname -- "$artifact_real")
            provider_home=$(dirname -- "$worktrees_parent")
            provider_root=$(dirname -- "$provider_home")
            provider_name=$(basename -- "$provider_home")
            [[ "$provider_root" == "$rig_namespace_real/polecats" ]] || {
                ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir is outside the rig artifact layouts"
                return 1
            }
            case "$provider_name" in
                ""|"."|".."|*[!A-Za-z0-9._-]*)
                    ARTIFACT_VALIDATION_FAILURE="legacy artifact has an unsafe provider owner"
                    return 1
                    ;;
            esac
        fi

        artifact_top=$("$GIT_CMD" -C "$artifact_real" rev-parse \
            --show-toplevel 2>/dev/null) || {
            ARTIFACT_VALIDATION_FAILURE="source artifact is not a Git worktree"
            return 1
        }
        artifact_top=$(CDPATH= cd -- "$artifact_top" 2>/dev/null && pwd -P) || {
            ARTIFACT_VALIDATION_FAILURE="could not canonicalize the artifact Git top"
            return 1
        }
        [[ "$artifact_top" == "$artifact_real" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact is a Git worktree subdirectory"
            return 1
        }
        artifact_common=$("$GIT_CMD" -C "$artifact_real" rev-parse \
            --path-format=absolute --git-common-dir 2>/dev/null) || {
            ARTIFACT_VALIDATION_FAILURE="could not resolve the artifact Git common directory"
            return 1
        }
        artifact_common=$(CDPATH= cd -- "$artifact_common" 2>/dev/null &&
            pwd -P) || {
            ARTIFACT_VALIDATION_FAILURE="could not canonicalize the artifact Git common directory"
            return 1
        }
        [[ "$artifact_common" == "$RIG_COMMON" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir belongs to another repository"
            return 1
        }
        [[ -f "$artifact_real/.git" && ! -L "$artifact_real/.git" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact is not a registered linked Git worktree"
            return 1
        }

        artifact_git_dir=$("$GIT_CMD" -C "$artifact_real" rev-parse \
            --path-format=absolute --absolute-git-dir 2>/dev/null) || {
            ARTIFACT_VALIDATION_FAILURE="could not resolve the artifact Git admin directory"
            return 1
        }
        artifact_git_dir=$(CDPATH= cd -- "$artifact_git_dir" 2>/dev/null &&
            pwd -P) || {
            ARTIFACT_VALIDATION_FAILURE="could not canonicalize the artifact Git admin directory"
            return 1
        }
        [[ "$(dirname -- "$artifact_git_dir")" == "$RIG_COMMON/worktrees" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact Git admin directory is not registered to the rig"
            return 1
        }

        read_one_line_file "$artifact_real/.git" || {
            ARTIFACT_VALIDATION_FAILURE="source artifact has an invalid .git pointer"
            return 1
        }
        case "$ONE_LINE" in
            "gitdir: "*) admin_ref=${ONE_LINE#gitdir: } ;;
            *)
                ARTIFACT_VALIDATION_FAILURE="source artifact has an invalid .git pointer"
                return 1
                ;;
        esac
        safe_atom "$admin_ref" || {
            ARTIFACT_VALIDATION_FAILURE="source artifact has an unsafe .git pointer"
            return 1
        }
        admin_real=$(resolve_dir_ref "$artifact_real" "$admin_ref") || {
            ARTIFACT_VALIDATION_FAILURE="source artifact .git pointer is unavailable"
            return 1
        }
        [[ "$admin_real" == "$artifact_git_dir" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact .git pointer does not match its Git admin directory"
            return 1
        }

        read_one_line_file "$admin_real/gitdir" || {
            ARTIFACT_VALIDATION_FAILURE="source artifact Git admin backpointer is invalid"
            return 1
        }
        admin_backref=$ONE_LINE
        admin_backreal=$(resolve_file_ref "$admin_real" "$admin_backref") || {
            ARTIFACT_VALIDATION_FAILURE="source artifact Git admin backpointer is unavailable"
            return 1
        }
        [[ "$admin_backreal" == "$artifact_real/.git" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact Git admin backpointer does not match the artifact"
            return 1
        }

        read_one_line_file "$admin_real/commondir" || {
            ARTIFACT_VALIDATION_FAILURE="source artifact Git admin commondir is invalid"
            return 1
        }
        admin_common_ref=$ONE_LINE
        admin_common_real=$(resolve_dir_ref "$admin_real" "$admin_common_ref") || {
            ARTIFACT_VALIDATION_FAILURE="source artifact Git admin commondir is unavailable"
            return 1
        }
        [[ "$admin_common_real" == "$RIG_COMMON" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact Git admin commondir belongs to another repository"
            return 1
        }

        "$GIT_CMD" -C "$RIG_ROOT" worktree list --porcelain -z \
            >/dev/null 2>&1 || {
            ARTIFACT_VALIDATION_FAILURE="could not list the rig's registered worktrees"
            return 1
        }
        while IFS= read -r -d '' listed; do
            if [[ "$listed" == "worktree $artifact_real" ]]; then
                registered_count=$((registered_count + 1))
            fi
        done < <("$GIT_CMD" -C "$RIG_ROOT" worktree list --porcelain -z \
            2>/dev/null)
        [[ "$registered_count" -eq 1 ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact is not exactly one registered rig worktree"
            return 1
        }

        current_branch=$("$GIT_CMD" -C "$artifact_real" \
            branch --show-current 2>/dev/null) || {
            ARTIFACT_VALIDATION_FAILURE="could not read the artifact branch"
            return 1
        }
        if [[ "$CONFLICT_STAGE_EXEC" == "true" ]]; then
            [[ "$SOURCE_BRANCH" == "$EXPECTED_BRANCH" ]] || {
                ARTIFACT_VALIDATION_FAILURE="source metadata.branch is not the canonical task branch"
                return 1
            }
            [[ -z "$current_branch" ||
               "$current_branch" == "$EXPECTED_BRANCH" ]] || {
                ARTIFACT_VALIDATION_FAILURE="workspace transition found a wrong named branch"
                return 1
            }
        else
            [[ "$SOURCE_BRANCH" == "$EXPECTED_BRANCH" ]] || {
                ARTIFACT_VALIDATION_FAILURE="source metadata.branch is not the canonical task branch"
                return 1
            }
            [[ "$current_branch" == "$EXPECTED_BRANCH" ]] || {
                ARTIFACT_VALIDATION_FAILURE="source artifact is not on the canonical task branch"
                return 1
            }
        fi
    }

    CONVOY_JSON=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
        indeterminate "could not read the exact input convoy from the authoritative store"
    SOURCE_ID=$(convoy_source_id "$CONVOY_JSON") ||
        indeterminate "input convoy identity/schema or sole source did not verify"
    case "$SOURCE_ID" in
        ""|"."|".."|*[!A-Za-z0-9._-]*)
            indeterminate "the input convoy source id is unsafe"
            ;;
    esac

    SOURCE_JSON=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) ||
        indeterminate "could not read the exact source bead"
    SOURCE_CONTEXT=$(source_context "$SOURCE_JSON") ||
        indeterminate "source identity, open/unassigned state, or artifact metadata did not verify"
    SOURCE_ARTIFACT_DIR=$(printf '%s' "$SOURCE_CONTEXT" | jq -er '.artifact') ||
        indeterminate "could not decode source artifact metadata"
    SOURCE_BRANCH=$(printf '%s' "$SOURCE_CONTEXT" | jq -er '.branch') ||
        indeterminate "could not decode source branch metadata"
    safe_atom "$SOURCE_ARTIFACT_DIR" ||
        indeterminate "source metadata.artifact_dir contains unsafe control characters"
    [[ -z "$SOURCE_BRANCH" ]] || safe_atom "$SOURCE_BRANCH" ||
        indeterminate "source metadata.branch contains unsafe control characters"
    case "$SOURCE_ARTIFACT_DIR" in
        /*) ;;
        *) indeterminate "source metadata.artifact_dir is not absolute" ;;
    esac

    RIG_COMMON=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) ||
        indeterminate "could not resolve the rig Git common directory"
    RIG_COMMON=$(CDPATH= cd -- "$RIG_COMMON" 2>/dev/null && pwd -P) ||
        indeterminate "could not canonicalize the rig Git common directory"
    ARTIFACT_REAL=$(CDPATH= cd -- "$SOURCE_ARTIFACT_DIR" 2>/dev/null &&
        pwd -P) ||
        indeterminate "source metadata.artifact_dir is unavailable"
    [[ "$ARTIFACT_REAL" == "$SOURCE_ARTIFACT_DIR" ]] ||
        indeterminate "source metadata.artifact_dir is redirected"
    EXPECTED_BRANCH="polecat/$SOURCE_ID"

    validate_artifact_context "$SOURCE_ARTIFACT_DIR" ||
        indeterminate "$ARTIFACT_VALIDATION_FAILURE"

    cd -- "$ARTIFACT_REAL" ||
        indeterminate "source artifact disappeared before final authoritative reads"

    EXEC_STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not re-read the exact claimed step before exec"
    EXEC_STEP_RESULT=$(validate_step "$EXEC_STEP_JSON" "$STEP_ASSIGNEE" \
        "in_progress" "__empty__") ||
        indeterminate "claimed step changed before artifact command execution"
    [[ "$EXEC_STEP_RESULT" == "$STEP_BEAD_ID"$'\t'"$ROOT_BEAD_ID" ]] ||
        indeterminate "claimed step provenance changed before exec"
    classify_root "$ROOT_BEAD_ID" live
    [[ $? -eq 0 ]] ||
        indeterminate "workflow root changed before artifact command execution"

    EXEC_CONVOY_JSON=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
        indeterminate "could not re-read the exact authoritative input convoy before exec"
    EXEC_SOURCE_ID=$(convoy_source_id "$EXEC_CONVOY_JSON") ||
        indeterminate "input convoy identity/schema/source changed before exec"
    [[ "$EXEC_SOURCE_ID" == "$SOURCE_ID" ]] ||
        indeterminate "input convoy sole source changed before exec"

    EXEC_SOURCE_JSON=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) ||
        indeterminate "could not re-read the exact source before exec"
    EXEC_SOURCE_CONTEXT=$(source_context "$EXEC_SOURCE_JSON") ||
        indeterminate "source identity, open/unassigned state, or artifact context changed before exec"
    [[ "$EXEC_SOURCE_CONTEXT" == "$SOURCE_CONTEXT" ]] ||
        indeterminate "source artifact metadata changed before exec"

    FINAL_CWD=$(pwd -P 2>/dev/null) ||
        indeterminate "could not resolve the final artifact working directory"
    [[ "$FINAL_CWD" == "$ARTIFACT_REAL" ]] ||
        indeterminate "source artifact path changed during final authoritative reads"
    validate_artifact_context "." ||
        indeterminate "final artifact proof failed: $ARTIFACT_VALIDATION_FAILURE"

    export GC_POLECAT_SOURCE_ID="$SOURCE_ID"
    export GC_POLECAT_SOURCE_BRANCH="$SOURCE_BRANCH"
    export GC_POLECAT_ARTIFACT_DIR="$ARTIFACT_REAL"
    export GC_POLECAT_CONVOY_ID="$CONVOY_ID"
    exec -- "${EXEC_ARGV[@]}"
    indeterminate "could not execute the requested artifact command"
fi

if ! run_gc_bd update "$STEP_BEAD_ID" \
     --set-metadata gc.outcome=pass \
     --status=closed \
     --append-notes "Completed through validated Gastown polecat-step protocol: $STEP_REF"; then
    indeterminate "could not persist closed/pass on the exact claimed step"
fi

VERIFY_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not read back the completed step"
VERIFY_RESULT=$(validate_step "$VERIFY_JSON" "$STEP_ASSIGNEE" \
    "closed" "pass") ||
    indeterminate "completed step did not read back as exact closed/pass"
[[ "$VERIFY_RESULT" == "$STEP_BEAD_ID"$'\t'"$ROOT_BEAD_ID" ]] ||
    indeterminate "completed step provenance changed during readback"
classify_root "$ROOT_BEAD_ID" replay
[[ $? -eq 0 ]] ||
    indeterminate "workflow root changed during completion readback"

printf 'POLECAT_STEP_COMPLETE step=%s ref=%s root=%s convoy=%s replay=false\n' \
    "$STEP_BEAD_ID" "$STEP_REF" "$ROOT_BEAD_ID" "$CONVOY_ID"
