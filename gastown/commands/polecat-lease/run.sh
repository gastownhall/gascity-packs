#!/usr/bin/env bash
# Deterministic rejection-rebase and push protocol for Gastown polecats.
#
# This command deliberately owns the Git/ref transactions.  The formula calls
# it instead of asking a model to reproduce a crash-sensitive protocol from
# prose.  Bead metadata is only a mirror; the authoritative lease is a
# create-only set of refs in the repository's common Git directory.

set -u -o pipefail

EXIT_USAGE=2
EXIT_HARD=64
EXIT_INDETERMINATE=75

ACTION=${1:-}
if [[ -n "$ACTION" ]]; then
    shift
fi

SOURCE_ID=""
CONVOY_ID=""
BASE_BRANCH=""
BRANCH=""
WITNESS_TARGET=""
AUTO_PUSH=""

usage() {
    cat >&2 <<'EOF'
Usage:
  gc gastown polecat-lease workspace \
    --source ID --convoy ID --base BRANCH --branch BRANCH --witness TARGET
  gc gastown polecat-lease publish-rebase \
    --source ID --convoy ID --base BRANCH --branch BRANCH --witness TARGET
  gc gastown polecat-lease submit \
    --source ID --convoy ID --base BRANCH --branch BRANCH --witness TARGET \
    --auto-push true|false
EOF
}

while (($#)); do
    case "$1" in
        --source)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            SOURCE_ID=$2
            shift 2
            ;;
        --convoy)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            CONVOY_ID=$2
            shift 2
            ;;
        --base)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            BASE_BRANCH=$2
            shift 2
            ;;
        --branch)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            BRANCH=$2
            shift 2
            ;;
        --witness)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            WITNESS_TARGET=$2
            shift 2
            ;;
        --auto-push)
            [[ $# -ge 2 ]] || { usage; exit "$EXIT_USAGE"; }
            AUTO_PUSH=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "polecat-lease: unknown argument: $1" >&2
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
    workspace|publish-rebase|submit) ;;
    *)
        usage
        exit "$EXIT_USAGE"
        ;;
esac
if [[ "$ACTION" == "submit" ]]; then
    case "$AUTO_PUSH" in
        true|false) ;;
        *)
            echo "polecat-lease: submit requires explicit --auto-push true or false" >&2
            exit "$EXIT_USAGE"
            ;;
    esac
elif [[ -n "$AUTO_PUSH" ]]; then
    echo "polecat-lease: --auto-push is valid only for submit" >&2
    exit "$EXIT_USAGE"
fi
for required in SOURCE_ID CONVOY_ID BASE_BRANCH BRANCH WITNESS_TARGET; do
    if [[ -z "${!required}" ]]; then
        echo "polecat-lease: missing required ${required}" >&2
        usage
        exit "$EXIT_USAGE"
    fi
done

GC_CMD=${GC_BIN:-}
if [[ -z "$GC_CMD" ]]; then
    GC_CMD=$(command -v gc 2>/dev/null || true)
fi
if [[ -z "$GC_CMD" || ! -x "$GC_CMD" ]]; then
    echo "polecat-lease: the invoking gc executable is unavailable" >&2
    exit "$EXIT_INDETERMINATE"
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "polecat-lease: jq is required" >&2
    exit "$EXIT_INDETERMINATE"
fi
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "polecat-lease: cwd is not a Git worktree" >&2
    exit "$EXIT_INDETERMINATE"
fi

[[ -n "${GC_CITY_PATH:-}" && -n "${GC_RIG:-}" &&
   -n "${GC_RIG_ROOT:-}" ]] || {
    echo "polecat-lease: GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required" >&2
    exit "$EXIT_INDETERMINATE"
}
case "$GC_RIG" in
    ""|"."|".."|*[!A-Za-z0-9._-]*)
        echo "polecat-lease: the runtime rig name is unsafe" >&2
        exit "$EXIT_INDETERMINATE"
        ;;
esac
RUNTIME_RIG=$GC_RIG
CITY_ROOT=$(CDPATH= cd -- "$GC_CITY_PATH" 2>/dev/null && pwd -P) || {
    echo "polecat-lease: could not canonicalize the city root" >&2
    exit "$EXIT_INDETERMINATE"
}
RIG_ROOT=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) || {
    echo "polecat-lease: could not canonicalize the rig root" >&2
    exit "$EXIT_INDETERMINATE"
}

run_gc() {
    "$GC_CMD" "$@"
}

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
    echo "POLECAT_LEASE_INDETERMINATE: $*" >&2
    echo "Protected state was preserved; inspect the diagnostic before retrying." >&2
    echo "This failure path did not perform Graph terminalization or drain." >&2
    exit "$EXIT_INDETERMINATE"
}

safe_atom() {
    local value=$1
    [[ -n "$value" ]] || return 1
    [[ "$value" != *$'\n'* && "$value" != *$'\r'* && "$value" != *$'\t'* ]]
}

is_oid() {
    local oid=$1
    case "${#oid}" in
        40|64) ;;
        *) return 1 ;;
    esac
    case "$oid" in
        *[!0-9a-f]*) return 1 ;;
    esac
}

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

prove_authoritative_convoy_source() {
    local convoy_json convoy_source
    convoy_json=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
        return 1
    convoy_source=$(convoy_source_id "$convoy_json") || return 1
    [[ "$convoy_source" == "$SOURCE_ID" ]]
}

for atom in "$SOURCE_ID" "$CONVOY_ID" "$BASE_BRANCH" "$BRANCH" "$WITNESS_TARGET"; do
    safe_atom "$atom" || {
        echo "polecat-lease: unsafe empty/control-character argument" >&2
        exit "$EXIT_USAGE"
    }
done

EXPECTED_BRANCH="polecat/$SOURCE_ID"
if [[ "$BRANCH" != "$EXPECTED_BRANCH" ]]; then
    echo "polecat-lease: branch $BRANCH does not equal $EXPECTED_BRANCH" >&2
    exit "$EXIT_HARD"
fi
git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 || {
    echo "polecat-lease: invalid feature branch" >&2
    exit "$EXIT_HARD"
}
git check-ref-format --branch "$BASE_BRANCH" >/dev/null 2>&1 || {
    echo "polecat-lease: invalid base branch" >&2
    exit "$EXIT_HARD"
}

BRANCH_REF="refs/heads/$BRANCH"
TRACKING_REF="refs/remotes/origin/$BRANCH"
BASE_REMOTE_REF="refs/remotes/origin/$BASE_BRANCH"

LEASE_KEY=$(printf 'gascity-polecat-push-lease-v1\0%s' "$SOURCE_ID" | git hash-object --stdin 2>/dev/null) ||
    indeterminate "could not derive the opaque lease key"
is_oid "$LEASE_KEY" || indeterminate "Git returned an invalid lease key"

LEASE_NS="refs/gascity/polecat-push-leases/$LEASE_KEY"
CONTEXT_REF="$LEASE_NS/context"
EXPECTED_REF="$LEASE_NS/expected"
PRE_REF="$LEASE_NS/pre-rebase"
BASE_REF="$LEASE_NS/base"
REBASED_REF="$LEASE_NS/rebased"
SUBMIT_REF="$LEASE_NS/submit"

for ref in "$CONTEXT_REF" "$EXPECTED_REF" "$PRE_REF" "$BASE_REF" \
           "$REBASED_REF" "$SUBMIT_REF"; do
    git check-ref-format "$ref" >/dev/null 2>&1 ||
        indeterminate "Git rejected an internal lease ref"
done

if ! printf 'start\noption no-deref\nprepare\nabort\n' |
     git update-ref --stdin >/dev/null 2>&1; then
    indeterminate "Git lacks transactional update-ref support"
fi

EXPECTED_STEP_REF="mol-polecat-work.workspace-setup"
if [[ "$ACTION" == "submit" ]]; then
    EXPECTED_STEP_REF="mol-polecat-work.submit-and-exit"
fi

RUNTIME_IDENTITIES=()
STEP_ASSIGNEE=""
STEP_BEAD_ID=""
ROOT_BEAD_ID=""
PROVENANCE_READY=0
TERMINAL_RECOVERY=0
ROOT_RIG_NAME=""
ROOT_BINDING_PREFIX=""
WITNESS_CANONICAL=""

add_runtime_identity() {
    local value=$1 existing
    [[ -n "$value" ]] || return 0
    safe_atom "$value" || return 1
    for existing in "${RUNTIME_IDENTITIES[@]}"; do
        [[ "$existing" != "$value" ]] || return 0
    done
    RUNTIME_IDENTITIES+=("$value")
}

identity_is_runtime() {
    local value=$1 existing
    for existing in "${RUNTIME_IDENTITIES[@]}"; do
        [[ "$existing" != "$value" ]] || return 0
    done
    return 1
}

classify_workflow_root() {
    local root_json=$1 root_id=$2 mode=$3 classification
    classification=$(printf '%s' "$root_json" | jq -er \
        --arg id "$root_id" --arg convoy "$CONVOY_ID" \
        --arg base "$BASE_BRANCH" --arg mode "$mode" '
        if type != "array" or length != 1 or .[0].id != $id or
           (.[0].metadata | type) != "object" or
           .[0].metadata["gc.kind"] != "workflow" or
           .[0].metadata["gc.formula_contract"] != "graph.v2" or
           ((.[0].metadata | has("gc.formula_name")) and
            .[0].metadata["gc.formula_name"] != "mol-polecat-work") or
           (.[0].metadata["gc.input_convoy_id"] | type) != "string" or
           (.[0].metadata["gc.input_convoy_id"] | length) == 0 or
           (.[0].metadata["gc.var.base_branch"] | type) != "string" or
           (.[0].metadata["gc.var.base_branch"] | length) == 0 or
           (.[0].status | type) != "string" or
           (.[0].status | length) == 0 or
           ((.[0].metadata | has("gc.outcome")) and
            (.[0].metadata["gc.outcome"] | type) != "string")
        then error("root identity or immutable Graph-v2 provenance mismatch")
        elif .[0].metadata["gc.input_convoy_id"] != $convoy
        then "other"
        elif .[0].metadata["gc.var.base_branch"] != $base
        then error("target root base authority mismatch")
        elif $mode == "live" and
             (.[0].status != "in_progress" or
              ((.[0].metadata | has("gc.outcome")) and
               .[0].metadata["gc.outcome"] != ""))
        then error("target workflow root is not active")
        elif $mode == "recovery" and
             (((.[0].status == "in_progress" and
                (((.[0].metadata | has("gc.outcome")) | not) or
                 .[0].metadata["gc.outcome"] == "")) or
               (.[0].status == "closed" and
                .[0].metadata["gc.outcome"] == "fail")) | not)
        then error("target workflow root has incoherent recovery state")
        elif $mode != "live" and $mode != "recovery"
        then error("unsupported workflow root classification mode")
        else "match"
        end' 2>/dev/null) || return 2
    case "$classification" in
        match) return 0 ;;
        other) return 1 ;;
        *) return 2 ;;
    esac
}

