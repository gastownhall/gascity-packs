#!/bin/sh
# Idempotently retire a Gastown task artifact after a terminal handoff.
#
# Usage: task-artifact-cleanup.sh <work-bead-id>
#
# Required environment:
#   GC_CITY_PATH  physical Gas City root
#   GC_RIG        rig name
#   GC_RIG_ROOT   canonical rig repository

set -eu

WORK=${1:-}
if [ "$#" -ne 1 ] || [ -z "$WORK" ]; then
    echo "usage: task-artifact-cleanup.sh <work-bead-id>" >&2
    exit 2
fi

case "$WORK" in
    "."|".."|*[!A-Za-z0-9._-]*)
        echo "ARTIFACT_CLEANUP_BLOCKED unsafe work bead id: $WORK" >&2
        exit 2
        ;;
esac

if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_RIG:-}" ] ||
   [ -z "${GC_RIG_ROOT:-}" ]; then
    echo "ARTIFACT_CLEANUP_BLOCKED GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required" >&2
    exit 2
fi
case "$GC_RIG" in
    "."|".."|*[!A-Za-z0-9._-]*)
        echo "ARTIFACT_CLEANUP_BLOCKED unsafe rig name: $GC_RIG" >&2
        exit 2
        ;;
esac

for required_command in gc git jq; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        echo "ARTIFACT_CLEANUP_BLOCKED missing command: $required_command" >&2
        exit 2
    fi
done

CITY_ROOT=$(CDPATH= cd -- "$GC_CITY_PATH" 2>/dev/null && pwd -P) || {
    echo "ARTIFACT_CLEANUP_BLOCKED city root is missing: $GC_CITY_PATH" >&2
    exit 2
}
RIG_ROOT=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) || {
    echo "ARTIFACT_CLEANUP_BLOCKED rig root is missing: $GC_RIG_ROOT" >&2
    exit 2
}
RIG_NAMESPACE="$CITY_ROOT/.gc/worktrees/$GC_RIG"
RIG_NAMESPACE_REAL=$(CDPATH= cd -- "$RIG_NAMESPACE" 2>/dev/null && pwd -P) || {
    echo "ARTIFACT_CLEANUP_BLOCKED rig worktree namespace is missing: $RIG_NAMESPACE" >&2
    exit 2
}
if [ "$RIG_NAMESPACE_REAL" != "$RIG_NAMESPACE" ]; then
    echo "ARTIFACT_CLEANUP_BLOCKED rig worktree namespace is redirected: $RIG_NAMESPACE" >&2
    exit 2
fi

artifact_git_common_dir() {
    repo_dir=$1
    common_dir=$(git -C "$repo_dir" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) || return 1
    (CDPATH= cd -- "$common_dir" 2>/dev/null && pwd -P)
}

task_artifact_path_shape() {
    shaped_candidate=$1
    shaped_bead=$2
    shaped_canonical="$RIG_NAMESPACE_REAL/artifacts/worktrees/$shaped_bead"
    shaped_worktrees_parent=
    shaped_provider_home=
    shaped_provider_root=
    shaped_provider_name=

    [ "$(basename -- "$shaped_candidate")" = "$shaped_bead" ] || return 1
    [ "$(basename -- "$(dirname -- "$shaped_candidate")")" = worktrees ] ||
        return 1
    if [ "$shaped_candidate" = "$shaped_canonical" ]; then
        return 0
    fi

    shaped_worktrees_parent=$(dirname -- "$shaped_candidate")
    shaped_provider_home=$(dirname -- "$shaped_worktrees_parent")
    shaped_provider_root=$(dirname -- "$shaped_provider_home")
    shaped_provider_name=$(basename -- "$shaped_provider_home")
    [ "$shaped_provider_root" = "$RIG_NAMESPACE_REAL/polecats" ] || return 1
    case "$shaped_provider_name" in
        ""|"."|".."|*[!A-Za-z0-9._-]*) return 1 ;;
    esac
}

validate_task_artifact() {
    candidate=$1
    bead_id=$2
    candidate_real=
    candidate_top=
    candidate_common=
    rig_common=

    [ -n "$candidate" ] && [ -d "$candidate" ] || return 1
    candidate_real=$(CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P) ||
        return 1
    task_artifact_path_shape "$candidate_real" "$bead_id" || return 1

    candidate_top=$(git -C "$candidate_real" rev-parse \
        --show-toplevel 2>/dev/null) || return 1
    candidate_top=$(CDPATH= cd -- "$candidate_top" 2>/dev/null && pwd -P) ||
        return 1
    [ "$candidate_top" = "$candidate_real" ] || return 1
    candidate_common=$(artifact_git_common_dir "$candidate_real") || return 1
    rig_common=$(artifact_git_common_dir "$RIG_ROOT") || return 1
    [ "$candidate_common" = "$rig_common" ] || return 1

    printf '%s\n' "$candidate_real"
}

bd_show_work() {
    gc bd --rig "$GC_RIG" show "$WORK" --json
}

