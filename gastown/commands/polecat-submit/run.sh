#!/usr/bin/env bash
# Deterministic submit-state reconciliation and Graph-v2 step completion.

set -u -o pipefail

EXIT_USAGE=2
EXIT_INDETERMINATE=75
STEP_REF="mol-polecat-work.submit-and-exit"
REPLAY_VERSION="1"

ACTION=${1:-}
if [[ -n "$ACTION" ]]; then
    shift
fi

MODE=""
CONVOY_ID=""
SOURCE_ID=""
EXPECTED_BRANCH=""

usage() {
    cat >&2 <<'EOF'
Usage:
  gc gastown polecat-submit guard
  gc gastown polecat-submit complete \
    --convoy ID --source ID --branch polecat/ID \
    --mode auto_push_false|refinery
EOF
}

while (($#)); do
    case "$1" in
        --mode)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            MODE=$2
            shift 2
            ;;
        --convoy)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            CONVOY_ID=$2
            shift 2
            ;;
        --source)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            SOURCE_ID=$2
            shift 2
            ;;
        --branch)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            EXPECTED_BRANCH=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "polecat-submit: unknown argument: $1" >&2
            usage
            exit "$EXIT_USAGE"
            ;;
    esac
done

if (($#)); then
    usage
    exit "$EXIT_USAGE"
fi
case "$ACTION" in
    guard)
        if [[ -n "$MODE$CONVOY_ID$SOURCE_ID$EXPECTED_BRANCH" ]]; then
            usage
            exit "$EXIT_USAGE"
        fi
        ;;
    complete)
        if [[ -z "$MODE" || -z "$CONVOY_ID" || -z "$SOURCE_ID" ||
              -z "$EXPECTED_BRANCH" ]]; then
            usage
            exit "$EXIT_USAGE"
        fi
        case "$MODE" in
            auto_push_false|refinery) ;;
            *)
                echo "polecat-submit: unsupported evidence mode: $MODE" >&2
                exit "$EXIT_USAGE"
                ;;
        esac
        ;;
    *)
        usage
        exit "$EXIT_USAGE"
        ;;
esac

safe_atom() {
    local value=$1
    [[ -n "$value" &&
       "$value" != -* && "$value" != *' '* &&
       "$value" != *$'\n'* && "$value" != *$'\r'* &&
       "$value" != *$'\t'* ]]
}

safe_component() {
    local value=$1
    [[ "$value" != *[!A-Za-z0-9._-]* ]]
}

if [[ "$ACTION" == "complete" ]]; then
    safe_atom "$CONVOY_ID" && safe_atom "$SOURCE_ID" &&
        safe_atom "$EXPECTED_BRANCH" || {
        echo "polecat-submit: unsafe empty/control-character argument" >&2
        exit "$EXIT_USAGE"
    }
    [[ "$EXPECTED_BRANCH" == "polecat/$SOURCE_ID" ]] || {
        echo "polecat-submit: expected branch must be exactly polecat/$SOURCE_ID" >&2
        exit "$EXIT_USAGE"
    }
fi

GC_CMD=${GC_BIN:-}
if [[ -z "$GC_CMD" ]]; then
    GC_CMD=$(command -v gc 2>/dev/null || true)
fi
if [[ -z "$GC_CMD" || ! -x "$GC_CMD" ]]; then
    echo "polecat-submit: the invoking gc executable is unavailable" >&2
    exit "$EXIT_INDETERMINATE"
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "polecat-submit: jq is required" >&2
    exit "$EXIT_INDETERMINATE"
fi

run_gc_bd() {
    local command=("$GC_CMD" "bd")
    "${command[@]}" "$@"
}

run_gc_convoy() {
    local command=("$GC_CMD" "convoy")
    "${command[@]}" "$@"
}

fail_closed() {
    echo "POLECAT_SUBMIT_INDETERMINATE: $*" >&2
    exit "$EXIT_INDETERMINATE"
}

declare -a RUNTIME_IDENTITIES=()

add_identity() {
    local value=$1 existing
    [[ -n "$value" ]] || return 0
    safe_atom "$value" || return 1
    for existing in "${RUNTIME_IDENTITIES[@]}"; do
        [[ "$existing" != "$value" ]] || return 0
    done
    RUNTIME_IDENTITIES+=("$value")
}

for identity in \
    "${BEADS_ACTOR:-}" \
    "${GC_SESSION_NAME:-}" \
    "${GC_SESSION_ID:-}" \
    "${GC_ALIAS:-}" \
    "${GC_AGENT:-}"; do
    add_identity "$identity" ||
        fail_closed "a current runtime identity is unsafe"
done
[[ "${#RUNTIME_IDENTITIES[@]}" -gt 0 ]] ||
    fail_closed "no current runtime identity is available"
CURRENT_SESSION_ID=${GC_SESSION_ID:-}
[[ -n "$CURRENT_SESSION_ID" ]] && safe_atom "$CURRENT_SESSION_ID" ||
    fail_closed "an exact nonempty GC_SESSION_ID is required"

identity_is_current() {
    local candidate=$1 identity
    for identity in "${RUNTIME_IDENTITIES[@]}"; do
        [[ "$candidate" != "$identity" ]] || return 0
    done
    return 1
}