for runtime_identity in \
    "${BEADS_ACTOR:-}" \
    "${GC_SESSION_NAME:-}" \
    "${GC_SESSION_ID:-}" \
    "${GC_ALIAS:-}" \
    "${GC_AGENT:-}"; do
    add_runtime_identity "$runtime_identity" ||
        indeterminate "a configured runtime identity is unsafe"
done
((${#RUNTIME_IDENTITIES[@]} > 0)) ||
    indeterminate "no safe runtime identity is available"
CURRENT_SESSION_ID=${GC_SESSION_ID:-}
if [[ "$ACTION" == "submit" ]]; then
    [[ -n "$CURRENT_SESSION_ID" ]] && safe_atom "$CURRENT_SESSION_ID" ||
        indeterminate "submit proof requires an exact nonempty GC_SESSION_ID"
fi

derive_graph_context() {
    local step_list step_matches step_json root_json
    local step_code root_code candidate_id candidate_root
    local candidate_assignee existing identity root_class root_mode
    local -a live_step_ids=()
    local -a closed_step_ids=()
    local candidate_count=0

    for identity in "${RUNTIME_IDENTITIES[@]}"; do
        step_list=$(run_gc_bd list --assignee "$identity" --status=in_progress \
            --limit=0 --json 2>/dev/null)
        step_code=$?
        [[ "$step_code" -eq 0 ]] || return 1
        step_matches=$(printf '%s' "$step_list" |
            jq -ce --arg ref "$EXPECTED_STEP_REF" \
                --arg actor "$identity" '
            if type == "array" and
               all(.[]; type == "object" and
                        .status == "in_progress" and .assignee == $actor)
            then [.[] |
              select(.metadata["gc.step_ref"] == $ref) |
              if (.id | type) == "string" and (.id | length) > 0
              then .
              else error("matching live step has no string id")
              end]
            else error("live step list is not an object array")
            end' 2>/dev/null) || return 1
        while IFS= read -r candidate_id; do
            [[ -n "$candidate_id" ]] || continue
            safe_atom "$candidate_id" || return 1
            for existing in "${live_step_ids[@]}"; do
                [[ "$existing" != "$candidate_id" ]] || return 1
            done
            live_step_ids+=("$candidate_id")
        done < <(printf '%s' "$step_matches" | jq -r '.[].id')
    done

    if ((${#live_step_ids[@]} == 1)); then
        STEP_BEAD_ID=${live_step_ids[0]}
        step_json=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null)
        [[ $? -eq 0 ]] || return 1
        STEP_ASSIGNEE=$(printf '%s' "$step_json" | jq -er \
            --arg id "$STEP_BEAD_ID" --arg ref "$EXPECTED_STEP_REF" '
            if type == "array" and length == 1 and
               .[0].id == $id and .[0].status == "in_progress" and
               (.[0].assignee | type) == "string" and
               (.[0].assignee | length) > 0 and
               .[0].metadata["gc.step_ref"] == $ref and
               (((.[0].metadata | has("gc.outcome")) | not) or
                .[0].metadata["gc.outcome"] == "")
            then .[0].assignee
            else error("step identity/provenance mismatch")
            end' 2>/dev/null) || return 1
        identity_is_runtime "$STEP_ASSIGNEE" || return 1
        ROOT_BEAD_ID=$(printf '%s' "$step_json" | jq -er \
            --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
            --arg ref "$EXPECTED_STEP_REF" '
            if type == "array" and length == 1 and
               .[0].id == $id and .[0].status == "in_progress" and
               .[0].assignee == $actor and
               .[0].metadata["gc.step_ref"] == $ref and
               (((.[0].metadata | has("gc.outcome")) | not) or
                .[0].metadata["gc.outcome"] == "") and
               (.[0].metadata["gc.root_bead_id"] | type) == "string" and
               (.[0].metadata["gc.root_bead_id"] | length) > 0
            then .[0].metadata["gc.root_bead_id"]
            else error("step provenance mismatch")
            end' 2>/dev/null) || return 1
    elif ((${#live_step_ids[@]} == 0)); then
        # A prior hard-conflict attempt may have durably closed the exact step
        # and then crashed before drain-ack.  Recover only a closed hard-failure
        # candidate whose workflow root binds this input convoy.
        for identity in "${RUNTIME_IDENTITIES[@]}"; do
            step_list=$(run_gc_bd list --assignee "$identity" --status=closed \
                --limit=0 --json 2>/dev/null)
            step_code=$?
            [[ "$step_code" -eq 0 ]] || return 1
            step_matches=$(printf '%s' "$step_list" |
                jq -ce --arg ref "$EXPECTED_STEP_REF" \
                    --arg actor "$identity" '
                if type == "array" and
                   all(.[]; type == "object" and
                            .status == "closed" and .assignee == $actor)
                then [.[] |
                  select(.metadata["gc.step_ref"] == $ref and
                         .metadata["gc.outcome"] == "fail" and
                         .metadata["gc.failure_class"] == "hard" and
                         .metadata["gc.failure_reason"] == "push_lease_conflict") |
                  if (.id | type) == "string" and (.id | length) > 0
                  then .
                  else error("matching closed step has no string id")
                  end]
                else error("closed step list is not an object array")
                end' 2>/dev/null) || return 1
            while IFS= read -r candidate_id; do
                [[ -n "$candidate_id" ]] || continue
                safe_atom "$candidate_id" || return 1
                for existing in "${closed_step_ids[@]}"; do
                    [[ "$existing" != "$candidate_id" ]] || return 1
                done
                closed_step_ids+=("$candidate_id")
            done < <(printf '%s' "$step_matches" | jq -r '.[].id')
        done

        for candidate_id in "${closed_step_ids[@]}"; do
            step_json=$(run_gc_bd show "$candidate_id" --json 2>/dev/null) ||
                return 1
            candidate_assignee=$(printf '%s' "$step_json" | jq -er \
                --arg id "$candidate_id" --arg ref "$EXPECTED_STEP_REF" '
                if type == "array" and length == 1 and .[0].id == $id and
                   .[0].status == "closed" and
                   (.[0].assignee | type) == "string" and
                   (.[0].assignee | length) > 0 and
                   .[0].metadata["gc.step_ref"] == $ref and
                   (.[0].metadata["gc.root_bead_id"] | type) == "string" and
                   (.[0].metadata["gc.root_bead_id"] | length) > 0 and
                   .[0].metadata["gc.outcome"] == "fail" and
                   .[0].metadata["gc.failure_class"] == "hard" and
                   .[0].metadata["gc.failure_reason"] == "push_lease_conflict"
                then .[0].assignee
                else error("closed step provenance mismatch")
                end' 2>/dev/null) || return 1
            identity_is_runtime "$candidate_assignee" || return 1
            candidate_root=$(printf '%s' "$step_json" |
                jq -er '.[0].metadata["gc.root_bead_id"]' 2>/dev/null) ||
                return 1
            safe_atom "$candidate_id" && safe_atom "$candidate_root" || return 1
            root_json=$(run_gc_bd show "$candidate_root" --json 2>/dev/null) ||
                return 1
            classify_workflow_root "$root_json" "$candidate_root" recovery
            root_class=$?
            case "$root_class" in
                0)
                    candidate_count=$((candidate_count + 1))
                    STEP_BEAD_ID=$candidate_id
                    ROOT_BEAD_ID=$candidate_root
                    STEP_ASSIGNEE=$candidate_assignee
                    ;;
                1)
                    # Canonical history for another convoy is irrelevant.
                    ;;
                *)
                    # Malformed or unreadable provenance cannot be ignored.
                    return 1
                    ;;
            esac
        done
        [[ "$candidate_count" -eq 1 ]] || return 1
        step_json=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
            return 1
        printf '%s' "$step_json" | jq -e \
            --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
            --arg ref "$EXPECTED_STEP_REF" --arg root "$ROOT_BEAD_ID" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == "closed" and .[0].assignee == $actor and
            .[0].metadata["gc.step_ref"] == $ref and
            .[0].metadata["gc.root_bead_id"] == $root and
            .[0].metadata["gc.outcome"] == "fail" and
            .[0].metadata["gc.failure_class"] == "hard" and
            .[0].metadata["gc.failure_reason"] == "push_lease_conflict"' \
            >/dev/null 2>&1 || return 1
        TERMINAL_RECOVERY=1
    else
        return 1
    fi

    root_json=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null)
    root_code=$?
    [[ "$root_code" -eq 0 ]] || return 1
    root_mode=live
    [[ "$TERMINAL_RECOVERY" -eq 0 ]] || root_mode=recovery
    classify_workflow_root "$root_json" "$ROOT_BEAD_ID" "$root_mode" ||
        return 1
    printf '%s' "$root_json" | jq -e '
        type == "array" and length == 1 and
        ((.[0].metadata["gc.var.rig_name"] // "") | type) == "string" and
        ((.[0].metadata["gc.var.binding_prefix"] // "") | type) == "string"' \
        >/dev/null 2>&1 || return 1
    ROOT_RIG_NAME=$(printf '%s' "$root_json" |
        jq -er '.[0].metadata["gc.var.rig_name"] // ""' 2>/dev/null) ||
        return 1
    ROOT_BINDING_PREFIX=$(printf '%s' "$root_json" |
        jq -er '.[0].metadata["gc.var.binding_prefix"] // ""' 2>/dev/null) ||
        return 1
    safe_atom "${ROOT_RIG_NAME:-hq}" &&
        safe_atom "${ROOT_BINDING_PREFIX:-unbound}" || return 1
    WITNESS_CANONICAL="${ROOT_RIG_NAME:+$ROOT_RIG_NAME/}${ROOT_BINDING_PREFIX}witness"
    [[ "$WITNESS_TARGET" == "$WITNESS_CANONICAL" ]] || return 1
    WITNESS_TARGET=$WITNESS_CANONICAL

    prove_authoritative_convoy_source || return 1
    safe_atom "$ROOT_BEAD_ID" || return 1
    PROVENANCE_READY=1
    return 0
}

derive_graph_context ||
    indeterminate "could not prove the exact claimed Graph-v2 step/root/source"

SOURCE_JSON=""
SOURCE_STATUS=""
SOURCE_ASSIGNEE=""
SOURCE_BRANCH=""
SOURCE_REJECTED=""
SOURCE_AUTO_PUSH=""
SOURCE_ARTIFACT_DIR=""

load_source() {
    SOURCE_JSON=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null)
    [[ $? -eq 0 ]] || return 1
    printf '%s' "$SOURCE_JSON" | jq -e --arg id "$SOURCE_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        (.[0].status | type) == "string" and
        ((.[0].assignee // "") | type) == "string" and
        ((.[0].metadata // {}) | type) == "object" and
        ((.[0].metadata.branch // "") | type) == "string" and
        ((.[0].metadata.rejection_reason // "") | type) == "string" and
        ((.[0].metadata.artifact_dir // "") | type) == "string" and
        (((.[0].metadata | has("auto_push")) | not) or
         (.[0].metadata.auto_push | type) == "boolean")' \
        >/dev/null 2>&1 || return 1
    SOURCE_STATUS=$(printf '%s' "$SOURCE_JSON" | jq -er '.[0].status') ||
        return 1
    SOURCE_ASSIGNEE=$(printf '%s' "$SOURCE_JSON" | jq -er '.[0].assignee // ""') ||
        return 1
    SOURCE_BRANCH=$(printf '%s' "$SOURCE_JSON" | jq -er '.[0].metadata.branch // ""') ||
        return 1
    SOURCE_REJECTED=$(printf '%s' "$SOURCE_JSON" | jq -er '
        ((.[0].metadata.rejection_reason // "") != "") | tostring') ||
        return 1
    SOURCE_AUTO_PUSH=$(printf '%s' "$SOURCE_JSON" | jq -er '
        if .[0].metadata | has("auto_push")
        then (.[0].metadata.auto_push | tostring)
        else ""
        end') || return 1
    SOURCE_ARTIFACT_DIR=$(printf '%s' "$SOURCE_JSON" | jq -er '
        .[0].metadata.artifact_dir // ""') ||
        return 1
    return 0
}

load_source || indeterminate "could not read the exact source bead"

WORKTREE_TOP=""
WORKTREE_FINGERPRINT=""
REPO_COMMON_FINGERPRINT=""

artifact_git_common_dir() {
    local repo_dir=$1 common_dir
    common_dir=$(git -C "$repo_dir" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) || return 1
    (CDPATH= cd -- "$common_dir" 2>/dev/null && pwd -P)
}

safe_path_atom() {
    local value=$1
    case "$value" in
        ""|"."|".."|*[!A-Za-z0-9._-]*) return 1 ;;
    esac
}

validate_worktree_binding() {
    local current_top recorded_top recorded_git_top
    local city_root rig_root recorded_common rig_common
    local rig_namespace rig_namespace_real canonical_path
    local worktrees_parent provider_home provider_root provider_name

    [[ -n "$SOURCE_ARTIFACT_DIR" ]] ||
        indeterminate "source metadata has no recorded artifact_dir"
    [[ -n "${GC_CITY_PATH:-}" && -n "${GC_RIG:-}" &&
       -n "${GC_RIG_ROOT:-}" ]] ||
        indeterminate "GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required"
    safe_path_atom "$SOURCE_ID" ||
        indeterminate "source id is unsafe for an artifact path"
    safe_path_atom "$GC_RIG" ||
        indeterminate "rig name is unsafe for an artifact path"
    city_root=$(CDPATH= cd -- "$GC_CITY_PATH" 2>/dev/null && pwd -P) ||
        indeterminate "could not canonicalize the city root"
    rig_root=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) ||
        indeterminate "could not canonicalize the rig root"
    rig_namespace="$city_root/.gc/worktrees/$GC_RIG"
    rig_namespace_real=$(CDPATH= cd -- "$rig_namespace" 2>/dev/null && pwd -P) ||
        indeterminate "could not resolve the city/rig worktree namespace"
    [[ "$rig_namespace_real" == "$rig_namespace" ]] ||
        indeterminate "city/rig worktree namespace is redirected"

    recorded_top=$(CDPATH= cd -- "$SOURCE_ARTIFACT_DIR" 2>/dev/null && pwd -P) ||
        indeterminate "recorded source artifact_dir is unavailable"
    [[ "$(basename -- "$recorded_top")" == "$SOURCE_ID" &&
       "$(basename -- "$(dirname -- "$recorded_top")")" == "worktrees" ]] ||
        indeterminate "source metadata.artifact_dir is not bead-scoped"

    canonical_path="$rig_namespace_real/artifacts/worktrees/$SOURCE_ID"
    if [[ "$recorded_top" != "$canonical_path" ]]; then
        worktrees_parent=$(dirname -- "$recorded_top")
        provider_home=$(dirname -- "$worktrees_parent")
        provider_root=$(dirname -- "$provider_home")
        provider_name=$(basename -- "$provider_home")
        [[ "$provider_root" == "$rig_namespace_real/polecats" ]] ||
            indeterminate "source metadata.artifact_dir is outside the rig artifact layouts"
        safe_path_atom "$provider_name" ||
            indeterminate "source metadata.artifact_dir has an unsafe provider owner"
    fi

    recorded_git_top=$(git -C "$recorded_top" rev-parse \
        --show-toplevel 2>/dev/null) ||
        indeterminate "source metadata.artifact_dir is not a Git worktree"
    recorded_git_top=$(CDPATH= cd -- "$recorded_git_top" 2>/dev/null && pwd -P) ||
        indeterminate "could not canonicalize the recorded artifact Git top"
    [[ "$recorded_git_top" == "$recorded_top" ]] ||
        indeterminate "source metadata.artifact_dir is a worktree subdirectory"
    recorded_common=$(artifact_git_common_dir "$recorded_top") ||
        indeterminate "could not resolve the artifact Git common directory"
    rig_common=$(artifact_git_common_dir "$rig_root") ||
        indeterminate "could not resolve the rig Git common directory"
    [[ "$recorded_common" == "$rig_common" ]] ||
        indeterminate "source metadata.artifact_dir belongs to another repository"

    current_top=$(git rev-parse --show-toplevel 2>/dev/null) ||
        indeterminate "could not resolve the current worktree top"
    current_top=$(CDPATH= cd -- "$current_top" 2>/dev/null && pwd -P) ||
        indeterminate "could not canonicalize the current worktree top"
    [[ "$current_top" == "$recorded_top" ]] ||
        indeterminate "current Git worktree does not equal source metadata.artifact_dir"
    WORKTREE_TOP=$current_top
    WORKTREE_FINGERPRINT=$(printf 'worktree-v1\0%s' "$WORKTREE_TOP" |
        git hash-object --stdin 2>/dev/null) ||
        indeterminate "could not fingerprint the bound worktree"
    is_oid "$WORKTREE_FINGERPRINT" ||
        indeterminate "invalid worktree fingerprint"
    REPO_COMMON_FINGERPRINT=$(printf 'git-common-v1\0%s' "$rig_common" |
        git hash-object --stdin 2>/dev/null) ||
        indeterminate "could not fingerprint the repository common directory"
    is_oid "$REPO_COMMON_FINGERPRINT" ||
        indeterminate "invalid repository common-directory fingerprint"
}

validate_worktree_binding

enforce_auto_push_policy() {
    [[ "$ACTION" == "submit" ]] || return 0
    case "$AUTO_PUSH:$SOURCE_AUTO_PUSH" in
        true:|true:true|false:false) return 0 ;;
        true:false)
            indeterminate "source metadata.auto_push=false prohibits an automatic push"
            ;;
        false:|false:true)
            indeterminate "auto_push=false requires exact boolean source metadata.auto_push=false"
            ;;
        *)
            indeterminate "source metadata.auto_push has an unsupported value"
            ;;
    esac
}

enforce_auto_push_policy

FETCH_URL=""
PUSH_URL=""
FETCH_FINGERPRINT=""
PUSH_FINGERPRINT=""

single_remote_url() {
    local mode=$1
    local output line count=0 selected=""
    if [[ "$mode" == "push" ]]; then
        output=$(git remote get-url --push --all origin 2>/dev/null) || return 1
    else
        output=$(git remote get-url --all origin 2>/dev/null) || return 1
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

FETCH_URL=$(single_remote_url fetch) ||
    indeterminate "origin must have exactly one fetch URL"
PUSH_URL=$(single_remote_url push) ||
    indeterminate "origin must have exactly one effective push URL"
FETCH_FINGERPRINT=$(printf 'fetch-url-v1\0%s' "$FETCH_URL" |
    git hash-object --stdin 2>/dev/null) ||
    indeterminate "could not fingerprint origin fetch URL"
PUSH_FINGERPRINT=$(printf 'push-url-v1\0%s' "$PUSH_URL" |
    git hash-object --stdin 2>/dev/null) ||
    indeterminate "could not fingerprint origin push URL"
is_oid "$FETCH_FINGERPRINT" && is_oid "$PUSH_FINGERPRINT" ||
    indeterminate "invalid origin URL fingerprint"

emit_context() {
    printf '%s\n' \
        "version=1" \
        "source=$SOURCE_ID" \
        "workflow_root=$ROOT_BEAD_ID" \
        "input_convoy=$CONVOY_ID" \
        "branch=$BRANCH" \
        "target=$BASE_BRANCH" \
        "witness=$WITNESS_CANONICAL" \
        "worktree_fingerprint=$WORKTREE_FINGERPRINT" \
        "origin_fetch_fingerprint=$FETCH_FINGERPRINT" \
        "origin_push_fingerprint=$PUSH_FINGERPRINT"
}

CONTEXT_EXPECTED=$(emit_context | git hash-object --stdin 2>/dev/null) ||
    indeterminate "could not hash lease context"
is_oid "$CONTEXT_EXPECTED" || indeterminate "invalid context object id"

emit_submit_proof_key() {
    printf '%s\n' \
        "schema=gascity-polecat-submit-proof-key-v1" \
        "source=$SOURCE_ID" \
        "workflow_root=$ROOT_BEAD_ID" \
        "step=$STEP_BEAD_ID" \
        "input_convoy=$CONVOY_ID" \
        "session_id=$CURRENT_SESSION_ID"
}

SUBMIT_PROOF_VERSION="1"
SUBMIT_PROOF_KEY=$(emit_submit_proof_key | git hash-object --stdin 2>/dev/null) ||
    indeterminate "could not derive the submit-proof key"
is_oid "$SUBMIT_PROOF_KEY" ||
    indeterminate "Git returned an invalid submit-proof key"
SUBMIT_PROOF_NS="refs/gascity/polecat-submit-proofs/v1/$SUBMIT_PROOF_KEY"
SUBMIT_PROOF_CONTEXT_REF="$SUBMIT_PROOF_NS/context"
SUBMIT_PROOF_HEAD_REF="$SUBMIT_PROOF_NS/head"
for ref in "$SUBMIT_PROOF_CONTEXT_REF" "$SUBMIT_PROOF_HEAD_REF"; do
    git check-ref-format "$ref" >/dev/null 2>&1 ||
        indeterminate "Git rejected an internal submit-proof ref"
done

CONTEXT_OID=""
EXPECTED_OID=""
PRE_OID=""
BASE_OID=""
REBASED_OID=""
SUBMIT_OID=""
NS_COUNT=0
NS_STATE="absent"

read_ref() {
    local ref=$1 code oid
    oid=$(git rev-parse --verify --quiet "$ref" 2>/dev/null)
    code=$?
    case "$code" in
        0)
            is_oid "$oid" || return 1
            printf '%s' "$oid"
            ;;
        1)
            printf ''
            ;;
        *)
            return 1
            ;;
    esac
}

ref_equals() {
    local ref=$1 expected=$2 observed
    observed=$(read_ref "$ref") ||
        indeterminate "could not read local ref $ref"
    [[ "$observed" == "$expected" ]]
}

read_namespace_once() {
    CONTEXT_OID=$(read_ref "$CONTEXT_REF") ||
        indeterminate "could not read lease context ref"
    EXPECTED_OID=$(read_ref "$EXPECTED_REF") ||
        indeterminate "could not read lease expected ref"
    PRE_OID=$(read_ref "$PRE_REF") ||
        indeterminate "could not read lease pre-rebase ref"
    BASE_OID=$(read_ref "$BASE_REF") ||
        indeterminate "could not read lease base ref"
    REBASED_OID=$(read_ref "$REBASED_REF") ||
        indeterminate "could not read lease rebased ref"
    SUBMIT_OID=$(read_ref "$SUBMIT_REF") ||
        indeterminate "could not read lease submit ref"
    NS_COUNT=0
    for oid in "$CONTEXT_OID" "$EXPECTED_OID" "$PRE_OID" "$BASE_OID" \
               "$REBASED_OID" "$SUBMIT_OID"; do
        [[ -z "$oid" ]] || NS_COUNT=$((NS_COUNT + 1))
    done
    case "$NS_COUNT" in
        0) NS_STATE="absent"; return 0 ;;
        4)
            if [[ -n "$CONTEXT_OID" && -n "$EXPECTED_OID" &&
                  -n "$PRE_OID" && -n "$BASE_OID" &&
                  -z "$REBASED_OID" && -z "$SUBMIT_OID" ]]; then
                NS_STATE="captured"
                return 0
            fi
            ;;
        5)
            if [[ -n "$CONTEXT_OID" && -n "$EXPECTED_OID" &&
                  -n "$PRE_OID" && -n "$BASE_OID" &&
                  -n "$REBASED_OID" && -z "$SUBMIT_OID" ]]; then
                NS_STATE="rebased"
                return 0
            fi
            ;;
        6)
            NS_STATE="submit-frozen"
            return 0
            ;;
    esac
    NS_STATE="partial"
    return 1
}

load_namespace() {
    local attempt
    for attempt in 1 2 3; do
        if read_namespace_once; then
            return 0
        fi
        sleep 1
    done
    return 1
}

validate_commit_ref() {
    local ref=$1 oid=$2 kind observed
    is_oid "$oid" || return 1
    ! git symbolic-ref -q "$ref" >/dev/null 2>&1 || return 1
    kind=$(git cat-file -t "$oid" 2>/dev/null) || return 1
    [[ "$kind" == "commit" ]] || return 1
    observed=$(read_ref "$ref") ||
        indeterminate "could not re-read authoritative lease ref $ref"
    [[ "$observed" == "$oid" ]]
}

validate_namespace() {
    [[ "$NS_STATE" != "partial" ]] || return 1
    [[ "$NS_STATE" != "absent" ]] || return 0
    ! git symbolic-ref -q "$CONTEXT_REF" >/dev/null 2>&1 || return 1
    [[ "$CONTEXT_OID" == "$CONTEXT_EXPECTED" ]] || return 1
    [[ "$(git cat-file -t "$CONTEXT_OID" 2>/dev/null)" == "blob" ]] || return 1
    [[ "$(git cat-file blob "$CONTEXT_OID" 2>/dev/null)" == "$(emit_context)" ]] ||
        return 1
    validate_commit_ref "$EXPECTED_REF" "$EXPECTED_OID" || return 1
    validate_commit_ref "$PRE_REF" "$PRE_OID" || return 1
    validate_commit_ref "$BASE_REF" "$BASE_OID" || return 1
    if [[ "$NS_STATE" == "rebased" || "$NS_STATE" == "submit-frozen" ]]; then
        validate_commit_ref "$REBASED_REF" "$REBASED_OID" || return 1
    fi
    if [[ "$NS_STATE" == "submit-frozen" ]]; then
        validate_commit_ref "$SUBMIT_REF" "$SUBMIT_OID" || return 1
    fi
    return 0
}

M_NS=""
M_CONTEXT=""
M_EXPECTED=""
M_PRE=""
M_BASE=""
M_REBASED=""
M_SUBMIT=""
M_BRANCH=""
M_ROOT=""
M_STATE=""
M_MANUAL=""
MIRROR_COUNT=0

load_mirror() {
    load_source || return 1
    local row
    row=$(printf '%s' "$SOURCE_JSON" | jq -er '
        .[0].metadata as $m |
        [
          ($m.polecat_push_lease_ref // ""),
          ($m.polecat_push_lease_context_oid // ""),
          ($m.polecat_push_lease_expected_sha // ""),
          ($m.polecat_push_lease_pre_sha // ""),
          ($m.polecat_push_lease_base_sha // ""),
          ($m.polecat_push_lease_rebased_sha // ""),
          ($m.polecat_push_lease_submit_sha // ""),
          ($m.polecat_push_lease_branch // ""),
          ($m.polecat_push_lease_root // ""),
          ($m.polecat_push_lease_state // ""),
          (if $m | has("polecat_push_lease_manual_pending")
           then ($m.polecat_push_lease_manual_pending |
                 if type == "boolean" then tostring
                 elif type == "string" then .
                 else error("lease mirror manual-pending flag is not boolean/string")
                 end)
           else ""
           end)
        ] | map(if type == "string" then . else error("lease mirror is not string") end)
          | join("\u001f")' 2>/dev/null) || return 1
    IFS=$'\x1f' read -r M_NS M_CONTEXT M_EXPECTED M_PRE M_BASE M_REBASED \
        M_SUBMIT M_BRANCH M_ROOT M_STATE M_MANUAL <<<"$row"
    MIRROR_COUNT=0
    for value in "$M_NS" "$M_CONTEXT" "$M_EXPECTED" "$M_PRE" "$M_BASE" \
                 "$M_REBASED" "$M_SUBMIT" "$M_BRANCH" "$M_ROOT" "$M_STATE" \
                 "$M_MANUAL"; do
        [[ -z "$value" ]] || MIRROR_COUNT=$((MIRROR_COUNT + 1))
    done
    return 0
}

mirror_state_for_refs() {
    case "$NS_STATE" in
        captured) printf 'captured' ;;
        rebased) printf 'rebased' ;;
        submit-frozen)
            if [[ "$M_MANUAL" == "true" ]]; then
                printf 'manual-pending'
            else
                printf 'submit-frozen'
            fi
            ;;
        *) printf '' ;;
    esac
}

mirror_matches_refs() {
    local expected_state expected_manual="false"
    expected_state=$(mirror_state_for_refs)
    [[ "$expected_state" != "manual-pending" ]] || expected_manual="true"
    [[ "$M_NS" == "$LEASE_NS" &&
       "$M_CONTEXT" == "$CONTEXT_OID" &&
       "$M_EXPECTED" == "$EXPECTED_OID" &&
       "$M_PRE" == "$PRE_OID" &&
       "$M_BASE" == "$BASE_OID" &&
       "$M_REBASED" == "$REBASED_OID" &&
       "$M_SUBMIT" == "$SUBMIT_OID" &&
       "$M_BRANCH" == "$BRANCH" &&
       "$M_ROOT" == "$ROOT_BEAD_ID" &&
       "$M_STATE" == "$expected_state" &&
       "$M_MANUAL" == "$expected_manual" ]]
}

mirror_is_known_prior_phase() {
    [[ "$M_NS" == "$LEASE_NS" &&
       "$M_CONTEXT" == "$CONTEXT_OID" &&
       "$M_EXPECTED" == "$EXPECTED_OID" &&
       "$M_PRE" == "$PRE_OID" &&
       "$M_BASE" == "$BASE_OID" &&
       "$M_BRANCH" == "$BRANCH" &&
       "$M_ROOT" == "$ROOT_BEAD_ID" ]] || return 1
    case "$NS_STATE" in
        rebased)
            [[ -z "$M_REBASED" && -z "$M_SUBMIT" &&
               "$M_STATE" == "captured" && "$M_MANUAL" == "false" ]]
            ;;
        submit-frozen)
            if [[ "$M_REBASED" == "$REBASED_OID" && -z "$M_SUBMIT" &&
                  "$M_STATE" == "rebased" && "$M_MANUAL" == "false" ]]; then
                return 0
            fi
            return 1
            ;;
        *)
            return 1
            ;;
    esac
}

sync_mirror() {
    local state manual="false"
    prove_live_source_step
    state=$(mirror_state_for_refs)
    [[ "$state" != "manual-pending" ]] || manual="true"
    local args=(
        update "$SOURCE_ID"
        --set-metadata "polecat_push_lease_ref=$LEASE_NS"
        --set-metadata "polecat_push_lease_context_oid=$CONTEXT_OID"
        --set-metadata "polecat_push_lease_expected_sha=$EXPECTED_OID"
        --set-metadata "polecat_push_lease_pre_sha=$PRE_OID"
        --set-metadata "polecat_push_lease_base_sha=$BASE_OID"
        --set-metadata "polecat_push_lease_branch=$BRANCH"
        --set-metadata "polecat_push_lease_root=$ROOT_BEAD_ID"
        --set-metadata "polecat_push_lease_state=$state"
        --set-metadata "polecat_push_lease_manual_pending=$manual"
    )
    if [[ -n "$REBASED_OID" ]]; then
        args+=(--set-metadata "polecat_push_lease_rebased_sha=$REBASED_OID")
    else
        args+=(--unset-metadata polecat_push_lease_rebased_sha)
    fi
    if [[ -n "$SUBMIT_OID" ]]; then
        args+=(--set-metadata "polecat_push_lease_submit_sha=$SUBMIT_OID")
    else
        args+=(--unset-metadata polecat_push_lease_submit_sha)
    fi
    run_gc_bd "${args[@]}" >/dev/null 2>&1 || return 1
    load_mirror || return 1
    mirror_matches_refs
}

clear_mirror() {
    prove_live_source_step
    local keys=(
        polecat_push_lease_ref
        polecat_push_lease_context_oid
        polecat_push_lease_expected_sha
        polecat_push_lease_pre_sha
        polecat_push_lease_base_sha
        polecat_push_lease_rebased_sha
        polecat_push_lease_submit_sha
        polecat_push_lease_branch
        polecat_push_lease_root
        polecat_push_lease_state
        polecat_push_lease_manual_pending
    )
    local args=(update "$SOURCE_ID")
    local key
    for key in "${keys[@]}"; do
        args+=(--unset-metadata "$key")
    done
    run_gc_bd "${args[@]}" >/dev/null 2>&1 || return 1
    load_mirror || return 1
    [[ "$MIRROR_COUNT" -eq 0 ]]
}

OBSERVED_REMOTE=""
LOCAL_HEAD=""

revalidate_terminal_authority() {
    local step_json root_json root_mode=live

    step_json=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        return 1
    if [[ "$TERMINAL_RECOVERY" -eq 1 ]]; then
        printf '%s' "$step_json" | jq -e \
            --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
            --arg ref "$EXPECTED_STEP_REF" --arg root "$ROOT_BEAD_ID" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == "closed" and .[0].assignee == $actor and
            .[0].metadata["gc.step_ref"] == $ref and
            .[0].metadata["gc.root_bead_id"] == $root and
            .[0].metadata["gc.outcome"] == "fail" and
            .[0].metadata["gc.failure_class"] == "hard" and
            .[0].metadata["gc.failure_reason"] == "push_lease_conflict"' \
            >/dev/null 2>&1 || return 1
        root_mode=recovery
    else
        printf '%s' "$step_json" | jq -e \
            --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
            --arg ref "$EXPECTED_STEP_REF" --arg root "$ROOT_BEAD_ID" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].status == "in_progress" and .[0].assignee == $actor and
            .[0].metadata["gc.step_ref"] == $ref and
            .[0].metadata["gc.root_bead_id"] == $root and
            (((.[0].metadata | has("gc.outcome")) | not) or
             .[0].metadata["gc.outcome"] == "")' \
            >/dev/null 2>&1 || return 1
    fi

    root_json=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null) ||
        return 1
    classify_workflow_root "$root_json" "$ROOT_BEAD_ID" "$root_mode" ||
        return 1
    printf '%s' "$root_json" | jq -e \
        --arg id "$ROOT_BEAD_ID" --arg rig "$ROOT_RIG_NAME" \
        --arg prefix "$ROOT_BINDING_PREFIX" '
        type == "array" and length == 1 and .[0].id == $id and
        (.[0].metadata["gc.var.rig_name"] // "") == $rig and
        (.[0].metadata["gc.var.binding_prefix"] // "") == $prefix' \
        >/dev/null 2>&1 || return 1
    prove_authoritative_convoy_source
}

terminalize_hard() {
    local reason=$1 source_json step_json verify_json detail
    local status assignee route halt step_status step_outcome step_class

    detail=$(printf '%s\n' \
        "Deterministic polecat push-lease conflict: $reason" \
        "source=$SOURCE_ID workflow_root=$ROOT_BEAD_ID branch=$BRANCH" \
        "lease_ref=$LEASE_NS" \
        "expected=${EXPECTED_OID:-<none>}" \
        "observed=${OBSERVED_REMOTE:-<missing>}" \
        "rebased=${REBASED_OID:-<none>}" \
        "submit=${SUBMIT_OID:-<none>}" \
        "local=${LOCAL_HEAD:-<unknown>}")

    revalidate_terminal_authority || {
        echo "polecat-lease: Graph authority changed before hard terminalization" >&2
        return 1
    }
    source_json=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) || return 1
    status=$(printf '%s' "$source_json" | jq -er '.[0].status' 2>/dev/null) ||
        return 1
    assignee=$(printf '%s' "$source_json" | jq -er '.[0].assignee // ""' 2>/dev/null) ||
        return 1
    if [[ "$status" == "open" && -z "$assignee" ]]; then
        run_gc_bd update "$SOURCE_ID" \
            --status=blocked --assignee "" \
            --set-metadata gc.routed_to=human \
            --set-metadata polecat_halt_reason=push_lease_conflict \
            --set-metadata "polecat_push_lease_ref=$LEASE_NS" \
            --set-metadata "polecat_push_expected_sha=${EXPECTED_OID:-}" \
            --set-metadata "polecat_push_observed_sha=${OBSERVED_REMOTE:-missing}" \
            --set-metadata "polecat_push_local_sha=${LOCAL_HEAD:-}" \
            --append-notes "$detail" >/dev/null 2>&1 || return 1
    elif [[ "$status" != "blocked" || -n "$assignee" ]]; then
        echo "polecat-lease: source state changed; refusing to overwrite it" >&2
        return 1
    fi

    verify_json=$(run_gc_bd show "$SOURCE_ID" --json 2>/dev/null) || return 1
    status=$(printf '%s' "$verify_json" | jq -er '.[0].status' 2>/dev/null) ||
        return 1
    assignee=$(printf '%s' "$verify_json" | jq -er '.[0].assignee // ""' 2>/dev/null) ||
        return 1
    route=$(printf '%s' "$verify_json" | jq -er '.[0].metadata["gc.routed_to"] // ""' 2>/dev/null) ||
        return 1
    halt=$(printf '%s' "$verify_json" | jq -er '.[0].metadata.polecat_halt_reason // ""' 2>/dev/null) ||
        return 1
    [[ "$status" == "blocked" && -z "$assignee" &&
       "$route" == "human" && "$halt" == "push_lease_conflict" ]] || return 1

    run_gc mail send "$WITNESS_TARGET" \
        -s "HARD: polecat push lease conflict for $SOURCE_ID" \
        -m "$detail" --notify >/dev/null 2>&1 || return 1

    step_json=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) || return 1
    step_status=$(printf '%s' "$step_json" | jq -er '.[0].status' 2>/dev/null) ||
        return 1
    if [[ "$step_status" == "in_progress" ]]; then
        printf '%s' "$step_json" | jq -e \
            --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
            --arg ref "$EXPECTED_STEP_REF" --arg root "$ROOT_BEAD_ID" '
            type == "array" and length == 1 and .[0].id == $id and
            .[0].assignee == $actor and .[0].metadata["gc.step_ref"] == $ref and
            .[0].metadata["gc.root_bead_id"] == $root' \
            >/dev/null 2>&1 || return 1
        run_gc_bd update "$STEP_BEAD_ID" \
            --set-metadata gc.outcome=fail \
            --set-metadata gc.failure_class=hard \
            --set-metadata gc.failure_reason=push_lease_conflict \
            --status=closed --append-notes "$detail" >/dev/null 2>&1 || return 1
    fi
    verify_json=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) || return 1
    printf '%s' "$verify_json" | jq -e \
        --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
        --arg ref "$EXPECTED_STEP_REF" --arg root "$ROOT_BEAD_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "closed" and .[0].assignee == $actor and
        .[0].metadata["gc.step_ref"] == $ref and
        .[0].metadata["gc.root_bead_id"] == $root and
        .[0].metadata["gc.outcome"] == "fail" and
        .[0].metadata["gc.failure_class"] == "hard" and
        .[0].metadata["gc.failure_reason"] == "push_lease_conflict"' \
        >/dev/null 2>&1 || return 1
    return 0
}

hard_conflict() {
    local reason=$*
    echo "POLECAT_LEASE_HARD_CONFLICT: $reason" >&2
    if [[ "$PROVENANCE_READY" -eq 1 ]] && terminalize_hard "$reason"; then
        if ! run_gc runtime drain-ack >/dev/null 2>&1; then
            echo "polecat-lease: terminal state verified but drain-ack failed; retry required" >&2
            exit "$EXIT_INDETERMINATE"
        fi
    else
        echo "polecat-lease: terminal state did not verify; refusing to drain" >&2
    fi
    exit "$EXIT_HARD"
}

checked_ancestor() {
    local ancestor=$1 descendant=$2 label=$3 code
    git merge-base --is-ancestor "$ancestor" "$descendant" >/dev/null 2>&1
    code=$?
    case "$code" in
        0) return 0 ;;
        1) return 1 ;;
        *) indeterminate "Git could not evaluate ancestry for $label (exit $code)" ;;
    esac
}

require_ancestor() {
    local ancestor=$1 descendant=$2 conflict=$3
    checked_ancestor "$ancestor" "$descendant" "$conflict" ||
        hard_conflict "$conflict"
}

prove_live_source_step() {
    local step_json root_json
    load_source ||
        indeterminate "could not re-read source state before a protected transition"
    enforce_auto_push_policy
    validate_worktree_binding
    if [[ "$SOURCE_STATUS" != "open" || -n "$SOURCE_ASSIGNEE" ||
          "$SOURCE_BRANCH" != "$BRANCH" ]]; then
        indeterminate "source ownership/branch changed during the lease protocol"
    fi
    step_json=$(run_gc_bd show "$STEP_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not re-read the exact Graph step before a protected transition"
    printf '%s' "$step_json" | jq -e \
        --arg id "$STEP_BEAD_ID" --arg actor "$STEP_ASSIGNEE" \
        --arg ref "$EXPECTED_STEP_REF" --arg root "$ROOT_BEAD_ID" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == "in_progress" and .[0].assignee == $actor and
        .[0].metadata["gc.step_ref"] == $ref and
        .[0].metadata["gc.root_bead_id"] == $root and
        (((.[0].metadata | has("gc.outcome")) | not) or
         .[0].metadata["gc.outcome"] == "")' \
        >/dev/null 2>&1 ||
        indeterminate "exact Graph step ownership/state changed during the lease protocol"
    root_json=$(run_gc_bd show "$ROOT_BEAD_ID" --json 2>/dev/null) ||
        indeterminate "could not re-read the exact Graph root before a protected transition"
    classify_workflow_root "$root_json" "$ROOT_BEAD_ID" live ||
        indeterminate "exact Graph root state changed during the lease protocol"
    prove_authoritative_convoy_source ||
        indeterminate "convoy identity/source changed during the lease protocol"
    if git symbolic-ref -q "$BRANCH_REF" >/dev/null 2>&1; then
        hard_conflict "canonical branch became a symbolic ref"
    fi
}

for direct_ref in "$BRANCH_REF" "$TRACKING_REF" "$BASE_REMOTE_REF"; do
    if git symbolic-ref -q "$direct_ref" >/dev/null 2>&1; then
        hard_conflict "local branch/tracking authority is a symbolic ref: $direct_ref"
    fi
done
if [[ "$SOURCE_BRANCH" != "$BRANCH" ]]; then
    if [[ "$ACTION" == "workspace" && -z "$SOURCE_BRANCH" ]]; then
        indeterminate "source metadata.branch is absent; run gc gastown polecat-workspace execute"
    fi
    hard_conflict "source metadata.branch does not match the canonical branch"
fi
if [[ "$SOURCE_STATUS" == "blocked" ]]; then
    hard_conflict "source is already blocked by an unresolved lease conflict"
fi
if [[ "$SOURCE_STATUS" != "open" || -n "$SOURCE_ASSIGNEE" ]]; then
    hard_conflict "source is not open and unassigned"
fi

load_namespace || hard_conflict "partial lease namespace after bounded retry"
validate_namespace || hard_conflict "lease namespace/context is corrupt or belongs to another workflow"
load_mirror || indeterminate "could not read lease metadata mirror"

if [[ "$NS_STATE" != "absent" ]]; then
    if [[ "$MIRROR_COUNT" -eq 0 ]]; then
        sync_mirror || indeterminate "could not reconstruct and verify the lease mirror"
    elif ! mirror_matches_refs; then
        if mirror_is_known_prior_phase; then
            sync_mirror ||
                indeterminate "could not advance a stale lease metadata mirror"
        else
            hard_conflict "mutable lease metadata does not match authoritative Git refs"
        fi
    fi
elif [[ "$MIRROR_COUNT" -ne 0 ]]; then
    # The only valid refs-absent mirror is a crash after verified push and
    # atomic ref cleanup but before metadata cleanup.  It is classified below.
    if [[ "$M_CONTEXT" != "$CONTEXT_EXPECTED" || -z "$M_SUBMIT" ||
          "$M_BRANCH" != "$BRANCH" || "$M_ROOT" != "$ROOT_BEAD_ID" ]]; then
        hard_conflict "metadata-only lease state is incomplete or belongs elsewhere"
    fi
fi

REMOTE_STATE=""
REMOTE_OID=""

read_push_remote() {
    local output code oid ref extra
    output=$(git ls-remote --exit-code --refs -- "$PUSH_URL" "$BRANCH_REF" 2>/dev/null)
    code=$?
    case "$code" in
        0)
            [[ "$output" != *$'\n'* ]] || {
                REMOTE_STATE="malformed"
                REMOTE_OID=""
                return 0
            }
            read -r oid ref extra <<<"$output"
            if [[ -n "$oid" && "$ref" == "$BRANCH_REF" && -z "${extra:-}" ]] &&
               is_oid "$oid"; then
                REMOTE_STATE="present"
                REMOTE_OID=$oid
            else
                REMOTE_STATE="malformed"
                REMOTE_OID=""
            fi
            ;;
        2)
            REMOTE_STATE="missing"
            REMOTE_OID=""
            ;;
        *)
            REMOTE_STATE="unreadable"
            REMOTE_OID=""
            ;;
    esac
}

recover_metadata_only_cleanup() {
    local branch_oid
    [[ "$NS_STATE" == "absent" && "$MIRROR_COUNT" -ne 0 ]] || return 1
    is_oid "$M_SUBMIT" || hard_conflict "metadata-only submit oid is invalid"
    branch_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read branch after lease ref cleanup"
    [[ "$branch_oid" == "$M_SUBMIT" ]] ||
        hard_conflict "branch changed after lease refs were cleaned"
    read_push_remote
    case "$REMOTE_STATE" in
        present)
            OBSERVED_REMOTE=$REMOTE_OID
            [[ "$REMOTE_OID" == "$M_SUBMIT" ]] ||
                hard_conflict "remote differs from metadata-only submitted state"
            ;;
        missing|malformed)
            OBSERVED_REMOTE=${REMOTE_OID:-missing}
            hard_conflict "remote is missing/malformed after lease ref cleanup"
            ;;
        unreadable)
            indeterminate "could not verify metadata-only post-push state"
            ;;
    esac
    clear_mirror || indeterminate "post-push lease metadata cleanup did not verify"
    M_NS=""
    M_CONTEXT=""
    M_EXPECTED=""
    M_PRE=""
    M_BASE=""
    M_REBASED=""
    M_SUBMIT=""
    M_BRANCH=""
    M_ROOT=""
    M_STATE=""
    M_MANUAL=""
    MIRROR_COUNT=0
    return 0
}

if [[ "$NS_STATE" == "absent" && "$MIRROR_COUNT" -ne 0 ]]; then
    recover_metadata_only_cleanup
fi

fetch_base() {
    git fetch --no-tags -- "$FETCH_URL" \
        "+refs/heads/$BASE_BRANCH:$BASE_REMOTE_REF" >/dev/null 2>&1
}

fetch_feature_from_push_remote() {
    git fetch --no-tags -- "$PUSH_URL" \
        "+$BRANCH_REF:$TRACKING_REF" >/dev/null 2>&1
}

clear_rejection_after_rebase() {
    prove_live_source_step
    run_gc_bd update "$SOURCE_ID" \
        --unset-metadata rejection_reason \
        --set-metadata "fork_sha=$BASE_OID" >/dev/null 2>&1 || return 1
    load_source || return 1
    local fork
    fork=$(printf '%s' "$SOURCE_JSON" | jq -er '.[0].metadata.fork_sha // ""' 2>/dev/null) ||
        return 1
    [[ "$SOURCE_REJECTED" == "false" && "$fork" == "$BASE_OID" ]]
}

capture_lease() {
    local written candidate_expected candidate_pre candidate_base
    prove_live_source_step
    candidate_expected=$EXPECTED_OID
    candidate_pre=$PRE_OID
    candidate_base=$BASE_OID
    written=$(emit_context | git hash-object -w --stdin 2>/dev/null) ||
        indeterminate "could not write context object"
    [[ "$written" == "$CONTEXT_EXPECTED" ]] ||
        indeterminate "written context object did not match its digest"
    CONTEXT_OID=$written
    if printf '%s\n' \
        start \
        "option no-deref" \
        "create $CONTEXT_REF $CONTEXT_OID" \
        "create $EXPECTED_REF $EXPECTED_OID" \
        "create $PRE_REF $PRE_OID" \
        "create $BASE_REF $BASE_OID" \
        prepare \
        commit | git update-ref --stdin >/dev/null 2>&1; then
        :
    else
        load_namespace || hard_conflict "concurrent lease creation left partial refs"
        validate_namespace || hard_conflict "concurrent lease has different context"
        if [[ "$NS_STATE" == "absent" ]]; then
            indeterminate "lease creation failed without publishing any refs"
        fi
        if [[ "$CONTEXT_OID" != "$written" ||
              "$EXPECTED_OID" != "$candidate_expected" ||
              "$PRE_OID" != "$candidate_pre" ||
              "$BASE_OID" != "$candidate_base" ]]; then
            hard_conflict "concurrent lease candidate differs from this fetched branch/base"
        fi
    fi
    load_namespace || hard_conflict "captured lease refs are incomplete"
    validate_namespace || hard_conflict "captured lease refs failed validation"
    sync_mirror || indeterminate "captured lease metadata did not verify"
}

publish_rebase_result() {
    local symbolic result
    prove_live_source_step
    symbolic=$(git symbolic-ref -q HEAD 2>/dev/null || true)
    [[ -z "$symbolic" ]] ||
        hard_conflict "rebase publication requires detached HEAD"
    [[ ! -d "$(git rev-parse --git-path rebase-merge)" &&
       ! -d "$(git rev-parse --git-path rebase-apply)" ]] ||
        indeterminate "rebase is still in progress; resolve/continue it first"
    result=$(git rev-parse --verify HEAD 2>/dev/null) ||
        indeterminate "could not resolve detached rebase result"
    is_oid "$result" || indeterminate "invalid detached rebase result"
    [[ "$(git cat-file -t "$result" 2>/dev/null)" == "commit" ]] ||
        indeterminate "detached rebase result is not a commit"
    require_ancestor "$BASE_REF" "$result" \
        "detached rebase result is not based on captured base"

    if printf '%s\n' \
        start \
        "option no-deref" \
        "verify $CONTEXT_REF $CONTEXT_OID" \
        "verify $EXPECTED_REF $EXPECTED_OID" \
        "verify $PRE_REF $PRE_OID" \
        "verify $BASE_REF $BASE_OID" \
        "update $BRANCH_REF $result $PRE_OID" \
        "create $REBASED_REF $result" \
        prepare \
        commit | git update-ref --stdin >/dev/null 2>&1; then
        REBASED_OID=$result
    else
        load_namespace || hard_conflict "rebase publication left partial refs"
        validate_namespace || hard_conflict "rebase publication raced different state"
        if [[ "$NS_STATE" == "captured" ]] &&
           ref_equals "$BRANCH_REF" "$PRE_OID"; then
            indeterminate "rebase publication transaction failed without changing state"
        fi
        if [[ "$NS_STATE" != "rebased" || "$REBASED_OID" != "$result" ]] ||
           ! ref_equals "$BRANCH_REF" "$result"; then
            hard_conflict "another rebase result won the branch CAS"
        fi
    fi
    git switch "$BRANCH" >/dev/null 2>&1 ||
        indeterminate "rebase published but branch checkout failed"
    load_namespace || hard_conflict "published rebase namespace is incomplete"
    validate_namespace || hard_conflict "published rebase namespace failed validation"
    sync_mirror || indeterminate "rebased lease mirror did not verify"
    clear_rejection_after_rebase ||
        indeterminate "rebase published but source rejection metadata did not update"
}

workspace_action() {
    local branch_oid head_oid symbolic

    if [[ "$NS_STATE" == "captured" ]]; then
        read_push_remote
        case "$REMOTE_STATE" in
            present)
                OBSERVED_REMOTE=$REMOTE_OID
                [[ "$REMOTE_OID" == "$EXPECTED_OID" ]] ||
                    hard_conflict "remote moved after rejection lease capture"
                ;;
            missing|malformed)
                OBSERVED_REMOTE=${REMOTE_OID:-missing}
                hard_conflict "leased remote branch is missing or malformed"
                ;;
            unreadable)
                indeterminate "could not read leased push remote"
                ;;
        esac
        branch_oid=$(read_ref "$BRANCH_REF") ||
            indeterminate "could not read branch before detached rebase"
        [[ "$branch_oid" == "$PRE_OID" ]] ||
            hard_conflict "branch changed before detached rebase publication"
        if [[ -d "$(git rev-parse --git-path rebase-merge)" ||
              -d "$(git rev-parse --git-path rebase-apply)" ]]; then
            if [[ -n "$(git ls-files -u 2>/dev/null)" ]]; then
                echo "POLECAT_LEASE_REBASE_CONFLICT: resolve and stage the detached rebase, then rerun:" >&2
                echo "  gc gastown polecat-workspace execute" >&2
                exit "$EXIT_INDETERMINATE"
            fi
            if ! GIT_EDITOR=true git rebase --continue; then
                if [[ -d "$(git rev-parse --git-path rebase-merge)" ||
                      -d "$(git rev-parse --git-path rebase-apply)" ]]; then
                    echo "POLECAT_LEASE_REBASE_CONFLICT: resolve and stage the detached rebase, then rerun:" >&2
                    echo "  gc gastown polecat-workspace execute" >&2
                    exit "$EXIT_INDETERMINATE"
                fi
                indeterminate "git rebase --continue failed without leaving resumable state"
            fi
            publish_rebase_result
            return 0
        fi
        symbolic=$(git symbolic-ref -q HEAD 2>/dev/null || true)
        head_oid=$(git rev-parse --verify HEAD 2>/dev/null || true)
        if [[ -z "$symbolic" && "$head_oid" != "$PRE_OID" ]]; then
            publish_rebase_result
            return 0
        fi
        git switch --detach "$PRE_REF" >/dev/null 2>&1 ||
            indeterminate "could not detach at captured PRE"
        if ! git rebase "$BASE_REF"; then
            if [[ -d "$(git rev-parse --git-path rebase-merge)" ||
                  -d "$(git rev-parse --git-path rebase-apply)" ]]; then
                echo "POLECAT_LEASE_REBASE_CONFLICT: resolve and stage the detached rebase, then rerun:" >&2
                echo "  gc gastown polecat-workspace execute" >&2
                exit "$EXIT_INDETERMINATE"
            fi
            indeterminate "git rebase failed without leaving a resumable rebase state"
        fi
        publish_rebase_result
        return 0
    fi

    if [[ "$NS_STATE" == "rebased" || "$NS_STATE" == "submit-frozen" ]]; then
        branch_oid=$(read_ref "$BRANCH_REF") ||
            indeterminate "could not read leased branch on restart"
        [[ -n "$branch_oid" ]] || hard_conflict "leased branch ref is missing"
        require_ancestor "$BASE_REF" "$branch_oid" \
            "leased branch abandoned the captured base"
        require_ancestor "$REBASED_REF" "$branch_oid" \
            "leased branch rewrote the published rebase"
        if [[ "$NS_STATE" == "submit-frozen" && "$branch_oid" != "$SUBMIT_OID" ]]; then
            hard_conflict "branch changed after submit was frozen"
        fi
        read_push_remote
        case "$REMOTE_STATE" in
            present)
                OBSERVED_REMOTE=$REMOTE_OID
                if [[ "$REMOTE_OID" != "$EXPECTED_OID" &&
                      "$REMOTE_OID" != "$SUBMIT_OID" ]]; then
                    hard_conflict "remote moved outside the leased transition"
                fi
                ;;
            missing|malformed)
                OBSERVED_REMOTE=${REMOTE_OID:-missing}
                hard_conflict "leased remote is missing or malformed"
                ;;
            unreadable)
                indeterminate "could not read leased push remote"
                ;;
        esac
        git switch "$BRANCH" >/dev/null 2>&1 ||
            indeterminate "could not check out the leased branch"
        sync_mirror || indeterminate "lease mirror did not verify on restart"
        clear_rejection_after_rebase ||
            indeterminate "rebased source metadata did not verify on restart"
        return 0
    fi

    # No lease: perform ordinary authoritative branch synchronization first.
    fetch_base || indeterminate "could not fetch the target base branch"
    read_push_remote
    case "$REMOTE_STATE" in
        present)
            OBSERVED_REMOTE=$REMOTE_OID
            fetch_feature_from_push_remote ||
                indeterminate "could not fetch the push destination branch"
            branch_oid=$(read_ref "$BRANCH_REF") ||
                indeterminate "could not inspect the local feature branch"
            if [[ -n "$branch_oid" ]]; then
                git switch "$BRANCH" >/dev/null 2>&1 ||
                    indeterminate "could not check out the existing branch"
                if checked_ancestor "$TRACKING_REF" "$branch_oid" \
                    "fetched feature tip versus local branch"; then
                    :
                elif checked_ancestor "$branch_oid" "$TRACKING_REF" \
                    "local branch versus fetched feature tip"; then
                    git merge --ff-only "$TRACKING_REF" >/dev/null 2>&1 ||
                        indeterminate "local branch could not fast-forward to the fetched feature tip"
                else
                    hard_conflict "local branch diverged before lease capture"
                fi
            else
                git switch -c "$BRANCH" "$TRACKING_REF" >/dev/null 2>&1 ||
                    indeterminate "could not create the local tracking branch"
            fi
            ;;
        missing)
            OBSERVED_REMOTE="missing"
            if [[ "$SOURCE_REJECTED" == "true" ]]; then
                hard_conflict "rejected branch is missing on the push remote"
            fi
            branch_oid=$(read_ref "$BRANCH_REF") ||
                indeterminate "could not inspect the local-only feature branch"
            [[ -n "$branch_oid" ]] ||
                hard_conflict "metadata branch exists neither locally nor remotely"
            git switch "$BRANCH" >/dev/null 2>&1 ||
                indeterminate "could not check out the local-only branch"
            ;;
        malformed)
            hard_conflict "push remote returned malformed branch data"
            ;;
        unreadable)
            indeterminate "could not read the push destination"
            ;;
    esac

    [[ "$SOURCE_REJECTED" == "true" ]] || return 0
    [[ "$REMOTE_STATE" == "present" ]] ||
        hard_conflict "cannot lease a rejected local-only branch"
    EXPECTED_OID=$(read_ref "$TRACKING_REF") ||
        indeterminate "could not read fetched feature tracking ref"
    PRE_OID=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read pre-rebase branch ref"
    BASE_OID=$(read_ref "$BASE_REMOTE_REF") ||
        indeterminate "could not read fetched base tracking ref"
    for oid in "$EXPECTED_OID" "$PRE_OID" "$BASE_OID"; do
        is_oid "$oid" || indeterminate "captured Git ref has an invalid oid"
        [[ "$(git cat-file -t "$oid" 2>/dev/null)" == "commit" ]] ||
            indeterminate "captured Git ref is not a commit"
    done
    require_ancestor "$EXPECTED_OID" "$PRE_OID" \
        "local branch is not based on the fetched push-remote tip"
    capture_lease
    workspace_action
}