bd_update_work() {
    gc bd --rig "$GC_RIG" update "$WORK" "$@"
}

record_cleanup_state() {
    state=$1
    bd_update_work --set-metadata artifact_cleanup_state="$state"
}

complete_without_path() {
    bd_update_work \
        --unset-metadata artifact_dir \
        --unset-metadata work_dir \
        --set-metadata artifact_cleanup_state=complete
    echo "ARTIFACT_CLEANUP_COMPLETE work=$WORK artifact=absent"
}

WORK_JSON=$(bd_show_work) || {
    echo "ARTIFACT_CLEANUP_BLOCKED could not read work bead $WORK" >&2
    exit 1
}
WORK_RECORD=$(printf '%s' "$WORK_JSON" | jq -ce '
    if type == "array" and length == 1 and (.[0] | type) == "object" and
       ((.[0].metadata // {}) | type) == "object"
    then .[0]
    else error("expected exactly one work bead object")
    end
') || {
    echo "ARTIFACT_CLEANUP_BLOCKED invalid work bead response for $WORK" >&2
    exit 1
}

STATUS=$(printf '%s' "$WORK_RECORD" | jq -r '.status // empty')
META=$(printf '%s' "$WORK_RECORD" | jq -c '.metadata // {}')
HANDOFF_RESULT=$(printf '%s' "$META" | jq -r '.merge_result // empty')
CLEANUP_STATE=$(printf '%s' "$META" | jq -r '.artifact_cleanup_state // empty')
EXPECTED_ARTIFACT_SHA=$(printf '%s' "$META" |
    jq -r '.artifact_source_sha // empty')
TASK_ARTIFACT=$(printf '%s' "$META" | jq -r '
    if ((.artifact_dir // "") | length) > 0
    then .artifact_dir
    else (.work_dir // empty)
    end')

TERMINAL=false
if [ "$STATUS" = closed ]; then
    case "$HANDOFF_RESULT" in
        merged|already_merged|pull_request|pull_request_merged|mr_merged)
            TERMINAL=true
            ;;
    esac
fi

if [ "$TERMINAL" != true ]; then
    if [ "$CLEANUP_STATE" != pending ]; then
        record_cleanup_state pending || {
            echo "ARTIFACT_CLEANUP_BLOCKED could not record pending state for $WORK" >&2
            exit 1
        }
    fi
    echo "ARTIFACT_CLEANUP_DEFERRED work=$WORK status=${STATUS:-unknown} result=${HANDOFF_RESULT:-unknown}"
    exit 0
fi

if [ -z "$TASK_ARTIFACT" ]; then
    if [ "$CLEANUP_STATE" = complete ]; then
        echo "ARTIFACT_CLEANUP_COMPLETE work=$WORK artifact=absent"
        exit 0
    fi
    complete_without_path
    exit 0
fi

if [ ! -e "$TASK_ARTIFACT" ]; then
    # Crash-safe retry: removal may have succeeded before its metadata update.
    if ! task_artifact_path_shape "$TASK_ARTIFACT" "$WORK"; then
        record_cleanup_state blocked || true
        echo "ARTIFACT_CLEANUP_BLOCKED missing artifact path has an unsafe layout for $WORK: $TASK_ARTIFACT" >&2
        exit 1
    fi
    complete_without_path
    exit 0
fi

SAFE_ARTIFACT=$(validate_task_artifact "$TASK_ARTIFACT" "$WORK") || {
    record_cleanup_state blocked || true
    echo "ARTIFACT_CLEANUP_BLOCKED unsafe artifact path for $WORK: $TASK_ARTIFACT" >&2
    exit 1
}
if [ -z "$EXPECTED_ARTIFACT_SHA" ]; then
    record_cleanup_state blocked || true
    echo "ARTIFACT_CLEANUP_BLOCKED missing artifact_source_sha for $WORK" >&2
    exit 1
fi
LOCAL_SHA=$(git -C "$SAFE_ARTIFACT" rev-parse HEAD 2>/dev/null) || {
    record_cleanup_state blocked || true
    echo "ARTIFACT_CLEANUP_BLOCKED unreadable artifact HEAD for $WORK" >&2
    exit 1
}
if [ "$LOCAL_SHA" != "$EXPECTED_ARTIFACT_SHA" ]; then
    record_cleanup_state blocked || true
    echo "ARTIFACT_CLEANUP_BLOCKED artifact HEAD mismatch for $WORK" >&2
    exit 1
fi
if [ -n "$(git -C "$SAFE_ARTIFACT" status --porcelain --untracked-files=all)" ]; then
    record_cleanup_state blocked || true
    echo "ARTIFACT_CLEANUP_BLOCKED artifact is dirty for $WORK" >&2
    exit 1
fi

if ! git -C "$RIG_ROOT" worktree remove "$SAFE_ARTIFACT"; then
    record_cleanup_state blocked || true
    echo "ARTIFACT_CLEANUP_BLOCKED clean artifact could not be removed for $WORK" >&2
    exit 1
fi

complete_without_path
