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
  gc gastown polecat-lease record-replay \
    --source ID --convoy ID --base BRANCH --branch BRANCH --witness TARGET
    (internal; invoked only by the lease-owned Git rebase sequencer)
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
    workspace|publish-rebase|record-replay|submit) ;;
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
    exit "$EXIT_USAGE"
fi
git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 || {
    echo "polecat-lease: invalid feature branch" >&2
    exit "$EXIT_USAGE"
}
git check-ref-format --branch "$BASE_BRANCH" >/dev/null 2>&1 || {
    echo "polecat-lease: invalid base branch" >&2
    exit "$EXIT_USAGE"
}

BRANCH_REF="refs/heads/$BRANCH"
TRACKING_REF="refs/remotes/origin/$BRANCH"
BASE_REMOTE_REF="refs/remotes/origin/$BASE_BRANCH"

LEASE_KEY=$(printf 'gascity-polecat-push-lease-v1\0%s' "$SOURCE_ID" | git hash-object --stdin 2>/dev/null) ||
    indeterminate "could not derive the opaque lease key"
is_oid "$LEASE_KEY" || indeterminate "Git returned an invalid lease key"

LEASE_NS="refs/gascity/polecat-push-leases/$LEASE_KEY"
REBASE_WORK_BRANCH="gascity-polecat-rebase/$LEASE_KEY"
REBASE_WORK_REF="refs/heads/$REBASE_WORK_BRANCH"
CONTEXT_REF="$LEASE_NS/context"
EXPECTED_REF="$LEASE_NS/expected"
PRE_REF="$LEASE_NS/pre-rebase"
BASE_REF="$LEASE_NS/base"
CANDIDATE_REF="$LEASE_NS/candidate"
REBASED_REF="$LEASE_NS/rebased"
SUBMIT_REF="$LEASE_NS/submit"

for ref in "$REBASE_WORK_REF" "$CONTEXT_REF" "$EXPECTED_REF" "$PRE_REF" "$BASE_REF" \
           "$CANDIDATE_REF" "$REBASED_REF" "$SUBMIT_REF"; do
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

LEASE_POINTER_LINE=
lease_read_one_line_file() {
    local file=$1 line count=0
    LEASE_POINTER_LINE=
    [[ -f "$file" && ! -L "$file" ]] || return 1
    while IFS= read -r line || [[ -n "$line" ]]; do
        count=$((count + 1))
        [[ "$count" -eq 1 ]] || return 1
        LEASE_POINTER_LINE=$line
    done <"$file"
    [[ "$count" -eq 1 ]]
}