publish_action() {
    [[ "$NS_STATE" == "captured" ]] ||
        hard_conflict "publish-rebase requires captured pre-rebase state"
    local branch_oid head_oid
    branch_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read branch before explicit rebase publication"
    head_oid=$(git rev-parse --verify HEAD 2>/dev/null || true)
    [[ "$branch_oid" == "$PRE_OID" ]] ||
        hard_conflict "branch changed before explicit rebase publication"
    [[ -n "$head_oid" && "$head_oid" != "$PRE_OID" ]] ||
        hard_conflict "no detached rebase result is available to publish"
    publish_rebase_result
}

freeze_submit() {
    local head_oid
    prove_live_source_step
    head_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read branch before submit freeze"
    is_oid "$head_oid" || indeterminate "could not resolve branch submit head"
    require_ancestor "$BASE_REF" "$head_oid" \
        "submit head abandoned the captured base"
    require_ancestor "$REBASED_REF" "$head_oid" \
        "submit head rewrote the published rebase"
    if printf '%s\n' \
        start \
        "option no-deref" \
        "verify $CONTEXT_REF $CONTEXT_OID" \
        "verify $EXPECTED_REF $EXPECTED_OID" \
        "verify $PRE_REF $PRE_OID" \
        "verify $BASE_REF $BASE_OID" \
        "verify $REBASED_REF $REBASED_OID" \
        "verify $BRANCH_REF $head_oid" \
        "create $SUBMIT_REF $head_oid" \
        prepare \
        commit | git update-ref --stdin >/dev/null 2>&1; then
        SUBMIT_OID=$head_oid
    else
        load_namespace || hard_conflict "submit freeze left partial refs"
        validate_namespace || hard_conflict "submit freeze raced different state"
        if [[ "$NS_STATE" == "rebased" ]] &&
           ref_equals "$BRANCH_REF" "$head_oid"; then
            indeterminate "submit freeze transaction failed without changing state"
        fi
        [[ "$NS_STATE" == "submit-frozen" &&
           "$SUBMIT_OID" == "$head_oid" ]] ||
            hard_conflict "another submit head won the freeze transaction"
    fi
    load_namespace || hard_conflict "submit namespace is incomplete"
    validate_namespace || hard_conflict "submit namespace failed validation"
    sync_mirror || indeterminate "submit-frozen metadata did not verify"
}

