#!/usr/bin/env bash
# Deterministic, artifact-bound staging for one lease-owned rebase conflict.

set -u -o pipefail

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
EXIT_INDETERMINATE=75
STEP_REF="mol-polecat-work.workspace-setup"

usage() {
    echo "Usage: gc gastown polecat-conflict stage" >&2
}

if [[ "${1:-}" != "stage" || $# -ne 1 ]]; then
    usage
    exit "$EXIT_USAGE"
fi

indeterminate() {
    echo "POLECAT_CONFLICT_INDETERMINATE: $*" >&2
    echo "The index and lease proof were not accepted as complete; inspect and retry." >&2
    exit "$EXIT_INDETERMINATE"
}

safe_atom() {
    local value=$1
    [[ -n "$value" && "$value" != *$'\n'* &&
       "$value" != *$'\r'* && "$value" != *$'\t'* ]]
}

safe_component() {
    local value=$1
    case "$value" in
        ""|"."|".."|*[!A-Za-z0-9._-]*) return 1 ;;
    esac
}

is_oid() {
    local oid=$1
    case "${#oid}" in 40|64) ;; *) return 1 ;; esac
    [[ "$oid" != *[!0-9a-f]* ]]
}

[[ -n "${GC_CITY_PATH:-}" && -n "${GC_RIG:-}" &&
   -n "${GC_RIG_ROOT:-}" ]] ||
    indeterminate "GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required"
safe_component "$GC_RIG" ||
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
command -v jq >/dev/null 2>&1 || indeterminate "jq is required"
GIT_CMD=$(command -v git 2>/dev/null || true)
[[ -n "$GIT_CMD" && -x "$GIT_CMD" ]] || indeterminate "git is required"

run_gc_bd() {
    local command=("$GC_CMD" "bd" "--rig" "$RUNTIME_RIG")
    GC_NO_API=1 GC_CITY="$CITY_ROOT" GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$RIG_ROOT" GC_STORE_SCOPE=rig \
        "${command[@]}" "$@"
}

run_gc_convoy() {
    GC_NO_API=1 GC_CITY="$CITY_ROOT" GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$RIG_ROOT" GC_STORE_SCOPE=rig \
        "$GC_CMD" convoy "$@"
}