lease_resolve_dir_ref() {
    local base=$1 ref=$2 candidate
    case "$ref" in
        /*) candidate=$ref ;;
        *) candidate="$base/$ref" ;;
    esac
    (CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P)
}

lease_resolve_file_ref() {
    local base=$1 ref=$2 candidate parent parent_real
    case "$ref" in
        /*) candidate=$ref ;;
        *) candidate="$base/$ref" ;;
    esac
    parent=$(dirname -- "$candidate") || return 1
    parent_real=$(CDPATH= cd -- "$parent" 2>/dev/null && pwd -P) || return 1
    printf '%s/%s\n' "$parent_real" "$(basename -- "$candidate")"
}

validate_worktree_binding() {
    local current_top recorded_top recorded_git_top
    local city_root rig_root recorded_common rig_common
    local rig_namespace rig_namespace_real canonical_path
    local worktrees_parent provider_home provider_root provider_name
    local artifact_git_dir dotgit_ref dotgit_real backref backreal listed
    local registered_count=0

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
    [[ "$recorded_top" == "$SOURCE_ARTIFACT_DIR" ]] ||
        indeterminate "source metadata.artifact_dir is redirected"
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

    artifact_git_dir=$(git -C "$recorded_top" rev-parse \
        --path-format=absolute --absolute-git-dir 2>/dev/null) ||
        indeterminate "could not resolve the artifact Git admin directory"
    artifact_git_dir=$(CDPATH= cd -- "$artifact_git_dir" 2>/dev/null && pwd -P) ||
        indeterminate "could not canonicalize the artifact Git admin directory"
    [[ "$(dirname -- "$artifact_git_dir")" == "$rig_common/worktrees" ]] ||
        indeterminate "artifact Git admin directory is not registered to the rig"
    lease_read_one_line_file "$recorded_top/.git" ||
        indeterminate "source artifact has an invalid or redirected .git pointer"
    case "$LEASE_POINTER_LINE" in
        "gitdir: "*) dotgit_ref=${LEASE_POINTER_LINE#gitdir: } ;;
        *) indeterminate "source artifact has an invalid .git pointer" ;;
    esac
    safe_atom "$dotgit_ref" ||
        indeterminate "source artifact has an unsafe .git pointer"
    dotgit_real=$(lease_resolve_dir_ref "$recorded_top" "$dotgit_ref") ||
        indeterminate "source artifact .git pointer is unavailable"
    [[ "$dotgit_real" == "$artifact_git_dir" ]] ||
        indeterminate "source artifact .git pointer does not match Git identity"
    lease_read_one_line_file "$artifact_git_dir/gitdir" ||
        indeterminate "source artifact Git admin backpointer is invalid"
    backref=$LEASE_POINTER_LINE
    backreal=$(lease_resolve_file_ref "$artifact_git_dir" "$backref") ||
        indeterminate "source artifact Git admin backpointer is unavailable"
    [[ "$backreal" == "$recorded_top/.git" ]] ||
        indeterminate "source artifact Git admin backpointer does not match artifact"
    while IFS= read -r -d '' listed; do
        [[ "$listed" == "worktree $recorded_top" ]] &&
            registered_count=$((registered_count + 1))
    done < <(git -C "$rig_root" worktree list --porcelain -z 2>/dev/null)
    [[ "$registered_count" -eq 1 ]] ||
        indeterminate "source artifact is not exactly one registered rig worktree"

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
        "rebase_work_ref=$REBASE_WORK_REF" \
        "worktree_fingerprint=$WORKTREE_FINGERPRINT" \
        "repo_common_fingerprint=$REPO_COMMON_FINGERPRINT" \
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
REBASE_WORK_OID=""
CANDIDATE_OID=""
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
    REBASE_WORK_OID=$(read_ref "$REBASE_WORK_REF") ||
        indeterminate "could not read lease-owned rebase work ref"
    CONTEXT_OID=$(read_ref "$CONTEXT_REF") ||
        indeterminate "could not read lease context ref"
    EXPECTED_OID=$(read_ref "$EXPECTED_REF") ||
        indeterminate "could not read lease expected ref"
    PRE_OID=$(read_ref "$PRE_REF") ||
        indeterminate "could not read lease pre-rebase ref"
    BASE_OID=$(read_ref "$BASE_REF") ||
        indeterminate "could not read lease base ref"
    CANDIDATE_OID=$(read_ref "$CANDIDATE_REF") ||
        indeterminate "could not read lease candidate ref"
    REBASED_OID=$(read_ref "$REBASED_REF") ||
        indeterminate "could not read lease rebased ref"
    SUBMIT_OID=$(read_ref "$SUBMIT_REF") ||
        indeterminate "could not read lease submit ref"
    NS_COUNT=0
    for oid in "$CONTEXT_OID" "$EXPECTED_OID" "$PRE_OID" "$BASE_OID" \
               "$CANDIDATE_OID" "$REBASED_OID" "$SUBMIT_OID"; do
        [[ -z "$oid" ]] || NS_COUNT=$((NS_COUNT + 1))
    done
    case "$NS_COUNT" in
        0)
            if [[ -z "$REBASE_WORK_OID" ]]; then
                NS_STATE="absent"
                return 0
            fi
            ;;
        4)
            if [[ -n "$CONTEXT_OID" && -n "$EXPECTED_OID" &&
                  -n "$PRE_OID" && -n "$BASE_OID" &&
                  -z "$CANDIDATE_OID" && -z "$REBASED_OID" &&
                  -z "$SUBMIT_OID" && -n "$REBASE_WORK_OID" ]]; then
                NS_STATE="captured"
                return 0
            fi
            ;;
        5)
            if [[ -n "$CONTEXT_OID" && -n "$EXPECTED_OID" &&
                  -n "$PRE_OID" && -n "$BASE_OID" &&
                  -z "$SUBMIT_OID" ]]; then
                if [[ -n "$CANDIDATE_OID" && -z "$REBASED_OID" ]]; then
                    [[ -n "$REBASE_WORK_OID" ]] || {
                        NS_STATE="partial"
                        return 1
                    }
                    NS_STATE="candidate"
                    return 0
                elif [[ -z "$CANDIDATE_OID" && -n "$REBASED_OID" ]]; then
                    [[ -z "$REBASE_WORK_OID" ]] || {
                        NS_STATE="partial"
                        return 1
                    }
                    NS_STATE="rebased"
                    return 0
                fi
            fi
            ;;
        6)
            if [[ -z "$CANDIDATE_OID" && -n "$REBASED_OID" &&
                  -n "$SUBMIT_OID" && -z "$REBASE_WORK_OID" ]]; then
                NS_STATE="submit-frozen"
                return 0
            fi
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

shell_single_quote() {
    local value=${1//\'/\'\\\'\'}
    printf "'%s'" "$value"
}

build_replay_recorder_command() {
    local value command=""
    for value in \
        "$GC_CMD" gastown polecat-lease record-replay \
        --source "$SOURCE_ID" \
        --convoy "$CONVOY_ID" \
        --base "$BASE_BRANCH" \
        --branch "$BRANCH" \
        --witness "$WITNESS_TARGET"; do
        if [[ -n "${command:-}" ]]; then
            command+=" "
        fi
        command+=$(shell_single_quote "$value") || return 1
    done
    printf '%s' "$command"
}

REPLAY_RECORDER_COMMAND=$(build_replay_recorder_command) ||
    indeterminate "could not construct the constrained rebase recorder command"
[[ -n "$REPLAY_RECORDER_COMMAND" &&
   "$REPLAY_RECORDER_COMMAND" != *$'\n'* &&
   "$REPLAY_RECORDER_COMMAND" != *$'\r'* &&
   "$REPLAY_RECORDER_COMMAND" != *$'\t'* ]] ||
    indeterminate "the constrained rebase recorder command is unsafe"

# The trusted sequencer records one immutable source/result pair per frozen
# source commit.  Its last exec creates the final ref in the same transaction
# as the last pair, so a completed work ref is restart-adoptable only when the
# entire exact replay chain was sealed before Git removed its rebase state.
REPLAY_PROOF_READY=0
REPLAY_PROOF_STATE="absent"
REPLAY_PROOF_RECORDED=0
REPLAY_PROOF_TIP_OID=""
REPLAY_PROOF_FINAL_OID=""
REPLAY_ORIGINAL_BASE=""
REPLAY_SOURCE_COUNT=0
REPLAY_SOURCE_DIGEST=""
REPLAY_RECORDER_DIGEST=""
REPLAY_PROOF_GENERATION=""
REPLAY_PROOF_NS=""
REPLAY_PROOF_CONTEXT_REF=""
REPLAY_PROOF_FINAL_REF=""
REPLAY_SOURCE_COMMITS=()
REPLAY_RESULT_COMMITS=()

emit_replay_proof_context() {
    printf '%s\n' \
        "schema=gascity-polecat-rebase-proof-v1" \
        "lease_context_oid=$CONTEXT_OID" \
        "source=$SOURCE_ID" \
        "workflow_root=$ROOT_BEAD_ID" \
        "input_convoy=$CONVOY_ID" \
        "branch=$BRANCH" \
        "rebase_work_ref=$REBASE_WORK_REF" \
        "pre_oid=$PRE_OID" \
        "base_oid=$BASE_OID" \
        "original_base_oid=$REPLAY_ORIGINAL_BASE" \
        "source_count=$REPLAY_SOURCE_COUNT" \
        "source_sequence_digest=$REPLAY_SOURCE_DIGEST" \
        "recorder_command_digest=$REPLAY_RECORDER_DIGEST"
}

initialize_replay_proof() {
    local commit line observed parent extra previous

    [[ "$REPLAY_PROOF_READY" -eq 0 ]] || return 0
    is_oid "$CONTEXT_OID" && is_oid "$PRE_OID" && is_oid "$BASE_OID" ||
        return 1
    REPLAY_ORIGINAL_BASE=$(git merge-base "$PRE_OID" "$BASE_OID" 2>/dev/null) ||
        return 1
    is_oid "$REPLAY_ORIGINAL_BASE" || return 1
    mapfile -t REPLAY_SOURCE_COMMITS < <(
        git rev-list --reverse --topo-order \
            "$REPLAY_ORIGINAL_BASE..$PRE_OID" 2>/dev/null
    )
    REPLAY_SOURCE_COUNT=${#REPLAY_SOURCE_COMMITS[@]}
    [[ "$REPLAY_SOURCE_COUNT" -gt 0 ]] || return 1

    previous=$REPLAY_ORIGINAL_BASE
    for commit in "${REPLAY_SOURCE_COMMITS[@]}"; do
        is_oid "$commit" || return 1
        line=$(git rev-list --parents -n 1 "$commit" 2>/dev/null) || return 1
        read -r observed parent extra <<<"$line"
        [[ "$observed" == "$commit" && "$parent" == "$previous" &&
           -z "${extra:-}" ]] || return 1
        previous=$commit
    done
    [[ "$previous" == "$PRE_OID" ]] || return 1

    REPLAY_SOURCE_DIGEST=$(
        printf '%s\n' "${REPLAY_SOURCE_COMMITS[@]}" |
            git hash-object --stdin 2>/dev/null
    ) || return 1
    REPLAY_RECORDER_DIGEST=$(
        printf '%s\n' "$REPLAY_RECORDER_COMMAND" |
            git hash-object --stdin 2>/dev/null
    ) || return 1
    is_oid "$REPLAY_SOURCE_DIGEST" && is_oid "$REPLAY_RECORDER_DIGEST" ||
        return 1
    REPLAY_PROOF_GENERATION=$(emit_replay_proof_context |
        git hash-object --stdin 2>/dev/null) || return 1
    is_oid "$REPLAY_PROOF_GENERATION" || return 1
    REPLAY_PROOF_NS="refs/gascity/polecat-rebase-proofs/v1/$LEASE_KEY/$REPLAY_PROOF_GENERATION"
    REPLAY_PROOF_CONTEXT_REF="$REPLAY_PROOF_NS/context"
    REPLAY_PROOF_FINAL_REF="$REPLAY_PROOF_NS/final"
    git check-ref-format "$REPLAY_PROOF_CONTEXT_REF" >/dev/null 2>&1 ||
        return 1
    git check-ref-format "$REPLAY_PROOF_FINAL_REF" >/dev/null 2>&1 ||
        return 1
    REPLAY_PROOF_READY=1
}

replay_ordinal_ref() {
    local kind=$1 ordinal=$2 suffix
    [[ "$kind" == "source" || "$kind" == "replay" ]] || return 1
    [[ "$ordinal" =~ ^[1-9][0-9]*$ ]] || return 1
    printf -v suffix '%08d' "$ordinal" || return 1
    printf '%s/%s/%s' "$REPLAY_PROOF_NS" "$kind" "$suffix"
}

validate_replay_proof_prefix() {
    local context_oid final_oid source_ref replay_ref source_oid replay_oid
    local actual_refs actual_count=0 expected_count=0 ordinal
    local line observed parent extra previous

    initialize_replay_proof || return 1
    actual_refs=$(git for-each-ref --format='%(refname)' \
        "$REPLAY_PROOF_NS/" 2>/dev/null) || return 1
    if [[ -n "$actual_refs" ]]; then
        while IFS= read -r ref; do
            [[ -n "$ref" ]] || return 1
            actual_count=$((actual_count + 1))
        done <<<"$actual_refs"
    fi

    context_oid=$(read_ref "$REPLAY_PROOF_CONTEXT_REF") || return 1
    if [[ -z "$context_oid" ]]; then
        [[ "$actual_count" -eq 0 ]] || return 1
        REPLAY_PROOF_STATE="absent"
        REPLAY_PROOF_RECORDED=0
        REPLAY_PROOF_TIP_OID=""
        REPLAY_PROOF_FINAL_OID=""
        return 0
    fi
    ! git symbolic-ref -q "$REPLAY_PROOF_CONTEXT_REF" >/dev/null 2>&1 ||
        return 1
    [[ "$context_oid" == "$REPLAY_PROOF_GENERATION" &&
       "$(git cat-file -t "$context_oid" 2>/dev/null)" == "blob" &&
       "$(git cat-file blob "$context_oid" 2>/dev/null)" == \
         "$(emit_replay_proof_context)" ]] || return 1

    REPLAY_PROOF_RECORDED=0
    REPLAY_RESULT_COMMITS=()
    previous=$BASE_OID
    for ((ordinal = 1; ordinal <= REPLAY_SOURCE_COUNT; ordinal++)); do
        source_ref=$(replay_ordinal_ref source "$ordinal") || return 1
        replay_ref=$(replay_ordinal_ref replay "$ordinal") || return 1
        git check-ref-format "$source_ref" >/dev/null 2>&1 || return 1
        git check-ref-format "$replay_ref" >/dev/null 2>&1 || return 1
        source_oid=$(read_ref "$source_ref") || return 1
        replay_oid=$(read_ref "$replay_ref") || return 1
        if [[ -z "$source_oid" && -z "$replay_oid" ]]; then
            break
        fi
        [[ -n "$source_oid" && -n "$replay_oid" ]] || return 1
        validate_commit_ref "$source_ref" "$source_oid" || return 1
        validate_commit_ref "$replay_ref" "$replay_oid" || return 1
        [[ "$source_oid" == "${REPLAY_SOURCE_COMMITS[ordinal - 1]}" ]] ||
            return 1
        line=$(git rev-list --parents -n 1 "$replay_oid" 2>/dev/null) ||
            return 1
        read -r observed parent extra <<<"$line"
        [[ "$observed" == "$replay_oid" && "$parent" == "$previous" &&
           -z "${extra:-}" ]] || return 1
        previous=$replay_oid
        REPLAY_RESULT_COMMITS[ordinal - 1]=$replay_oid
        REPLAY_PROOF_RECORDED=$ordinal
    done
    REPLAY_PROOF_TIP_OID=""
    if [[ "$REPLAY_PROOF_RECORDED" -gt 0 ]]; then
        REPLAY_PROOF_TIP_OID=$previous
    fi

    final_oid=$(read_ref "$REPLAY_PROOF_FINAL_REF") || return 1
    if [[ -n "$final_oid" ]]; then
        validate_commit_ref "$REPLAY_PROOF_FINAL_REF" "$final_oid" || return 1
        [[ "$REPLAY_PROOF_RECORDED" -eq "$REPLAY_SOURCE_COUNT" &&
           "$final_oid" == "$previous" ]] || return 1
        REPLAY_PROOF_STATE="complete"
        REPLAY_PROOF_FINAL_OID=$final_oid
        expected_count=$((2 + 2 * REPLAY_PROOF_RECORDED))
    else
        [[ "$REPLAY_PROOF_RECORDED" -lt "$REPLAY_SOURCE_COUNT" ]] || return 1
        REPLAY_PROOF_STATE="partial"
        REPLAY_PROOF_FINAL_OID=""
        expected_count=$((1 + 2 * REPLAY_PROOF_RECORDED))
    fi
    [[ "$actual_count" -eq "$expected_count" ]]
}

validate_complete_replay_proof() {
    local candidate=$1
    validate_replay_proof_prefix || return 1
    [[ "$REPLAY_PROOF_STATE" == "complete" &&
       "$REPLAY_PROOF_RECORDED" -eq "$REPLAY_SOURCE_COUNT" &&
       "$REPLAY_PROOF_FINAL_OID" == "$candidate" ]]
}

emit_complete_replay_proof_verifications() {
    local expected_tip=$1 ordinal source_ref replay_ref
    [[ "$REPLAY_PROOF_STATE" == "complete" &&
       "$REPLAY_PROOF_RECORDED" -eq "$REPLAY_SOURCE_COUNT" &&
       "$REPLAY_PROOF_FINAL_OID" == "$expected_tip" ]] || return 1
    printf '%s\n' "verify $REPLAY_PROOF_CONTEXT_REF $REPLAY_PROOF_GENERATION"
    for ((ordinal = 1; ordinal <= REPLAY_SOURCE_COUNT; ordinal++)); do
        source_ref=$(replay_ordinal_ref source "$ordinal") || return 1
        replay_ref=$(replay_ordinal_ref replay "$ordinal") || return 1
        printf '%s\n' \
            "verify $source_ref ${REPLAY_SOURCE_COMMITS[ordinal - 1]}" \
            "verify $replay_ref ${REPLAY_RESULT_COMMITS[ordinal - 1]}"
    done
    printf '%s\n' "verify $REPLAY_PROOF_FINAL_REF $expected_tip"
}

validate_candidate_lineage() {
    local candidate=$1
    is_oid "$candidate" || return 1
    [[ "$(git cat-file -t "$candidate" 2>/dev/null)" == "commit" ]] || return 1
    git merge-base --is-ancestor "$BASE_OID" "$candidate" >/dev/null 2>&1 ||
        return 1
    validate_complete_replay_proof "$candidate"
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
    if [[ "$NS_STATE" == "captured" ]]; then
        validate_commit_ref "$REBASE_WORK_REF" "$REBASE_WORK_OID" || return 1
        ref_equals "$BRANCH_REF" "$PRE_OID" || return 1
        if [[ "$REBASE_WORK_OID" != "$PRE_OID" ]]; then
            validate_candidate_lineage "$REBASE_WORK_OID" || return 1
        fi
    fi
    if [[ "$NS_STATE" == "candidate" ]]; then
        validate_commit_ref "$CANDIDATE_REF" "$CANDIDATE_OID" || return 1
        validate_commit_ref "$REBASE_WORK_REF" "$REBASE_WORK_OID" || return 1
        [[ "$REBASE_WORK_OID" == "$CANDIDATE_OID" ]] || return 1
        validate_candidate_lineage "$CANDIDATE_OID" || return 1
        ref_equals "$BRANCH_REF" "$PRE_OID" || return 1
    fi
    if [[ "$NS_STATE" == "rebased" || "$NS_STATE" == "submit-frozen" ]]; then
        validate_commit_ref "$REBASED_REF" "$REBASED_OID" || return 1
        validate_candidate_lineage "$REBASED_OID" || return 1
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
        captured|candidate) printf 'captured' ;;
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
    [[ "$PROVENANCE_READY" -eq 1 ]] ||
        indeterminate "hard conflict lacks exact Graph provenance for quarantine"
    terminalize_hard "$reason" || {
        echo "polecat-lease: terminal state did not verify; refusing to drain" >&2
        exit "$EXIT_INDETERMINATE"
    }
    if ! run_gc runtime drain-ack >/dev/null 2>&1; then
        echo "polecat-lease: terminal state verified but drain-ack failed; retry required" >&2
        exit "$EXIT_INDETERMINATE"
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
        "create $REBASE_WORK_REF $PRE_OID" \
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

record_rebase_candidate() {
    local result branch_oid
    prove_live_source_step
    [[ "$NS_STATE" == "captured" ]] ||
        indeterminate "rebase candidate recording requires captured lease state"
    [[ ! -d "$(git rev-parse --git-path rebase-merge)" &&
       ! -d "$(git rev-parse --git-path rebase-apply)" ]] ||
        indeterminate "cannot record a rebase candidate while rebase state is active"
    result=$(read_ref "$REBASE_WORK_REF") ||
        indeterminate "could not resolve the lease-owned rebase work ref"
    [[ -n "$result" ]] ||
        indeterminate "lease-owned rebase work ref is missing"
    validate_candidate_lineage "$result" ||
        indeterminate "lease-owned rebase result does not preserve captured lineage"
    branch_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read the canonical branch before candidate recording"
    [[ "$branch_oid" == "$PRE_OID" ]] ||
        hard_conflict "canonical branch changed before candidate recording"

    if {
        printf '%s\n' \
            start \
            "option no-deref" \
            "verify $CONTEXT_REF $CONTEXT_OID" \
            "verify $EXPECTED_REF $EXPECTED_OID" \
            "verify $PRE_REF $PRE_OID" \
            "verify $BASE_REF $BASE_OID" \
            "verify $BRANCH_REF $PRE_OID" \
            "verify $REBASE_WORK_REF $result"
        emit_complete_replay_proof_verifications "$result" || exit 1
        printf '%s\n' \
            "create $CANDIDATE_REF $result" \
            prepare \
            commit
    } | git update-ref --stdin >/dev/null 2>&1; then
        :
    else
        load_namespace || hard_conflict "candidate recording left partial refs"
        validate_namespace || hard_conflict "candidate recording raced different state"
        if [[ "$NS_STATE" == "captured" ]]; then
            indeterminate "candidate recording transaction failed without changing state"
        fi
        [[ "$NS_STATE" == "candidate" && "$CANDIDATE_OID" == "$result" ]] ||
            hard_conflict "another detached candidate won the lease evidence CAS"
    fi
    load_namespace || hard_conflict "recorded candidate namespace is incomplete"
    validate_namespace || hard_conflict "recorded candidate evidence failed validation"
    [[ "$NS_STATE" == "candidate" && "$CANDIDATE_OID" == "$result" ]] ||
        hard_conflict "recorded candidate evidence changed unexpectedly"
    sync_mirror || indeterminate "candidate lease mirror did not verify"
}

publish_rebase_result() {
    local result status
    prove_live_source_step
    [[ "$NS_STATE" == "candidate" ]] ||
        indeterminate "rebase publication requires lease-owned candidate evidence"
    validate_namespace ||
        hard_conflict "rebase candidate evidence is incomplete or incoherent"
    [[ ! -d "$(git rev-parse --git-path rebase-merge)" &&
       ! -d "$(git rev-parse --git-path rebase-apply)" ]] ||
        indeterminate "rebase is still in progress; resolve/continue it first"
    result=$(read_ref "$REBASE_WORK_REF") ||
        indeterminate "could not resolve lease-owned rebase work ref"
    [[ "$result" == "$CANDIDATE_OID" &&
       "$REBASE_WORK_OID" == "$CANDIDATE_OID" ]] ||
        hard_conflict "rebase work ref does not equal the lease-owned candidate"
    validate_candidate_lineage "$result" ||
        hard_conflict "lease-owned candidate no longer preserves captured lineage"
    status=$(git status --porcelain --untracked-files=all 2>/dev/null) ||
        indeterminate "could not inspect rebase worktree before publication"
    [[ -z "$status" ]] ||
        indeterminate "rebase worktree is dirty before publication"
    git switch --detach "$CANDIDATE_REF" >/dev/null 2>&1 ||
        indeterminate "could not detach from the lease-owned temporary branch"
    [[ "$(git rev-parse --verify HEAD 2>/dev/null)" == "$result" ]] ||
        indeterminate "detached publication HEAD does not equal the candidate"

    if {
        printf '%s\n' \
            start \
            "option no-deref" \
            "verify $CONTEXT_REF $CONTEXT_OID" \
            "verify $EXPECTED_REF $EXPECTED_OID" \
            "verify $PRE_REF $PRE_OID" \
            "verify $BASE_REF $BASE_OID"
        emit_complete_replay_proof_verifications "$result" || exit 1
        printf '%s\n' \
            "update $BRANCH_REF $result $PRE_OID" \
            "create $REBASED_REF $result" \
            "delete $CANDIDATE_REF $CANDIDATE_OID" \
            "delete $REBASE_WORK_REF $result" \
            prepare \
            commit
    } | git update-ref --stdin >/dev/null 2>&1; then
        REBASED_OID=$result
        CANDIDATE_OID=""
        REBASE_WORK_OID=""
    else
        load_namespace || hard_conflict "rebase publication left partial refs"
        validate_namespace || hard_conflict "rebase publication raced different state"
        if [[ "$NS_STATE" == "candidate" ]] &&
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

REBASE_STOPPED_OID=""
REBASE_ONTO_OID=""
CONFLICT_GENERATION=""
CONFLICT_NS=""
CONFLICT_CONTEXT_REF=""
CONFLICT_TREE_REF=""
CONFLICT_DONE_REF=""
CONFLICT_PARENT_OID=""
CONFLICT_PROOF_TREE=""
REBASE_LINE=""

read_rebase_line() {
    local file=$1 line count=0
    REBASE_LINE=""
    [[ -f "$file" && ! -L "$file" ]] || return 1
    while IFS= read -r line || [[ -n "$line" ]]; do
        count=$((count + 1))
        [[ "$count" -eq 1 ]] || return 1
        REBASE_LINE=$line
    done <"$file"
    [[ "$count" -eq 1 && -n "$REBASE_LINE" &&
       "$REBASE_LINE" != *$'\r'* && "$REBASE_LINE" != *$'\t'* ]]
}

emit_conflict_generation() {
    jq -cnS \
        --arg schema "gascity-polecat-conflict-generation-v1" \
        --arg lease_context "$CONTEXT_OID" \
        --arg source "$SOURCE_ID" \
        --arg root "$ROOT_BEAD_ID" \
        --arg step "$STEP_BEAD_ID" \
        --arg convoy "$CONVOY_ID" \
        --arg work_ref "$REBASE_WORK_REF" \
        --arg pre "$PRE_OID" \
        --arg base "$BASE_OID" \
        --arg stopped "$REBASE_STOPPED_OID" \
        --arg rebase_head "$REBASE_STOPPED_OID" \
        --arg onto "$REBASE_ONTO_OID" \
        '{
          schema: $schema,
          lease_context_oid: $lease_context,
          source: $source,
          workflow_root: $root,
          step: $step,
          input_convoy: $convoy,
          rebase_work_ref: $work_ref,
          pre_oid: $pre,
          base_oid: $base,
          stopped_oid: $stopped,
          rebase_head_oid: $rebase_head,
          onto_oid: $onto
        }'
}

load_active_rebase_generation() {
    local state_dir rebase_head
    state_dir=$(git rev-parse --git-path rebase-merge 2>/dev/null) || return 1
    [[ -d "$state_dir" && ! -L "$state_dir" ]] || return 1
    [[ ! -e "$(git rev-parse --git-path rebase-apply 2>/dev/null)" ]] ||
        return 1
    read_rebase_line "$state_dir/head-name" || return 1
    [[ "$REBASE_LINE" == "$REBASE_WORK_REF" ]] || return 1
    read_rebase_line "$state_dir/orig-head" || return 1
    [[ "$REBASE_LINE" == "$PRE_OID" ]] || return 1
    read_rebase_line "$state_dir/onto" || return 1
    REBASE_ONTO_OID=$REBASE_LINE
    [[ "$REBASE_ONTO_OID" == "$BASE_OID" ]] || return 1
    read_rebase_line "$state_dir/stopped-sha" || return 1
    REBASE_STOPPED_OID=$REBASE_LINE
    is_oid "$REBASE_STOPPED_OID" || return 1
    [[ "$(git cat-file -t "$REBASE_STOPPED_OID" 2>/dev/null)" == "commit" ]] ||
        return 1
    rebase_head=$(git rev-parse --verify REBASE_HEAD 2>/dev/null) || return 1
    [[ "$rebase_head" == "$REBASE_STOPPED_OID" ]] || return 1
    ref_equals "$BRANCH_REF" "$PRE_OID" || return 1
    ref_equals "$REBASE_WORK_REF" "$PRE_OID" || return 1
    CONFLICT_GENERATION=$(emit_conflict_generation |
        git hash-object --stdin 2>/dev/null) || return 1
    is_oid "$CONFLICT_GENERATION" || return 1
    CONFLICT_NS="refs/gascity/polecat-conflicts/v1/$LEASE_KEY/$CONFLICT_GENERATION"
    CONFLICT_CONTEXT_REF="$CONFLICT_NS/context"
    CONFLICT_TREE_REF="$CONFLICT_NS/tree"
    CONFLICT_DONE_REF="$CONFLICT_NS/done"
    for ref in "$CONFLICT_CONTEXT_REF" "$CONFLICT_TREE_REF" \
               "$CONFLICT_DONE_REF"; do
        git check-ref-format "$ref" >/dev/null 2>&1 || return 1
    done
}

conflict_stage_diagnostic() {
    echo "POLECAT_LEASE_REBASE_CONFLICT: stage this exact lease-owned conflict generation:" >&2
    printf '  gc gastown polecat-step exec --convoy %q --step-ref %q -- gc gastown polecat-conflict stage\n' \
        "$CONVOY_ID" "$EXPECTED_STEP_REF" >&2
    echo "Then rerun only: gc gastown polecat-workspace execute" >&2
}

require_conflict_done() {
    local context_oid tree_oid done_oid context_body actual_tree ref
    local unmerged unstaged untracked
    CONFLICT_PARENT_OID=""
    CONFLICT_PROOF_TREE=""
    load_active_rebase_generation || return 1
    for ref in "$CONFLICT_CONTEXT_REF" "$CONFLICT_TREE_REF" \
               "$CONFLICT_DONE_REF"; do
        git symbolic-ref -q "$ref" >/dev/null 2>&1 && return 1
    done
    context_oid=$(read_ref "$CONFLICT_CONTEXT_REF") || return 1
    tree_oid=$(read_ref "$CONFLICT_TREE_REF") || return 1
    done_oid=$(read_ref "$CONFLICT_DONE_REF") || return 1
    is_oid "$context_oid" && is_oid "$tree_oid" && is_oid "$done_oid" ||
        return 1
    [[ "$tree_oid" == "$done_oid" ]] || return 1
    [[ "$(git cat-file -t "$context_oid" 2>/dev/null)" == "blob" &&
       "$(git cat-file -t "$tree_oid" 2>/dev/null)" == "tree" ]] || return 1
    context_body=$(git cat-file blob "$context_oid" 2>/dev/null) || return 1
    CONFLICT_PARENT_OID=$(printf '%s' "$context_body" |
        jq -er '.conflict_parent_oid' 2>/dev/null) || return 1
    is_oid "$CONFLICT_PARENT_OID" || return 1
    [[ "$(git cat-file -t "$CONFLICT_PARENT_OID" 2>/dev/null)" == "commit" ]] ||
        return 1
    printf '%s' "$context_body" | jq -e \
        --arg schema "gascity-polecat-conflict-context-v1" \
        --arg generation "$CONFLICT_GENERATION" \
        --arg lease_context "$CONTEXT_OID" \
        --arg source "$SOURCE_ID" --arg root "$ROOT_BEAD_ID" \
        --arg step "$STEP_BEAD_ID" --arg convoy "$CONVOY_ID" \
        --arg work_ref "$REBASE_WORK_REF" \
        --arg pre "$PRE_OID" --arg base "$BASE_OID" \
        --arg stopped "$REBASE_STOPPED_OID" --arg onto "$REBASE_ONTO_OID" \
        --arg parent "$CONFLICT_PARENT_OID" --arg tree "$tree_oid" '
        type == "object" and .schema == $schema and
        .generation == $generation and .lease_context_oid == $lease_context and
        .source == $source and .workflow_root == $root and .step == $step and
        .input_convoy == $convoy and .rebase_work_ref == $work_ref and
        .pre_oid == $pre and .base_oid == $base and
        .stopped_oid == $stopped and .rebase_head_oid == $stopped and
        .onto_oid == $onto and .conflict_parent_oid == $parent and
        .expected_tree_oid == $tree and
        (.unmerged_tuple_digest | type) == "string" and
        (.unmerged_tuple_digest | length) > 0' >/dev/null 2>&1 || return 1
    unmerged=$(git ls-files -u 2>/dev/null) || return 1
    [[ -z "$unmerged" ]] || return 1
    unstaged=$(git diff --name-only 2>/dev/null) || return 1
    [[ -z "$unstaged" ]] || return 1
    untracked=$(git ls-files --others --exclude-standard 2>/dev/null) ||
        return 1
    [[ -z "$untracked" ]] || return 1
    git diff --cached --check >/dev/null 2>&1 || return 1
    actual_tree=$(git write-tree 2>/dev/null) || return 1
    [[ "$actual_tree" == "$tree_oid" ]] || return 1
    CONFLICT_PROOF_TREE=$tree_oid
}

commit_replays_stopped_conflict() {
    local commit=$1 parent=$2 stopped=$3 tree=$4
    local line observed parent_observed extra author_a author_b message_a message_b
    line=$(git rev-list --parents -n 1 "$commit" 2>/dev/null) || return 1
    read -r observed parent_observed extra <<<"$line"
    [[ "$observed" == "$commit" && "$parent_observed" == "$parent" &&
       -z "$extra" ]] || return 1
    [[ "$(git rev-parse "$commit^{tree}" 2>/dev/null)" == "$tree" ]] ||
        return 1
    author_a=$(git show -s --format='%an%n%ae%n%aI' "$commit" |
        git hash-object --stdin 2>/dev/null) || return 1
    author_b=$(git show -s --format='%an%n%ae%n%aI' "$stopped" |
        git hash-object --stdin 2>/dev/null) || return 1
    message_a=$(git show -s --format='%B' "$commit" |
        git hash-object --stdin 2>/dev/null) || return 1
    message_b=$(git show -s --format='%B' "$stopped" |
        git hash-object --stdin 2>/dev/null) || return 1
    [[ "$author_a" == "$author_b" && "$message_a" == "$message_b" ]]
}

materialize_empty_conflict_commit() {
    local current_head parent_tree
    current_head=$(git rev-parse --verify HEAD 2>/dev/null) || return 1
    parent_tree=$(git rev-parse "$CONFLICT_PARENT_OID^{tree}" 2>/dev/null) ||
        return 1
    if [[ "$current_head" == "$CONFLICT_PARENT_OID" ]]; then
        [[ "$CONFLICT_PROOF_TREE" == "$parent_tree" ]] || return 0
        if ! GIT_EDITOR=true git commit --allow-empty \
            --no-verify -C "$REBASE_STOPPED_OID" >/dev/null 2>&1; then
            current_head=$(git rev-parse --verify HEAD 2>/dev/null) ||
                return 1
            commit_replays_stopped_conflict \
                "$current_head" "$CONFLICT_PARENT_OID" \
                "$REBASE_STOPPED_OID" "$CONFLICT_PROOF_TREE" ||
                return 1
        fi
        current_head=$(git rev-parse --verify HEAD 2>/dev/null) || return 1
        commit_replays_stopped_conflict \
            "$current_head" "$CONFLICT_PARENT_OID" \
            "$REBASE_STOPPED_OID" "$CONFLICT_PROOF_TREE"
        return
    fi
    # A crash may occur after the exact empty commit is materialized but before
    # rebase --continue advances the sequencer.  Accept only that one replay.
    commit_replays_stopped_conflict \
        "$current_head" "$CONFLICT_PARENT_OID" \
        "$REBASE_STOPPED_OID" "$CONFLICT_PROOF_TREE"
}

REPLAY_EXEC_ORDINAL=0
REPLAY_SEQUENCE_DONE_COUNT=0
REPLAY_SEQUENCE_LAST_DONE_LINE=""
REPLAY_SEQUENCE_FIRST_TODO_LINE=""

replay_pick_line_matches() {
    local line=$1 source_oid=$2
    [[ "$line" == "pick $source_oid" ||
       "$line" == "pick $source_oid "* ]]
}

load_trusted_replay_sequence() {
    local state_dir done_file todo_file backup_file line source_oid
    local ordinal line_index backup_commands_done=0 current_branch
    local -a done_lines=() todo_lines=() sequence_lines=() backup_lines=()

    initialize_replay_proof || return 1
    state_dir=$(git rev-parse --git-path rebase-merge 2>/dev/null) || return 1
    [[ -d "$state_dir" && ! -L "$state_dir" ]] || return 1
    [[ ! -e "$(git rev-parse --git-path rebase-apply 2>/dev/null)" ]] ||
        return 1
    read_rebase_line "$state_dir/head-name" || return 1
    [[ "$REBASE_LINE" == "$REBASE_WORK_REF" ]] || return 1
    read_rebase_line "$state_dir/orig-head" || return 1
    [[ "$REBASE_LINE" == "$PRE_OID" ]] || return 1
    read_rebase_line "$state_dir/onto" || return 1
    [[ "$REBASE_LINE" == "$BASE_OID" ]] || return 1
    [[ -f "$state_dir/interactive" && ! -L "$state_dir/interactive" &&
       -f "$state_dir/keep_redundant_commits" &&
       ! -L "$state_dir/keep_redundant_commits" &&
       -f "$state_dir/no-reschedule-failed-exec" &&
       ! -L "$state_dir/no-reschedule-failed-exec" ]] || return 1

    done_file="$state_dir/done"
    todo_file="$state_dir/git-rebase-todo"
    backup_file="$state_dir/git-rebase-todo.backup"
    for file in "$done_file" "$todo_file" "$backup_file"; do
        [[ -f "$file" && ! -L "$file" ]] || return 1
    done
    mapfile -t done_lines <"$done_file" || return 1
    mapfile -t todo_lines <"$todo_file" || return 1
    sequence_lines=("${done_lines[@]}" "${todo_lines[@]}")
    [[ "${#sequence_lines[@]}" -eq $((2 * REPLAY_SOURCE_COUNT)) ]] ||
        return 1

    for ((ordinal = 1; ordinal <= REPLAY_SOURCE_COUNT; ordinal++)); do
        line_index=$((2 * (ordinal - 1)))
        source_oid=${REPLAY_SOURCE_COMMITS[ordinal - 1]}
        replay_pick_line_matches "${sequence_lines[line_index]}" "$source_oid" ||
            return 1
        [[ "${sequence_lines[line_index + 1]}" == \
           "exec $REPLAY_RECORDER_COMMAND" ]] || return 1
    done

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$backup_commands_done" -eq 1 ]]; then
            continue
        fi
        if [[ -z "$line" ]]; then
            backup_commands_done=1
            continue
        fi
        backup_lines+=("$line")
    done <"$backup_file"
    [[ "$backup_commands_done" -eq 1 &&
       "${#backup_lines[@]}" -eq $((2 * REPLAY_SOURCE_COUNT)) ]] ||
        return 1
    for ((ordinal = 1; ordinal <= REPLAY_SOURCE_COUNT; ordinal++)); do
        line_index=$((2 * (ordinal - 1)))
        source_oid=${REPLAY_SOURCE_COMMITS[ordinal - 1]}
        replay_pick_line_matches "${backup_lines[line_index]}" "$source_oid" ||
            return 1
        [[ "${backup_lines[line_index + 1]}" == \
           "exec $REPLAY_RECORDER_COMMAND" ]] || return 1
    done

    REPLAY_SEQUENCE_DONE_COUNT=${#done_lines[@]}
    REPLAY_SEQUENCE_LAST_DONE_LINE=""
    if [[ "$REPLAY_SEQUENCE_DONE_COUNT" -gt 0 ]]; then
        REPLAY_SEQUENCE_LAST_DONE_LINE=${done_lines[REPLAY_SEQUENCE_DONE_COUNT - 1]}
    fi
    REPLAY_SEQUENCE_FIRST_TODO_LINE=""
    if [[ "${#todo_lines[@]}" -gt 0 ]]; then
        REPLAY_SEQUENCE_FIRST_TODO_LINE=${todo_lines[0]}
    fi
    current_branch=$(git branch --show-current 2>/dev/null) || return 1
    [[ -z "$current_branch" ]] || return 1
    ref_equals "$BRANCH_REF" "$PRE_OID" || return 1
    ref_equals "$REBASE_WORK_REF" "$PRE_OID" || return 1
}

load_trusted_replay_exec_sequence() {
    local status
    load_trusted_replay_sequence || return 1
    [[ "$REPLAY_SEQUENCE_DONE_COUNT" -ge 2 &&
       $((REPLAY_SEQUENCE_DONE_COUNT % 2)) -eq 0 ]] || return 1
    REPLAY_EXEC_ORDINAL=$((REPLAY_SEQUENCE_DONE_COUNT / 2))
    [[ "$REPLAY_EXEC_ORDINAL" -ge 1 &&
       "$REPLAY_EXEC_ORDINAL" -le "$REPLAY_SOURCE_COUNT" &&
       "$REPLAY_SEQUENCE_LAST_DONE_LINE" == \
         "exec $REPLAY_RECORDER_COMMAND" ]] || return 1
    status=$(git status --porcelain --untracked-files=all 2>/dev/null) ||
        return 1
    [[ -z "$status" ]] || return 1
}

load_trusted_replay_conflict_sequence() {
    local ordinal source_oid
    load_trusted_replay_sequence || return 1
    [[ "$REPLAY_SEQUENCE_DONE_COUNT" -ge 1 &&
       $((REPLAY_SEQUENCE_DONE_COUNT % 2)) -eq 1 ]] || return 1
    ordinal=$(((REPLAY_SEQUENCE_DONE_COUNT + 1) / 2))
    [[ "$ordinal" -ge 1 && "$ordinal" -le "$REPLAY_SOURCE_COUNT" ]] ||
        return 1
    source_oid=${REPLAY_SOURCE_COMMITS[ordinal - 1]}
    replay_pick_line_matches "$REPLAY_SEQUENCE_LAST_DONE_LINE" "$source_oid" ||
        return 1
    [[ "$REPLAY_SEQUENCE_FIRST_TODO_LINE" == \
       "exec $REPLAY_RECORDER_COMMAND" &&
       "$REBASE_STOPPED_OID" == "$source_oid" ]] || return 1
    validate_replay_proof_prefix || return 1
    [[ "$REPLAY_PROOF_RECORDED" -eq $((ordinal - 1)) ]]
}

replay_commit_preserves_source_identity() {
    local replay=$1 source=$2 replay_author source_author
    local replay_message source_message
    replay_author=$(git show -s --format='%an%n%ae%n%aI' "$replay" |
        git hash-object --stdin 2>/dev/null) || return 1
    source_author=$(git show -s --format='%an%n%ae%n%aI' "$source" |
        git hash-object --stdin 2>/dev/null) || return 1
    replay_message=$(git show -s --format='%B' "$replay" |
        git hash-object --stdin 2>/dev/null) || return 1
    source_message=$(git show -s --format='%B' "$source" |
        git hash-object --stdin 2>/dev/null) || return 1
    [[ "$replay_author" == "$source_author" &&
       "$replay_message" == "$source_message" ]]
}

emit_replay_record_transaction() {
    local ordinal=$1 source_ref=$2 replay_ref=$3
    local source_oid=$4 replay_oid=$5 previous_source_ref previous_replay_ref

    printf '%s\n' \
        start \
        "option no-deref" \
        "verify $CONTEXT_REF $CONTEXT_OID" \
        "verify $EXPECTED_REF $EXPECTED_OID" \
        "verify $PRE_REF $PRE_OID" \
        "verify $BASE_REF $BASE_OID" \
        "verify $BRANCH_REF $PRE_OID" \
        "verify $REBASE_WORK_REF $PRE_OID"
    if [[ "$ordinal" -eq 1 ]]; then
        printf '%s\n' "create $REPLAY_PROOF_CONTEXT_REF $REPLAY_PROOF_GENERATION"
    else
        previous_source_ref=$(replay_ordinal_ref source "$((ordinal - 1))") ||
            return 1
        previous_replay_ref=$(replay_ordinal_ref replay "$((ordinal - 1))") ||
            return 1
        printf '%s\n' \
            "verify $REPLAY_PROOF_CONTEXT_REF $REPLAY_PROOF_GENERATION" \
            "verify $previous_source_ref ${REPLAY_SOURCE_COMMITS[ordinal - 2]}" \
            "verify $previous_replay_ref $REPLAY_PROOF_TIP_OID"
    fi
    printf '%s\n' \
        "create $source_ref $source_oid" \
        "create $replay_ref $replay_oid"
    if [[ "$ordinal" -eq "$REPLAY_SOURCE_COUNT" ]]; then
        printf '%s\n' "create $REPLAY_PROOF_FINAL_REF $replay_oid"
    fi
    printf '%s\n' prepare commit
}

record_replay_action() {
    local ordinal source_oid replay_oid source_ref replay_ref
    local previous written line observed parent extra

    prove_live_source_step
    [[ "$NS_STATE" == "captured" &&
       "$REBASE_WORK_OID" == "$PRE_OID" ]] ||
        hard_conflict "internal replay recorder requires the frozen captured lease"
    validate_replay_proof_prefix ||
        hard_conflict "existing replay proof prefix is incomplete or incoherent"
    load_trusted_replay_exec_sequence ||
        hard_conflict "internal replay recorder is outside the exact trusted rebase sequence"
    ordinal=$REPLAY_EXEC_ORDINAL
    [[ "$REPLAY_PROOF_RECORDED" -eq $((ordinal - 1)) ]] ||
        hard_conflict "trusted rebase recorder ordinal does not extend its durable prefix"

    source_oid=${REPLAY_SOURCE_COMMITS[ordinal - 1]}
    replay_oid=$(git rev-parse --verify HEAD 2>/dev/null) ||
        indeterminate "could not resolve the trusted replay commit"
    is_oid "$replay_oid" || indeterminate "trusted replay commit id is invalid"
    previous=$BASE_OID
    if [[ "$ordinal" -gt 1 ]]; then
        previous=$REPLAY_PROOF_TIP_OID
    fi
    line=$(git rev-list --parents -n 1 "$replay_oid" 2>/dev/null) ||
        indeterminate "could not inspect the trusted replay parent"
    read -r observed parent extra <<<"$line"
    [[ "$observed" == "$replay_oid" && "$parent" == "$previous" &&
       -z "${extra:-}" ]] ||
        hard_conflict "trusted replay commit does not extend the exact prior replay"
    replay_commit_preserves_source_identity "$replay_oid" "$source_oid" ||
        hard_conflict "trusted replay commit changed source author or message identity"

    source_ref=$(replay_ordinal_ref source "$ordinal") ||
        indeterminate "could not derive the replay source proof ref"
    replay_ref=$(replay_ordinal_ref replay "$ordinal") ||
        indeterminate "could not derive the replay result proof ref"
    if [[ "$ordinal" -eq 1 ]]; then
        written=$(emit_replay_proof_context |
            git hash-object -w --stdin 2>/dev/null) ||
            indeterminate "could not write the replay proof context object"
        [[ "$written" == "$REPLAY_PROOF_GENERATION" ]] ||
            indeterminate "written replay proof context changed its content address"
    fi

    if emit_replay_record_transaction \
            "$ordinal" "$source_ref" "$replay_ref" \
            "$source_oid" "$replay_oid" |
        git update-ref --stdin >/dev/null 2>&1; then
        :
    else
        validate_replay_proof_prefix ||
            hard_conflict "replay proof transaction left incoherent evidence"
        if [[ "$REPLAY_PROOF_RECORDED" -eq $((ordinal - 1)) ]]; then
            indeterminate "replay proof transaction failed without recording its ordinal"
        fi
        [[ "$REPLAY_PROOF_RECORDED" -eq "$ordinal" ]] ||
            hard_conflict "another replay proof writer advanced a different ordinal"
    fi

    validate_replay_proof_prefix ||
        hard_conflict "recorded replay proof failed exact readback"
    [[ "$REPLAY_PROOF_RECORDED" -eq "$ordinal" ]] ||
        hard_conflict "recorded replay proof did not advance exactly one ordinal"
    if [[ "$ordinal" -eq "$REPLAY_SOURCE_COUNT" ]]; then
        [[ "$REPLAY_PROOF_STATE" == "complete" &&
           "$REPLAY_PROOF_TIP_OID" == "$replay_oid" &&
           "$REPLAY_PROOF_FINAL_OID" == "$replay_oid" ]] ||
            hard_conflict "final replay ordinal did not atomically seal its exact tip"
    else
        [[ "$REPLAY_PROOF_STATE" == "partial" &&
           "$REPLAY_PROOF_TIP_OID" == "$replay_oid" &&
           -z "$REPLAY_PROOF_FINAL_OID" ]] ||
            hard_conflict "nonfinal replay ordinal did not retain its exact prefix tip"
    fi
    load_trusted_replay_exec_sequence ||
        hard_conflict "trusted rebase sequence changed during replay proof recording"
}

workspace_action() {
    local branch_oid rebase_help

    if [[ "$NS_STATE" == "candidate" ]]; then
        read_push_remote
        case "$REMOTE_STATE" in
            present)
                OBSERVED_REMOTE=$REMOTE_OID
                [[ "$REMOTE_OID" == "$EXPECTED_OID" ]] ||
                    hard_conflict "remote moved after rebase candidate recording"
                ;;
            missing|malformed)
                OBSERVED_REMOTE=${REMOTE_OID:-missing}
                hard_conflict "candidate-bound remote branch is missing or malformed"
                ;;
            unreadable)
                indeterminate "could not read candidate-bound push remote"
                ;;
        esac
        [[ "$REBASE_WORK_OID" == "$CANDIDATE_OID" ]] ||
            hard_conflict "lease-owned rebase work ref no longer presents the candidate"
        publish_rebase_result
        return 0
    fi

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
            indeterminate "could not read branch before lease-owned rebase"
        [[ "$branch_oid" == "$PRE_OID" ]] ||
            hard_conflict "canonical branch changed before lease-owned rebase"
        if [[ -d "$(git rev-parse --git-path rebase-merge)" ||
              -d "$(git rev-parse --git-path rebase-apply)" ]]; then
            load_active_rebase_generation ||
                hard_conflict "active rebase does not match the captured lease generation"
            load_trusted_replay_conflict_sequence ||
                hard_conflict "active conflict rebase changed its trusted replay sequence"
            if [[ -n "$(git ls-files -u 2>/dev/null)" ]]; then
                conflict_stage_diagnostic
                exit "$EXIT_INDETERMINATE"
            fi
            require_conflict_done || {
                conflict_stage_diagnostic
                indeterminate "active rebase lacks an exact completed conflict-stage proof"
            }
            materialize_empty_conflict_commit ||
                indeterminate "could not preserve the exact empty conflict commit"
            [[ -z "$(git ls-files -u 2>/dev/null)" &&
               -z "$(git diff --name-only 2>/dev/null)" &&
               -z "$(git ls-files --others --exclude-standard 2>/dev/null)" &&
               "$(git write-tree 2>/dev/null)" == "$CONFLICT_PROOF_TREE" ]] ||
                indeterminate "conflict proof changed before rebase continuation"
            git diff --cached --check >/dev/null 2>&1 ||
                indeterminate "conflict proof failed its final continuation check"
            load_active_rebase_generation &&
                load_trusted_replay_conflict_sequence ||
                hard_conflict "trusted replay sequence changed before conflict continuation"
            if ! GIT_EDITOR=true git rebase --continue; then
                if [[ -d "$(git rev-parse --git-path rebase-merge)" ||
                      -d "$(git rev-parse --git-path rebase-apply)" ]]; then
                    load_active_rebase_generation ||
                        hard_conflict "continued rebase left an unbound conflict generation"
                    load_trusted_replay_conflict_sequence ||
                        hard_conflict "continued rebase changed its trusted replay sequence"
                    conflict_stage_diagnostic
                    exit "$EXIT_INDETERMINATE"
                fi
                indeterminate "git rebase --continue failed without lease-owned success evidence"
            fi
            load_namespace ||
                hard_conflict "completed rebase left partial lease refs"
            validate_namespace ||
                hard_conflict "completed rebase changed lease-owned work authority"
            record_rebase_candidate
            publish_rebase_result
            return 0
        fi
        if [[ "$REBASE_WORK_OID" != "$PRE_OID" ]]; then
            validate_candidate_lineage "$REBASE_WORK_OID" ||
                hard_conflict "lease-owned completed rebase lacks its exact replay proof"
            record_rebase_candidate
            publish_rebase_result
            return 0
        fi
        validate_replay_proof_prefix ||
            hard_conflict "replay proof namespace is incoherent before rebase start"
        [[ "$REPLAY_PROOF_STATE" == "absent" ]] ||
            hard_conflict "captured lease has orphaned replay proof without an active rebase"
        git switch "$REBASE_WORK_BRANCH" >/dev/null 2>&1 ||
            indeterminate "could not check out the lease-owned temporary rebase branch"
        rebase_help=$(LC_ALL=C git rebase -h 2>&1 || true)
        [[ "$rebase_help" == *"reapply-cherry-picks"* &&
           "$rebase_help" == *"--empty"* &&
           "$rebase_help" == *"--exec"* ]] ||
            indeterminate "Git lacks the count-preserving rebase policy"
        if ! GIT_CONFIG_PARAMETERS= \
             GIT_CONFIG_COUNT=6 \
             GIT_CONFIG_KEY_0=rebase.abbreviateCommands \
             GIT_CONFIG_VALUE_0=false \
             GIT_CONFIG_KEY_1=rebase.rescheduleFailedExec \
             GIT_CONFIG_VALUE_1=false \
             GIT_CONFIG_KEY_2=rebase.autoSquash \
             GIT_CONFIG_VALUE_2=false \
             GIT_CONFIG_KEY_3=rebase.updateRefs \
             GIT_CONFIG_VALUE_3=false \
             GIT_CONFIG_KEY_4=rebase.rebaseMerges \
             GIT_CONFIG_VALUE_4=false \
             GIT_CONFIG_KEY_5=rebase.instructionFormat \
             GIT_CONFIG_VALUE_5=%s \
             git rebase --merge --reapply-cherry-picks --empty=keep \
                 --exec "$REPLAY_RECORDER_COMMAND" "$BASE_REF"; then
            if [[ -d "$(git rev-parse --git-path rebase-merge)" ||
                  -d "$(git rev-parse --git-path rebase-apply)" ]]; then
                load_active_rebase_generation ||
                    hard_conflict "failed rebase left an unbound conflict generation"
                load_trusted_replay_conflict_sequence ||
                    hard_conflict "failed rebase changed its trusted replay sequence"
                conflict_stage_diagnostic
                exit "$EXIT_INDETERMINATE"
            fi
            load_namespace ||
                hard_conflict "failed rebase left partial lease refs"
            validate_namespace ||
                hard_conflict "failed rebase changed lease-owned authority incoherently"
            indeterminate "git rebase returned nonzero; retry will inspect only the lease-owned work ref"
        fi
        load_namespace ||
            hard_conflict "completed rebase left partial lease refs"
        validate_namespace ||
            hard_conflict "completed rebase changed lease-owned work authority"
        record_rebase_candidate
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
    [[ "$NS_STATE" == "candidate" ]] ||
        indeterminate "publish-rebase requires exact lease-owned candidate evidence"
    local branch_oid
    branch_oid=$(read_ref "$BRANCH_REF") ||
        indeterminate "could not read branch before explicit rebase publication"
    [[ "$branch_oid" == "$PRE_OID" ]] ||
        hard_conflict "branch changed before explicit rebase publication"
    [[ "$REBASE_WORK_OID" == "$CANDIDATE_OID" ]] ||
        hard_conflict "rebase work ref does not equal the recorded candidate"
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
    if {
        printf '%s\n' \
            start \
            "option no-deref" \
            "verify $CONTEXT_REF $CONTEXT_OID" \
            "verify $EXPECTED_REF $EXPECTED_OID" \
            "verify $PRE_REF $PRE_OID" \
            "verify $BASE_REF $BASE_OID" \
            "verify $REBASED_REF $REBASED_OID" \
            "verify $BRANCH_REF $head_oid"
        emit_complete_replay_proof_verifications "$REBASED_OID" || exit 1
        printf '%s\n' \
            "create $SUBMIT_REF $head_oid" \
            prepare \
            commit
    } | git update-ref --stdin >/dev/null 2>&1; then
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
    record-replay)
        record_replay_action
        ;;
    submit)
        submit_action
        ;;
esac

ACTION_RC=$?
exit "$ACTION_RC"