cleanup_namespace() {
    prove_live_source_step
    if printf '%s\n' \
        start \
        "option no-deref" \
        "verify $BRANCH_REF $SUBMIT_OID" \
        "delete $CONTEXT_REF $CONTEXT_OID" \
        "delete $EXPECTED_REF $EXPECTED_OID" \
        "delete $PRE_REF $PRE_OID" \
        "delete $BASE_REF $BASE_OID" \
        "delete $REBASED_REF $REBASED_OID" \
        "delete $SUBMIT_REF $SUBMIT_OID" \
        prepare \
        commit | git update-ref --stdin >/dev/null 2>&1; then
        :
    else
        load_namespace || hard_conflict "lease cleanup exposed partial refs"
        if [[ "$NS_STATE" != "absent" ]]; then
            validate_namespace || hard_conflict "lease cleanup raced changed refs"
            indeterminate "lease cleanup transaction failed without changing state"
        fi
    fi
    load_namespace || hard_conflict "post-cleanup namespace is partial"
    [[ "$NS_STATE" == "absent" ]] ||
        indeterminate "lease refs remain after cleanup"
    clear_mirror || indeterminate "lease metadata remains after ref cleanup"
}

normal_push() {
    local head_oid push_code
    prove_live_source_step
    head_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read ordinary submit branch"
    is_oid "$head_oid" || indeterminate "could not freeze ordinary submit head"
    LOCAL_HEAD=$head_oid
    read_push_remote
    if [[ "$REMOTE_STATE" == "present" && "$REMOTE_OID" == "$head_oid" ]]; then
        prove_live_source_step
        ref_equals "$BRANCH_REF" "$head_oid" ||
            indeterminate "ordinary branch changed while prior push state was verified"
        return 0
    fi
    ref_equals "$BRANCH_REF" "$head_oid" ||
        indeterminate "ordinary branch changed before its frozen oid could be pushed"
    git push -- "$PUSH_URL" "$head_oid:$BRANCH_REF"
    push_code=$?
    if [[ "$push_code" -ne 0 ]]; then
        read_push_remote
        if [[ "$REMOTE_STATE" == "present" && "$REMOTE_OID" == "$head_oid" ]]; then
            prove_live_source_step
            ref_equals "$BRANCH_REF" "$head_oid" ||
                indeterminate "ordinary branch changed after a lost push response"
            return 0
        fi
        echo "polecat-lease: ordinary push failed (exit $push_code); state preserved" >&2
        indeterminate "ordinary non-force push did not verify"
    fi
    read_push_remote
    [[ "$REMOTE_STATE" == "present" && "$REMOTE_OID" == "$head_oid" ]] ||
        indeterminate "ordinary push response succeeded but remote did not verify"
    prove_live_source_step
    ref_equals "$BRANCH_REF" "$head_oid" ||
        indeterminate "ordinary branch changed while its frozen oid was being pushed"
}

