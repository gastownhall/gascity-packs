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

root_context_for() {
    local root_json=$1 root_id=$2
    printf '%s' "$root_json" | jq -ec \
        --arg id "$root_id" '
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

artifact_resolve_dir_ref() {
    local base=$1 ref=$2 candidate
    case "$ref" in
        /*) candidate=$ref ;;
        *) candidate="$base/$ref" ;;
    esac
    (CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P)
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
    local candidate=$1 policy=${2:-existing} source_id=${3:-${SOURCE_ID:-}}
    local candidate_real candidate_top candidate_common rig_common
    local rig_namespace rig_namespace_real canonical_path
    local worktrees_parent provider_home provider_root provider_name
    local git_dir git_dir_real dotgit_ref dotgit_real

    [[ -n "$source_id" && -n "$candidate" && -d "$candidate" ]] || return 1
    candidate_real=$(CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P) ||
        return 1
    [[ "$candidate_real" == "$candidate" ]] || return 1
    [[ "$(basename -- "$candidate_real")" == "$source_id" ]] || return 1
    [[ "$(basename -- "$(dirname -- "$candidate_real")")" == "worktrees" ]] ||
        return 1

    rig_namespace="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG"
    rig_namespace_real=$(CDPATH= cd -- "$rig_namespace" 2>/dev/null && pwd -P) ||
        return 1
    [[ "$rig_namespace_real" == "$rig_namespace" ]] || return 1
    canonical_path="$rig_namespace_real/artifacts/worktrees/$source_id"
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

    # A linked worktree must expose the ordinary one-line .git pointer.  A
    # symlink, directory, multiline file, or redirected pointer is not durable
    # artifact identity.
    artifact_read_one_line_file "$candidate_real/.git" || return 1
    case "$ARTIFACT_POINTER_LINE" in
        "gitdir: "*) dotgit_ref=${ARTIFACT_POINTER_LINE#gitdir: } ;;
        *) return 1 ;;
    esac
    [[ -n "$dotgit_ref" && "$dotgit_ref" != *$'\n'* &&
       "$dotgit_ref" != *$'\r'* && "$dotgit_ref" != *$'\t'* ]] || return 1
    dotgit_real=$(artifact_resolve_dir_ref "$candidate_real" "$dotgit_ref") ||
        return 1
    git_dir=$("$GIT_CMD" -C "$candidate_real" rev-parse \
        --path-format=absolute --absolute-git-dir 2>/dev/null) || return 1
    git_dir_real=$(CDPATH= cd -- "$git_dir" 2>/dev/null && pwd -P) || return 1
    [[ "$dotgit_real" == "$git_dir_real" &&
       "$(dirname -- "$git_dir_real")" == "$rig_common/worktrees" ]] || return 1

    artifact_is_registered_worktree "$RIG_ROOT" "$candidate_real" || return 1
    printf '%s\n' "$candidate_real"
}
# END ARTIFACT_WORKTREE_VALIDATOR

emit_setup_key() {
    local step=$1 root=$2 source=$3 session=$4
    printf '%s\n' \
        "schema=gascity-polecat-workspace-setup-key-v1" \
        "step=$step" \
        "workflow_root=$root" \
        "source=$source" \
        "session_id=$session"
}

emit_setup_context() {
    local step=$1 root=$2 convoy=$3 source=$4 session=$5 artifact=$6
    local branch=$7 base=$8 fork=$9 head=${10} setup=${11}
    printf '%s\n' \
        "schema=gascity-polecat-workspace-setup-context-v1" \
        "step=$step" \
        "workflow_root=$root" \
        "input_convoy=$convoy" \
        "source=$source" \
        "session_id=$session" \
        "artifact=$artifact" \
        "branch=$branch" \
        "target=$base" \
        "fork_oid=$fork" \
        "head_oid=$head" \
        "setup_digest=$setup"
}

validate_fork_head() {
    local repo=$1 fork=$2 head=$3
    is_oid "$fork" && is_oid "$head" || return 1
    [[ "$("$GIT_CMD" -C "$repo" cat-file -t "$fork" 2>/dev/null)" == "commit" &&
       "$("$GIT_CMD" -C "$repo" cat-file -t "$head" 2>/dev/null)" == "commit" ]] ||
        return 1
    "$GIT_CMD" -C "$repo" merge-base --is-ancestor "$fork" "$head" \
        >/dev/null 2>&1
}

validate_setup_proof() {
    local key=$1 context=$2 require_done=$3
    local step=$4 root=$5 convoy=$6 source=$7 session=$8 artifact=$9
    local branch=${10} base=${11} fork=${12} head=${13} setup=${14}
    local expected_key expected_context namespace context_ref head_ref done_ref
    local observed_context observed_head observed_done observed_body expected_body

    expected_key=$(emit_setup_key "$step" "$root" "$source" "$session" |
        "$GIT_CMD" -C "$RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    expected_context=$(emit_setup_context \
        "$step" "$root" "$convoy" "$source" "$session" "$artifact" \
        "$branch" "$base" "$fork" "$head" "$setup" |
        "$GIT_CMD" -C "$RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    [[ "$key" == "$expected_key" && "$context" == "$expected_context" ]] ||
        return 1
    is_oid "$key" && is_oid "$context" || return 1
    namespace="refs/gascity/polecat-workspace-setups/v1/$key"
    context_ref="$namespace/context"
    head_ref="$namespace/head"
    done_ref="$namespace/done"
    for ref in "$context_ref" "$head_ref" "$done_ref"; do
        ! "$GIT_CMD" -C "$RIG_ROOT" symbolic-ref -q "$ref" \
            >/dev/null 2>&1 || return 1
    done
    observed_context=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
        --verify --quiet "$context_ref" 2>/dev/null) || return 1
    observed_head=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
        --verify --quiet "$head_ref" 2>/dev/null) || return 1
    observed_body=$("$GIT_CMD" -C "$RIG_ROOT" cat-file blob \
        "$context" 2>/dev/null) || return 1
    expected_body=$(emit_setup_context \
        "$step" "$root" "$convoy" "$source" "$session" "$artifact" \
        "$branch" "$base" "$fork" "$head" "$setup") || return 1
    [[ "$observed_context" == "$context" && "$observed_head" == "$head" &&
       "$("$GIT_CMD" -C "$RIG_ROOT" cat-file -t "$context" 2>/dev/null)" == "blob" &&
       "$observed_body" == "$expected_body" ]] || return 1
    observed_done=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
        --verify --quiet "$done_ref" 2>/dev/null)
    case "$require_done:$?" in
        true:0) [[ "$observed_done" == "$head" ]] ;;
        false:1) return 0 ;;
        *) return 1 ;;
    esac
}

physical_directory_is_exact() {
    local path=$1 resolved
    [[ -d "$path" && ! -L "$path" ]] || return 1
    resolved=$(CDPATH= cd -- "$path" 2>/dev/null && pwd -P) || return 1
    [[ "$resolved" == "$path" ]]
}

replay_closed_workspace() {
    local listed matches candidate_id candidate_json candidate minimal
    local candidate_count=0 replay_step="" replay_root="" replay_convoy=""
    local replay_source="" replay_branch="" replay_artifact=""
    local replay_base="" replay_fork="" replay_head="" replay_setup=""
    local replay_setup_key="" replay_setup_context="" root_lifecycle
    local root_json root_context_now convoy_json derived_source source_json
    local expected_branch setup_digest current_branch status artifact_now root_rig
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
        minimal=$(printf '%s' "$candidate_json" | jq -ce \
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
               (.[0].metadata["gc.root_bead_id"] | length) > 0
            then {
              assignee: .[0].assignee,
              root: .[0].metadata["gc.root_bead_id"]
            }
            else error("closed workspace receipt has no replay identity")
            end' 2>/dev/null) || return 2
        identity_is_current "$(printf '%s' "$minimal" | jq -er '.assignee')" ||
            return 2
        replay_root=$(printf '%s' "$minimal" | jq -er '.root') || return 2
        safe_atom "$replay_root" || return 2

        root_json=$(run_gc_bd show "$replay_root" --json 2>/dev/null) || return 2
        root_lifecycle=$(printf '%s' "$root_json" | jq -er \
            --arg id "$replay_root" '
            if type == "array" and length == 1 and .[0].id == $id and
               (.[0].status | type) == "string" and
               ((.[0].metadata // {}) | type) == "object"
            then
              if .[0].status == "in_progress" and
                 (((.[0].metadata | has("gc.outcome")) | not) or
                  .[0].metadata["gc.outcome"] == "")
              then "active"
              else "terminal"
              end
            else error("closed receipt root identity is unreadable")
            end' 2>/dev/null) || return 2
        if [[ "$root_lifecycle" == "terminal" ]]; then
            # Reused sessions legitimately retain old receipts.  Terminal
            # generations are history, not ambiguity with the current graph.
            continue
        fi
        root_context_now=$(root_context_for "$root_json" "$replay_root") ||
            return 2
        replay_convoy=$(printf '%s' "$root_context_now" | jq -er '.convoy') ||
            return 2
        replay_base=$(printf '%s' "$root_context_now" | jq -er '.base') ||
            return 2
        root_rig=$(printf '%s' "$root_context_now" | jq -er '.rig') || return 2
        [[ "$root_rig" == "$RUNTIME_RIG" ]] || return 2

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
               (.[0].metadata["gc.polecat_workspace_setup_digest"] | type) == "string" and
               .[0].metadata["gc.polecat_workspace_setup_state"] == "complete" and
               (.[0].metadata["gc.polecat_workspace_setup_key"] | type) == "string" and
               (.[0].metadata["gc.polecat_workspace_setup_context_oid"] | type) == "string"
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
              setup: .[0].metadata["gc.polecat_workspace_setup_digest"],
              setup_key: .[0].metadata["gc.polecat_workspace_setup_key"],
              setup_context:
                .[0].metadata["gc.polecat_workspace_setup_context_oid"]
            }
            else error("closed workspace receipt is incomplete")
            end' 2>/dev/null) || return 2
        [[ "$(printf '%s' "$candidate" | jq -er '.root')" == "$replay_root" &&
           "$(printf '%s' "$candidate" | jq -er '.convoy')" == "$replay_convoy" &&
           "$(printf '%s' "$candidate" | jq -er '.base')" == "$replay_base" ]] ||
            return 2
        replay_source=$(printf '%s' "$candidate" | jq -er '.source') || return 2
        replay_branch=$(printf '%s' "$candidate" | jq -er '.branch') || return 2
        replay_artifact=$(printf '%s' "$candidate" | jq -er '.artifact') || return 2
        replay_fork=$(printf '%s' "$candidate" | jq -er '.fork') || return 2
        replay_head=$(printf '%s' "$candidate" | jq -er '.head') || return 2
        replay_setup=$(printf '%s' "$candidate" | jq -er '.setup') || return 2
        replay_setup_key=$(printf '%s' "$candidate" | jq -er '.setup_key') ||
            return 2
        replay_setup_context=$(printf '%s' "$candidate" |
            jq -er '.setup_context') || return 2
        safe_atom "$replay_root" && safe_atom "$replay_convoy" &&
            safe_path_component "$replay_source" && safe_atom "$replay_base" ||
            return 2
        expected_branch="polecat/$replay_source"
        [[ "$replay_branch" == "$expected_branch" ]] || return 2
        is_oid "$replay_fork" && is_oid "$replay_head" &&
            is_oid "$replay_setup" && is_oid "$replay_setup_key" &&
            is_oid "$replay_setup_context" || return 2
        [[ "$replay_artifact" == /* &&
           "$replay_artifact" != *$'\n'* &&
           "$replay_artifact" != *$'\r'* &&
           "$replay_artifact" != *$'\t'* ]] || return 2

        convoy_json=$(run_gc_convoy status "$replay_convoy" --json 2>/dev/null) ||
            return 2
        derived_source=$(convoy_source_id "$convoy_json" "$replay_convoy") ||
            return 2
        [[ "$derived_source" == "$replay_source" ]] || return 2

        source_json=$(run_gc_bd show "$replay_source" --json 2>/dev/null) ||
            return 2
        printf '%s' "$source_json" | jq -e \
            --arg id "$replay_source" --arg branch "$expected_branch" \
            --arg artifact "$replay_artifact" --arg fork "$replay_fork" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == "open" and ((.[0].assignee // "") == "") and
            ((.[0].metadata // {}) | type) == "object" and
            .[0].metadata.branch == $branch and
            ((.[0].metadata.artifact_dir // "") == $artifact) and
            .[0].metadata.fork_sha == $fork and
            ((.[0].metadata.work_dir // "") == "")
        ' >/dev/null 2>&1 || return 2

        setup_digest=$(printf '%s' \
            "$(printf '%s' "$root_context_now" | jq -er '.setup')" |
            "$GIT_CMD" -C "$RIG_ROOT" hash-object --stdin 2>/dev/null) ||
            return 2
        [[ "$setup_digest" == "$replay_setup" ]] || return 2
        artifact_now=$(validate_artifact_worktree \
            "$replay_artifact" existing "$replay_source") || return 2
        [[ "$artifact_now" == "$replay_artifact" ]] || return 2
        current_branch=$("$GIT_CMD" -C "$artifact_now" \
            branch --show-current 2>/dev/null) || return 2
        [[ "$current_branch" == "$expected_branch" ]] || return 2
        status=$("$GIT_CMD" -C "$artifact_now" status --porcelain \
            --untracked-files=all 2>/dev/null) || return 2
        [[ -z "$status" ]] || return 2
        [[ "$("$GIT_CMD" -C "$artifact_now" rev-parse \
                 --verify HEAD 2>/dev/null)" == "$replay_head" ]] || return 2
        validate_fork_head "$artifact_now" "$replay_fork" "$replay_head" ||
            return 2
        validate_setup_proof \
            "$replay_setup_key" "$replay_setup_context" true \
            "$candidate_id" "$replay_root" "$replay_convoy" "$replay_source" \
            "$CURRENT_SESSION_ID" "$replay_artifact" "$expected_branch" \
            "$replay_base" "$replay_fork" "$replay_head" "$replay_setup" ||
            return 2

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
    root_context_for "$root_json" "$ROOT_BEAD_ID"
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
SOURCE_AUTHORITY_CANONICAL=""

source_authority_context() {
    local source_json=$1
    printf '%s' "$source_json" | jq -ecS --arg id "$SOURCE_ID" '
        if type == "array" and length == 1 and .[0].id == $id and
           (.[0].status | type) == "string" and
           ((.[0].assignee // "") | type) == "string" and
           ((.[0].metadata // {}) | type) == "object" and
           ((.[0].metadata.branch // "") | type) == "string" and
           ((.[0].metadata.rejection_reason // "") | type) == "string" and
           ((.[0].metadata.artifact_dir // "") | type) == "string" and
           ((.[0].metadata.work_dir // "") | type) == "string" and
           ((.[0].metadata.fork_sha // "") | type) == "string"
        then {
          id: .[0].id,
          status: .[0].status,
          assignee: (.[0].assignee // ""),
          branch: (.[0].metadata.branch // ""),
          rejection: (.[0].metadata.rejection_reason // ""),
          artifact: (.[0].metadata.artifact_dir // ""),
          work: (.[0].metadata.work_dir // ""),
          fork: (.[0].metadata.fork_sha // "")
        }
        else error("source authority mismatch")
        end' 2>/dev/null
}

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
    SOURCE_AUTHORITY_CANONICAL=$(source_authority_context "$SOURCE_JSON") ||
        return 1
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

revalidate_source_authority() {
    local source_now authority_now
    source_now=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) || return 1
    authority_now=$(source_authority_context "$source_now") || return 1
    [[ "$authority_now" == "$SOURCE_AUTHORITY_CANONICAL" ]]
}

durable_hard_block() {
    local code=$1 reason=$2 block_code block_output
    local subject message
    local source_now step_now root_now root_context_now convoy_now derived_source
    echo "POLECAT_WORKSPACE_HARD: $code: $reason" >&2
    block_output=$(run_gc gastown polecat-step block \
        --convoy "$CONVOY_ID" \
        --step-ref "$STEP_REF" \
        --code "$code" \
        --reason "$reason")
    block_code=$?
    if [[ "$block_code" -ne 0 ]]; then
        echo "POLECAT_WORKSPACE_INDETERMINATE: durable block failed (exit $block_code)" >&2
        exit "$EXIT_INDETERMINATE"
    fi
    printf '%s\n' "$block_output"

    # Exit 64 is reserved for a quarantine that remains exactly readable after
    # the blocking helper returns.  A lost/misreported response is retryable
    # uncertainty, not proof of a durable hard outcome.
    root_now=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "durable block returned but the workflow root was unreadable"
    root_context_now=$(root_context "$root_now") ||
        indeterminate "durable block returned but Graph root authority changed"
    root_context_now=$(printf '%s' "$root_context_now" | jq -cS .) ||
        indeterminate "durable block returned but Graph root authority was malformed"
    [[ "$root_context_now" == "$ROOT_CONTEXT_CANONICAL" ]] ||
        indeterminate "durable block returned after Graph root authority drift"
    convoy_now=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
        indeterminate "durable block returned but convoy authority was unreadable"
    derived_source=$(convoy_source_id "$convoy_now" "$CONVOY_ID") ||
        indeterminate "durable block returned but convoy authority was malformed"
    [[ "$derived_source" == "$SOURCE_ID" ]] ||
        indeterminate "durable block returned after convoy source drift"
    source_now=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) ||
        indeterminate "durable block returned but source quarantine was unreadable"
    printf '%s' "$source_now" | jq -e \
        --arg id "$SOURCE_ID" --arg code "$code" --arg reason "$reason" \
        --arg step "$STEP_BEAD_ID" --arg root "$ROOT_BEAD_ID" \
        --arg convoy "$CONVOY_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "blocked" and ((.[0].assignee // "") == "") and
        .[0].metadata["gc.routed_to"] == "human" and
        .[0].metadata.blocked_reason == $reason and
        .[0].metadata["gc.polecat_block_code"] == $code and
        ((.[0].metadata["gc.polecat_block_version"] // "" | tostring) == "1") and
        .[0].metadata["gc.polecat_block_step_ref"] == "mol-polecat-work.workspace-setup" and
        .[0].metadata["gc.polecat_block_step_id"] == $step and
        .[0].metadata["gc.polecat_block_root"] == $root and
        .[0].metadata["gc.polecat_block_convoy"] == $convoy
    ' >/dev/null 2>&1 ||
        indeterminate "durable block returned without an exact source quarantine"
    step_now=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "durable block returned but step quarantine was unreadable"
    printf '%s' "$step_now" | jq -e \
        --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
        --arg code "$code" --arg reason "$reason" \
        --arg root "$ROOT_BEAD_ID" --arg source "$SOURCE_ID" \
        --arg convoy "$CONVOY_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "blocked" and .[0].assignee == $actor and
        .[0].metadata["gc.step_ref"] == "mol-polecat-work.workspace-setup" and
        .[0].metadata["gc.root_bead_id"] == $root and
        .[0].metadata["gc.blocked_reason"] == $reason and
        .[0].metadata["gc.polecat_block_code"] == $code and
        ((.[0].metadata["gc.polecat_block_version"] // "" | tostring) == "1") and
        .[0].metadata["gc.polecat_block_source"] == $source and
        .[0].metadata["gc.polecat_block_convoy"] == $convoy
    ' >/dev/null 2>&1 ||
        indeterminate "durable block returned without an exact step quarantine"
    subject="POLECAT WORKSPACE QUARANTINE: $SOURCE_ID"
    message=$(printf '%s\n' \
        "Source: $SOURCE_ID" \
        "Workflow root: $ROOT_BEAD_ID" \
        "Step: $STEP_BEAD_ID" \
        "Convoy: $CONVOY_ID" \
        "Code: $code" \
        "Reason: $reason" \
        "The durable quarantine requires explicit human reconciliation; do not rerun project setup automatically.") ||
        indeterminate "could not encode the quarantine notification"
    run_gc mail send "$WITNESS_TARGET" \
        -s "$subject" -m "$message" --notify ||
        indeterminate "durable quarantine verified but Witness notification failed"
    # A successful block is terminal quarantine, never workspace success.
    exit "$EXIT_HARD"
}

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
    RIG_NAMESPACE="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG"
    for namespace_parent in \
        "$CITY_ROOT/.gc" \
        "$CITY_ROOT/.gc/worktrees" \
        "$RIG_NAMESPACE"; do
        physical_directory_is_exact "$namespace_parent" ||
            durable_hard_block \
                "workspace.artifact-ancestor-unsafe" \
                "task artifact ancestor is missing, redirected, or is not a physical directory"
    done
    ARTIFACT_HOME="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG/artifacts"
    if [[ -L "$ARTIFACT_HOME" ||
          (-e "$ARTIFACT_HOME" && ! -d "$ARTIFACT_HOME") ]]; then
        durable_hard_block \
            "workspace.artifact-root-unsafe" \
            "task artifact root is redirected or is not a directory"
    fi
    if [[ ! -e "$ARTIFACT_HOME" ]]; then
        mkdir -- "$ARTIFACT_HOME" ||
            indeterminate "could not create the task artifact root"
    fi
    physical_directory_is_exact "$ARTIFACT_HOME" ||
        durable_hard_block \
            "workspace.artifact-root-redirected" \
            "task artifact root resolves outside the city and rig namespace"
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
    if [[ ! -e "$WORKTREE_PARENT" ]]; then
        mkdir -- "$WORKTREE_PARENT" ||
            indeterminate "could not create the task worktree parent"
    fi
    physical_directory_is_exact "$WORKTREE_PARENT" ||
        durable_hard_block \
            "workspace.worktree-parent-redirected" \
            "task worktree parent resolves outside the artifact root"
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

if [[ "$SOURCE_ARTIFACT_DIR" != "$WORKTREE" ||
      -n "$SOURCE_LEGACY_WORK_DIR" ]]; then
    revalidate_graph_context ||
        indeterminate "Graph authority changed before artifact metadata mutation"
    revalidate_source_authority ||
        indeterminate "source authority changed before artifact metadata mutation"
    EXPECTED_SOURCE_AUTHORITY=$(printf '%s' "$SOURCE_AUTHORITY_CANONICAL" |
        jq -cS --arg artifact "$WORKTREE" \
            '.artifact = $artifact | .work = ""') ||
        indeterminate "could not derive the artifact metadata transition"
    run_gc_bd update "$SOURCE_ID" \
        --set-metadata "artifact_dir=$WORKTREE" \
        --unset-metadata work_dir ||
        indeterminate "could not persist canonical artifact_dir"
    load_source ||
        indeterminate "could not read back canonical artifact_dir"
    [[ "$SOURCE_AUTHORITY_CANONICAL" == "$EXPECTED_SOURCE_AUTHORITY" ]] ||
        indeterminate "source authority drifted during artifact metadata mutation"
    revalidate_graph_context ||
        indeterminate "Graph authority drifted during artifact metadata mutation"
fi
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
    BRANCH_HEAD=$("$GIT_CMD" -C "$WORKTREE" rev-parse --verify HEAD 2>/dev/null) ||
        indeterminate "could not resolve the recovered canonical branch"
    validate_fork_head "$WORKTREE" "$FORK_SHA" "$BRANCH_HEAD" ||
        durable_hard_block \
            "workspace.recovered-branch-no-fork" \
            "canonical task branch fork is not a coherent commit ancestor"
    revalidate_graph_context ||
        indeterminate "Graph authority changed before branch metadata mutation"
    revalidate_source_authority ||
        indeterminate "source authority changed before branch metadata mutation"
    EXPECTED_SOURCE_AUTHORITY=$(printf '%s' "$SOURCE_AUTHORITY_CANONICAL" |
        jq -cS --arg branch "$EXPECTED_BRANCH" --arg fork "$FORK_SHA" \
            '.branch = $branch | .fork = $fork') ||
        indeterminate "could not derive the branch metadata transition"
    run_gc_bd update "$SOURCE_ID" \
        --set-metadata "branch=$EXPECTED_BRANCH" \
        --set-metadata "fork_sha=$FORK_SHA" ||
        indeterminate "could not persist canonical branch metadata"
    load_source ||
        indeterminate "could not read back canonical branch metadata"
    [[ "$SOURCE_AUTHORITY_CANONICAL" == "$EXPECTED_SOURCE_AUTHORITY" ]] ||
        indeterminate "source authority drifted during branch metadata mutation"
    revalidate_graph_context ||
        indeterminate "Graph authority drifted during branch metadata mutation"
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

CURRENT_HEAD=$("$GIT_CMD" -C "$WORKTREE" rev-parse --verify HEAD 2>/dev/null) ||
    indeterminate "could not resolve the canonical task branch head"
validate_fork_head "$WORKTREE" "$SOURCE_FORK_SHA" "$CURRENT_HEAD" ||
    durable_hard_block \
        "workspace.fork-authority-invalid" \
        "source fork_sha is not an existing commit ancestor of the task head"

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
    local step_json=$1 head=$2 fork=$3 setup_state=$4
    printf '%s' "$step_json" | jq -e \
        --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
        --arg ref "$STEP_REF" --arg root "$ROOT_BEAD_ID" \
        --arg version "$RECEIPT_VERSION" --arg source "$SOURCE_ID" \
        --arg convoy "$CONVOY_ID" --arg session "$CURRENT_SESSION_ID" \
        --arg artifact "$WORKTREE" --arg branch "$EXPECTED_BRANCH" \
        --arg base "$ROOT_BASE_BRANCH" --arg fork "$fork" \
        --arg head "$head" --arg setup "$SETUP_DIGEST" \
        --arg setup_state "$setup_state" --arg setup_key "$SETUP_KEY" \
        --arg setup_context "$SETUP_CONTEXT_OID" '
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
        .[0].metadata["gc.polecat_workspace_setup_digest"] == $setup and
        .[0].metadata["gc.polecat_workspace_setup_state"] == $setup_state and
        .[0].metadata["gc.polecat_workspace_setup_key"] == $setup_key and
        .[0].metadata["gc.polecat_workspace_setup_context_oid"] == $setup_context
    ' >/dev/null 2>&1
}

HEAD_OID=$("$GIT_CMD" -C "$WORKTREE" rev-parse --verify HEAD 2>/dev/null) ||
    indeterminate "could not resolve synchronized task head"
is_oid "$HEAD_OID" ||
    indeterminate "synchronized task head is malformed"
FORK_SHA=$SOURCE_FORK_SHA
is_oid "$FORK_SHA" ||
    indeterminate "source fork_sha is missing or malformed"
validate_fork_head "$WORKTREE" "$FORK_SHA" "$HEAD_OID" ||
    indeterminate "source fork_sha is not a coherent commit ancestor of task HEAD"

SETUP_KEY=$(emit_setup_key \
    "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$SOURCE_ID" "$CURRENT_SESSION_ID" |
    "$GIT_CMD" -C "$RIG_ROOT" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not derive the workspace setup intent key"
SETUP_CONTEXT_OID=$(emit_setup_context \
    "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
    "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" "$ROOT_BASE_BRANCH" \
    "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST" |
    "$GIT_CMD" -C "$RIG_ROOT" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not derive the workspace setup intent context"
is_oid "$SETUP_KEY" && is_oid "$SETUP_CONTEXT_OID" ||
    indeterminate "workspace setup intent identity is malformed"
SETUP_NAMESPACE="refs/gascity/polecat-workspace-setups/v1/$SETUP_KEY"
SETUP_CONTEXT_REF="$SETUP_NAMESPACE/context"
SETUP_HEAD_REF="$SETUP_NAMESPACE/head"
SETUP_DONE_REF="$SETUP_NAMESPACE/done"
SETUP_NS_CONTEXT=""
SETUP_NS_HEAD=""
SETUP_NS_DONE=""
SETUP_NS_STATE=""

for setup_ref in "$SETUP_CONTEXT_REF" "$SETUP_HEAD_REF" "$SETUP_DONE_REF"; do
    "$GIT_CMD" -C "$RIG_ROOT" check-ref-format "$setup_ref" >/dev/null 2>&1 ||
        indeterminate "Git rejected a workspace setup intent ref"
done
if ! printf 'start\noption no-deref\nprepare\nabort\n' |
     "$GIT_CMD" -C "$RIG_ROOT" update-ref --stdin >/dev/null 2>&1; then
    indeterminate "Git lacks transactional update-ref support for setup intent"
fi
command -v flock >/dev/null 2>&1 ||
    indeterminate "flock is required for exclusive setup execution"

ensure_setup_lock_directory() {
    local path=$1 resolved
    if [[ -L "$path" || (-e "$path" && ! -d "$path") ]]; then
        return 1
    fi
    if [[ ! -e "$path" ]]; then
        mkdir -- "$path" 2>/dev/null || {
            [[ -d "$path" && ! -L "$path" ]] || return 1
        }
    fi
    [[ -d "$path" && ! -L "$path" ]] || return 1
    resolved=$(CDPATH= cd -- "$path" 2>/dev/null && pwd -P) || return 1
    [[ "$resolved" == "$path" ]]
}

SETUP_GIT_COMMON=$(artifact_git_common_dir "$RIG_ROOT") ||
    indeterminate "could not resolve the setup lock repository"
[[ "$SETUP_GIT_COMMON" == /* && -d "$SETUP_GIT_COMMON" &&
   ! -L "$SETUP_GIT_COMMON" ]] ||
    indeterminate "setup lock repository is redirected or unsafe"
SETUP_LOCK_ROOT="$SETUP_GIT_COMMON/gascity-locks"
SETUP_LOCK_PARENT="$SETUP_LOCK_ROOT/polecat-workspace-setups-v1"
SETUP_LOCK_PATH="$SETUP_LOCK_PARENT/$SETUP_KEY"
SETUP_LOCK_FILE="$SETUP_LOCK_PATH/lock"
ensure_setup_lock_directory "$SETUP_LOCK_ROOT" &&
    ensure_setup_lock_directory "$SETUP_LOCK_PARENT" &&
    ensure_setup_lock_directory "$SETUP_LOCK_PATH" ||
    indeterminate "could not create a physical setup lock directory"
if [[ ! -e "$SETUP_LOCK_FILE" && ! -L "$SETUP_LOCK_FILE" ]]; then
    (set -o noclobber; : >"$SETUP_LOCK_FILE") 2>/dev/null || {
        [[ -f "$SETUP_LOCK_FILE" && ! -L "$SETUP_LOCK_FILE" ]] ||
            indeterminate "could not exclusively create the exact setup lock file"
    }
fi
[[ -f "$SETUP_LOCK_FILE" && ! -L "$SETUP_LOCK_FILE" ]] ||
    indeterminate "setup lock file is redirected or is not a regular file"
exec {SETUP_LOCK_FD}<>"$SETUP_LOCK_FILE" ||
    indeterminate "could not open the exact setup lock"
SETUP_LOCK_PATH_ID=$(stat -Lc '%d:%i:%h' "$SETUP_LOCK_FILE" 2>/dev/null) ||
    indeterminate "could not identify the setup lock path"
SETUP_LOCK_FD_ID=$(stat -Lc '%d:%i:%h' "/proc/$$/fd/$SETUP_LOCK_FD" \
    2>/dev/null) ||
    indeterminate "could not identify the opened setup lock"
[[ "$SETUP_LOCK_PATH_ID" == "$SETUP_LOCK_FD_ID" &&
   "${SETUP_LOCK_PATH_ID##*:}" == "1" ]] ||
    indeterminate "setup lock file identity or containment is unsafe"
flock -n "$SETUP_LOCK_FD" ||
    indeterminate "another executor currently owns this exact workspace setup"
[[ -f "$SETUP_LOCK_FILE" && ! -L "$SETUP_LOCK_FILE" &&
   "$(stat -Lc '%d:%i:%h' "$SETUP_LOCK_FILE" 2>/dev/null)" == \
     "$SETUP_LOCK_FD_ID" ]] ||
    indeterminate "setup lock path changed while acquiring ownership"

read_setup_ref() {
    local ref=$1 value code
    value=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
        --verify --quiet "$ref" 2>/dev/null)
    code=$?
    case "$code" in
        0)
            is_oid "$value" || return 1
            printf '%s' "$value"
            ;;
        1) printf '' ;;
        *) return 1 ;;
    esac
}

load_setup_namespace() {
    local count=0
    SETUP_NS_CONTEXT=$(read_setup_ref "$SETUP_CONTEXT_REF") || return 1
    SETUP_NS_HEAD=$(read_setup_ref "$SETUP_HEAD_REF") || return 1
    SETUP_NS_DONE=$(read_setup_ref "$SETUP_DONE_REF") || return 1
    for value in "$SETUP_NS_CONTEXT" "$SETUP_NS_HEAD" "$SETUP_NS_DONE"; do
        [[ -z "$value" ]] || count=$((count + 1))
    done
    case "$count" in
        0) SETUP_NS_STATE=absent ;;
        2)
            [[ -n "$SETUP_NS_CONTEXT" && -n "$SETUP_NS_HEAD" &&
               -z "$SETUP_NS_DONE" ]] || return 1
            SETUP_NS_STATE=attempted
            ;;
        3) SETUP_NS_STATE=complete ;;
        *) return 1 ;;
    esac
}

create_setup_intent() {
    local written
    written=$(emit_setup_context \
        "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
        "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" "$ROOT_BASE_BRANCH" \
        "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST" |
        "$GIT_CMD" -C "$RIG_ROOT" hash-object -w --stdin 2>/dev/null) ||
        return 1
    [[ "$written" == "$SETUP_CONTEXT_OID" ]] || return 1

    # This is the exclusive exactly-once gate.  An identical concurrent
    # invocation that loses either create must not infer ownership merely
    # because the winner's refs now match.
    printf '%s\n' \
        start \
        "option no-deref" \
        "verify refs/heads/$EXPECTED_BRANCH $HEAD_OID" \
        "create $SETUP_CONTEXT_REF $SETUP_CONTEXT_OID" \
        "create $SETUP_HEAD_REF $HEAD_OID" \
        prepare \
        commit |
        "$GIT_CMD" -C "$RIG_ROOT" update-ref --stdin >/dev/null 2>&1 ||
        return 1
    load_setup_namespace || return 1
    [[ "$SETUP_NS_STATE" == "attempted" ]] || return 1
    validate_setup_proof \
        "$SETUP_KEY" "$SETUP_CONTEXT_OID" false \
        "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
        "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" \
        "$ROOT_BASE_BRANCH" "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST"
}

mark_setup_done() {
    load_setup_namespace || return 1
    case "$SETUP_NS_STATE" in
        complete)
            validate_setup_proof \
                "$SETUP_KEY" "$SETUP_CONTEXT_OID" true \
                "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
                "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" \
                "$ROOT_BASE_BRANCH" "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST"
            return
            ;;
        attempted)
            validate_setup_proof \
                "$SETUP_KEY" "$SETUP_CONTEXT_OID" false \
                "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
                "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" \
                "$ROOT_BASE_BRANCH" "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST" ||
                return 1
            ;;
        *) return 1 ;;
    esac
    if printf '%s\n' \
        start \
        "option no-deref" \
        "verify $SETUP_CONTEXT_REF $SETUP_CONTEXT_OID" \
        "verify $SETUP_HEAD_REF $HEAD_OID" \
        "create $SETUP_DONE_REF $HEAD_OID" \
        prepare \
        commit |
        "$GIT_CMD" -C "$RIG_ROOT" update-ref --stdin >/dev/null 2>&1; then
        :
    else
        # A lost response is safe only if the exact done proof won.
        load_setup_namespace || return 1
        [[ "$SETUP_NS_STATE" == "complete" ]] || return 1
    fi
    validate_setup_proof \
        "$SETUP_KEY" "$SETUP_CONTEXT_OID" true \
        "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
        "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" \
        "$ROOT_BASE_BRANCH" "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST"
}

STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not re-read workspace step before setup"
SETUP_RUN_MODE=""
if receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA" complete; then
    # A prior invocation completed setup and durably recorded the exact state.
    # Re-run only proof finalization/completion after exact rebinding.
    mark_setup_done ||
        indeterminate "completed setup receipt lacks its exact durable Git proof"
    SETUP_RUN_MODE=done
elif receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA" attempted; then
    validate_setup_proof \
        "$SETUP_KEY" "$SETUP_CONTEXT_OID" false \
        "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
        "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" \
        "$ROOT_BASE_BRANCH" "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST" ||
        indeterminate "attempted setup receipt conflicts with its durable intent"
    if [[ -n "$ROOT_SETUP_COMMAND" ]]; then
        durable_hard_block \
            "workspace.setup-execution-ambiguous" \
            "project setup has a durable attempted receipt but no completion receipt; explicit reconciliation is required"
    fi
    # An empty setup command has no external effect to repeat.  Its exact
    # attempted receipt can therefore be promoted without invoking a shell.
    SETUP_RUN_MODE=complete-empty
else
    RECEIPT_KEY_COUNT=$(printf '%s' "$STEP_JSON" | jq -er '
        [.[0].metadata | keys[] |
         select(startswith("gc.polecat_workspace_"))] | length
    ' 2>/dev/null) ||
        indeterminate "could not inspect prior workspace receipt metadata"
    [[ "$RECEIPT_KEY_COUNT" == "0" ]] ||
        indeterminate "workspace step carries a partial or conflicting durable receipt"

    load_setup_namespace ||
        indeterminate "workspace setup intent namespace is partial or unreadable"
    case "$SETUP_NS_STATE" in
        absent)
            revalidate_graph_context ||
                indeterminate "Graph authority changed before setup intent creation"
            revalidate_source_authority ||
                indeterminate "source authority changed before setup intent creation"
            create_setup_intent ||
                indeterminate "could not exclusively create the workspace setup intent"
            ;;
        attempted)
            validate_setup_proof \
                "$SETUP_KEY" "$SETUP_CONTEXT_OID" false \
                "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
                "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" \
                "$ROOT_BASE_BRANCH" "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST" ||
                indeterminate "receipt-free setup intent does not match current authority"
            # The per-generation lock proves the prior intent owner is no
            # longer running.  Protocol order guarantees setup cannot begin
            # before the attempted Graph receipt is durably readable, so this
            # receipt-free state is safe to adopt.
            ;;
        complete)
            indeterminate "workspace setup done proof exists without its exact Graph receipt"
            ;;
        *)
            indeterminate "workspace setup intent namespace has an invalid state"
            ;;
    esac
    revalidate_graph_context ||
        indeterminate "Graph authority changed before setup receipt creation"
    revalidate_source_authority ||
        indeterminate "source authority changed before setup receipt creation"

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
        --set-metadata "gc.polecat_workspace_setup_digest=$SETUP_DIGEST" \
        --set-metadata "gc.polecat_workspace_setup_state=attempted" \
        --set-metadata "gc.polecat_workspace_setup_key=$SETUP_KEY" \
        --set-metadata "gc.polecat_workspace_setup_context_oid=$SETUP_CONTEXT_OID" ||
        indeterminate "could not persist the pre-execution workspace setup receipt"
    STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not read back the pre-execution workspace setup receipt"
    receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA" attempted ||
        indeterminate "pre-execution workspace setup receipt did not read back exactly"
    if [[ -n "$ROOT_SETUP_COMMAND" ]]; then
        SETUP_RUN_MODE=execute
    else
        SETUP_RUN_MODE=complete-empty
    fi
fi

if [[ "$SETUP_RUN_MODE" != "done" ]]; then
    WORKTREE_NOW=$(validate_artifact_worktree \
        "$SOURCE_ARTIFACT_DIR" existing) ||
        indeterminate "task artifact changed before project setup"
    [[ "$WORKTREE_NOW" == "$WORKTREE" ]] ||
        indeterminate "task artifact identity changed before project setup"
    BRANCH_BEFORE_SETUP=$("$GIT_CMD" -C "$WORKTREE" \
        branch --show-current 2>/dev/null) ||
        indeterminate "could not read task branch before project setup"
    HEAD_BEFORE_SETUP=$("$GIT_CMD" -C "$WORKTREE" \
        rev-parse --verify HEAD 2>/dev/null) ||
        indeterminate "could not read task HEAD before project setup"
    [[ "$BRANCH_BEFORE_SETUP" == "$EXPECTED_BRANCH" &&
       "$HEAD_BEFORE_SETUP" == "$HEAD_OID" ]] ||
        indeterminate "task branch or HEAD changed before project setup"
    STATUS=$("$GIT_CMD" -C "$WORKTREE" status --porcelain \
        --untracked-files=all 2>/dev/null) ||
        indeterminate "could not inspect task status before project setup"
    [[ -z "$STATUS" ]] ||
        indeterminate "task artifact became dirty before project setup"
    validate_fork_head "$WORKTREE" "$FORK_SHA" "$HEAD_OID" ||
        indeterminate "fork authority changed before project setup"
    revalidate_source_authority ||
        indeterminate "source authority changed before project setup"
    revalidate_graph_context ||
        indeterminate "Graph authority changed before project setup"

    if [[ "$SETUP_RUN_MODE" == "execute" ]]; then
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

    revalidate_graph_context ||
        indeterminate "Graph authority changed before setup receipt completion"
    revalidate_source_authority ||
        indeterminate "source authority changed before setup receipt completion"
    STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not re-read attempted setup receipt"
    receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA" attempted ||
        indeterminate "attempted setup receipt changed before completion"
    run_gc_bd update "$STEP_BEAD_ID" \
        --set-metadata "gc.polecat_workspace_setup_state=complete" ||
        indeterminate "could not persist the workspace completion receipt"
    STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not read back the workspace completion receipt"
    receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA" complete ||
        indeterminate "workspace completion receipt did not read back exactly"
    mark_setup_done ||
        indeterminate "workspace completion receipt is durable but setup proof finalization failed"
fi

revalidate_graph_context ||
    indeterminate "Graph authority changed before workspace completion"
load_source ||
    indeterminate "could not re-read source before workspace completion"
[[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
   "$SOURCE_BRANCH" == "$EXPECTED_BRANCH" &&
   "$SOURCE_ARTIFACT_DIR" == "$WORKTREE" &&
   "$SOURCE_FORK_SHA" == "$FORK_SHA" ]] ||
    indeterminate "source authority changed before workspace completion"
WORKTREE=$(validate_artifact_worktree "$SOURCE_ARTIFACT_DIR" existing) ||
    indeterminate "task artifact changed before workspace completion"
FINAL_BRANCH=$("$GIT_CMD" -C "$WORKTREE" branch --show-current 2>/dev/null) ||
    indeterminate "could not read task branch before workspace completion"
FINAL_HEAD=$("$GIT_CMD" -C "$WORKTREE" rev-parse --verify HEAD 2>/dev/null) ||
    indeterminate "could not read task HEAD before workspace completion"
[[ "$FINAL_BRANCH" == "$EXPECTED_BRANCH" && "$FINAL_HEAD" == "$HEAD_OID" ]] ||
    indeterminate "task branch or HEAD changed before workspace completion"
STATUS=$("$GIT_CMD" -C "$WORKTREE" status --porcelain \
    --untracked-files=all 2>/dev/null) ||
    indeterminate "could not inspect task status before workspace completion"
[[ -z "$STATUS" ]] ||
    indeterminate "task artifact became dirty before workspace completion"
validate_fork_head "$WORKTREE" "$FORK_SHA" "$HEAD_OID" ||
    indeterminate "fork authority changed before workspace completion"
STEP_JSON=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not re-read the completion receipt"
receipt_matches_live_step "$STEP_JSON" "$HEAD_OID" "$FORK_SHA" complete ||
    indeterminate "workspace completion receipt changed before Graph completion"
validate_setup_proof \
    "$SETUP_KEY" "$SETUP_CONTEXT_OID" true \
    "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
    "$CURRENT_SESSION_ID" "$WORKTREE" "$EXPECTED_BRANCH" "$ROOT_BASE_BRANCH" \
    "$FORK_SHA" "$HEAD_OID" "$SETUP_DIGEST" ||
    indeterminate "workspace setup proof changed before Graph completion"
run_gc gastown polecat-step complete \
    --convoy "$CONVOY_ID" \
    --step-ref "$STEP_REF" ||
    indeterminate "workspace receipt is durable but Graph completion did not verify"

printf 'POLECAT_WORKSPACE_EXECUTE_COMPLETE step=%s root=%s convoy=%s source=%s branch=%s artifact=%s replay=false session=%s\n' \
    "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
    "$EXPECTED_BRANCH" "$WORKTREE" "$CURRENT_SESSION_ID"