replay_closed_step() {
    local closed_matches='[]' listed matches identity
    local candidate present_count context
    local candidate_id candidate_assignee root_id replay_session
    local replay_source replay_convoy replay_branch replay_mode replay_terminal
    local root_json root_context root_convoy root_base root_rig root_prefix
    local convoy_json derived_source source_json source_record
    local source_status source_assignee source_branch source_target source_token
    local source_branch_ready source_halt refinery_target
    local coherent_count=0 replay_line=""

    for identity in "${RUNTIME_IDENTITIES[@]}"; do
        listed=$(run_gc_bd list --assignee "$identity" --status=closed \
            --limit=0 --json 2>/dev/null) ||
            fail_closed "could not list closed steps for identity $identity"
        matches=$(printf '%s' "$listed" | jq -ce \
            --arg actor "$identity" --arg ref "$STEP_REF" '
            if type == "array" and
               all(.[]; type == "object" and
                   .status == "closed" and .assignee == $actor and
                   ((.metadata // {}) | type) == "object")
            then [.[] |
              select(.metadata["gc.step_ref"] == $ref and
                     .metadata["gc.outcome"] == "pass")]
            else error("closed step query contradicted its exact filters")
            end' 2>/dev/null) ||
            fail_closed "the closed step list for identity $identity was malformed"
        closed_matches=$(jq -cn \
            --argjson accumulated "$closed_matches" \
            --argjson matches "$matches" \
            '$accumulated + $matches') ||
            fail_closed "could not aggregate closed submit steps"
    done

    printf '%s' "$closed_matches" | jq -e '
        all(.[]; (.id | type) == "string" and (.id | length) > 0) and
        ((map(.id) | unique | length) == length)
    ' >/dev/null 2>&1 ||
        fail_closed "closed submit history contains duplicate or malformed ids"

    while IFS= read -r candidate; do
        [[ -n "$candidate" ]] || continue
        present_count=$(printf '%s' "$candidate" | jq -er '
            (.metadata // {}) as $m |
            ["gc.polecat_submit_version",
             "gc.polecat_submit_source_id",
             "gc.polecat_submit_convoy_id",
             "gc.polecat_submit_branch",
             "gc.polecat_submit_mode",
             "gc.polecat_submit_terminal",
             "gc.polecat_submit_session_id"] |
            map(. as $key | select($m | has($key))) | length
        ' 2>/dev/null) ||
            fail_closed "closed submit history metadata is malformed"
        [[ "$present_count" != "0" ]] || continue
        [[ "$present_count" == "7" ]] ||
            fail_closed "closed submit history has partial replay metadata"

        context=$(printf '%s' "$candidate" | jq -ec \
            --arg ref "$STEP_REF" --argjson version "$REPLAY_VERSION" '
            if (.id | type) == "string" and (.id | length) > 0 and
               .status == "closed" and
               (.assignee | type) == "string" and (.assignee | length) > 0 and
               .metadata["gc.step_ref"] == $ref and
               .metadata["gc.outcome"] == "pass" and
               .metadata["gc.polecat_submit_version"] == $version and
               (.metadata["gc.root_bead_id"] | type) == "string" and
               (.metadata["gc.root_bead_id"] | length) > 0 and
               (.metadata["gc.polecat_submit_source_id"] | type) == "string" and
               (.metadata["gc.polecat_submit_source_id"] | length) > 0 and
               (.metadata["gc.polecat_submit_convoy_id"] | type) == "string" and
               (.metadata["gc.polecat_submit_convoy_id"] | length) > 0 and
               (.metadata["gc.polecat_submit_branch"] | type) == "string" and
               (.metadata["gc.polecat_submit_branch"] | length) > 0 and
               (.metadata["gc.polecat_submit_mode"] |
                  IN("auto_push_false", "refinery")) and
               (.metadata["gc.polecat_submit_terminal"] |
                  IN("branch_ready", "refinery", "closed")) and
               (.metadata["gc.polecat_submit_session_id"] | type) == "string" and
               (.metadata["gc.polecat_submit_session_id"] | length) > 0
            then {
              id: .id,
              assignee: .assignee,
              root: .metadata["gc.root_bead_id"],
              source: .metadata["gc.polecat_submit_source_id"],
              convoy: .metadata["gc.polecat_submit_convoy_id"],
              branch: .metadata["gc.polecat_submit_branch"],
              mode: .metadata["gc.polecat_submit_mode"],
              terminal: .metadata["gc.polecat_submit_terminal"],
              session: .metadata["gc.polecat_submit_session_id"]
            }
            else error("closed submit replay contract mismatch")
            end' 2>/dev/null) ||
            fail_closed "closed submit history violates the replay contract"
        candidate_id=$(printf '%s' "$context" | jq -er '.id')
        candidate_assignee=$(printf '%s' "$context" | jq -er '.assignee')
        root_id=$(printf '%s' "$context" | jq -er '.root')
        replay_source=$(printf '%s' "$context" | jq -er '.source')
        replay_convoy=$(printf '%s' "$context" | jq -er '.convoy')
        replay_branch=$(printf '%s' "$context" | jq -er '.branch')
        replay_mode=$(printf '%s' "$context" | jq -er '.mode')
        replay_terminal=$(printf '%s' "$context" | jq -er '.terminal')
        replay_session=$(printf '%s' "$context" | jq -er '.session')
        safe_atom "$candidate_id" && safe_atom "$candidate_assignee" &&
            safe_atom "$root_id" && safe_atom "$replay_source" &&
            safe_atom "$replay_convoy" && safe_atom "$replay_branch" &&
            safe_atom "$replay_session" ||
            fail_closed "closed submit replay identity is unsafe"
        identity_is_current "$candidate_assignee" ||
            fail_closed "closed submit replay assignee is not a current identity"
        # A runtime name or alias may be reused. The persisted session identity
        # prevents unrelated historical work from becoming retry evidence.
        [[ "$replay_session" == "$CURRENT_SESSION_ID" ]] || continue

        if [[ "$ACTION" == "complete" &&
              ("$replay_convoy" != "$CONVOY_ID" ||
               "$replay_source" != "$SOURCE_ID" ||
               "$replay_branch" != "$EXPECTED_BRANCH" ||
               "$replay_mode" != "$MODE") ]]; then
            continue
        fi
        [[ "$replay_branch" == "polecat/$replay_source" ]] ||
            fail_closed "closed submit replay branch is not canonical"
        if [[ "$replay_mode" == "auto_push_false" ]]; then
            [[ "$replay_terminal" == "branch_ready" ]] ||
                fail_closed "auto_push_false replay has an incoherent terminal kind"
        elif [[ "$replay_mode" == "refinery" ]]; then
            [[ "$replay_terminal" == "refinery" ||
               "$replay_terminal" == "closed" ]] ||
                fail_closed "refinery replay has an incoherent terminal kind"
        fi

        candidate=$(run_gc_bd show "$candidate_id" --json 2>/dev/null) ||
            fail_closed "could not read the exact closed submit step"
        printf '%s' "$candidate" | jq -e \
            --arg id "$candidate_id" --arg actor "$candidate_assignee" \
            --arg ref "$STEP_REF" --arg root "$root_id" \
            --argjson version "$REPLAY_VERSION" --arg source "$replay_source" \
            --arg convoy "$replay_convoy" --arg branch "$replay_branch" \
            --arg mode "$replay_mode" --arg terminal "$replay_terminal" \
            --arg session "$replay_session" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == "closed" and .[0].assignee == $actor and
            .[0].metadata["gc.step_ref"] == $ref and
            .[0].metadata["gc.root_bead_id"] == $root and
            .[0].metadata["gc.outcome"] == "pass" and
            .[0].metadata["gc.polecat_submit_version"] == $version and
            .[0].metadata["gc.polecat_submit_source_id"] == $source and
            .[0].metadata["gc.polecat_submit_convoy_id"] == $convoy and
            .[0].metadata["gc.polecat_submit_branch"] == $branch and
            .[0].metadata["gc.polecat_submit_mode"] == $mode and
            .[0].metadata["gc.polecat_submit_terminal"] == $terminal and
            .[0].metadata["gc.polecat_submit_session_id"] == $session
        ' >/dev/null 2>&1 ||
            fail_closed "closed submit replay changed after listing"

        root_json=$(run_gc_bd show "$root_id" --json 2>/dev/null) ||
            fail_closed "could not read replay workflow root"
        root_context=$(printf '%s' "$root_json" | jq -ec \
            --arg id "$root_id" '
            if type == "array" and length == 1 and .[0].id == $id and
               ((.[0].status == "in_progress" and
                 (((.[0].metadata | has("gc.outcome")) | not) or
                  .[0].metadata["gc.outcome"] == "")) or
                (.[0].status == "closed" and
                 (.[0].metadata["gc.outcome"] | IN("pass", "fail")))) and
               .[0].metadata["gc.kind"] == "workflow" and
               .[0].metadata["gc.formula_contract"] == "graph.v2" and
               (((.[0].metadata | has("gc.formula_name")) | not) or
                .[0].metadata["gc.formula_name"] == "mol-polecat-work") and
               (.[0].metadata["gc.input_convoy_id"] | type) == "string" and
               (.[0].metadata["gc.input_convoy_id"] | length) > 0 and
               (.[0].metadata["gc.var.base_branch"] | type) == "string" and
               (.[0].metadata["gc.var.base_branch"] | length) > 0 and
               ((.[0].metadata["gc.var.rig_name"] // "") | type) == "string" and
               ((.[0].metadata["gc.var.binding_prefix"] // "") | type) == "string"
            then {
              convoy: .[0].metadata["gc.input_convoy_id"],
              base: .[0].metadata["gc.var.base_branch"],
              rig: (.[0].metadata["gc.var.rig_name"] // ""),
              prefix: (.[0].metadata["gc.var.binding_prefix"] // "")
            }
            else error("replay workflow root provenance mismatch")
            end' 2>/dev/null) ||
            fail_closed "replay workflow root provenance did not verify"
        root_convoy=$(printf '%s' "$root_context" | jq -er '.convoy')
        root_base=$(printf '%s' "$root_context" | jq -er '.base')
        root_rig=$(printf '%s' "$root_context" | jq -er '.rig')
        root_prefix=$(printf '%s' "$root_context" | jq -er '.prefix')
        [[ "$root_convoy" == "$replay_convoy" ]] ||
            fail_closed "closed submit replay convoy disagrees with its root"
        safe_atom "$root_base" &&
            safe_component "$root_rig" && safe_component "$root_prefix" ||
            fail_closed "closed submit replay root context is unsafe"
        if [[ -n "${GC_RIG:-}" && "$root_rig" != "$GC_RIG" ]]; then
            fail_closed "replay workflow root rig does not match runtime rig"
        fi
        refinery_target="${root_rig:+$root_rig/}${root_prefix}refinery"
        safe_atom "$refinery_target" ||
            fail_closed "replay workflow root refinery identity is unsafe"

        convoy_json=$(run_gc_convoy status "$replay_convoy" --json 2>/dev/null) ||
            fail_closed "could not read replay input convoy"
        derived_source=$(printf '%s' "$convoy_json" | jq -er '
            if type == "object" and (.children | type) == "array" and
               (.children | length) == 1 and
               (.children[0].id | type) == "string" and
               (.children[0].id | length) > 0
            then .children[0].id
            else error("replay convoy does not have one exact source")
            end' 2>/dev/null) ||
            fail_closed "replay input convoy does not have one exact source"
        [[ "$derived_source" == "$replay_source" ]] ||
            fail_closed "closed submit replay source disagrees with its convoy"

        source_json=$(run_gc_bd show "$replay_source" --json 2>/dev/null) ||
            fail_closed "could not read replay source"
        source_record=$(printf '%s' "$source_json" | jq -ce \
            --arg id "$replay_source" '
            if type == "array" and length == 1 and .[0].id == $id and
               (.[0].status | type) == "string" and
               ((.[0].assignee // "") | type) == "string" and
               ((.[0].metadata // {}) | type) == "object" and
               (.[0].metadata.branch | type) == "string" and
               (.[0].metadata.target | type) == "string" and
               (.[0].metadata["gc.polecat_submit_convoy"] | type) == "string"
            then .[0]
            else error("replay source identity/state mismatch")
            end' 2>/dev/null) ||
            fail_closed "replay source identity or metadata did not verify"
        source_status=$(printf '%s' "$source_record" | jq -er '.status')
        source_assignee=$(printf '%s' "$source_record" | jq -er '.assignee // ""')
        source_branch=$(printf '%s' "$source_record" | jq -er '.metadata.branch')
        source_target=$(printf '%s' "$source_record" | jq -er '.metadata.target')
        source_token=$(printf '%s' "$source_record" | jq -er \
            '.metadata["gc.polecat_submit_convoy"]')
        source_branch_ready=$(printf '%s' "$source_record" | jq -er '
            if .metadata | has("branch_ready")
            then (.metadata.branch_ready | tostring)
            else ""
            end')
        source_halt=$(printf '%s' "$source_record" | jq -er \
            '.metadata.halt_reason // ""')
        [[ "$source_branch" == "$replay_branch" &&
           "$source_branch" == "polecat/$replay_source" &&
           "$source_target" == "$root_base" &&
           "$source_token" == "$replay_convoy" ]] ||
            fail_closed "replay source generation, branch, or target mismatched"
        case "$replay_mode" in
            auto_push_false)
                [[ "$source_status" == "open" &&
                   -z "$source_assignee" &&
                   "$source_branch_ready" == "true" &&
                   "$source_halt" == "auto_push_false" ]] ||
                    fail_closed "auto_push_false replay evidence no longer matches"
                ;;
            refinery)
                [[ "$source_status" == "closed" ||
                   (("$source_status" == "open" ||
                     "$source_status" == "in_progress") &&
                    "$source_assignee" == "$refinery_target") ]] ||
                    fail_closed "refinery replay evidence no longer matches"
                ;;
        esac

        coherent_count=$((coherent_count + 1))
        if [[ "$ACTION" == "guard" ]]; then
            replay_line=$(jq -cn \
                --arg contract "polecat-submit.v1" \
                --arg action "terminal" \
                --arg step "$candidate_id" \
                --arg assignee "$candidate_assignee" \
                --arg root "$root_id" \
                --arg convoy "$replay_convoy" \
                --arg source "$replay_source" \
                --arg mode "$replay_mode" \
                --arg branch "$replay_branch" \
                --arg status "$source_status" \
                --arg source_assignee "$source_assignee" \
                '{contract: $contract, action: $action, step: $step,
                  assignee: $assignee, root: $root, convoy: $convoy,
                  source: $source, mode: $mode, branch: $branch,
                  status: $status, source_assignee: $source_assignee,
                  replay: true}') ||
                fail_closed "could not encode closed submit replay"
        else
            replay_line="POLECAT_SUBMIT_COMPLETE step=$candidate_id assignee=$candidate_assignee root=$root_id convoy=$replay_convoy source=$replay_source mode=$replay_mode branch=$replay_branch replay=true"
        fi
    done < <(printf '%s' "$closed_matches" | jq -c '.[]')

    [[ "$coherent_count" -le 1 ]] ||
        fail_closed "multiple coherent closed submit replays matched"
    [[ "$coherent_count" -eq 1 ]] || return 1
    printf '%s\n' "$replay_line"
    return 0
}

STEP_MATCHES='[]'
for identity in "${RUNTIME_IDENTITIES[@]}"; do
    listed=$(run_gc_bd list --assignee "$identity" --status=in_progress \
        --limit=0 --json 2>/dev/null) ||
        fail_closed "could not list in-progress steps for identity $identity"
    matches=$(printf '%s' "$listed" | jq -ce \
        --arg actor "$identity" --arg ref "$STEP_REF" '
        if type == "array" and
           all(.[]; type == "object" and
               .status == "in_progress" and .assignee == $actor and
               ((.metadata // {}) | type) == "object")
        then [.[] |
          select(.metadata["gc.step_ref"] == $ref and
                 (((.metadata | has("gc.outcome")) | not) or
                  .metadata["gc.outcome"] == ""))]
        else error("step query contradicted its exact filters")
        end' 2>/dev/null) ||
        fail_closed "the in-progress step list for identity $identity was malformed"
    STEP_MATCHES=$(jq -cn \
        --argjson accumulated "$STEP_MATCHES" \
        --argjson matches "$matches" \
        '$accumulated + $matches') ||
        fail_closed "could not aggregate current submit steps"
done

STEP_MATCH_COUNT=$(printf '%s' "$STEP_MATCHES" | jq -er 'length') ||
    fail_closed "could not count current submit steps"
if [[ "$STEP_MATCH_COUNT" == "0" ]]; then
    replay_closed_step && exit 0
    fail_closed "no current submit step or coherent closed replay was found"
fi
[[ "$STEP_MATCH_COUNT" == "1" ]] ||
    fail_closed "expected exactly one current submit step across runtime identities"
printf '%s' "$STEP_MATCHES" | jq -e '
    (.[0].id | type) == "string" and (.[0].id | length) > 0 and
    (.[0].assignee | type) == "string" and (.[0].assignee | length) > 0
' >/dev/null 2>&1 ||
    fail_closed "the current submit step is malformed"

STEP_BEAD_ID=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].id') ||
    fail_closed "the current submit step has no exact id"
STEP_ASSIGNEE=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].assignee') ||
    fail_closed "the current submit step has no exact assignee"
safe_atom "$STEP_BEAD_ID" && safe_atom "$STEP_ASSIGNEE" ||
    fail_closed "the current submit step identity is unsafe"

STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    fail_closed "could not read the exact submit step"
ROOT_BEAD_ID=$(printf '%s' "$STEP_JSON" | jq -er \
    --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
    --arg ref "$STEP_REF" '
    if type == "array" and length == 1 and .[0].id == $id and
       .[0].status == "in_progress" and .[0].assignee == $actor and
       .[0].metadata["gc.step_ref"] == $ref and
       (((.[0].metadata | has("gc.outcome")) | not) or
        .[0].metadata["gc.outcome"] == "") and
       (.[0].metadata["gc.root_bead_id"] | type) == "string" and
       (.[0].metadata["gc.root_bead_id"] | length) > 0
    then .[0].metadata["gc.root_bead_id"]
    else error("submit step identity/state mismatch")
    end' 2>/dev/null) ||
    fail_closed "submit step identity, ownership, or state did not verify"
safe_atom "$ROOT_BEAD_ID" ||
    fail_closed "the submit workflow root id is unsafe"

ROOT_JSON=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null) ||
    fail_closed "could not read the exact submit workflow root"
ROOT_CONTEXT=$(printf '%s' "$ROOT_JSON" | jq -ec \
    --arg id "$ROOT_BEAD_ID" '
    if type == "array" and length == 1 and .[0].id == $id and
       .[0].status == "in_progress" and
       .[0].metadata["gc.kind"] == "workflow" and
       .[0].metadata["gc.formula_contract"] == "graph.v2" and
       (((.[0].metadata | has("gc.formula_name")) | not) or
        .[0].metadata["gc.formula_name"] == "mol-polecat-work") and
       (((.[0].metadata | has("gc.outcome")) | not) or
        .[0].metadata["gc.outcome"] == "") and
       (.[0].metadata["gc.input_convoy_id"] | type) == "string" and
       (.[0].metadata["gc.input_convoy_id"] | length) > 0 and
       (.[0].metadata["gc.var.base_branch"] | type) == "string" and
       (.[0].metadata["gc.var.base_branch"] | length) > 0 and
       ((.[0].metadata["gc.var.rig_name"] // "") | type) == "string" and
       ((.[0].metadata["gc.var.binding_prefix"] // "") | type) == "string"
    then {
      convoy: .[0].metadata["gc.input_convoy_id"],
      base: .[0].metadata["gc.var.base_branch"],
      rig: (.[0].metadata["gc.var.rig_name"] // ""),
      prefix: (.[0].metadata["gc.var.binding_prefix"] // "")
    }
    else error("submit workflow root provenance mismatch")
    end' 2>/dev/null) ||
    fail_closed "submit workflow root provenance did not verify"
ROOT_CONVOY_ID=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.convoy') ||
    fail_closed "could not decode the root input convoy"
ROOT_BASE_BRANCH=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.base') ||
    fail_closed "could not decode the root base branch"
ROOT_RIG_NAME=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.rig') ||
    fail_closed "could not decode the root rig"
ROOT_BINDING_PREFIX=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.prefix') ||
    fail_closed "could not decode the root binding prefix"
safe_atom "$ROOT_CONVOY_ID" ||
    fail_closed "the root input convoy id is unsafe"
safe_atom "$ROOT_BASE_BRANCH" ||
    fail_closed "the root base branch is unsafe"
safe_component "$ROOT_RIG_NAME" && safe_component "$ROOT_BINDING_PREFIX" ||
    fail_closed "the workflow root rig or binding prefix is unsafe"
if [[ -n "${GC_RIG:-}" && "$ROOT_RIG_NAME" != "$GC_RIG" ]]; then
    fail_closed "workflow root rig $ROOT_RIG_NAME does not match runtime rig $GC_RIG"
fi
REFINERY_TARGET="${ROOT_RIG_NAME:+$ROOT_RIG_NAME/}${ROOT_BINDING_PREFIX}refinery"
safe_atom "$REFINERY_TARGET" ||
    fail_closed "the workflow root does not define a safe refinery identity"

if [[ "$ACTION" == "complete" && "$ROOT_CONVOY_ID" != "$CONVOY_ID" ]]; then
    fail_closed "submit step belongs to convoy $ROOT_CONVOY_ID, not $CONVOY_ID"
fi
CONVOY_ID=$ROOT_CONVOY_ID

CONVOY_JSON=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
    fail_closed "could not read the exact input convoy"
DERIVED_SOURCE_ID=$(printf '%s' "$CONVOY_JSON" | jq -er '
    if type == "object" and (.children | type) == "array" and
       (.children | length) == 1 and
       (.children[0].id | type) == "string" and
       (.children[0].id | length) > 0
    then .children[0].id
    else error("input convoy does not have one exact source")
    end' 2>/dev/null) ||
    fail_closed "input convoy does not have one exact source"
safe_atom "$DERIVED_SOURCE_ID" ||
    fail_closed "the derived source id is unsafe"
if [[ "$ACTION" == "complete" && "$DERIVED_SOURCE_ID" != "$SOURCE_ID" ]]; then
    fail_closed "input convoy source is $DERIVED_SOURCE_ID, not $SOURCE_ID"
fi
SOURCE_ID=$DERIVED_SOURCE_ID
CANONICAL_SOURCE_BRANCH="polecat/$SOURCE_ID"
SUBMIT_SESSION_ID=$CURRENT_SESSION_ID

load_source() {
    SOURCE_JSON=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) || return 1
    SOURCE_RECORD=$(printf '%s' "$SOURCE_JSON" | jq -ce --arg id "$SOURCE_ID" '
        if type == "array" and length == 1 and .[0].id == $id and
           (.[0].status | type) == "string" and
           ((.[0].assignee // "") | type) == "string" and
           ((.[0].metadata // {}) | type) == "object" and
           (((.[0].metadata | has("branch")) | not) or
            (.[0].metadata.branch | type) == "string") and
           (((.[0].metadata | has("target")) | not) or
            (.[0].metadata.target | type) == "string") and
           (((.[0].metadata | has("branch_ready")) | not) or
            (.[0].metadata.branch_ready | type) == "boolean") and
           (((.[0].metadata | has("halt_reason")) | not) or
            (.[0].metadata.halt_reason | type) == "string") and
           (((.[0].metadata | has("gc.polecat_submit_convoy")) | not) or
            (.[0].metadata["gc.polecat_submit_convoy"] | type) == "string")
        then .[0]
        else error("source identity/state mismatch")
        end' 2>/dev/null) || return 1
    SOURCE_STATUS=$(printf '%s' "$SOURCE_RECORD" | jq -er '.status')
    SOURCE_ASSIGNEE=$(printf '%s' "$SOURCE_RECORD" | jq -er '.assignee // ""')
    SOURCE_BRANCH=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata.branch // ""')
    SOURCE_TARGET=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata.target // ""')
    SOURCE_BRANCH_READY=$(printf '%s' "$SOURCE_RECORD" | jq -er '
        if .metadata | has("branch_ready")
        then (.metadata.branch_ready | tostring)
        else ""
        end')
    SOURCE_HALT_REASON=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata.halt_reason // ""')
    SOURCE_SUBMIT_CONVOY=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_convoy"] // ""')
}

load_source ||
    fail_closed "could not read the exact source bead"

revalidate_context() {
    local step_now root_now
    step_now=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) || return 1
    printf '%s' "$step_now" | jq -e \
        --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
        --arg ref "$STEP_REF" --arg root "$ROOT_BEAD_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "in_progress" and .[0].assignee == $actor and
        .[0].metadata["gc.step_ref"] == $ref and
        .[0].metadata["gc.root_bead_id"] == $root and
        (((.[0].metadata | has("gc.outcome")) | not) or
         .[0].metadata["gc.outcome"] == "")
    ' >/dev/null 2>&1 || return 1
    root_now=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null) || return 1
    printf '%s' "$root_now" | jq -e \
        --arg id "$ROOT_BEAD_ID" --arg convoy "$CONVOY_ID" \
        --arg base "$ROOT_BASE_BRANCH" --arg rig "$ROOT_RIG_NAME" \
        --arg prefix "$ROOT_BINDING_PREFIX" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "in_progress" and
        .[0].metadata["gc.kind"] == "workflow" and
        .[0].metadata["gc.formula_contract"] == "graph.v2" and
        (((.[0].metadata | has("gc.formula_name")) | not) or
         .[0].metadata["gc.formula_name"] == "mol-polecat-work") and
        .[0].metadata["gc.input_convoy_id"] == $convoy and
        .[0].metadata["gc.var.base_branch"] == $base and
        (.[0].metadata["gc.var.rig_name"] // "") == $rig and
        (.[0].metadata["gc.var.binding_prefix"] // "") == $prefix and
        (((.[0].metadata | has("gc.outcome")) | not) or
         .[0].metadata["gc.outcome"] == "")
    ' >/dev/null 2>&1
}

close_step() {
    local outcome=$1 replay_mode=$2 replay_terminal=$3 note=$4 verify
    case "$replay_mode:$replay_terminal" in
        auto_push_false:branch_ready|refinery:refinery|refinery:closed) ;;
        *) return 1 ;;
    esac
    revalidate_context || return 1
    load_source || return 1
    evidence_matches || return 1
    run_gc_bd update "$STEP_BEAD_ID" \
        --set-metadata "gc.outcome=$outcome" \
        --set-metadata "gc.polecat_submit_version=$REPLAY_VERSION" \
        --set-metadata "gc.polecat_submit_source_id=$SOURCE_ID" \
        --set-metadata "gc.polecat_submit_convoy_id=$CONVOY_ID" \
        --set-metadata "gc.polecat_submit_branch=$CANONICAL_SOURCE_BRANCH" \
        --set-metadata "gc.polecat_submit_mode=$replay_mode" \
        --set-metadata "gc.polecat_submit_terminal=$replay_terminal" \
        --set-metadata "gc.polecat_submit_session_id=$SUBMIT_SESSION_ID" \
        --status=closed \
        --append-notes "$note" >/dev/null || true
    verify=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) || return 1
    printf '%s' "$verify" | jq -e \
        --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
        --arg ref "$STEP_REF" --arg root "$ROOT_BEAD_ID" \
        --arg outcome "$outcome" --argjson version "$REPLAY_VERSION" \
        --arg source "$SOURCE_ID" --arg convoy "$CONVOY_ID" \
        --arg branch "$CANONICAL_SOURCE_BRANCH" \
        --arg mode "$replay_mode" --arg terminal "$replay_terminal" \
        --arg session "$SUBMIT_SESSION_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "closed" and .[0].assignee == $actor and
        .[0].metadata["gc.step_ref"] == $ref and
        .[0].metadata["gc.root_bead_id"] == $root and
        .[0].metadata["gc.outcome"] == $outcome and
        .[0].metadata["gc.polecat_submit_version"] == $version and
        .[0].metadata["gc.polecat_submit_source_id"] == $source and
        .[0].metadata["gc.polecat_submit_convoy_id"] == $convoy and
        .[0].metadata["gc.polecat_submit_branch"] == $branch and
        .[0].metadata["gc.polecat_submit_mode"] == $mode and
        .[0].metadata["gc.polecat_submit_terminal"] == $terminal and
        .[0].metadata["gc.polecat_submit_session_id"] == $session
    ' >/dev/null 2>&1
}

if [[ "$ACTION" == "guard" ]]; then
    if [[ -n "$SOURCE_SUBMIT_CONVOY" &&
          "$SOURCE_SUBMIT_CONVOY" != "$CONVOY_ID" ]]; then
        fail_closed "source $SOURCE_ID belongs to submit generation $SOURCE_SUBMIT_CONVOY, not $CONVOY_ID"
    fi

    TERMINAL_MODE=""
    TERMINAL_KIND=""
    if [[ "$SOURCE_SUBMIT_CONVOY" == "$CONVOY_ID" &&
          "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" &&
          "$SOURCE_TARGET" == "$ROOT_BASE_BRANCH" ]]; then
        if [[ "$SOURCE_STATUS" == "closed" ]]; then
            TERMINAL_MODE="refinery"
            TERMINAL_KIND="closed"
        elif [[ ("$SOURCE_STATUS" == "open" ||
                 "$SOURCE_STATUS" == "in_progress") &&
                "$SOURCE_ASSIGNEE" == "$REFINERY_TARGET" ]]; then
            TERMINAL_MODE="refinery"
            TERMINAL_KIND="refinery"
        elif [[ "$SOURCE_STATUS" == "open" &&
                -z "$SOURCE_ASSIGNEE" &&
                "$SOURCE_BRANCH_READY" == "true" &&
                "$SOURCE_HALT_REASON" == "auto_push_false" ]]; then
            TERMINAL_MODE="auto_push_false"
            TERMINAL_KIND="branch_ready"
        fi
    fi

    if [[ -n "$TERMINAL_MODE" ]]; then
        load_source ||
            fail_closed "could not re-read terminal source evidence"
        [[ "$SOURCE_SUBMIT_CONVOY" == "$CONVOY_ID" &&
           "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" &&
           "$SOURCE_TARGET" == "$ROOT_BASE_BRANCH" ]] ||
            fail_closed "terminal source generation, branch, or target changed before completion"
        case "$TERMINAL_MODE:$TERMINAL_KIND" in
            refinery:closed)
                [[ "$SOURCE_STATUS" == "closed" ]] ||
                    fail_closed "closed source evidence changed before completion"
                ;;
            refinery:refinery)
                [[ ("$SOURCE_STATUS" == "open" ||
                    "$SOURCE_STATUS" == "in_progress") &&
                   "$SOURCE_ASSIGNEE" == "$REFINERY_TARGET" ]] ||
                    fail_closed "refinery source evidence changed before completion"
                ;;
            auto_push_false:branch_ready)
                [[ "$SOURCE_STATUS" == "open" &&
                   -z "$SOURCE_ASSIGNEE" &&
                   "$SOURCE_BRANCH_READY" == "true" &&
                   "$SOURCE_HALT_REASON" == "auto_push_false" ]] ||
                    fail_closed "branch-ready source evidence changed before completion"
                ;;
            *)
                fail_closed "terminal source classification was incoherent"
                ;;
        esac
        jq -cn \
            --arg contract "polecat-submit.v1" \
            --arg action "terminal" \
            --arg step "$STEP_BEAD_ID" \
            --arg assignee "$STEP_ASSIGNEE" \
            --arg root "$ROOT_BEAD_ID" \
            --arg convoy "$CONVOY_ID" \
            --arg source "$SOURCE_ID" \
            --arg mode "$TERMINAL_MODE" \
            --arg branch "$CANONICAL_SOURCE_BRANCH" \
            --arg status "$SOURCE_STATUS" \
            --arg source_assignee "$SOURCE_ASSIGNEE" \
            '{contract: $contract, action: $action, step: $step,
              assignee: $assignee, root: $root, convoy: $convoy,
              source: $source, mode: $mode, branch: $branch,
              status: $status, source_assignee: $source_assignee,
              replay: false}' ||
            fail_closed "could not encode terminal submit-state result"
        exit 0
    fi
    if [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
          -z "$SOURCE_SUBMIT_CONVOY" ]]; then
        jq -cn \
            --arg contract "polecat-submit.v1" \
            --arg action "proceed" \
            --arg step "$STEP_BEAD_ID" \
            --arg assignee "$STEP_ASSIGNEE" \
            --arg root "$ROOT_BEAD_ID" \
            --arg convoy "$CONVOY_ID" \
            --arg source "$SOURCE_ID" \
            --arg branch "$CANONICAL_SOURCE_BRANCH" \
            '{contract: $contract, action: $action, step: $step,
              assignee: $assignee, root: $root, convoy: $convoy,
              source: $source, mode: "", branch: $branch,
              status: "open", source_assignee: "", replay: false}' ||
            fail_closed "could not encode proceed submit-state result"
        exit 0
    fi
    if [[ -n "$SOURCE_SUBMIT_CONVOY" ]]; then
        fail_closed "source $SOURCE_ID has current submit generation but incomplete terminal evidence"
    fi
    if [[ "$SOURCE_STATUS" == "closed" ]]; then
        fail_closed "closed source lacks exact submit-generation evidence"
    fi
    load_source ||
        fail_closed "could not re-read conflicting source evidence"
    if [[ -n "$SOURCE_SUBMIT_CONVOY" ]]; then
        fail_closed "conflicting source gained submit-generation evidence before fail completion"
    fi
    if [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
          -z "$SOURCE_SUBMIT_CONVOY" ]]; then
        fail_closed "conflicting source became proceedable before fail completion"
    fi
    if [[ "$SOURCE_ASSIGNEE" == "$REFINERY_TARGET" ]]; then
        fail_closed "refinery-assigned source lacks exact terminal generation evidence"
    fi
    echo "POLECAT_SUBMIT_CONFLICT source=$SOURCE_ID status=$SOURCE_STATUS assignee=${SOURCE_ASSIGNEE:-unassigned}" >&2
    exit "$EXIT_INDETERMINATE"
fi

evidence_matches() {
    [[ "$SOURCE_BRANCH" == "$EXPECTED_BRANCH" &&
       "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" &&
       "$SOURCE_TARGET" == "$ROOT_BASE_BRANCH" &&
       "$SOURCE_SUBMIT_CONVOY" == "$CONVOY_ID" ]] || return 1
    case "$MODE" in
        auto_push_false)
            [[ "$SOURCE_STATUS" == "open" &&
               -z "$SOURCE_ASSIGNEE" &&
               "$SOURCE_BRANCH_READY" == "true" &&
               "$SOURCE_HALT_REASON" == "auto_push_false" ]]
            ;;
        refinery)
            [[ "$SOURCE_STATUS" == "closed" ||
               (("$SOURCE_STATUS" == "open" ||
                 "$SOURCE_STATUS" == "in_progress") &&
                "$SOURCE_ASSIGNEE" == "$REFINERY_TARGET") ]]
            ;;
    esac
}

evidence_matches ||
    fail_closed "source $SOURCE_ID does not satisfy exact $MODE completion evidence"
# Re-read immediately before the workflow-step mutation. A changed source is
# not evidence for the earlier observation.
load_source ||
    fail_closed "could not re-read source evidence before completion"
evidence_matches ||
    fail_closed "source $SOURCE_ID evidence changed before completion"

case "$MODE" in
    auto_push_false) COMPLETION_TERMINAL="branch_ready" ;;
    refinery)
        if [[ "$SOURCE_STATUS" == "closed" ]]; then
            COMPLETION_TERMINAL="closed"
        else
            COMPLETION_TERMINAL="refinery"
        fi
        ;;
esac
close_step pass "$MODE" "$COMPLETION_TERMINAL" \
    "Submit complete with $MODE evidence on source $SOURCE_ID branch $EXPECTED_BRANCH" ||
    fail_closed "submit step did not persist and read back closed/pass"
printf 'POLECAT_SUBMIT_COMPLETE step=%s assignee=%s root=%s convoy=%s source=%s mode=%s branch=%s\n' \
    "$STEP_BEAD_ID" "$STEP_ASSIGNEE" "$ROOT_BEAD_ID" "$CONVOY_ID" \
    "$SOURCE_ID" "$MODE" "$EXPECTED_BRANCH"