leased_push() {
    local push_code
    LOCAL_HEAD=$SUBMIT_OID
    read_push_remote
    case "$REMOTE_STATE" in
        present)
            OBSERVED_REMOTE=$REMOTE_OID
            if [[ "$REMOTE_OID" == "$SUBMIT_OID" ]]; then
                cleanup_namespace
                return 0
            fi
            [[ "$REMOTE_OID" == "$EXPECTED_OID" ]] ||
                hard_conflict "remote moved before leased push"
            ;;
        missing|malformed)
            OBSERVED_REMOTE=${REMOTE_OID:-missing}
            hard_conflict "leased push destination is missing or malformed"
            ;;
        unreadable)
            indeterminate "could not read leased push destination"
            ;;
    esac

    prove_live_source_step
    git push \
        --force-with-lease="$BRANCH_REF:$EXPECTED_OID" \
        -- "$PUSH_URL" "$SUBMIT_REF:$BRANCH_REF"
    push_code=$?
    if [[ "$push_code" -ne 0 ]]; then
        read_push_remote
        case "$REMOTE_STATE" in
            present)
                OBSERVED_REMOTE=$REMOTE_OID
                if [[ "$REMOTE_OID" == "$SUBMIT_OID" ]]; then
                    cleanup_namespace
                    return 0
                fi
                if [[ "$REMOTE_OID" == "$EXPECTED_OID" ]]; then
                    echo "polecat-lease: push rejected without remote mutation (exit $push_code)" >&2
                    indeterminate "leased push failed operationally"
                fi
                hard_conflict "remote moved while leased push was attempted"
                ;;
            missing|malformed)
                OBSERVED_REMOTE=${REMOTE_OID:-missing}
                hard_conflict "remote disappeared or became malformed during leased push"
                ;;
            unreadable)
                indeterminate "leased push failed and remote could not be reread"
                ;;
        esac
    fi
    read_push_remote
    case "$REMOTE_STATE" in
        present)
            OBSERVED_REMOTE=$REMOTE_OID
            [[ "$REMOTE_OID" == "$SUBMIT_OID" ]] ||
                hard_conflict "leased push returned success but remote differs"
            ;;
        missing|malformed)
            OBSERVED_REMOTE=${REMOTE_OID:-missing}
            hard_conflict "leased push returned success but remote is missing/malformed"
            ;;
        unreadable)
            indeterminate "leased push returned success but verification is unreadable"
            ;;
    esac
    cleanup_namespace
}

