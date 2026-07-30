#!/usr/bin/env bash
# Deterministic workspace creation, recovery, setup, and Graph-v2 completion.

set -u -o pipefail

# Never let inherited repository selectors redirect a validation or mutation.
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

EXIT_USAGE=2
EXIT_HARD=64
EXIT_INDETERMINATE=75
STEP_REF="mol-polecat-work.workspace-setup"
RECEIPT_VERSION="1"

usage() {
    cat >&2 <<'EOF'
Usage:
  gc gastown polecat-workspace execute
EOF
}

ACTION=${1:-}
if [[ -n "$ACTION" ]]; then
    shift
fi
if [[ "$ACTION" != "execute" || $# -ne 0 ]]; then
    usage
    exit "$EXIT_USAGE"
fi

safe_atom() {
    local value=$1
    [[ -n "$value" && "$value" != -* &&
       "$value" != *' '* &&
       "$value" != *$'\n'* && "$value" != *$'\r'* &&
       "$value" != *$'\t'* ]]
}

safe_component() {
    local value=$1
    [[ "$value" != *[!A-Za-z0-9._-]* ]]
}

safe_path_component() {
    local value=$1
    [[ -n "$value" && "$value" != "." && "$value" != ".." ]] &&
        safe_component "$value"
}

is_oid() {
    local value=$1
    case "${#value}" in
        40|64) ;;
        *) return 1 ;;
    esac
    [[ "$value" != *[!0-9a-f]* ]]
}

indeterminate() {
    echo "POLECAT_WORKSPACE_INDETERMINATE: $*" >&2
    echo "Protected state was preserved; fix the diagnostic and rerun the same command." >&2
    exit "$EXIT_INDETERMINATE"
}

[[ -n "${GC_CITY_PATH:-}" && -n "${GC_RIG:-}" &&
   -n "${GC_RIG_ROOT:-}" ]] ||
    indeterminate "GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required"
safe_path_component "$GC_RIG" ||
    indeterminate "the runtime rig name is unsafe"
RUNTIME_RIG=$GC_RIG
CITY_ROOT=$(CDPATH= cd -- "$GC_CITY_PATH" 2>/dev/null && pwd -P) ||
    indeterminate "could not canonicalize the city root"
RIG_ROOT=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) ||
    indeterminate "could not canonicalize the rig root"

GC_CMD=${GC_BIN:-}
if [[ -z "$GC_CMD" ]]; then
    GC_CMD=$(command -v gc 2>/dev/null || true)
fi
[[ -n "$GC_CMD" && -x "$GC_CMD" ]] ||
    indeterminate "the invoking gc executable is unavailable"
command -v jq >/dev/null 2>&1 ||
    indeterminate "jq is required"
GIT_CMD=$(command -v git 2>/dev/null || true)
[[ -n "$GIT_CMD" && -x "$GIT_CMD" ]] ||
    indeterminate "git is required"

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