single_remote_url() {
    local mode=$1 output line selected="" count=0
    if [[ "$mode" == "push" ]]; then
        output=$("$GIT_CMD" remote get-url --push --all origin 2>/dev/null) ||
            return 1
    else
        output=$("$GIT_CMD" remote get-url --all origin 2>/dev/null) ||
            return 1
    fi
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        count=$((count + 1))
        selected=$line
    done <<<"$output"
    [[ "$count" -eq 1 ]] || return 1
    safe_atom "$selected" || return 1
    printf '%s' "$selected"
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
    "${BEADS_ACTOR:-}" "${GC_SESSION_NAME:-}" "${GC_SESSION_ID:-}" \
    "${GC_ALIAS:-}" "${GC_AGENT:-}"; do
    add_identity "$identity" ||
        indeterminate "a current runtime identity is unsafe"
done
[[ "${#RUNTIME_IDENTITIES[@]}" -gt 0 ]] ||
    indeterminate "no current runtime identity is available"

CONVOY_ID=${GC_POLECAT_CONVOY_ID:-}
ENV_SOURCE_ID=${GC_POLECAT_SOURCE_ID:-}
ENV_ARTIFACT_DIR=${GC_POLECAT_ARTIFACT_DIR:-}
ENV_BRANCH=${GC_POLECAT_SOURCE_BRANCH:-}
safe_atom "$CONVOY_ID" && safe_component "$ENV_SOURCE_ID" &&
    safe_atom "$ENV_ARTIFACT_DIR" && safe_atom "$ENV_BRANCH" ||
    indeterminate "validated polecat-step context is missing or unsafe"

STEP_MATCHES='[]'
for identity in "${RUNTIME_IDENTITIES[@]}"; do
    listed=$(run_gc_bd list --assignee "$identity" --status=in_progress \
        --limit=0 --json 2>/dev/null) ||
        indeterminate "could not list current workspace steps"
    matches=$(printf '%s' "$listed" | jq -ce \
        --arg actor "$identity" --arg ref "$STEP_REF" '
        if type == "array" and
           all(.[]; type == "object" and .status == "in_progress" and
               .assignee == $actor and ((.metadata // {}) | type) == "object")
        then [.[] | select(
          .metadata["gc.step_ref"] == $ref and
          (((.metadata | has("gc.outcome")) | not) or
           .metadata["gc.outcome"] == ""))]
        else error("workspace step query contradicted its filters")
        end' 2>/dev/null) ||
        indeterminate "workspace step query was malformed"
    STEP_MATCHES=$(jq -cn --argjson left "$STEP_MATCHES" \
        --argjson right "$matches" '$left + $right') ||
        indeterminate "could not aggregate workspace steps"
done
[[ "$(printf '%s' "$STEP_MATCHES" | jq -er 'length')" == "1" ]] ||
    indeterminate "expected exactly one current workspace step"
STEP_BEAD_ID=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].id') ||
    indeterminate "workspace step id is missing"
STEP_ASSIGNEE=$(printf '%s' "$STEP_MATCHES" | jq -er '.[0].assignee') ||
    indeterminate "workspace step assignee is missing"
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
       (.[0].metadata["gc.root_bead_id"] | type) == "string"
    then .[0].metadata["gc.root_bead_id"]
    else error("workspace step authority mismatch")
    end') ||
    indeterminate "workspace root id is missing"
safe_atom "$STEP_BEAD_ID" && safe_atom "$STEP_ASSIGNEE" &&
    safe_atom "$ROOT_BEAD_ID" ||
    indeterminate "workspace provenance contains unsafe identifiers"

ROOT_JSON=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null) ||
    indeterminate "could not read the workspace root"
ROOT_CONTEXT=$(printf '%s' "$ROOT_JSON" | jq -ecS \
    --arg id "$ROOT_BEAD_ID" --arg convoy "$CONVOY_ID" \
    --arg rig "$RUNTIME_RIG" '
    .[0].metadata["gc.graphv2_vars.v1"] as $raw |
    (if ($raw | type) == "object" then $raw else ($raw | fromjson) end) as $v |
    if type == "array" and length == 1 and .[0].id == $id and
       .[0].status == "in_progress" and
       .[0].metadata["gc.kind"] == "workflow" and
       .[0].metadata["gc.formula_contract"] == "graph.v2" and
       (((.[0].metadata | has("gc.formula_name")) | not) or
        .[0].metadata["gc.formula_name"] == "mol-polecat-work") and
       .[0].metadata["gc.input_convoy_id"] == $convoy and
       .[0].metadata["gc.var.rig_name"] == $rig and
       (((.[0].metadata | has("gc.outcome")) | not) or
        .[0].metadata["gc.outcome"] == "") and
       $v.base_branch == .[0].metadata["gc.var.base_branch"] and
       $v.rig_name == .[0].metadata["gc.var.rig_name"] and
       $v.binding_prefix == (.[0].metadata["gc.var.binding_prefix"] // "")
    then {
      base: $v.base_branch,
      rig: $v.rig_name,
      prefix: $v.binding_prefix
    }
    else error("root provenance mismatch")
    end' 2>/dev/null) ||
    indeterminate "workspace root Graph-v2 authority did not verify"
BASE_BRANCH=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.base') ||
    indeterminate "base branch is missing"
ROOT_BINDING_PREFIX=$(printf '%s' "$ROOT_CONTEXT" | jq -er '.prefix') ||
    indeterminate "binding prefix is missing"
safe_atom "$BASE_BRANCH" ||
    indeterminate "base branch is unsafe"
WITNESS_CANONICAL="${RUNTIME_RIG:+$RUNTIME_RIG/}${ROOT_BINDING_PREFIX}witness"
safe_atom "$WITNESS_CANONICAL" ||
    indeterminate "witness identity is unsafe"

CONVOY_JSON=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
    indeterminate "could not read the input convoy"
SOURCE_ID=$(printf '%s' "$CONVOY_JSON" | jq -er --arg convoy "$CONVOY_ID" '
    if type == "object" and .schema_version == "1" and
       .convoy.id == $convoy and (.children | type) == "array" and
       (.children | length) == 1 and
       (.children[0].id | type) == "string"
    then .children[0].id else error("convoy mismatch") end' 2>/dev/null) ||
    indeterminate "convoy source authority did not verify"
[[ "$SOURCE_ID" == "$ENV_SOURCE_ID" ]] ||
    indeterminate "polecat-step source context changed"
BRANCH="polecat/$SOURCE_ID"
[[ "$ENV_BRANCH" == "$BRANCH" ]] ||
    indeterminate "polecat-step branch context is not canonical"

SOURCE_JSON=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) ||
    indeterminate "could not read the source"
SOURCE_CONTEXT=$(printf '%s' "$SOURCE_JSON" | jq -ecS \
    --arg id "$SOURCE_ID" --arg branch "$BRANCH" \
    --arg artifact "$ENV_ARTIFACT_DIR" '
    if type == "array" and length == 1 and .[0].id == $id and
       .[0].status == "open" and ((.[0].assignee // "") == "") and
       ((.[0].metadata // {}) | type) == "object" and
       .[0].metadata.branch == $branch and
       .[0].metadata.artifact_dir == $artifact and
       ((.[0].metadata.work_dir // "") == "") and
       ((.[0].metadata.rejection_reason // "") | type) == "string" and
       (.[0].metadata.rejection_reason // "") != ""
    then {
      id: .[0].id,
      status: .[0].status,
      assignee: (.[0].assignee // ""),
      branch: .[0].metadata.branch,
      artifact: .[0].metadata.artifact_dir,
      rejection: .[0].metadata.rejection_reason,
      fork: (.[0].metadata.fork_sha // "")
    }
    else error("source authority mismatch")
    end' 2>/dev/null) ||
    indeterminate "source rejection/artifact authority did not verify"
ARTIFACT_DIR=$(printf '%s' "$SOURCE_CONTEXT" | jq -er '.artifact') ||
    indeterminate "source artifact is missing"

ONE_LINE=""
read_one_line() {
    local file=$1 line count=0
    ONE_LINE=""
    [[ -f "$file" && ! -L "$file" ]] || return 1
    while IFS= read -r line || [[ -n "$line" ]]; do
        count=$((count + 1))
        [[ "$count" -eq 1 ]] || return 1
        ONE_LINE=$line
    done <"$file"
    [[ "$count" -eq 1 && -n "$ONE_LINE" &&
       "$ONE_LINE" != *$'\r'* && "$ONE_LINE" != *$'\t'* ]]
}

validate_artifact() {
    local real top common rig_common admin ref resolved listed count=0
    local backref backparent backparent_real backreal rig_namespace
    local canonical worktrees_parent provider_home provider_root provider_name
    real=$(CDPATH= cd -- "$ARTIFACT_DIR" 2>/dev/null && pwd -P) || return 1
    [[ "$real" == "$ARTIFACT_DIR" ]] || return 1
    [[ "$(basename -- "$real")" == "$SOURCE_ID" &&
       "$(basename -- "$(dirname -- "$real")")" == "worktrees" ]] || return 1
    rig_namespace="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG"
    [[ "$(CDPATH= cd -- "$rig_namespace" 2>/dev/null && pwd -P)" == \
       "$rig_namespace" ]] || return 1
    canonical="$rig_namespace/artifacts/worktrees/$SOURCE_ID"
    if [[ "$real" != "$canonical" ]]; then
        worktrees_parent=$(dirname -- "$real")
        provider_home=$(dirname -- "$worktrees_parent")
        provider_root=$(dirname -- "$provider_home")
        provider_name=$(basename -- "$provider_home")
        [[ "$provider_root" == "$rig_namespace/polecats" ]] || return 1
        safe_component "$provider_name" || return 1
    fi
    top=$("$GIT_CMD" -C "$real" rev-parse --show-toplevel 2>/dev/null) ||
        return 1
    top=$(CDPATH= cd -- "$top" 2>/dev/null && pwd -P) || return 1
    [[ "$top" == "$real" ]] || return 1
    common=$("$GIT_CMD" -C "$real" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) || return 1
    common=$(CDPATH= cd -- "$common" 2>/dev/null && pwd -P) || return 1
    rig_common=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) || return 1
    rig_common=$(CDPATH= cd -- "$rig_common" 2>/dev/null && pwd -P) || return 1
    [[ "$common" == "$rig_common" ]] || return 1
    read_one_line "$real/.git" || return 1
    case "$ONE_LINE" in "gitdir: "*) ref=${ONE_LINE#gitdir: } ;; *) return 1 ;; esac
    case "$ref" in /*) admin=$ref ;; *) admin="$real/$ref" ;; esac
    resolved=$(CDPATH= cd -- "$admin" 2>/dev/null && pwd -P) || return 1
    [[ "$(dirname -- "$resolved")" == "$rig_common/worktrees" ]] || return 1
    read_one_line "$resolved/gitdir" || return 1
    backref=$ONE_LINE
    case "$backref" in
        /*) backreal=$backref ;;
        *)
            backparent=$(dirname -- "$resolved/$backref") || return 1
            backparent_real=$(CDPATH= cd -- "$backparent" 2>/dev/null &&
                pwd -P) || return 1
            backreal="$backparent_real/$(basename -- "$backref")"
            ;;
    esac
    [[ "$backreal" == "$real/.git" ]] || return 1
    while IFS= read -r -d '' listed; do
        [[ "$listed" == "worktree $real" ]] && count=$((count + 1))
    done < <("$GIT_CMD" -C "$RIG_ROOT" worktree list --porcelain -z 2>/dev/null)
    [[ "$count" -eq 1 ]] || return 1
    [[ "$(pwd -P 2>/dev/null)" == "$real" ]]
}
validate_artifact ||
    indeterminate "artifact path, repository, or registration did not verify"

RIG_COMMON=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
    --path-format=absolute --git-common-dir 2>/dev/null) ||
    indeterminate "could not resolve repository common directory"
RIG_COMMON=$(CDPATH= cd -- "$RIG_COMMON" 2>/dev/null && pwd -P) ||
    indeterminate "could not canonicalize repository common directory"
WORKTREE_FINGERPRINT=$(printf 'worktree-v1\0%s' "$ARTIFACT_DIR" |
    "$GIT_CMD" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not fingerprint worktree"
REPO_COMMON_FINGERPRINT=$(printf 'git-common-v1\0%s' "$RIG_COMMON" |
    "$GIT_CMD" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not fingerprint repository"
FETCH_URL=$(single_remote_url fetch) ||
    indeterminate "origin must have exactly one fetch URL"
PUSH_URL=$(single_remote_url push) ||
    indeterminate "origin must have exactly one push URL"
FETCH_FINGERPRINT=$(printf 'fetch-url-v1\0%s' "$FETCH_URL" |
    "$GIT_CMD" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not fingerprint fetch URL"
PUSH_FINGERPRINT=$(printf 'push-url-v1\0%s' "$PUSH_URL" |
    "$GIT_CMD" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not fingerprint push URL"

LEASE_KEY=$(printf 'gascity-polecat-push-lease-v1\0%s' "$SOURCE_ID" |
    "$GIT_CMD" hash-object --stdin 2>/dev/null) ||
    indeterminate "could not derive lease key"
LEASE_NS="refs/gascity/polecat-push-leases/$LEASE_KEY"
REBASE_WORK_REF="refs/heads/gascity-polecat-rebase/$LEASE_KEY"
CONTEXT_REF="$LEASE_NS/context"
EXPECTED_REF="$LEASE_NS/expected"
PRE_REF="$LEASE_NS/pre-rebase"
BASE_REF="$LEASE_NS/base"
for ref in "$CONTEXT_REF" "$EXPECTED_REF" "$PRE_REF" "$BASE_REF" \
           "$REBASE_WORK_REF"; do
    "$GIT_CMD" check-ref-format "$ref" >/dev/null 2>&1 ||
        indeterminate "internal lease ref is invalid"
done
for ref in "$CONTEXT_REF" "$EXPECTED_REF" "$PRE_REF" "$BASE_REF" \
           "$REBASE_WORK_REF" "refs/heads/$BRANCH" \
           "$LEASE_NS/candidate" "$LEASE_NS/rebased" "$LEASE_NS/submit"; do
    ! "$GIT_CMD" symbolic-ref -q "$ref" >/dev/null 2>&1 ||
        indeterminate "symbolic lease or branch ref is forbidden"
done
read_ref() {
    local ref=$1
    ! "$GIT_CMD" symbolic-ref -q "$ref" >/dev/null 2>&1 || return 1
    "$GIT_CMD" rev-parse --verify --quiet "$ref" 2>/dev/null
}
CONTEXT_OID=$(read_ref "$CONTEXT_REF") ||
    indeterminate "captured lease context is missing"
EXPECTED_OID=$(read_ref "$EXPECTED_REF") ||
    indeterminate "captured expected remote is missing"
PRE_OID=$(read_ref "$PRE_REF") ||
    indeterminate "captured PRE is missing"
BASE_OID=$(read_ref "$BASE_REF") ||
    indeterminate "captured base is missing"
REBASE_WORK_OID=$(read_ref "$REBASE_WORK_REF") ||
    indeterminate "lease-owned rebase work ref is missing"
for oid in "$CONTEXT_OID" "$EXPECTED_OID" "$PRE_OID" "$BASE_OID" \
           "$REBASE_WORK_OID"; do
    is_oid "$oid" || indeterminate "captured lease oid is malformed"
done
for oid in "$EXPECTED_OID" "$PRE_OID" "$BASE_OID" "$REBASE_WORK_OID"; do
    [[ "$("$GIT_CMD" cat-file -t "$oid" 2>/dev/null)" == "commit" ]] ||
        indeterminate "captured lease commit authority is malformed"
done
[[ "$REBASE_WORK_OID" == "$PRE_OID" &&
   "$(read_ref "refs/heads/$BRANCH")" == "$PRE_OID" ]] ||
    indeterminate "captured lease branches moved during the active rebase"
for suffix in candidate rebased submit; do
    [[ -z "$(read_ref "$LEASE_NS/$suffix" || true)" ]] ||
        indeterminate "captured lease is already beyond conflict staging"
done

emit_lease_context() {
    printf '%s\n' \
        "version=1" \
        "source=$SOURCE_ID" \
        "workflow_root=$ROOT_BEAD_ID" \
        "input_convoy=$CONVOY_ID" \
        "branch=$BRANCH" \
        "target=$BASE_BRANCH" \
        "witness=$WITNESS_CANONICAL" \
        "rebase_work_ref=$REBASE_WORK_REF" \
        "worktree_fingerprint=$WORKTREE_FINGERPRINT" \
        "repo_common_fingerprint=$REPO_COMMON_FINGERPRINT" \
        "origin_fetch_fingerprint=$FETCH_FINGERPRINT" \
        "origin_push_fingerprint=$PUSH_FINGERPRINT"
}
EXPECTED_CONTEXT=$(emit_lease_context | "$GIT_CMD" hash-object --stdin) ||
    indeterminate "could not compute lease context"
[[ "$CONTEXT_OID" == "$EXPECTED_CONTEXT" &&
   "$("$GIT_CMD" cat-file blob "$CONTEXT_OID" 2>/dev/null)" == \
     "$(emit_lease_context)" ]] ||
    indeterminate "captured lease context does not match this Graph/artifact"

REMOTE_LINE=$("$GIT_CMD" ls-remote --exit-code --heads "$PUSH_URL" \
    "refs/heads/$BRANCH" 2>/dev/null) ||
    indeterminate "could not verify the frozen push remote"
REMOTE_OID=$(printf '%s\n' "$REMOTE_LINE" | jq -Rrs \
    --arg ref "refs/heads/$BRANCH" '
    split("\n") | map(select(length > 0) | split("\t")) |
    if length == 1 and .[0][1] == $ref then .[0][0] else "" end') ||
    indeterminate "could not parse frozen remote"
[[ "$REMOTE_OID" == "$EXPECTED_OID" ]] ||
    indeterminate "push remote moved after lease capture"

REBASE_DIR=$("$GIT_CMD" rev-parse --git-path rebase-merge 2>/dev/null) ||
    indeterminate "could not resolve rebase state"
[[ -d "$REBASE_DIR" && ! -L "$REBASE_DIR" &&
   ! -e "$("$GIT_CMD" rev-parse --git-path rebase-apply 2>/dev/null)" ]] ||
    indeterminate "no exact merge-backend rebase conflict is active"
read_one_line "$REBASE_DIR/head-name" ||
    indeterminate "rebase head-name is unreadable"
[[ "$ONE_LINE" == "$REBASE_WORK_REF" ]] ||
    indeterminate "rebase is not bound to the lease-owned temporary branch"
read_one_line "$REBASE_DIR/orig-head" ||
    indeterminate "rebase orig-head is unreadable"
[[ "$ONE_LINE" == "$PRE_OID" ]] ||
    indeterminate "rebase orig-head differs from captured PRE"
read_one_line "$REBASE_DIR/onto" || indeterminate "rebase onto is unreadable"
ONTO_OID=$ONE_LINE
[[ "$ONTO_OID" == "$BASE_OID" ]] ||
    indeterminate "rebase onto differs from captured base"
read_one_line "$REBASE_DIR/stopped-sha" ||
    indeterminate "rebase stopped commit is unreadable"
STOPPED_OID=$ONE_LINE
REBASE_HEAD_OID=$("$GIT_CMD" rev-parse --verify REBASE_HEAD 2>/dev/null) ||
    indeterminate "REBASE_HEAD is missing"
[[ "$STOPPED_OID" == "$REBASE_HEAD_OID" ]] ||
    indeterminate "stopped commit and REBASE_HEAD differ"
CONFLICT_PARENT_OID=$("$GIT_CMD" rev-parse --verify HEAD 2>/dev/null) ||
    indeterminate "could not resolve the pre-continuation conflict parent"
is_oid "$CONFLICT_PARENT_OID" &&
    [[ "$("$GIT_CMD" cat-file -t "$CONFLICT_PARENT_OID" 2>/dev/null)" == \
       "commit" ]] ||
    indeterminate "pre-continuation conflict parent is not a commit"

emit_generation() {
    jq -cnS \
        --arg schema "gascity-polecat-conflict-generation-v1" \
        --arg lease_context "$CONTEXT_OID" --arg source "$SOURCE_ID" \
        --arg root "$ROOT_BEAD_ID" --arg step "$STEP_BEAD_ID" \
        --arg convoy "$CONVOY_ID" --arg work_ref "$REBASE_WORK_REF" \
        --arg pre "$PRE_OID" --arg base "$BASE_OID" \
        --arg stopped "$STOPPED_OID" --arg onto "$ONTO_OID" '
        {
          schema: $schema, lease_context_oid: $lease_context,
          source: $source, workflow_root: $root, step: $step,
          input_convoy: $convoy, rebase_work_ref: $work_ref,
          pre_oid: $pre, base_oid: $base, stopped_oid: $stopped,
          rebase_head_oid: $stopped, onto_oid: $onto
        }'
}
GENERATION=$(emit_generation | "$GIT_CMD" hash-object --stdin) ||
    indeterminate "could not derive conflict generation"
CONFLICT_NS="refs/gascity/polecat-conflicts/v1/$LEASE_KEY/$GENERATION"
CONFLICT_CONTEXT_REF="$CONFLICT_NS/context"
CONFLICT_TREE_REF="$CONFLICT_NS/tree"
CONFLICT_DONE_REF="$CONFLICT_NS/done"
for ref in "$CONFLICT_CONTEXT_REF" "$CONFLICT_TREE_REF" \
           "$CONFLICT_DONE_REF"; do
    "$GIT_CMD" check-ref-format "$ref" >/dev/null 2>&1 ||
        indeterminate "conflict proof ref is invalid"
done
proof_refs_are_direct() {
    local ref
    for ref in "$CONFLICT_CONTEXT_REF" "$CONFLICT_TREE_REF" \
               "$CONFLICT_DONE_REF"; do
        ! "$GIT_CMD" symbolic-ref -q "$ref" >/dev/null 2>&1 || return 1
    done
}
proof_refs_are_direct ||
    indeterminate "symbolic conflict proof ref is forbidden"

TMP_DIR=$(mktemp -d) || indeterminate "could not create conflict staging scratch"
trap 'rm -rf -- "$TMP_DIR"' EXIT
TUPLES_FILE="$TMP_DIR/unmerged"
UNSTAGED_FILE="$TMP_DIR/unstaged"
UNTRACKED_FILE="$TMP_DIR/untracked"
INDEX_COPY="$TMP_DIR/index"

PROOF_TREE=""
validate_proof_state() {
    local require_done=$1 context_oid tree_oid done_oid body actual_tree
    PROOF_TREE=""
    proof_refs_are_direct || return 1
    context_oid=$(read_ref "$CONFLICT_CONTEXT_REF") || return 1
    tree_oid=$(read_ref "$CONFLICT_TREE_REF") || return 1
    done_oid=$(read_ref "$CONFLICT_DONE_REF" || true)
    case "$require_done:$done_oid" in
        true:"$tree_oid") ;;
        false:"") ;;
        *) return 1 ;;
    esac
    is_oid "$context_oid" && is_oid "$tree_oid" || return 1
    [[ "$(git cat-file -t "$context_oid" 2>/dev/null)" == "blob" &&
       "$(git cat-file -t "$tree_oid" 2>/dev/null)" == "tree" ]] || return 1
    body=$("$GIT_CMD" cat-file blob "$context_oid" 2>/dev/null) || return 1
    printf '%s' "$body" | jq -e \
        --arg generation "$GENERATION" --arg lease "$CONTEXT_OID" \
        --arg source "$SOURCE_ID" --arg root "$ROOT_BEAD_ID" \
        --arg step "$STEP_BEAD_ID" --arg convoy "$CONVOY_ID" \
        --arg work "$REBASE_WORK_REF" --arg pre "$PRE_OID" \
        --arg base "$BASE_OID" --arg stopped "$STOPPED_OID" \
        --arg onto "$ONTO_OID" --arg parent "$CONFLICT_PARENT_OID" \
        --arg tree "$tree_oid" '
        .schema == "gascity-polecat-conflict-context-v1" and
        .generation == $generation and .lease_context_oid == $lease and
        .source == $source and .workflow_root == $root and .step == $step and
        .input_convoy == $convoy and .rebase_work_ref == $work and
        .pre_oid == $pre and .base_oid == $base and
        .stopped_oid == $stopped and .rebase_head_oid == $stopped and
        .onto_oid == $onto and .conflict_parent_oid == $parent and
        .expected_tree_oid == $tree and
        (.unmerged_tuple_digest | type) == "string"' >/dev/null 2>&1 ||
        return 1
    [[ -z "$("$GIT_CMD" ls-files -u 2>/dev/null)" &&
       -z "$("$GIT_CMD" diff --name-only 2>/dev/null)" &&
       -z "$("$GIT_CMD" ls-files --others --exclude-standard 2>/dev/null)" ]] ||
        return 1
    "$GIT_CMD" diff --cached --check >/dev/null 2>&1 || return 1
    actual_tree=$("$GIT_CMD" write-tree 2>/dev/null) || return 1
    [[ "$actual_tree" == "$tree_oid" ]] || return 1
    PROOF_TREE=$tree_oid
}

validate_done() {
    validate_proof_state true
}

revalidate_authority() {
    local remote_line remote_oid fetch_now push_now
    [[ "$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null |
            jq -cS . 2>/dev/null)" == \
       "$(printf '%s' "$STEP_JSON" | jq -cS . 2>/dev/null)" ]] || return 1
    [[ "$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null |
            jq -cS . 2>/dev/null)" == \
       "$(printf '%s' "$ROOT_JSON" | jq -cS . 2>/dev/null)" ]] || return 1
    [[ "$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null |
            jq -cS . 2>/dev/null)" == \
       "$(printf '%s' "$SOURCE_JSON" | jq -cS . 2>/dev/null)" ]] || return 1
    [[ "$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null |
            jq -cS . 2>/dev/null)" == \
       "$(printf '%s' "$CONVOY_JSON" | jq -cS . 2>/dev/null)" ]] || return 1
    validate_artifact || return 1
    [[ "$(read_ref "$CONTEXT_REF")" == "$CONTEXT_OID" &&
       "$(read_ref "$EXPECTED_REF")" == "$EXPECTED_OID" &&
       "$(read_ref "$PRE_REF")" == "$PRE_OID" &&
       "$(read_ref "$BASE_REF")" == "$BASE_OID" &&
       "$(read_ref "$REBASE_WORK_REF")" == "$PRE_OID" &&
       "$(read_ref "refs/heads/$BRANCH")" == "$PRE_OID" ]] || return 1
    [[ -z "$(read_ref "$LEASE_NS/candidate" || true)" &&
       -z "$(read_ref "$LEASE_NS/rebased" || true)" &&
       -z "$(read_ref "$LEASE_NS/submit" || true)" ]] || return 1
    read_one_line "$REBASE_DIR/head-name" || return 1
    [[ "$ONE_LINE" == "$REBASE_WORK_REF" ]] || return 1
    read_one_line "$REBASE_DIR/orig-head" || return 1
    [[ "$ONE_LINE" == "$PRE_OID" ]] || return 1
    read_one_line "$REBASE_DIR/onto" || return 1
    [[ "$ONE_LINE" == "$ONTO_OID" ]] || return 1
    read_one_line "$REBASE_DIR/stopped-sha" || return 1
    [[ "$ONE_LINE" == "$STOPPED_OID" &&
       "$("$GIT_CMD" rev-parse --verify REBASE_HEAD 2>/dev/null)" == \
         "$REBASE_HEAD_OID" &&
       "$("$GIT_CMD" rev-parse --verify HEAD 2>/dev/null)" == \
         "$CONFLICT_PARENT_OID" ]] || return 1
    fetch_now=$(single_remote_url fetch) || return 1
    push_now=$(single_remote_url push) || return 1
    [[ "$fetch_now" == "$FETCH_URL" && "$push_now" == "$PUSH_URL" ]] ||
        return 1
    remote_line=$("$GIT_CMD" ls-remote --exit-code --heads "$PUSH_URL" \
        "refs/heads/$BRANCH" 2>/dev/null) || return 1
    remote_oid=$(printf '%s\n' "$remote_line" | jq -Rrs \
        --arg ref "refs/heads/$BRANCH" '
        split("\n") | map(select(length > 0) | split("\t")) |
        if length == 1 and .[0][1] == $ref then .[0][0] else "" end') ||
        return 1
    [[ "$remote_oid" == "$EXPECTED_OID" ]]
}

"$GIT_CMD" ls-files -u -z >"$TUPLES_FILE" ||
    indeterminate "could not enumerate unmerged index tuples"
if [[ ! -s "$TUPLES_FILE" ]]; then
    if validate_done; then
        :
    elif validate_proof_state false; then
        revalidate_authority ||
            indeterminate "authority changed before recovering staged conflict proof"
        if ! printf '%s\n' \
            start \
            "option no-deref" \
            "verify $CONTEXT_REF $CONTEXT_OID" \
            "verify $EXPECTED_REF $EXPECTED_OID" \
            "verify $PRE_REF $PRE_OID" \
            "verify $BASE_REF $BASE_OID" \
            "verify refs/heads/$BRANCH $PRE_OID" \
            "verify $REBASE_WORK_REF $PRE_OID" \
            "verify $CONFLICT_CONTEXT_REF $(read_ref "$CONFLICT_CONTEXT_REF")" \
            "verify $CONFLICT_TREE_REF $PROOF_TREE" \
            "create $CONFLICT_DONE_REF $PROOF_TREE" \
            prepare \
            commit | "$GIT_CMD" update-ref --stdin >/dev/null 2>&1; then
            :
        fi
        validate_done ||
            indeterminate "staged conflict done recovery did not verify"
    else
        indeterminate "no unmerged paths remain and no exact intent proof matches"
    fi
    printf 'POLECAT_CONFLICT_STAGE_COMPLETE generation=%s tree=%s replay=true\n' \
        "$GENERATION" "$(read_ref "$CONFLICT_TREE_REF")"
    exit 0
fi

declare -a UNMERGED_PATHS=()
path_is_unmerged() {
    local candidate=$1 existing
    for existing in "${UNMERGED_PATHS[@]}"; do
        [[ "$existing" != "$candidate" ]] || return 0
    done
    return 1
}
while IFS= read -r -d '' tuple; do
    [[ "$tuple" == *$'\t'* ]] ||
        indeterminate "unmerged index tuple is malformed"
    path=${tuple#*$'\t'}
    [[ -n "$path" ]] || indeterminate "unmerged path is empty"
    if ! path_is_unmerged "$path"; then
        UNMERGED_PATHS+=("$path")
    fi
done <"$TUPLES_FILE"
[[ "${#UNMERGED_PATHS[@]}" -gt 0 ]] ||
    indeterminate "unmerged tuple set has no paths"
U_DIGEST=$("$GIT_CMD" hash-object --stdin <"$TUPLES_FILE") ||
    indeterminate "could not digest unmerged tuples"

"$GIT_CMD" ls-files --others --exclude-standard -z >"$UNTRACKED_FILE" ||
    indeterminate "could not enumerate untracked files"
[[ ! -s "$UNTRACKED_FILE" ]] ||
    indeterminate "untracked files are forbidden during conflict staging"
"$GIT_CMD" diff --name-only -z >"$UNSTAGED_FILE" ||
    indeterminate "could not enumerate unstaged tracked changes"
while IFS= read -r -d '' path; do
    path_is_unmerged "$path" ||
        indeterminate "unstaged tracked change exists outside the unmerged set"
done <"$UNSTAGED_FILE"

REAL_INDEX=$("$GIT_CMD" rev-parse --git-path index 2>/dev/null) ||
    indeterminate "could not resolve the real index"
[[ -f "$REAL_INDEX" && ! -L "$REAL_INDEX" ]] ||
    indeterminate "real index is missing or redirected"
cp -- "$REAL_INDEX" "$INDEX_COPY" ||
    indeterminate "could not copy the index for deterministic simulation"
GIT_INDEX_FILE="$INDEX_COPY" "$GIT_CMD" add -- "${UNMERGED_PATHS[@]}" ||
    indeterminate "could not simulate exact unmerged-path staging"
GIT_INDEX_FILE="$INDEX_COPY" "$GIT_CMD" diff --cached --check \
    -- "${UNMERGED_PATHS[@]}" ||
    indeterminate "resolved conflict has whitespace errors or conflict markers"
EXPECTED_TREE=$(GIT_INDEX_FILE="$INDEX_COPY" "$GIT_CMD" write-tree 2>/dev/null) ||
    indeterminate "could not derive expected post-stage tree"
is_oid "$EXPECTED_TREE" || indeterminate "expected tree oid is malformed"

emit_context() {
    jq -cnS \
        --arg schema "gascity-polecat-conflict-context-v1" \
        --arg generation "$GENERATION" --arg lease "$CONTEXT_OID" \
        --arg source "$SOURCE_ID" --arg root "$ROOT_BEAD_ID" \
        --arg step "$STEP_BEAD_ID" --arg convoy "$CONVOY_ID" \
        --arg work "$REBASE_WORK_REF" --arg pre "$PRE_OID" \
        --arg base "$BASE_OID" --arg stopped "$STOPPED_OID" \
        --arg onto "$ONTO_OID" --arg parent "$CONFLICT_PARENT_OID" \
        --arg u "$U_DIGEST" \
        --arg tree "$EXPECTED_TREE" '
        {
          schema: $schema, generation: $generation,
          lease_context_oid: $lease, source: $source,
          workflow_root: $root, step: $step, input_convoy: $convoy,
          rebase_work_ref: $work, pre_oid: $pre, base_oid: $base,
          stopped_oid: $stopped, rebase_head_oid: $stopped, onto_oid: $onto,
          conflict_parent_oid: $parent,
          unmerged_tuple_digest: $u, expected_tree_oid: $tree
        }'
}
CONTEXT_BODY=$(emit_context) ||
    indeterminate "could not encode conflict intent"
CONFLICT_CONTEXT_OID=$(printf '%s\n' "$CONTEXT_BODY" |
    "$GIT_CMD" hash-object -w --stdin 2>/dev/null) ||
    indeterminate "could not write conflict intent object"

EXISTING_CONTEXT=$(read_ref "$CONFLICT_CONTEXT_REF" || true)
EXISTING_TREE=$(read_ref "$CONFLICT_TREE_REF" || true)
EXISTING_DONE=$(read_ref "$CONFLICT_DONE_REF" || true)
if [[ -z "$EXISTING_CONTEXT" && -z "$EXISTING_TREE" &&
      -z "$EXISTING_DONE" ]]; then
    printf '%s\n' \
        start \
        "option no-deref" \
        "verify $CONTEXT_REF $CONTEXT_OID" \
        "verify $EXPECTED_REF $EXPECTED_OID" \
        "verify $PRE_REF $PRE_OID" \
        "verify $BASE_REF $BASE_OID" \
        "verify refs/heads/$BRANCH $PRE_OID" \
        "verify $REBASE_WORK_REF $PRE_OID" \
        "create $CONFLICT_CONTEXT_REF $CONFLICT_CONTEXT_OID" \
        "create $CONFLICT_TREE_REF $EXPECTED_TREE" \
        prepare \
        commit | "$GIT_CMD" update-ref --stdin >/dev/null 2>&1 || true
else
    :
fi
proof_refs_are_direct ||
    indeterminate "symbolic conflict proof ref appeared during intent creation"
EXISTING_CONTEXT=$(read_ref "$CONFLICT_CONTEXT_REF" || true)
EXISTING_TREE=$(read_ref "$CONFLICT_TREE_REF" || true)
EXISTING_DONE=$(read_ref "$CONFLICT_DONE_REF" || true)
[[ "$EXISTING_CONTEXT" == "$CONFLICT_CONTEXT_OID" &&
   "$EXISTING_TREE" == "$EXPECTED_TREE" &&
   ( -z "$EXISTING_DONE" || "$EXISTING_DONE" == "$EXPECTED_TREE" ) ]] ||
    indeterminate "conflict intent is partial or belongs to another resolution"
if [[ "$EXISTING_DONE" == "$EXPECTED_TREE" ]]; then
    validate_done ||
        indeterminate "existing conflict done proof does not match the index"
    printf 'POLECAT_CONFLICT_STAGE_COMPLETE generation=%s tree=%s replay=true\n' \
        "$GENERATION" "$EXPECTED_TREE"
    exit 0
fi

# Revalidate every authority snapshot immediately before touching the real index.
revalidate_authority ||
    indeterminate "Graph/source/artifact/lease/rebase authority changed before staging"
"$GIT_CMD" ls-files -u -z >"$TMP_DIR/unmerged-now" ||
    indeterminate "could not re-enumerate unmerged tuples"
[[ "$("$GIT_CMD" hash-object --stdin <"$TMP_DIR/unmerged-now")" == \
   "$U_DIGEST" ]] ||
    indeterminate "unmerged tuple set changed before staging"
"$GIT_CMD" ls-files --others --exclude-standard -z >"$UNTRACKED_FILE" ||
    indeterminate "could not re-enumerate untracked files"
[[ ! -s "$UNTRACKED_FILE" ]] ||
    indeterminate "untracked files appeared before staging"
"$GIT_CMD" diff --name-only -z >"$UNSTAGED_FILE" ||
    indeterminate "could not re-enumerate unstaged changes"
while IFS= read -r -d '' path; do
    path_is_unmerged "$path" ||
        indeterminate "unstaged tracked change appeared outside the unmerged set"
done <"$UNSTAGED_FILE"

"$GIT_CMD" add -- "${UNMERGED_PATHS[@]}" ||
    indeterminate "could not stage the exact unmerged path set"
[[ -z "$("$GIT_CMD" ls-files -u 2>/dev/null)" &&
   -z "$("$GIT_CMD" diff --name-only 2>/dev/null)" &&
   -z "$("$GIT_CMD" ls-files --others --exclude-standard 2>/dev/null)" ]] ||
    indeterminate "post-stage index or worktree is not exact and clean"
"$GIT_CMD" diff --cached --check >/dev/null 2>&1 ||
    indeterminate "post-stage tree has whitespace errors or conflict markers"
ACTUAL_TREE=$("$GIT_CMD" write-tree 2>/dev/null) ||
    indeterminate "could not write the staged conflict tree"
[[ "$ACTUAL_TREE" == "$EXPECTED_TREE" ]] ||
    indeterminate "post-stage tree differs from immutable intent"
revalidate_authority ||
    indeterminate "authority changed after staging and before done publication"

if ! printf '%s\n' \
    start \
    "option no-deref" \
    "verify $CONTEXT_REF $CONTEXT_OID" \
    "verify $EXPECTED_REF $EXPECTED_OID" \
    "verify $PRE_REF $PRE_OID" \
    "verify $BASE_REF $BASE_OID" \
    "verify refs/heads/$BRANCH $PRE_OID" \
    "verify $REBASE_WORK_REF $PRE_OID" \
    "verify $CONFLICT_CONTEXT_REF $CONFLICT_CONTEXT_OID" \
    "verify $CONFLICT_TREE_REF $EXPECTED_TREE" \
    "create $CONFLICT_DONE_REF $EXPECTED_TREE" \
    prepare \
    commit | "$GIT_CMD" update-ref --stdin >/dev/null 2>&1; then
    :
fi
validate_done ||
    indeterminate "conflict done proof did not read back exactly"
printf 'POLECAT_CONFLICT_STAGE_COMPLETE generation=%s tree=%s replay=false\n' \
    "$GENERATION" "$EXPECTED_TREE"