SUBMIT_PROOF_CONTEXT_OID=""
SUBMIT_PROOF_HEAD_OID=""
SUBMIT_PROOF_STATE="absent"

emit_submit_proof_context() {
    local head_oid=$1
    printf '%s\n' \
        "schema=gascity-polecat-submit-proof-v1" \
        "version=$SUBMIT_PROOF_VERSION" \
        "key=$SUBMIT_PROOF_KEY" \
        "source=$SOURCE_ID" \
        "workflow_root=$ROOT_BEAD_ID" \
        "step=$STEP_BEAD_ID" \
        "step_assignee=$STEP_ASSIGNEE" \
        "input_convoy=$CONVOY_ID" \
        "session_id=$CURRENT_SESSION_ID" \
        "branch=$BRANCH" \
        "target=$BASE_BRANCH" \
        "auto_push=$AUTO_PUSH" \
        "head_oid=$head_oid" \
        "rig=$ROOT_RIG_NAME" \
        "binding_prefix=$ROOT_BINDING_PREFIX" \
        "witness=$WITNESS_CANONICAL" \
        "repo_common_fingerprint=$REPO_COMMON_FINGERPRINT" \
        "worktree_fingerprint=$WORKTREE_FINGERPRINT" \
        "origin_fetch_fingerprint=$FETCH_FINGERPRINT" \
        "origin_push_fingerprint=$PUSH_FINGERPRINT"
}