run_gc() {
    GC_NO_API=1 \
    GC_CITY="$CITY_ROOT" \
    GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" \
    GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$RIG_ROOT" \
    GC_STORE_SCOPE=rig \
        "$GC_CMD" "$@"
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

convoy_source_id() {
    local convoy_json=$1 expected_convoy=$2
    printf '%s' "$convoy_json" | jq -er --arg convoy "$expected_convoy" '
        if type == "object" and .schema_version == "1" and
           (.convoy | type) == "object" and .convoy.id == $convoy and
           (.children | type) == "array" and (.children | length) == 1 and
           (.children[0].id | type) == "string" and
           (.children[0].id | length) > 0
        then .children[0].id
        else error("convoy identity/schema/source mismatch")
        end' 2>/dev/null
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
        indeterminate "a current runtime identity is unsafe"
done
[[ "${#RUNTIME_IDENTITIES[@]}" -gt 0 ]] ||
    indeterminate "no current runtime identity is available"
CURRENT_SESSION_ID=${GC_SESSION_ID:-}
safe_atom "$CURRENT_SESSION_ID" ||
    indeterminate "an exact nonempty GC_SESSION_ID is required"

identity_is_current() {
    local candidate=$1 identity
    for identity in "${RUNTIME_IDENTITIES[@]}"; do
        [[ "$candidate" != "$identity" ]] || return 0
    done
    return 1
}

replay_closed_workspace() {
    local listed matches candidate_id candidate_json candidate
    local candidate_count=0 replay_step="" replay_root="" replay_convoy=""
    local replay_source="" replay_branch="" replay_artifact=""
    local replay_base="" replay_fork="" replay_head="" replay_setup=""
    local root_json convoy_json derived_source
    declare -a seen_ids=()

    for identity in "${RUNTIME_IDENTITIES[@]}"; do
        listed=$(run_gc_bd list --assignee "$identity" --status=closed \
            --limit=0 --json 2>/dev/null) || return 2
        matches=$(printf '%s' "$listed" | jq -ce \
            --arg actor "$identity" --arg ref "$STEP_REF" \
            --arg session "$CURRENT_SESSION_ID" \
            --arg version "$RECEIPT_VERSION" '
            if type == "array" and
               all(.[]; type == "object" and .status == "closed" and
                   .assignee == $actor and ((.metadata // {}) | type) == "object")
            then [.[] |
              select(.metadata["gc.step_ref"] == $ref and
                     .metadata["gc.outcome"] == "pass" and
                     ((.metadata["gc.polecat_workspace_version"] // "" |
                       tostring) == $version) and
                     .metadata["gc.polecat_workspace_session_id"] == $session)]
            else error("closed workspace query contradicted its filters")
            end' 2>/dev/null) || return 2
        while IFS= read -r candidate_id; do
            [[ -n "$candidate_id" ]] || continue
            safe_atom "$candidate_id" || return 2
            for seen in "${seen_ids[@]}"; do
                [[ "$seen" != "$candidate_id" ]] || return 2
            done
            seen_ids+=("$candidate_id")
        done < <(printf '%s' "$matches" | jq -r '.[].id')
    done

    for candidate_id in "${seen_ids[@]}"; do
        candidate_json=$(run_gc_bd show "$candidate_id" --json 2>/dev/null) ||
            return 2
        candidate=$(printf '%s' "$candidate_json" | jq -ce \
            --arg id "$candidate_id" --arg ref "$STEP_REF" \
            --arg session "$CURRENT_SESSION_ID" \
            --arg version "$RECEIPT_VERSION" '
            if type == "array" and length == 1 and .[0].id == $id and
               .[0].status == "closed" and
               (.[0].assignee | type) == "string" and
               (.[0].assignee | length) > 0 and
               .[0].metadata["gc.step_ref"] == $ref and
               .[0].metadata["gc.outcome"] == "pass" and
               ((.[0].metadata["gc.polecat_workspace_version"] // "" |
                 tostring) == $version) and
               .[0].metadata["gc.polecat_workspace_session_id"] == $session and
               (.[0].metadata["gc.root_bead_id"] | type) == "string" and
               (.[0].metadata["gc.root_bead_id"] | length) > 0 and
               (.[0].metadata["gc.polecat_workspace_convoy_id"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_convoy_id"] | length) > 0 and
               (.[0].metadata["gc.polecat_workspace_source_id"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_source_id"] | length) > 0 and
               (.[0].metadata["gc.polecat_workspace_branch"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_branch"] | length) > 0 and
               (.[0].metadata["gc.polecat_workspace_artifact_dir"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_artifact_dir"] | length) > 0 and
               (.[0].metadata["gc.polecat_workspace_base_branch"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_base_branch"] | length) > 0 and
               (.[0].metadata["gc.polecat_workspace_fork_sha"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_head_sha"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_setup_digest"] | type) == "string"
            then {
              assignee: .[0].assignee,
              root: .[0].metadata["gc.root_bead_id"],
              convoy: .[0].metadata["gc.polecat_workspace_convoy_id"],
              source: .[0].metadata["gc.polecat_workspace_source_id"],
              branch: .[0].metadata["gc.polecat_workspace_branch"],
              artifact: .[0].metadata["gc.polecat_workspace_artifact_dir"],
              base: .[0].metadata["gc.polecat_workspace_base_branch"],
              fork: .[0].metadata["gc.polecat_workspace_fork_sha"],
              head: .[0].metadata["gc.polecat_workspace_head_sha"],
              setup: .[0].metadata["gc.polecat_workspace_setup_digest"]
            }
            else error("closed workspace receipt is incomplete")
            end' 2>/dev/null) || return 2
        identity_is_current "$(printf '%s' "$candidate" | jq -er '.assignee')" ||
            return 2
        replay_root=$(printf '%s' "$candidate" | jq -er '.root') || return 2
        replay_convoy=$(printf '%s' "$candidate" | jq -er '.convoy') || return 2
        replay_source=$(printf '%s' "$candidate" | jq -er '.source') || return 2
        replay_branch=$(printf '%s' "$candidate" | jq -er '.branch') || return 2
        replay_artifact=$(printf '%s' "$candidate" | jq -er '.artifact') || return 2
        replay_base=$(printf '%s' "$candidate" | jq -er '.base') || return 2
        replay_fork=$(printf '%s' "$candidate" | jq -er '.fork') || return 2
        replay_head=$(printf '%s' "$candidate" | jq -er '.head') || return 2
        replay_setup=$(printf '%s' "$candidate" | jq -er '.setup') || return 2
        safe_atom "$replay_root" && safe_atom "$replay_convoy" &&
            safe_path_component "$replay_source" && safe_atom "$replay_base" ||
            return 2
        [[ "$replay_branch" == "polecat/$replay_source" ]] || return 2
        is_oid "$replay_fork" && is_oid "$replay_head" &&
            is_oid "$replay_setup" || return 2
        [[ "$replay_artifact" == /* &&
           "$replay_artifact" != *$'\n'* &&
           "$replay_artifact" != *$'\r'* &&
           "$replay_artifact" != *$'\t'* ]] || return 2

        root_json=$(run_gc_bd show "$replay_root" --json 2>/dev/null) || return 2
        printf '%s' "$root_json" | jq -e \
            --arg id "$replay_root" --arg convoy "$replay_convoy" \
            --arg base "$replay_base" --arg rig "$RUNTIME_RIG" '
            type == "array" and length == 1 and .[0].id == $id and
            (.[0].status == "in_progress" or .[0].status == "closed") and
            .[0].metadata["gc.kind"] == "workflow" and
            .[0].metadata["gc.formula_contract"] == "graph.v2" and
            (((.[0].metadata | has("gc.formula_name")) | not) or
             .[0].metadata["gc.formula_name"] == "mol-polecat-work") and
            .[0].metadata["gc.input_convoy_id"] == $convoy and
            .[0].metadata["gc.var.base_branch"] == $base and
            (.[0].metadata["gc.var.rig_name"] // "") == $rig
        ' >/dev/null 2>&1 || return 2
        convoy_json=$(run_gc_convoy status "$replay_convoy" --json 2>/dev/null) ||
            return 2
        derived_source=$(convoy_source_id "$convoy_json" "$replay_convoy") ||
            return 2
        [[ "$derived_source" == "$replay_source" ]] || return 2
        candidate_count=$((candidate_count + 1))
        replay_step=$candidate_id
    done

    [[ "$candidate_count" -le 1 ]] || return 2
    [[ "$candidate_count" -eq 1 ]] || return 1
    printf 'POLECAT_WORKSPACE_EXECUTE_COMPLETE step=%s root=%s convoy=%s source=%s branch=%s artifact=%s replay=true session=%s\n' \
        "$replay_step" "$replay_root" "$replay_convoy" "$replay_source" \
        "$replay_branch" "$replay_artifact" "$CURRENT_SESSION_ID"
    return 0
}

STEP_MATCHES='[]'
for identity in "${RUNTIME_IDENTITIES[@]}"; do
    listed=$(run_gc_bd list --assignee "$identity" --status=in_progress \
        --limit=0 --json 2>/dev/null) ||
        indeterminate "could not list in-progress steps for identity $identity"
    matches=$(printf '%s' "$listed" | jq -ce \
        --arg actor "$identity" --arg ref "$STEP_REF" '
        if type == "array" and
           all(.[]; type == "object" and .status == "in_progress" and
               .assignee == $actor and ((.metadata // {}) | type) == "object")
        then [.[] |
          select(.metadata["gc.step_ref"] == $ref and
                 (((.metadata | has("gc.outcome")) | not) or
                  .metadata["gc.outcome"] == ""))]
        else error("workspace query contradicted its exact filters")
        end' 2>/dev/null) ||
        indeterminate "the in-progress step list for identity $identity was malformed"
    STEP_MATCHES=$(jq -cn \
        --argjson accumulated "$STEP_MATCHES" \
        --argjson matches "$matches" \
        '$accumulated + $matches') ||
        indeterminate "could not aggregate current workspace steps"
done

STEP_MATCH_COUNT=$(printf '%s' "$STEP_MATCHES" | jq -er 'length') ||
    indeterminate "could not count current workspace steps"
if [[ "$STEP_MATCH_COUNT" == "0" ]]; then
    replay_output=$(replay_closed_workspace)
    replay_code=$?
    case "$replay_code" in
        0)
            printf '%s\n' "$replay_output"
            exit 0
            ;;
        1)
            indeterminate "no current workspace step or coherent closed replay was found"
            ;;
        *)
            indeterminate "closed workspace history was malformed or ambiguous"
            ;;
    esac
fi
[[ "$STEP_MATCH_COUNT" == "1" ]] ||
    indeterminate "expected exactly one current workspace step across runtime identities"

STEP_BEAD_ID=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].id') ||
    indeterminate "the current workspace step has no exact id"
STEP_ASSIGNEE=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].assignee') ||
    indeterminate "the current workspace step has no exact assignee"
safe_atom "$STEP_BEAD_ID" && safe_atom "$STEP_ASSIGNEE" ||
    indeterminate "the current workspace step identity is unsafe"

STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not read the exact workspace step"
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
    else error("workspace step identity/state mismatch")
    end' 2>/dev/null) ||
    indeterminate "workspace step identity, ownership, or state did not verify"
safe_atom "$ROOT_BEAD_ID" ||
    indeterminate "the workspace workflow root id is unsafe"

root_context() {
    local root_json=$1
    printf '%s' "$root_json" | jq -ec \
        --arg id "$ROOT_BEAD_ID" '
        def vars:
          .[0].metadata["gc.graphv2_vars.v1"] as $raw |
          if ($raw | type) == "object" then $raw
          elif ($raw | type) == "string" then ($raw | fromjson)
          else error("missing graph variable snapshot")
          end;
        (vars) as $vars |
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
           ((.[0].metadata["gc.var.binding_prefix"] // "") | type) == "string" and
           ($vars | type) == "object" and
           ($vars.base_branch | type) == "string" and
           ($vars.rig_name | type) == "string" and
           ($vars.binding_prefix | type) == "string" and
           ($vars.setup_command | type) == "string" and
           $vars.base_branch == .[0].metadata["gc.var.base_branch"] and
           $vars.rig_name == (.[0].metadata["gc.var.rig_name"] // "") and
           $vars.binding_prefix ==
             (.[0].metadata["gc.var.binding_prefix"] // "")
        then {
          convoy: .[0].metadata["gc.input_convoy_id"],
          base: $vars.base_branch,
          rig: $vars.rig_name,
          prefix: $vars.binding_prefix,
          setup: $vars.setup_command
        }
        else error("workspace workflow root provenance mismatch")
        end' 2>/dev/null
}

ROOT_JSON=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not read the exact workspace workflow root"
ROOT_CONTEXT=$(root_context "$ROOT_JSON") ||
    indeterminate "workspace root provenance or graph variable snapshot did not verify"
ROOT_CONTEXT_CANONICAL=$(printf '%s' "$ROOT_CONTEXT" | jq -cS .) ||
    indeterminate "could not canonicalize the workspace root context"
CONVOY_ID=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.convoy') ||
    indeterminate "could not decode the root input convoy"
ROOT_BASE_BRANCH=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.base') ||
    indeterminate "could not decode the root base branch"
ROOT_RIG_NAME=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.rig') ||
    indeterminate "could not decode the root rig"
ROOT_BINDING_PREFIX=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.prefix') ||
    indeterminate "could not decode the root binding prefix"
ROOT_SETUP_COMMAND=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.setup') ||
    indeterminate "could not decode the root setup command"
safe_atom "$CONVOY_ID" && safe_atom "$ROOT_BASE_BRANCH" ||
    indeterminate "the root convoy or base branch is unsafe"
safe_path_component "$ROOT_RIG_NAME" && safe_component "$ROOT_BINDING_PREFIX" ||
    indeterminate "the root rig or binding prefix is unsafe"
[[ "$ROOT_RIG_NAME" == "$RUNTIME_RIG" ]] ||
    indeterminate "workflow root rig $ROOT_RIG_NAME does not match runtime rig $RUNTIME_RIG"
"$GIT_CMD" -C "$RIG_ROOT" check-ref-format "refs/heads/$ROOT_BASE_BRANCH" \
    >/dev/null 2>&1 ||
    indeterminate "the root base branch is not a valid Git branch"

CONVOY_JSON=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
    indeterminate "could not read the exact input convoy"
SOURCE_ID=$(convoy_source_id "$CONVOY_JSON" "$CONVOY_ID") ||
    indeterminate "input convoy identity/schema/source did not verify"
safe_path_component "$SOURCE_ID" ||
    indeterminate "the derived source id is unsafe"
EXPECTED_BRANCH="polecat/$SOURCE_ID"
"$GIT_CMD" -C "$RIG_ROOT" check-ref-format "refs/heads/$EXPECTED_BRANCH" \
    >/dev/null 2>&1 ||
    indeterminate "the canonical task branch is not a valid Git branch"
WITNESS_TARGET="${ROOT_RIG_NAME:+$ROOT_RIG_NAME/}${ROOT_BINDING_PREFIX}witness"
safe_atom "$WITNESS_TARGET" ||
    indeterminate "the workflow root does not define a safe witness identity"

SOURCE_JSON=""
SOURCE_STATUS=""
SOURCE_ASSIGNEE=""
SOURCE_BRANCH=""
SOURCE_REJECTION=""
SOURCE_ARTIFACT_DIR=""
SOURCE_LEGACY_WORK_DIR=""
SOURCE_FORK_SHA=""

load_source() {
    SOURCE_JSON=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) || return 1
    printf '%s' "$SOURCE_JSON" | jq -e --arg id "$SOURCE_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        (.[0].status | type) == "string" and
        ((.[0].assignee // "") | type) == "string" and
        ((.[0].metadata // {}) | type) == "object" and
        ((.[0].metadata.branch // "") | type) == "string" and
        ((.[0].metadata.rejection_reason // "") | type) == "string" and
        ((.[0].metadata.artifact_dir // "") | type) == "string" and
        ((.[0].metadata.work_dir // "") | type) == "string" and
        ((.[0].metadata.fork_sha // "") | type) == "string"
    ' >/dev/null 2>&1 || return 1
    SOURCE_STATUS=$(printf '%s' "$SOURCE_JSON" | jq -er '.[0].status') ||
        return 1
    SOURCE_ASSIGNEE=$(printf '%s' "$SOURCE_JSON" | jq -er \
        '.[0].assignee // ""') || return 1
    SOURCE_BRANCH=$(printf '%s' "$SOURCE_JSON" | jq -er \
        '.[0].metadata.branch // ""') || return 1
    SOURCE_REJECTION=$(printf '%s' "$SOURCE_JSON" | jq -er \
        '.[0].metadata.rejection_reason // ""') || return 1
    SOURCE_ARTIFACT_DIR=$(printf '%s' "$SOURCE_JSON" | jq -er \
        '.[0].metadata.artifact_dir // ""') || return 1
    SOURCE_LEGACY_WORK_DIR=$(printf '%s' "$SOURCE_JSON" | jq -er \
        '.[0].metadata.work_dir // ""') || return 1
    SOURCE_FORK_SHA=$(printf '%s' "$SOURCE_JSON" | jq -er \
        '.[0].metadata.fork_sha // ""') || return 1
}

load_source ||
    indeterminate "could not read the exact source bead"
[[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" ]] ||
    indeterminate "source is not open and unassigned"

revalidate_graph_context() {
    local step_now root_now root_context_now convoy_now source_now
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
    root_context_now=$(root_context "$root_now") || return 1
    root_context_now=$(printf '%s' "$root_context_now" | jq -cS .) || return 1
    [[ "$root_context_now" == "$ROOT_CONTEXT_CANONICAL" ]] || return 1
    convoy_now=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
        return 1
    source_now=$(convoy_source_id "$convoy_now" "$CONVOY_ID") || return 1
    [[ "$source_now" == "$SOURCE_ID" ]]
}

durable_hard_block() {
    local code=$1 reason=$2 block_code
    echo "POLECAT_WORKSPACE_HARD: $code: $reason" >&2
    run_gc gastown polecat-step block \
        --convoy "$CONVOY_ID" \
        --step-ref "$STEP_REF" \
        --code "$code" \
        --reason "$reason"
    block_code=$?
    if [[ "$block_code" -ne 0 ]]; then
        echo "POLECAT_WORKSPACE_INDETERMINATE: durable block failed (exit $block_code)" >&2
        exit "$EXIT_INDETERMINATE"
    fi
    # A successful block is terminal quarantine, never workspace success.
    exit "$EXIT_HARD"
}

# BEGIN ARTIFACT_WORKTREE_VALIDATOR
artifact_git_common_dir() {
    local repo_dir=$1 common_dir
    common_dir=$("$GIT_CMD" -C "$repo_dir" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) || return 1
    (CDPATH= cd -- "$common_dir" 2>/dev/null && pwd -P)
}

ARTIFACT_POINTER_LINE=
artifact_read_one_line_file() {
    local file=$1 line count=0
    ARTIFACT_POINTER_LINE=
    [[ -f "$file" && ! -L "$file" ]] || return 1
    while IFS= read -r line || [[ -n "$line" ]]; do
        count=$((count + 1))
        [[ "$count" -eq 1 ]] || return 1
        ARTIFACT_POINTER_LINE=$line
    done <"$file"
    [[ "$count" -eq 1 ]]
}

artifact_resolve_file_ref() {
    local base=$1 ref=$2 candidate parent parent_real
    case "$ref" in
        /*) candidate=$ref ;;
        *) candidate="$base/$ref" ;;
    esac
    parent=$(dirname -- "$candidate") || return 1
    parent_real=$(CDPATH= cd -- "$parent" 2>/dev/null && pwd -P) || return 1
    printf '%s/%s\n' "$parent_real" "$(basename -- "$candidate")"
}

artifact_is_registered_worktree() {
    local rig_root=$1 candidate=$2 listed count=0
    local git_dir backpointer_ref backpointer_real
    "$GIT_CMD" -C "$rig_root" worktree list --porcelain -z \
        >/dev/null 2>&1 || return 1
    while IFS= read -r -d '' listed; do
        [[ "$listed" == "worktree $candidate" ]] && count=$((count + 1))
    done < <("$GIT_CMD" -C "$rig_root" worktree list --porcelain -z 2>/dev/null)
    [[ "$count" -eq 1 ]] || return 1
    git_dir=$("$GIT_CMD" -C "$candidate" rev-parse \
        --path-format=absolute --absolute-git-dir 2>/dev/null) || return 1
    git_dir=$(CDPATH= cd -- "$git_dir" 2>/dev/null && pwd -P) || return 1
    artifact_read_one_line_file "$git_dir/gitdir" || return 1
    backpointer_ref=$ARTIFACT_POINTER_LINE
    backpointer_real=$(artifact_resolve_file_ref \
        "$git_dir" "$backpointer_ref") || return 1
    [[ "$backpointer_real" == "$candidate/.git" ]]
}

validate_artifact_worktree() {
    local candidate=$1 policy=${2:-existing}
    local candidate_real candidate_top candidate_common rig_common
    local rig_namespace rig_namespace_real canonical_path
    local worktrees_parent provider_home provider_root provider_name

    [[ -n "$candidate" && -d "$candidate" ]] || return 1
    candidate_real=$(CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P) ||
        return 1
    [[ "$(basename -- "$candidate_real")" == "$SOURCE_ID" ]] || return 1
    [[ "$(basename -- "$(dirname -- "$candidate_real")")" == "worktrees" ]] ||
        return 1

    rig_namespace="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG"
    rig_namespace_real=$(CDPATH= cd -- "$rig_namespace" 2>/dev/null && pwd -P) ||
        return 1
    [[ "$rig_namespace_real" == "$rig_namespace" ]] || return 1
    canonical_path="$rig_namespace_real/artifacts/worktrees/$SOURCE_ID"
    if [[ "$candidate_real" == "$canonical_path" ]]; then
        [[ "$policy" != "legacy-only" ]] || return 1
    else
        [[ "$policy" != "canonical-only" ]] || return 1
        worktrees_parent=$(dirname -- "$candidate_real")
        provider_home=$(dirname -- "$worktrees_parent")
        provider_root=$(dirname -- "$provider_home")
        provider_name=$(basename -- "$provider_home")
        [[ "$provider_root" == "$rig_namespace_real/polecats" ]] || return 1
        safe_path_component "$provider_name" || return 1
    fi

    candidate_top=$("$GIT_CMD" -C "$candidate_real" rev-parse \
        --show-toplevel 2>/dev/null) || return 1
    candidate_top=$(CDPATH= cd -- "$candidate_top" 2>/dev/null && pwd -P) ||
        return 1
    [[ "$candidate_top" == "$candidate_real" ]] || return 1
    candidate_common=$(artifact_git_common_dir "$candidate_real") || return 1
    rig_common=$(artifact_git_common_dir "$RIG_ROOT") || return 1
    [[ "$candidate_common" == "$rig_common" ]] || return 1
    artifact_is_registered_worktree "$RIG_ROOT" "$candidate_real" || return 1
    printf '%s\n' "$candidate_real"
}
# END ARTIFACT_WORKTREE_VALIDATOR

BASE_REMOTE_REF="refs/remotes/origin/$ROOT_BASE_BRANCH"
if "$GIT_CMD" -C "$RIG_ROOT" symbolic-ref -q "$BASE_REMOTE_REF" \
    >/dev/null 2>&1; then
    durable_hard_block \
        "workspace.base-authority-symbolic" \
        "fetched base authority is a symbolic ref"
fi
"$GIT_CMD" -C "$RIG_ROOT" fetch --no-tags --prune origin \
    "+refs/heads/$ROOT_BASE_BRANCH:$BASE_REMOTE_REF" ||
    indeterminate "could not fetch the exact target base branch"
BASE_OID=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse --verify "$BASE_REMOTE_REF" \
    2>/dev/null) ||
    indeterminate "could not resolve the fetched target base"
is_oid "$BASE_OID" ||
    indeterminate "the fetched target base oid is malformed"
[[ "$("$GIT_CMD" -C "$RIG_ROOT" cat-file -t "$BASE_OID" 2>/dev/null)" == "commit" ]] ||
    indeterminate "the fetched target base is not a commit"

WORKTREE=""
if [[ -n "$SOURCE_ARTIFACT_DIR" ]]; then
    if WORKTREE=$(validate_artifact_worktree "$SOURCE_ARTIFACT_DIR" existing); then
        :
    else
        durable_hard_block \
            "workspace.canonical-artifact-invalid" \
            "canonical artifact_dir is missing, redirected, or unsafe"
    fi
elif [[ -n "$SOURCE_LEGACY_WORK_DIR" ]]; then
    WORKTREE=$(validate_artifact_worktree \
        "$SOURCE_LEGACY_WORK_DIR" legacy-only 2>/dev/null || true)
fi

if [[ -z "$WORKTREE" ]]; then
    ARTIFACT_HOME="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG/artifacts"
    if [[ -L "$ARTIFACT_HOME" ||
          (-e "$ARTIFACT_HOME" && ! -d "$ARTIFACT_HOME") ]]; then
        durable_hard_block \
            "workspace.artifact-root-unsafe" \
            "task artifact root is redirected or is not a directory"
    fi
    mkdir -p -- "$ARTIFACT_HOME" ||
        indeterminate "could not create the task artifact root"
    ARTIFACT_HOME_REAL=$(CDPATH= cd -- "$ARTIFACT_HOME" 2>/dev/null && pwd -P) ||
        indeterminate "could not resolve the task artifact root"
    [[ "$ARTIFACT_HOME_REAL" == "$ARTIFACT_HOME" ]] ||
        durable_hard_block \
            "workspace.artifact-root-redirected" \
            "task artifact root resolves outside the city and rig namespace"
    WORKTREE_PARENT="$ARTIFACT_HOME/worktrees"
    if [[ -L "$WORKTREE_PARENT" ||
          (-e "$WORKTREE_PARENT" && ! -d "$WORKTREE_PARENT") ]]; then
        durable_hard_block \
            "workspace.worktree-parent-unsafe" \
            "task worktree parent is redirected or is not a directory"
    fi
    mkdir -p -- "$WORKTREE_PARENT" ||
        indeterminate "could not create the task worktree parent"
    WORKTREE_PARENT_REAL=$(CDPATH= cd -- "$WORKTREE_PARENT" 2>/dev/null && pwd -P) ||
        indeterminate "could not resolve the task worktree parent"
    [[ "$WORKTREE_PARENT_REAL" == "$WORKTREE_PARENT" ]] ||
        durable_hard_block \
            "workspace.worktree-parent-redirected" \
            "task worktree parent resolves outside the artifact root"
    WORKTREE_PATH="$WORKTREE_PARENT/$SOURCE_ID"
    if [[ -e "$WORKTREE_PATH" || -L "$WORKTREE_PATH" ]]; then
        WORKTREE=$(validate_artifact_worktree \
            "$WORKTREE_PATH" canonical-only 2>/dev/null || true)
        [[ -n "$WORKTREE" ]] ||
            durable_hard_block \
                "workspace.artifact-path-collision" \
                "canonical artifact path exists but is not this source's registered worktree"
    else
        "$GIT_CMD" -C "$RIG_ROOT" worktree prune ||
            indeterminate "could not prune stale worktree registrations"
        "$GIT_CMD" -C "$RIG_ROOT" worktree add \
            "$WORKTREE_PATH" --detach "$BASE_REMOTE_REF" ||
            indeterminate "could not create the canonical task worktree"
        WORKTREE=$(validate_artifact_worktree \
            "$WORKTREE_PATH" canonical-only 2>/dev/null || true)
        [[ -n "$WORKTREE" ]] ||
            durable_hard_block \
                "workspace.new-worktree-invalid" \
                "new task worktree failed canonical registration validation"
    fi
fi

run_gc_bd update "$SOURCE_ID" \
    --set-metadata "artifact_dir=$WORKTREE" \
    --unset-metadata work_dir ||
    indeterminate "could not persist canonical artifact_dir"
load_source ||
    indeterminate "could not read back canonical artifact_dir"
[[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
   "$SOURCE_ARTIFACT_DIR" == "$WORKTREE" &&
   -z "$SOURCE_LEGACY_WORK_DIR" ]] ||
    indeterminate "canonical artifact_dir did not read back exactly"
WORKTREE=$(validate_artifact_worktree "$SOURCE_ARTIFACT_DIR" existing) ||
    indeterminate "recorded artifact_dir failed read-back validation"
printf 'POLECAT_ARTIFACT_READY source=%s artifact=%s\n' \
    "$SOURCE_ID" "$WORKTREE"

CURRENT_BRANCH=$("$GIT_CMD" -C "$WORKTREE" branch --show-current 2>/dev/null) ||
    indeterminate "could not inspect the task worktree branch"
if [[ -z "$SOURCE_BRANCH" ]]; then
    [[ -z "$SOURCE_REJECTION" ]] ||
        durable_hard_block \
            "workspace.rejected-without-branch" \
            "rejected source has no recorded branch authority"
    STATUS=$("$GIT_CMD" -C "$WORKTREE" status --porcelain \
        --untracked-files=all 2>/dev/null) ||
        indeterminate "could not inspect the task worktree status"
    [[ -z "$STATUS" ]] ||
        durable_hard_block \
            "workspace.unrecorded-branch-work" \
            "artifact contains work absent from source branch metadata"

    if [[ "$CURRENT_BRANCH" == "$EXPECTED_BRANCH" ]]; then
        FORK_SHA=$("$GIT_CMD" -C "$WORKTREE" merge-base \
            "$EXPECTED_BRANCH" "$BASE_REMOTE_REF" 2>/dev/null) ||
            durable_hard_block \
                "workspace.recovered-branch-no-fork" \
                "canonical recovered branch has no verifiable fork point"
    elif [[ -n "$CURRENT_BRANCH" ]]; then
        durable_hard_block \
            "workspace.unrecorded-branch-work" \
            "artifact is on a noncanonical branch absent from source metadata"
    else
        HEAD_OID=$("$GIT_CMD" -C "$WORKTREE" rev-parse --verify HEAD 2>/dev/null) ||
            indeterminate "could not resolve detached task worktree head"
        "$GIT_CMD" -C "$WORKTREE" merge-base --is-ancestor \
            "$HEAD_OID" "$BASE_OID" >/dev/null 2>&1
        ancestry_code=$?
        case "$ancestry_code" in
            0) ;;
            1)
                durable_hard_block \
                    "workspace.unrecorded-branch-work" \
                    "detached artifact contains commits absent from source branch metadata"
                ;;
            *)
                indeterminate "Git could not classify detached artifact ancestry"
                ;;
        esac

        "$GIT_CMD" -C "$WORKTREE" ls-remote --exit-code --heads \
            origin "refs/heads/$EXPECTED_BRANCH" >/dev/null 2>&1
        remote_code=$?
        case "$remote_code" in
            2) ;;
            0)
                durable_hard_block \
                    "workspace.unrecorded-branch-work" \
                    "canonical remote branch exists but source metadata.branch is absent"
                ;;
            *)
                indeterminate "could not prove the canonical remote branch is absent"
                ;;
        esac

        LOCAL_BRANCH_OID=$("$GIT_CMD" -C "$WORKTREE" rev-parse \
            --verify --quiet "refs/heads/$EXPECTED_BRANCH" 2>/dev/null)
        local_branch_code=$?
        case "$local_branch_code" in
            0)
                [[ "$LOCAL_BRANCH_OID" == "$BASE_OID" ]] ||
                    durable_hard_block \
                        "workspace.unrecorded-branch-work" \
                        "canonical local branch contains work absent from source metadata"
                "$GIT_CMD" -C "$WORKTREE" switch "$EXPECTED_BRANCH" \
                    >/dev/null 2>&1 ||
                    indeterminate "could not recover the pristine canonical local branch"
                ;;
            1)
                "$GIT_CMD" -C "$WORKTREE" switch -c \
                    "$EXPECTED_BRANCH" "$BASE_REMOTE_REF" >/dev/null 2>&1 ||
                    indeterminate "could not create the canonical task branch"
                ;;
            *)
                indeterminate "could not inspect the canonical local branch"
                ;;
        esac
        FORK_SHA=$BASE_OID
    fi
    is_oid "$FORK_SHA" ||
        durable_hard_block \
            "workspace.recovered-branch-no-fork" \
            "canonical task branch has a malformed fork point"
    run_gc_bd update "$SOURCE_ID" \
        --set-metadata "branch=$EXPECTED_BRANCH" \
        --set-metadata "fork_sha=$FORK_SHA" ||
        indeterminate "could not persist canonical branch metadata"
    load_source ||
        indeterminate "could not read back canonical branch metadata"
    [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
       "$SOURCE_BRANCH" == "$EXPECTED_BRANCH" &&
       "$SOURCE_FORK_SHA" == "$FORK_SHA" &&
       "$SOURCE_ARTIFACT_DIR" == "$WORKTREE" ]] ||
        indeterminate "canonical branch metadata did not read back exactly"
elif [[ "$SOURCE_BRANCH" != "$EXPECTED_BRANCH" ]]; then
    durable_hard_block \
        "workspace.noncanonical-branch" \
        "source metadata.branch is not the canonical task branch"
fi

# The lease owns authoritative synchronization and rejection rebase recovery.
(
    cd -- "$WORKTREE" ||
        indeterminate "could not enter the exact task artifact"
    run_gc gastown polecat-lease workspace \
        --source "$SOURCE_ID" \
        --convoy "$CONVOY_ID" \
        --base "$ROOT_BASE_BRANCH" \
        --branch "$EXPECTED_BRANCH" \
        --witness "$WITNESS_TARGET"
) || exit $?

revalidate_graph_context ||
    indeterminate "Graph authority changed after workspace synchronization"
load_source ||
    indeterminate "could not re-read source after workspace synchronization"
[[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
   "$SOURCE_BRANCH" == "$EXPECTED_BRANCH" &&
   "$SOURCE_ARTIFACT_DIR" == "$WORKTREE" ]] ||
    indeterminate "source authority changed after workspace synchronization"
WORKTREE=$(validate_artifact_worktree "$SOURCE_ARTIFACT_DIR" existing) ||
    indeterminate "task artifact failed validation after workspace synchronization"

CURRENT_BRANCH=$("$GIT_CMD" -C "$WORKTREE" branch --show-current 2>/dev/null) ||
    indeterminate "could not read synchronized task branch"
[[ "$CURRENT_BRANCH" == "$EXPECTED_BRANCH" ]] ||
    indeterminate "workspace synchronization did not select the canonical task branch"
STATUS=$("$GIT_CMD" -C "$WORKTREE" status --porcelain \
    --untracked-files=all 2>/dev/null) ||
    indeterminate "could not inspect synchronized task status"
[[ -z "$STATUS" ]] ||
    indeterminate "task artifact is dirty before project setup"

SETUP_DIGEST=$(printf '%s' "$ROOT_SETUP_COMMAND" |
    "$GIT_CMD" -C "$RIG_ROOT" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not digest the graph setup command"
is_oid "$SETUP_DIGEST" ||
    indeterminate "the graph setup command digest is malformed"

receipt_matches_live_step() {
    local step_json=$1 head=$2 fork=$3
    printf '%s' "$step_json" | jq -e \
        --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
        --arg ref "$STEP_REF" --arg root "$ROOT_BEAD_ID" \
        --arg version "$RECEIPT_VERSION" --arg source "$SOURCE_ID" \
        --arg convoy "$CONVOY_ID" --arg session "$CURRENT_SESSION_ID" \
        --arg artifact "$WORKTREE" --arg branch "$EXPECTED_BRANCH" \
        --arg base "$ROOT_BASE_BRANCH" --arg fork "$fork" \
        --arg head "$head" --arg setup "$SETUP_DIGEST" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "in_progress" and .[0].assignee == $actor and
        .[0].metadata["gc.step_ref"] == $ref and
        .[0].metadata["gc.root_bead_id"] == $root and
        (((.[0].metadata | has("gc.outcome")) | not) or
         .[0].metadata["gc.outcome"] == "") and
        ((.[0].metadata["gc.polecat_workspace_version"] // "" | tostring) ==
         $version) and
        .[0].metadata["gc.polecat_workspace_source_id"] == $source and
        .[0].metadata["gc.polecat_workspace_convoy_id"] == $convoy and
        .[0].metadata["gc.polecat_workspace_session_id"] == $session and
        .[0].metadata["gc.polecat_workspace_artifact_dir"] == $artifact and
        .[0].metadata["gc.polecat_workspace_branch"] == $branch and
        .[0].metadata["gc.polecat_workspace_base_branch"] == $base and
        .[0].metadata["gc.polecat_workspace_fork_sha"] == $fork and
        .[0].metadata["gc.polecat_workspace_head_sha"] == $head and
        .[0].metadata["gc.polecat_workspace_setup_digest"] == $setup
    ' >/dev/null 2>&1
}

HEAD_OID=$("$GIT_CMD" -C "$WORKTREE" rev-parse --verify HEAD 2>/dev/null) ||
    indeterminate "could not resolve synchronized task head"
is_oid "$HEAD_OID" ||
    indeterminate "synchronized task head is malformed"
FORK_SHA=$SOURCE_FORK_SHA
is_oid "$FORK_SHA" ||
    indeterminate "source fork_sha is missing or malformed"

STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not re-read workspace step before setup"
if receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA"; then
    # A prior invocation completed setup and durably recorded the exact state.
    # Re-run only completion after revalidating that the receipt still binds.
    :
else
    RECEIPT_KEY_COUNT=$(printf '%s' "$STEP_JSON" | jq -er '
        [.[0].metadata | keys[] |
         select(startswith("gc.polecat_workspace_"))] | length
    ' 2>/dev/null) ||
        indeterminate "could not inspect prior workspace receipt metadata"
    [[ "$RECEIPT_KEY_COUNT" == "0" ]] ||
        indeterminate "workspace step carries a partial or conflicting durable receipt"

    if [[ -n "$ROOT_SETUP_COMMAND" ]]; then
        printf '%s\n' "$ROOT_SETUP_COMMAND" |
            (
                cd -- "$WORKTREE" ||
                    indeterminate "could not enter task artifact for setup"
                bash -se
            ) ||
            indeterminate "project setup command failed"
    fi

    revalidate_graph_context ||
        indeterminate "Graph authority changed while project setup ran"
    load_source ||
        indeterminate "could not re-read source after project setup"
    [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
       "$SOURCE_BRANCH" == "$EXPECTED_BRANCH" &&
       "$SOURCE_ARTIFACT_DIR" == "$WORKTREE" &&
       "$SOURCE_FORK_SHA" == "$FORK_SHA" ]] ||
        indeterminate "source authority changed while project setup ran"
    CURRENT_BRANCH=$("$GIT_CMD" -C "$WORKTREE" branch --show-current 2>/dev/null) ||
        indeterminate "could not read task branch after project setup"
    [[ "$CURRENT_BRANCH" == "$EXPECTED_BRANCH" ]] ||
        indeterminate "project setup changed the canonical task branch"
    STATUS=$("$GIT_CMD" -C "$WORKTREE" status --porcelain \
        --untracked-files=all 2>/dev/null) ||
        indeterminate "could not inspect task status after project setup"
    [[ -z "$STATUS" ]] ||
        indeterminate "project setup left the task artifact dirty"
    HEAD_AFTER_SETUP=$("$GIT_CMD" -C "$WORKTREE" rev-parse --verify HEAD 2>/dev/null) ||
        indeterminate "could not resolve task head after project setup"
    [[ "$HEAD_AFTER_SETUP" == "$HEAD_OID" ]] ||
        indeterminate "project setup changed the task head"

    run_gc_bd update "$STEP_BEAD_ID" \
        --set-metadata "gc.polecat_workspace_version=$RECEIPT_VERSION" \
        --set-metadata "gc.polecat_workspace_source_id=$SOURCE_ID" \
        --set-metadata "gc.polecat_workspace_convoy_id=$CONVOY_ID" \
        --set-metadata "gc.polecat_workspace_session_id=$CURRENT_SESSION_ID" \
        --set-metadata "gc.polecat_workspace_artifact_dir=$WORKTREE" \
        --set-metadata "gc.polecat_workspace_branch=$EXPECTED_BRANCH" \
        --set-metadata "gc.polecat_workspace_base_branch=$ROOT_BASE_BRANCH" \
        --set-metadata "gc.polecat_workspace_fork_sha=$FORK_SHA" \
        --set-metadata "gc.polecat_workspace_head_sha=$HEAD_OID" \
        --set-metadata "gc.polecat_workspace_setup_digest=$SETUP_DIGEST" ||
        indeterminate "could not persist the workspace completion receipt"
    STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not read back the workspace completion receipt"
    receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA" ||
        indeterminate "workspace completion receipt did not read back exactly"
fi

revalidate_graph_context ||
    indeterminate "Graph authority changed before workspace completion"
run_gc gastown polecat-step complete \
    --convoy "$CONVOY_ID" \
    --step-ref "$STEP_REF" ||
    indeterminate "workspace receipt is durable but Graph completion did not verify"

printf 'POLECAT_WORKSPACE_EXECUTE_COMPLETE step=%s root=%s convoy=%s source=%s branch=%s artifact=%s replay=false session=%s\n' \
    "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
    "$EXPECTED_BRANCH" "$WORKTREE" "$CURRENT_SESSION_ID"