read_submit_proof_once() {
    SUBMIT_PROOF_CONTEXT_OID=$(read_ref "$SUBMIT_PROOF_CONTEXT_REF") ||
        return 1
    SUBMIT_PROOF_HEAD_OID=$(read_ref "$SUBMIT_PROOF_HEAD_REF") ||
        return 1
    if [[ -z "$SUBMIT_PROOF_CONTEXT_OID" &&
          -z "$SUBMIT_PROOF_HEAD_OID" ]]; then
        SUBMIT_PROOF_STATE="absent"
    elif [[ -n "$SUBMIT_PROOF_CONTEXT_OID" &&
            -n "$SUBMIT_PROOF_HEAD_OID" ]]; then
        SUBMIT_PROOF_STATE="complete"
    else
        SUBMIT_PROOF_STATE="partial"
    fi
}

load_submit_proof() {
    local attempt
    for attempt in 1 2 3; do
        read_submit_proof_once || return 1
        [[ "$SUBMIT_PROOF_STATE" == "partial" ]] || return 0
        sleep 1
    done
    return 0
}

submit_proof_matches() {
    local expected_context=$1 expected_head=$2 observed_context
    [[ "$SUBMIT_PROOF_STATE" == "complete" &&
       "$SUBMIT_PROOF_CONTEXT_OID" == "$expected_context" &&
       "$SUBMIT_PROOF_HEAD_OID" == "$expected_head" ]] || return 1
    ! git symbolic-ref -q "$SUBMIT_PROOF_CONTEXT_REF" >/dev/null 2>&1 ||
        return 1
    validate_commit_ref "$SUBMIT_PROOF_HEAD_REF" "$expected_head" || return 1
    [[ "$(git cat-file -t "$expected_context" 2>/dev/null)" == "blob" ]] ||
        return 1
    observed_context=$(git cat-file blob "$expected_context" 2>/dev/null) ||
        return 1
    [[ "$observed_context" == "$(emit_submit_proof_context "$expected_head")" ]] ||
        return 1
    ref_equals "$SUBMIT_PROOF_CONTEXT_REF" "$expected_context" &&
        ref_equals "$SUBMIT_PROOF_HEAD_REF" "$expected_head"
}

revalidate_submit_proof_inputs() {
    local expected_head=$1 current branch_oid clean_status
    prove_live_source_step
    current=$(git branch --show-current 2>/dev/null || true)
    [[ "$current" == "$BRANCH" ]] ||
        indeterminate "submit proof is not running on the canonical branch"
    branch_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read the branch before submit-proof publication"
    [[ "$branch_oid" == "$expected_head" ]] ||
        indeterminate "canonical branch changed before submit-proof publication"
    clean_status=$(git status --porcelain --untracked-files=all 2>/dev/null) ||
        indeterminate "could not inspect final task-artifact status"
    [[ -z "$clean_status" ]] ||
        indeterminate "task artifact is dirty; refusing submit-proof publication"
    if [[ "$AUTO_PUSH" == "true" ]]; then
        read_push_remote
        [[ "$REMOTE_STATE" == "present" &&
           "$REMOTE_OID" == "$expected_head" ]] ||
            indeterminate "pushed branch no longer verifies at the exact submit head"
    fi
}

emit_submit_proof_receipt() {
    local context_oid=$1 head_oid=$2
    printf 'POLECAT_SUBMIT_PROOF version=%s key=%s context=%s head=%s auto_push=%s\n' \
        "$SUBMIT_PROOF_VERSION" "$SUBMIT_PROOF_KEY" "$context_oid" \
        "$head_oid" "$AUTO_PUSH"
}

reuse_existing_submit_proof() {
    local head_oid context_oid
    load_submit_proof ||
        indeterminate "could not inspect the existing submit-proof namespace"
    case "$SUBMIT_PROOF_STATE" in
        absent)
            return 1
            ;;
        partial)
            hard_conflict "existing submit-proof namespace is partial"
            ;;
        complete)
            ;;
    esac
    [[ "$NS_STATE" == "absent" ]] ||
        hard_conflict "submit proof coexists with unfinished rejection-lease refs"
    head_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not resolve the branch for submit-proof retry"
    is_oid "$head_oid" ||
        indeterminate "canonical branch has no valid submit-proof retry head"
    context_oid=$(emit_submit_proof_context "$head_oid" |
        git hash-object --stdin 2>/dev/null) ||
        indeterminate "could not hash the submit-proof retry context"
    submit_proof_matches "$context_oid" "$head_oid" ||
        hard_conflict "existing submit proof differs from this workflow context or head"
    revalidate_submit_proof_inputs "$head_oid"
    emit_submit_proof_receipt "$context_oid" "$head_oid"
    return 0
}

persist_submit_proof() {
    local head_oid context_oid written

    head_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not resolve the submit-proof head"
    is_oid "$head_oid" ||
        indeterminate "canonical branch has no valid submit-proof head"
    revalidate_submit_proof_inputs "$head_oid"

    context_oid=$(emit_submit_proof_context "$head_oid" |
        git hash-object --stdin 2>/dev/null) ||
        indeterminate "could not hash the submit-proof context"
    is_oid "$context_oid" ||
        indeterminate "Git returned an invalid submit-proof context id"
    written=$(emit_submit_proof_context "$head_oid" |
        git hash-object -w --stdin 2>/dev/null) ||
        indeterminate "could not write the submit-proof context object"
    [[ "$written" == "$context_oid" ]] ||
        indeterminate "written submit-proof context did not match its digest"

    if printf '%s\n' \
        start \
        "option no-deref" \
        "verify $BRANCH_REF $head_oid" \
        "create $SUBMIT_PROOF_CONTEXT_REF $context_oid" \
        "create $SUBMIT_PROOF_HEAD_REF $head_oid" \
        prepare \
        commit | git update-ref --stdin >/dev/null 2>&1; then
        :
    else
        load_submit_proof ||
            indeterminate "could not read submit proof after create-only transaction failure"
        case "$SUBMIT_PROOF_STATE" in
            absent)
                indeterminate "submit-proof transaction failed without publishing refs"
                ;;
            partial)
                hard_conflict "submit-proof transaction exposed partial refs"
                ;;
            complete)
                submit_proof_matches "$context_oid" "$head_oid" ||
                    hard_conflict "another submit proof won with different context or head"
                ;;
        esac
    fi

    load_submit_proof ||
        indeterminate "could not read the durable submit proof"
    [[ "$SUBMIT_PROOF_STATE" != "partial" ]] ||
        hard_conflict "durable submit-proof namespace is partial"
    submit_proof_matches "$context_oid" "$head_oid" ||
        hard_conflict "durable submit proof failed exact readback validation"
    revalidate_submit_proof_inputs "$head_oid"

    emit_submit_proof_receipt "$context_oid" "$head_oid"
}

submit_action() {
    local current branch_oid
    current=$(git branch --show-current 2>/dev/null || true)
    [[ "$current" == "$BRANCH" ]] ||
        hard_conflict "submit is not running on the canonical branch"
    branch_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read canonical submit branch"
    is_oid "$branch_oid" || indeterminate "canonical branch ref is missing"
    if reuse_existing_submit_proof; then
        return 0
    fi

    if [[ "$NS_STATE" == "absent" ]]; then
        if [[ "$AUTO_PUSH" == "false" ]]; then
            echo "POLECAT_LEASE_AUTO_PUSH_FALSE: no rejection lease; no push performed"
            persist_submit_proof
            return 0
        fi
        normal_push
        persist_submit_proof
        return 0
    fi
    [[ "$NS_STATE" != "captured" ]] ||
        hard_conflict "submit reached before rejection rebase publication"
    if [[ "$AUTO_PUSH" == "false" ]]; then
        indeterminate "auto_push=false is unsupported for a rejection-rebased branch; submit was not frozen or pushed"
    fi
    if [[ "$NS_STATE" == "rebased" ]]; then
        freeze_submit
    fi
    [[ "$NS_STATE" == "submit-frozen" ]] ||
        hard_conflict "submit state did not freeze"
    branch_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not re-read branch after submit freeze"
    [[ "$branch_oid" == "$SUBMIT_OID" ]] ||
        hard_conflict "branch changed after submit freeze"
    require_ancestor "$BASE_REF" "$SUBMIT_REF" \
        "frozen submit abandoned captured base"
    require_ancestor "$REBASED_REF" "$SUBMIT_REF" \
        "frozen submit abandoned published rebase"

    leased_push
    persist_submit_proof
}

case "$ACTION" in
    workspace)
        workspace_action
        ;;
    publish-rebase)
        publish_action
        ;;
    submit)
        submit_action
        ;;
esac

ACTION_RC=$?
exit "$ACTION_RC"
