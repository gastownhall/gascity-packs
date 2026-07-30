#!/usr/bin/env bash
# Deterministic submit-state reconciliation and Graph-v2 step completion.

set -u -o pipefail

# Repository-selection overrides are unsafe during terminal submit: they can
# make validation inspect one repository while the lease or Git mutation uses
# another. Preserve transport/credential configuration, but remove inherited
# repository selectors and injected Git config before the first Git probe.
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
STEP_REF="mol-polecat-work.submit-and-exit"
REPLAY_VERSION="2"
EXECUTE_VERSION="1"
LEASE_EVIDENCE_VERSION="1"

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
  gc gastown polecat-submit execute
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
    guard|execute)
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

is_oid() {
    local value=$1
    case "${#value}" in
        40|64) ;;
        *) return 1 ;;
    esac
    [[ "$value" != *[!0-9a-f]* ]]
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

[[ -n "${GC_CITY_PATH:-}" && -n "${GC_RIG:-}" &&
   -n "${GC_RIG_ROOT:-}" ]] || {
    echo "polecat-submit: GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required" >&2
    exit "$EXIT_INDETERMINATE"
}
case "$GC_RIG" in
    ""|"."|".."|*[!A-Za-z0-9._-]*)
        echo "polecat-submit: the runtime rig name is unsafe" >&2
        exit "$EXIT_INDETERMINATE"
        ;;
esac
RUNTIME_RIG=$GC_RIG
CITY_ROOT=$(CDPATH= cd -- "$GC_CITY_PATH" 2>/dev/null && pwd -P) || {
    echo "polecat-submit: could not canonicalize the city root" >&2
    exit "$EXIT_INDETERMINATE"
}
RIG_ROOT=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) || {
    echo "polecat-submit: could not canonicalize the rig root" >&2
    exit "$EXIT_INDETERMINATE"
}

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
GIT_CMD=$(command -v git 2>/dev/null || true)
if [[ -z "$GIT_CMD" || ! -x "$GIT_CMD" ]]; then
    echo "polecat-submit: git is required" >&2
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

fail_closed() {
    echo "POLECAT_SUBMIT_INDETERMINATE: $*" >&2
    exit "$EXIT_INDETERMINATE"
}

convoy_source_id() {
    local convoy_json=$1 expected_convoy=$2
    printf '%s' "$convoy_json" | jq -er --arg convoy "$expected_convoy" '
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

revalidate_convoy_membership() {
    local convoy_json source_now
    convoy_json=$(run_gc_convoy status "$CONVOY_ID" --json 2>/dev/null) ||
        return 1
    source_now=$(convoy_source_id "$convoy_json" "$CONVOY_ID") ||
        return 1
    [[ "$source_now" == "$SOURCE_ID" ]]
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

single_origin_url() {
    local mode=$1 output line count=0 selected=""
    if [[ "$mode" == "push" ]]; then
        output=$(git -C "$PROOF_RIG_ROOT" remote get-url --push --all origin 2>/dev/null) ||
            return 1
    else
        output=$(git -C "$PROOF_RIG_ROOT" remote get-url --all origin 2>/dev/null) ||
            return 1
    fi
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        count=$((count + 1))
        selected=$line
    done <<<"$output"
    [[ "$count" -eq 1 ]] && safe_atom "$selected" || return 1
    printf '%s' "$selected"
}

emit_submit_proof_key() {
    printf '%s\n' \
        "schema=gascity-polecat-submit-proof-key-v1" \
        "source=$SOURCE_ID" \
        "workflow_root=$ROOT_BEAD_ID" \
        "step=$STEP_BEAD_ID" \
        "input_convoy=$CONVOY_ID" \
        "session_id=$CURRENT_SESSION_ID"
}

emit_submit_proof_context() {
    printf '%s\n' \
        "schema=gascity-polecat-submit-proof-v1" \
        "version=$LEASE_EVIDENCE_VERSION" \
        "key=$PROOF_KEY" \
        "source=$SOURCE_ID" \
        "workflow_root=$ROOT_BEAD_ID" \
        "step=$STEP_BEAD_ID" \
        "step_assignee=$STEP_ASSIGNEE" \
        "input_convoy=$CONVOY_ID" \
        "session_id=$CURRENT_SESSION_ID" \
        "branch=$CANONICAL_SOURCE_BRANCH" \
        "target=$ROOT_BASE_BRANCH" \
        "auto_push=$PROOF_AUTO_PUSH" \
        "head_oid=$SOURCE_EXECUTE_HEAD" \
        "rig=$ROOT_RIG_NAME" \
        "binding_prefix=$ROOT_BINDING_PREFIX" \
        "witness=$PROOF_WITNESS" \
        "repo_common_fingerprint=$PROOF_REPOSITORY_FINGERPRINT" \
        "worktree_fingerprint=$PROOF_WORKTREE_FINGERPRINT" \
        "origin_fetch_fingerprint=$PROOF_FETCH_FINGERPRINT" \
        "origin_push_fingerprint=$PROOF_PUSH_FINGERPRINT"
}

prepare_submit_proof_refs() {
    [[ -n "${GC_RIG_ROOT:-}" ]] || return 1
    PROOF_RIG_ROOT=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) ||
        return 1
    PROOF_KEY=$(emit_submit_proof_key |
        git -C "$PROOF_RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    is_oid "$PROOF_KEY" || return 1
    PROOF_NS="refs/gascity/polecat-submit-proofs/v1/$PROOF_KEY"
    PROOF_CONTEXT_REF="$PROOF_NS/context"
    PROOF_HEAD_REF="$PROOF_NS/head"
    git -C "$PROOF_RIG_ROOT" check-ref-format "$PROOF_CONTEXT_REF" >/dev/null 2>&1 &&
        git -C "$PROOF_RIG_ROOT" check-ref-format "$PROOF_HEAD_REF" >/dev/null 2>&1
}

probe_submit_proof_refs() {
    local context_oid="" head_oid="" context_code head_code
    context_oid=$(git -C "$PROOF_RIG_ROOT" rev-parse \
        --verify --quiet "$PROOF_CONTEXT_REF" 2>/dev/null)
    context_code=$?
    head_oid=$(git -C "$PROOF_RIG_ROOT" rev-parse \
        --verify --quiet "$PROOF_HEAD_REF" 2>/dev/null)
    head_code=$?
    case "$context_code:$head_code" in
        1:1)
            PROOF_REF_STATE="absent"
            ;;
        0:0)
            is_oid "$context_oid" && is_oid "$head_oid" || return 1
            PROOF_REF_STATE="complete"
            ;;
        0:1|1:0)
            PROOF_REF_STATE="partial"
            ;;
        *)
            return 1
            ;;
    esac
}

prepare_submit_proof_context() {
    local mode=$1 rig_common fetch_url push_url
    case "$mode" in
        auto_push_false) PROOF_AUTO_PUSH=false ;;
        refinery) PROOF_AUTO_PUSH=true ;;
        *) return 1 ;;
    esac
    [[ -n "$SOURCE_EXECUTE_ARTIFACT" ]] || return 1
    PROOF_WITNESS="${ROOT_RIG_NAME:+$ROOT_RIG_NAME/}${ROOT_BINDING_PREFIX}witness"
    safe_atom "$PROOF_WITNESS" || return 1
    prepare_submit_proof_refs || return 1
    rig_common=$(git -C "$PROOF_RIG_ROOT" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) || return 1
    PROOF_COMMON_DIR=$(CDPATH= cd -- "$rig_common" 2>/dev/null && pwd -P) ||
        return 1
    PROOF_REPOSITORY_FINGERPRINT=$(printf 'git-common-v1\0%s' "$PROOF_COMMON_DIR" |
        git -C "$PROOF_RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    PROOF_WORKTREE_FINGERPRINT=$(printf 'worktree-v1\0%s' "$SOURCE_EXECUTE_ARTIFACT" |
        git -C "$PROOF_RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    fetch_url=$(single_origin_url fetch) || return 1
    push_url=$(single_origin_url push) || return 1
    PROOF_FETCH_FINGERPRINT=$(printf 'fetch-url-v1\0%s' "$fetch_url" |
        git -C "$PROOF_RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    PROOF_PUSH_FINGERPRINT=$(printf 'push-url-v1\0%s' "$push_url" |
        git -C "$PROOF_RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    for proof_oid in "$PROOF_REPOSITORY_FINGERPRINT" \
        "$PROOF_WORKTREE_FINGERPRINT" "$PROOF_FETCH_FINGERPRINT" \
        "$PROOF_PUSH_FINGERPRINT" "$SOURCE_EXECUTE_HEAD"; do
        is_oid "$proof_oid" || return 1
    done
    PROOF_EXPECTED_CONTEXT=$(emit_submit_proof_context |
        git -C "$PROOF_RIG_ROOT" hash-object --stdin 2>/dev/null) || return 1
    is_oid "$PROOF_EXPECTED_CONTEXT"
}

verify_submit_proof() {
    local context_oid head_oid body expected
    context_oid=$(git -C "$PROOF_RIG_ROOT" rev-parse --verify "$PROOF_CONTEXT_REF" 2>/dev/null) ||
        return 1
    head_oid=$(git -C "$PROOF_RIG_ROOT" rev-parse --verify "$PROOF_HEAD_REF" 2>/dev/null) ||
        return 1
    [[ "$context_oid" == "$PROOF_EXPECTED_CONTEXT" &&
       "$head_oid" == "$SOURCE_EXECUTE_HEAD" ]] || return 1
    ! git -C "$PROOF_RIG_ROOT" symbolic-ref -q "$PROOF_CONTEXT_REF" >/dev/null 2>&1 &&
        ! git -C "$PROOF_RIG_ROOT" symbolic-ref -q "$PROOF_HEAD_REF" >/dev/null 2>&1 ||
        return 1
    [[ "$(git -C "$PROOF_RIG_ROOT" cat-file -t "$context_oid" 2>/dev/null)" == "blob" &&
       "$(git -C "$PROOF_RIG_ROOT" cat-file -t "$head_oid" 2>/dev/null)" == "commit" ]] ||
        return 1
    body=$(git -C "$PROOF_RIG_ROOT" cat-file blob "$context_oid" 2>/dev/null) ||
        return 1
    expected=$(emit_submit_proof_context) || return 1
    [[ "$body" == "$expected" ]] || return 1
    VERIFIED_PROOF_KEY=$PROOF_KEY
    VERIFIED_PROOF_CONTEXT=$context_oid
    VERIFIED_PROOF_HEAD=$head_oid
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
    [[ "$count" -eq 1 && -n "$ONE_LINE" &&
       "$ONE_LINE" != *$'\n'* && "$ONE_LINE" != *$'\r'* &&
       "$ONE_LINE" != *$'\t'* ]]
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
validate_registered_artifact() {
    local candidate=$1 expected_path=$2 expected_branch=$3
    local expected_head=$4 require_clean=$5
    local artifact_real rig_namespace rig_namespace_real canonical_artifact
    local worktrees_parent provider_home provider_root provider_name
    local artifact_top artifact_common rig_common artifact_git_dir
    local admin_ref admin_real admin_backref admin_backreal
    local admin_common_ref admin_common_real current_branch current_head
    local current_status listed registered_count=0

    ARTIFACT_VALIDATION_FAILURE=""
    artifact_real=$(CDPATH= cd -- "$candidate" 2>/dev/null && pwd -P) || {
        ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir is unavailable"
        return 1
    }
    [[ "$artifact_real" == "$expected_path" ]] || {
        ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir is redirected"
        return 1
    }
    [[ "$(basename -- "$artifact_real")" == "$SOURCE_ID" &&
       "$(basename -- "$(dirname -- "$artifact_real")")" == "worktrees" ]] || {
        ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir is not bead-scoped"
        return 1
    }

    rig_namespace="$CITY_ROOT/.gc/worktrees/$ROOT_RIG_NAME"
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
        safe_component "$provider_name" && [[ -n "$provider_name" ]] || {
            ARTIFACT_VALIDATION_FAILURE="legacy artifact has an unsafe provider owner"
            return 1
        }
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
    rig_common=$("$GIT_CMD" -C "$RIG_ROOT" rev-parse \
        --path-format=absolute --git-common-dir 2>/dev/null) || {
        ARTIFACT_VALIDATION_FAILURE="could not resolve the rig Git common directory"
        return 1
    }
    rig_common=$(CDPATH= cd -- "$rig_common" 2>/dev/null && pwd -P) || {
        ARTIFACT_VALIDATION_FAILURE="could not canonicalize the rig Git common directory"
        return 1
    }
    [[ "$artifact_common" == "$rig_common" ]] || {
        ARTIFACT_VALIDATION_FAILURE="source metadata.artifact_dir belongs to another repository"
        return 1
    }
    if [[ -n "${PROOF_COMMON_DIR:-}" &&
          "$artifact_common" != "$PROOF_COMMON_DIR" ]]; then
        ARTIFACT_VALIDATION_FAILURE="source artifact repository differs from its submit proof"
        return 1
    fi
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
    [[ "$(dirname -- "$artifact_git_dir")" == "$rig_common/worktrees" ]] || {
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
    [[ "$admin_common_real" == "$rig_common" ]] || {
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
    [[ "$current_branch" == "$expected_branch" ]] || {
        ARTIFACT_VALIDATION_FAILURE="source artifact is not on the canonical task branch"
        return 1
    }
    if [[ -n "$expected_head" ]]; then
        current_head=$("$GIT_CMD" -C "$artifact_real" \
            rev-parse --verify HEAD 2>/dev/null) || {
            ARTIFACT_VALIDATION_FAILURE="could not read the artifact head"
            return 1
        }
        [[ "$current_head" == "$expected_head" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact head differs from its submit proof"
            return 1
        }
    fi
    if [[ "$require_clean" == "true" ]]; then
        current_status=$("$GIT_CMD" -C "$artifact_real" status --porcelain \
            --untracked-files=all 2>/dev/null) || {
            ARTIFACT_VALIDATION_FAILURE="could not inspect the artifact status"
            return 1
        }
        [[ -z "$current_status" ]] || {
            ARTIFACT_VALIDATION_FAILURE="source artifact is dirty"
            return 1
        }
    fi
}

verify_artifact_at_submit_proof() {
    local mode=$1
    case "$mode" in
        auto_push_false|refinery) ;;
        *) return 1 ;;
    esac
    if [[ ! -d "$SOURCE_EXECUTE_ARTIFACT" ]]; then
        return 1
    fi
    validate_registered_artifact "$SOURCE_EXECUTE_ARTIFACT" \
        "$SOURCE_EXECUTE_ARTIFACT" "$CANONICAL_SOURCE_BRANCH" \
        "$SOURCE_EXECUTE_HEAD" true || {
        echo "polecat-submit: artifact proof did not verify: $ARTIFACT_VALIDATION_FAILURE" >&2
        return 1
    }
}

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
            (.[0].metadata["gc.polecat_submit_convoy"] | type) == "string") and
           (((.[0].metadata | has("artifact_dir")) | not) or
            (.[0].metadata.artifact_dir | type) == "string") and
           (((.[0].metadata | has("auto_push")) | not) or
            (.[0].metadata.auto_push | type) == "boolean") and
           (((.[0].metadata | has("gc.polecat_submit_execute_version")) | not) or
            (.[0].metadata["gc.polecat_submit_execute_version"] | type) == "number") and
           (((.[0].metadata | has("gc.polecat_submit_lease_version")) | not) or
            (.[0].metadata["gc.polecat_submit_lease_version"] | type) == "number") and
           (((.[0].metadata | has("gc.polecat_submit_execute_session_id")) | not) or
            (.[0].metadata["gc.polecat_submit_execute_session_id"] | type) == "string") and
           (((.[0].metadata | has("gc.polecat_submit_execute_step_id")) | not) or
            (.[0].metadata["gc.polecat_submit_execute_step_id"] | type) == "string") and
           (((.[0].metadata | has("gc.polecat_submit_execute_head_sha")) | not) or
            (.[0].metadata["gc.polecat_submit_execute_head_sha"] | type) == "string") and
           (((.[0].metadata | has("gc.polecat_submit_execute_artifact_dir")) | not) or
            (.[0].metadata["gc.polecat_submit_execute_artifact_dir"] | type) == "string") and
           (((.[0].metadata | has("gc.polecat_submit_proof_key")) | not) or
            (.[0].metadata["gc.polecat_submit_proof_key"] | type) == "string") and
           (((.[0].metadata | has("gc.polecat_submit_proof_context")) | not) or
            (.[0].metadata["gc.polecat_submit_proof_context"] | type) == "string") and
           (((.[0].metadata | has("gc.polecat_submit_proof_head")) | not) or
            (.[0].metadata["gc.polecat_submit_proof_head"] | type) == "string") and
           (((.[0].metadata | has("artifact_source_sha")) | not) or
            (.[0].metadata.artifact_source_sha | type) == "string") and
           (((.[0].metadata | has("artifact_cleanup_state")) | not) or
            (.[0].metadata.artifact_cleanup_state | type) == "string")
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
    SOURCE_ARTIFACT_DIR=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata.artifact_dir // ""')
    SOURCE_AUTO_PUSH=$(printf '%s' "$SOURCE_RECORD" | jq -er '
        if .metadata | has("auto_push")
        then (.metadata.auto_push | tostring)
        else ""
        end')
    SOURCE_EXECUTE_VERSION=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_execute_version"] // "" | tostring')
    SOURCE_LEASE_VERSION=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_lease_version"] // "" | tostring')
    SOURCE_EXECUTE_SESSION=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_execute_session_id"] // ""')
    SOURCE_EXECUTE_STEP=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_execute_step_id"] // ""')
    SOURCE_EXECUTE_HEAD=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_execute_head_sha"] // ""')
    SOURCE_EXECUTE_ARTIFACT=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_execute_artifact_dir"] // ""')
    SOURCE_PROOF_KEY=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_proof_key"] // ""')
    SOURCE_PROOF_CONTEXT=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_proof_context"] // ""')
    SOURCE_PROOF_HEAD=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata["gc.polecat_submit_proof_head"] // ""')
    SOURCE_ARTIFACT_SOURCE_SHA=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata.artifact_source_sha // ""')
    SOURCE_ARTIFACT_CLEANUP_STATE=$(printf '%s' "$SOURCE_RECORD" | jq -er \
        '.metadata.artifact_cleanup_state // ""')
    SOURCE_ARTIFACT_SOURCE_SHA_PRESENT=$(printf '%s' "$SOURCE_RECORD" | jq -r \
        '.metadata | has("artifact_source_sha")')
    SOURCE_ARTIFACT_CLEANUP_STATE_PRESENT=$(printf '%s' "$SOURCE_RECORD" | jq -r \
        '.metadata | has("artifact_cleanup_state")')
}

source_policy_matches_mode() {
    local mode=$1
    case "$mode:$SOURCE_AUTO_PUSH" in
        auto_push_false:false|refinery:|refinery:true) return 0 ;;
        *) return 1 ;;
    esac
}

source_artifact_evidence_matches() {
    local mode=$1
    if [[ "$SOURCE_ARTIFACT_DIR" == "$SOURCE_EXECUTE_ARTIFACT" ]]; then
        [[ "$SOURCE_ARTIFACT_SOURCE_SHA_PRESENT" == "false" &&
           "$SOURCE_ARTIFACT_CLEANUP_STATE_PRESENT" == "false" ]] ||
            return 1
        verify_artifact_at_submit_proof "$mode"
        return
    fi

    # A verified refinery may remove the registered worktree only after the
    # source is closed. The cleanup command records the exact submitted head,
    # clears artifact_dir, and marks the cleanup complete in one read-backed
    # update. No other missing or redirected artifact state is terminal proof.
    [[ "$mode" == "refinery" && "$SOURCE_STATUS" == "closed" &&
       -z "$SOURCE_ARTIFACT_DIR" &&
       "$SOURCE_ARTIFACT_SOURCE_SHA_PRESENT" == "true" &&
       "$SOURCE_ARTIFACT_CLEANUP_STATE_PRESENT" == "true" &&
       "$SOURCE_ARTIFACT_SOURCE_SHA" == "$SOURCE_EXECUTE_HEAD" &&
       "$SOURCE_ARTIFACT_CLEANUP_STATE" == "complete" &&
       ! -e "$SOURCE_EXECUTE_ARTIFACT" &&
       ! -L "$SOURCE_EXECUTE_ARTIFACT" ]]
}

execution_evidence_matches() {
    local mode=$1
    [[ "$SOURCE_EXECUTE_VERSION" == "$EXECUTE_VERSION" &&
       "$SOURCE_LEASE_VERSION" == "$LEASE_EVIDENCE_VERSION" &&
       "$SOURCE_EXECUTE_SESSION" == "$CURRENT_SESSION_ID" &&
       "$SOURCE_EXECUTE_STEP" == "$STEP_BEAD_ID" &&
       -n "$SOURCE_EXECUTE_ARTIFACT" ]] || return 1
    source_policy_matches_mode "$mode" || return 1
    is_oid "$SOURCE_EXECUTE_HEAD" || return 1
    case "$SOURCE_EXECUTE_ARTIFACT" in
        /*) ;;
        *) return 1 ;;
    esac
    prepare_submit_proof_context "$mode" || return 1
    [[ "$SOURCE_PROOF_KEY" == "$PROOF_KEY" &&
       "$SOURCE_PROOF_CONTEXT" == "$PROOF_EXPECTED_CONTEXT" &&
       "$SOURCE_PROOF_HEAD" == "$SOURCE_EXECUTE_HEAD" ]] || return 1
    verify_submit_proof || return 1
    [[ "$VERIFIED_PROOF_KEY" == "$SOURCE_PROOF_KEY" &&
       "$VERIFIED_PROOF_CONTEXT" == "$SOURCE_PROOF_CONTEXT" &&
       "$VERIFIED_PROOF_HEAD" == "$SOURCE_PROOF_HEAD" ]] || return 1
    source_artifact_evidence_matches "$mode"
}

evidence_matches() {
    execution_evidence_matches "$MODE" || return 1
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
        *) return 1 ;;
    esac
}

replay_closed_step() {
    local closed_matches='[]' listed matches identity
    local candidate present_count context
    local candidate_id candidate_assignee root_id replay_session
    local replay_source replay_convoy replay_branch replay_mode replay_terminal
    local replay_execute_version replay_lease_version replay_execute_session
    local replay_execute_step replay_execute_head replay_execute_artifact
    local replay_proof_key replay_proof_context replay_proof_head
    local root_json root_context root_convoy root_base root_rig root_prefix
    local convoy_json derived_source source_json source_record
    local source_status source_assignee source_branch source_target source_token
    local source_branch_ready source_halt refinery_target
    local coherent_count=0 replay_line="" legacy_candidates='[]'
    local partial_candidates='[]' partial_context partial_count
    local candidate_version legacy_context selected_root="" selected_source=""
    local selected_convoy="" requested_context

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
        replay_session=$(printf '%s' "$candidate" | jq -er \
            '.metadata["gc.polecat_submit_session_id"] // ""' 2>/dev/null) ||
            fail_closed "closed submit history session metadata is malformed"
        # Session ids are immutable. Discard unrelated history before applying
        # the current proof schema so legacy rows from another run cannot poison
        # the exact current replay.
        [[ -n "$replay_session" ]] || continue
        [[ "$replay_session" == "$CURRENT_SESSION_ID" ]] || continue
        candidate_version=$(printf '%s' "$candidate" | jq -er \
            '.metadata["gc.polecat_submit_version"] // "" | tostring' 2>/dev/null) ||
            fail_closed "closed submit history version metadata is malformed"
        if [[ "$candidate_version" != "$REPLAY_VERSION" ]]; then
            legacy_context=$(printf '%s' "$candidate" | jq -ce \
                --arg ref "$STEP_REF" '
                if (.id | type) == "string" and (.id | length) > 0 and
                   .status == "closed" and
                   .metadata["gc.step_ref"] == $ref and
                   .metadata["gc.outcome"] == "pass" and
                   .metadata["gc.polecat_submit_version"] == 1 and
                   (.metadata["gc.root_bead_id"] | type) == "string" and
                   (.metadata["gc.polecat_submit_source_id"] | type) == "string" and
                   (.metadata["gc.polecat_submit_convoy_id"] | type) == "string" and
                   (.metadata["gc.polecat_submit_session_id"] | type) == "string"
                then {
                  id: .id,
                  root: .metadata["gc.root_bead_id"],
                  source: .metadata["gc.polecat_submit_source_id"],
                  convoy: .metadata["gc.polecat_submit_convoy_id"],
                  session: .metadata["gc.polecat_submit_session_id"]
                }
                else error("legacy replay row is partial or malformed")
                end' 2>/dev/null) ||
                fail_closed "closed submit legacy history is partial or malformed"
            [[ "$(printf '%s' "$legacy_context" | jq -er '.session')" == \
               "$CURRENT_SESSION_ID" ]] || continue
            legacy_candidates=$(jq -cn \
                --argjson rows "$legacy_candidates" \
                --argjson row "$legacy_context" '$rows + [$row]') ||
                fail_closed "could not aggregate legacy submit history"
            continue
        fi
        if [[ "$ACTION" == "complete" ]]; then
            requested_context=$(printf '%s' "$candidate" | jq -ce '
                if (.metadata["gc.polecat_submit_source_id"] | type) == "string" and
                   (.metadata["gc.polecat_submit_convoy_id"] | type) == "string" and
                   (.metadata["gc.polecat_submit_branch"] | type) == "string" and
                   (.metadata["gc.polecat_submit_mode"] | type) == "string"
                then {
                  source: .metadata["gc.polecat_submit_source_id"],
                  convoy: .metadata["gc.polecat_submit_convoy_id"],
                  branch: .metadata["gc.polecat_submit_branch"],
                  mode: .metadata["gc.polecat_submit_mode"]
                }
                else error("requested replay tuple is partial or malformed")
                end' 2>/dev/null) ||
                fail_closed "closed submit history lacks a safe requested replay tuple"
            if [[ "$(printf '%s' "$requested_context" | jq -er '.source')" != "$SOURCE_ID" ||
                  "$(printf '%s' "$requested_context" | jq -er '.convoy')" != "$CONVOY_ID" ||
                  "$(printf '%s' "$requested_context" | jq -er '.branch')" != "$EXPECTED_BRANCH" ||
                  "$(printf '%s' "$requested_context" | jq -er '.mode')" != "$MODE" ]]; then
                continue
            fi
        fi
        present_count=$(printf '%s' "$candidate" | jq -er '
            (.metadata // {}) as $m |
            ["gc.polecat_submit_version",
             "gc.polecat_submit_source_id",
             "gc.polecat_submit_convoy_id",
             "gc.polecat_submit_branch",
             "gc.polecat_submit_mode",
             "gc.polecat_submit_terminal",
             "gc.polecat_submit_session_id",
             "gc.polecat_submit_execute_version",
             "gc.polecat_submit_lease_version",
             "gc.polecat_submit_execute_session_id",
             "gc.polecat_submit_execute_step_id",
             "gc.polecat_submit_execute_head_sha",
             "gc.polecat_submit_execute_artifact_dir",
             "gc.polecat_submit_proof_key",
             "gc.polecat_submit_proof_context",
             "gc.polecat_submit_proof_head"] |
            map(. as $key | select($m | has($key))) | length
        ' 2>/dev/null) ||
            fail_closed "closed submit history metadata is malformed"
        [[ "$present_count" != "0" ]] || continue
        if [[ "$present_count" != "16" ]]; then
            if [[ "$ACTION" == "complete" ]]; then
                fail_closed "closed submit history has partial replay metadata"
            fi
            partial_context=$(printf '%s' "$candidate" | jq -ce '
                if (.metadata["gc.root_bead_id"] | type) == "string" and
                   (.metadata["gc.root_bead_id"] | length) > 0 and
                   (.metadata["gc.polecat_submit_source_id"] | type) == "string" and
                   (.metadata["gc.polecat_submit_source_id"] | length) > 0 and
                   (.metadata["gc.polecat_submit_convoy_id"] | type) == "string" and
                   (.metadata["gc.polecat_submit_convoy_id"] | length) > 0
                then {
                  root: .metadata["gc.root_bead_id"],
                  source: .metadata["gc.polecat_submit_source_id"],
                  convoy: .metadata["gc.polecat_submit_convoy_id"]
                }
                else error("partial replay row lacks canonical provenance")
                end' 2>/dev/null) ||
                fail_closed "closed submit history has unclassifiable partial replay metadata"
            partial_candidates=$(jq -cn \
                --argjson rows "$partial_candidates" \
                --argjson row "$partial_context" '$rows + [$row]') ||
                fail_closed "could not aggregate partial submit history"
            continue
        fi

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
               (.metadata["gc.polecat_submit_session_id"] | length) > 0 and
               .metadata["gc.polecat_submit_execute_version"] == 1 and
               .metadata["gc.polecat_submit_lease_version"] == 1 and
               (.metadata["gc.polecat_submit_execute_session_id"] | type) == "string" and
               (.metadata["gc.polecat_submit_execute_session_id"] | length) > 0 and
               (.metadata["gc.polecat_submit_execute_step_id"] | type) == "string" and
               (.metadata["gc.polecat_submit_execute_step_id"] | length) > 0 and
               (.metadata["gc.polecat_submit_execute_head_sha"] | type) == "string" and
               (.metadata["gc.polecat_submit_execute_head_sha"] | length) > 0 and
               (.metadata["gc.polecat_submit_execute_artifact_dir"] | type) == "string" and
               (.metadata["gc.polecat_submit_execute_artifact_dir"] | length) > 0 and
               (.metadata["gc.polecat_submit_proof_key"] | type) == "string" and
               (.metadata["gc.polecat_submit_proof_key"] | length) > 0 and
               (.metadata["gc.polecat_submit_proof_context"] | type) == "string" and
               (.metadata["gc.polecat_submit_proof_context"] | length) > 0 and
               (.metadata["gc.polecat_submit_proof_head"] | type) == "string" and
               (.metadata["gc.polecat_submit_proof_head"] | length) > 0
            then {
              id: .id,
              assignee: .assignee,
              root: .metadata["gc.root_bead_id"],
              source: .metadata["gc.polecat_submit_source_id"],
              convoy: .metadata["gc.polecat_submit_convoy_id"],
              branch: .metadata["gc.polecat_submit_branch"],
              mode: .metadata["gc.polecat_submit_mode"],
              terminal: .metadata["gc.polecat_submit_terminal"],
              session: .metadata["gc.polecat_submit_session_id"],
              execute_version: .metadata["gc.polecat_submit_execute_version"],
              lease_version: .metadata["gc.polecat_submit_lease_version"],
              execute_session: .metadata["gc.polecat_submit_execute_session_id"],
              execute_step: .metadata["gc.polecat_submit_execute_step_id"],
              execute_head: .metadata["gc.polecat_submit_execute_head_sha"],
              execute_artifact: .metadata["gc.polecat_submit_execute_artifact_dir"],
              proof_key: .metadata["gc.polecat_submit_proof_key"],
              proof_context: .metadata["gc.polecat_submit_proof_context"],
              proof_head: .metadata["gc.polecat_submit_proof_head"]
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
        replay_execute_version=$(printf '%s' "$context" | jq -er '.execute_version')
        replay_lease_version=$(printf '%s' "$context" | jq -er '.lease_version')
        replay_execute_session=$(printf '%s' "$context" | jq -er '.execute_session')
        replay_execute_step=$(printf '%s' "$context" | jq -er '.execute_step')
        replay_execute_head=$(printf '%s' "$context" | jq -er '.execute_head')
        replay_execute_artifact=$(printf '%s' "$context" | jq -er '.execute_artifact')
        replay_proof_key=$(printf '%s' "$context" | jq -er '.proof_key')
        replay_proof_context=$(printf '%s' "$context" | jq -er '.proof_context')
        replay_proof_head=$(printf '%s' "$context" | jq -er '.proof_head')
        safe_atom "$candidate_id" && safe_atom "$candidate_assignee" &&
            safe_atom "$root_id" && safe_atom "$replay_source" &&
            safe_atom "$replay_convoy" && safe_atom "$replay_branch" &&
            safe_atom "$replay_session" && safe_atom "$replay_execute_session" &&
            safe_atom "$replay_execute_step" && is_oid "$replay_execute_head" &&
            is_oid "$replay_proof_key" && is_oid "$replay_proof_context" &&
            is_oid "$replay_proof_head" ||
            fail_closed "closed submit replay identity is unsafe"
        [[ "$replay_execute_version" == "$EXECUTE_VERSION" &&
           "$replay_lease_version" == "$LEASE_EVIDENCE_VERSION" &&
           "$replay_execute_session" == "$replay_session" &&
           "$replay_execute_step" == "$candidate_id" &&
           "$replay_proof_head" == "$replay_execute_head" ]] ||
            fail_closed "closed submit replay execution receipt is incoherent"
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
            --arg session "$replay_session" \
            --argjson execute_version "$EXECUTE_VERSION" \
            --argjson lease_version "$LEASE_EVIDENCE_VERSION" \
            --arg execute_session "$replay_execute_session" \
            --arg execute_step "$replay_execute_step" \
            --arg execute_head "$replay_execute_head" \
            --arg execute_artifact "$replay_execute_artifact" \
            --arg proof_key "$replay_proof_key" \
            --arg proof_context "$replay_proof_context" \
            --arg proof_head "$replay_proof_head" '
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
            .[0].metadata["gc.polecat_submit_session_id"] == $session and
            .[0].metadata["gc.polecat_submit_execute_version"] == $execute_version and
            .[0].metadata["gc.polecat_submit_lease_version"] == $lease_version and
            .[0].metadata["gc.polecat_submit_execute_session_id"] == $execute_session and
            .[0].metadata["gc.polecat_submit_execute_step_id"] == $execute_step and
            .[0].metadata["gc.polecat_submit_execute_head_sha"] == $execute_head and
            .[0].metadata["gc.polecat_submit_execute_artifact_dir"] == $execute_artifact and
            .[0].metadata["gc.polecat_submit_proof_key"] == $proof_key and
            .[0].metadata["gc.polecat_submit_proof_context"] == $proof_context and
            .[0].metadata["gc.polecat_submit_proof_head"] == $proof_head
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
        if [[ "$root_rig" != "$RUNTIME_RIG" ]]; then
            fail_closed "replay workflow root rig does not match runtime rig"
        fi
        refinery_target="${root_rig:+$root_rig/}${root_prefix}refinery"
        safe_atom "$refinery_target" ||
            fail_closed "replay workflow root refinery identity is unsafe"

        convoy_json=$(run_gc_convoy status "$replay_convoy" --json 2>/dev/null) ||
            fail_closed "could not read replay input convoy"
        derived_source=$(convoy_source_id "$convoy_json" "$replay_convoy") ||
            fail_closed "replay input convoy identity/schema/source did not verify"
        [[ "$derived_source" == "$replay_source" ]] ||
            fail_closed "closed submit replay source disagrees with its convoy"

        source_json=$(run_gc_bd show "$replay_source" --json 2>/dev/null) ||
            fail_closed "could not read replay source"
        source_record=$(printf '%s' "$source_json" | jq -ce \
            --arg id "$replay_source" \
            --argjson execute_version "$EXECUTE_VERSION" \
            --argjson lease_version "$LEASE_EVIDENCE_VERSION" \
            --arg execute_session "$replay_execute_session" \
            --arg execute_step "$replay_execute_step" \
            --arg execute_head "$replay_execute_head" \
            --arg execute_artifact "$replay_execute_artifact" \
            --arg proof_key "$replay_proof_key" \
            --arg proof_context "$replay_proof_context" \
            --arg proof_head "$replay_proof_head" '
            if type == "array" and length == 1 and .[0].id == $id and
               (.[0].status | type) == "string" and
               ((.[0].assignee // "") | type) == "string" and
               ((.[0].metadata // {}) | type) == "object" and
               (.[0].metadata.branch | type) == "string" and
               (.[0].metadata.target | type) == "string" and
               (.[0].metadata["gc.polecat_submit_convoy"] | type) == "string" and
               ((.[0].metadata.artifact_dir // "") | type) == "string" and
               (((.[0].metadata | has("auto_push")) | not) or
                (.[0].metadata.auto_push | type) == "boolean") and
               .[0].metadata["gc.polecat_submit_execute_version"] == $execute_version and
               .[0].metadata["gc.polecat_submit_lease_version"] == $lease_version and
               .[0].metadata["gc.polecat_submit_execute_session_id"] == $execute_session and
               .[0].metadata["gc.polecat_submit_execute_step_id"] == $execute_step and
               .[0].metadata["gc.polecat_submit_execute_head_sha"] == $execute_head and
               .[0].metadata["gc.polecat_submit_execute_artifact_dir"] == $execute_artifact and
               .[0].metadata["gc.polecat_submit_proof_key"] == $proof_key and
               .[0].metadata["gc.polecat_submit_proof_context"] == $proof_context and
               .[0].metadata["gc.polecat_submit_proof_head"] == $proof_head and
               (((.[0].metadata | has("artifact_source_sha")) | not) or
                (.[0].metadata.artifact_source_sha | type) == "string") and
               (((.[0].metadata | has("artifact_cleanup_state")) | not) or
                (.[0].metadata.artifact_cleanup_state | type) == "string")
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

        STEP_BEAD_ID=$candidate_id
        STEP_ASSIGNEE=$candidate_assignee
        ROOT_BEAD_ID=$root_id
        CONVOY_ID=$replay_convoy
        SOURCE_ID=$replay_source
        CANONICAL_SOURCE_BRANCH=$replay_branch
        ROOT_BASE_BRANCH=$root_base
        ROOT_RIG_NAME=$root_rig
        ROOT_BINDING_PREFIX=$root_prefix
        REFINERY_TARGET=$refinery_target
        SOURCE_STATUS=$source_status
        SOURCE_ASSIGNEE=$source_assignee
        SOURCE_BRANCH=$source_branch
        SOURCE_TARGET=$source_target
        SOURCE_SUBMIT_CONVOY=$source_token
        SOURCE_BRANCH_READY=$source_branch_ready
        SOURCE_HALT_REASON=$source_halt
        SOURCE_ARTIFACT_DIR=$(printf '%s' "$source_record" | jq -er \
            '.metadata.artifact_dir // ""')
        SOURCE_AUTO_PUSH=$(printf '%s' "$source_record" | jq -er '
            if .metadata | has("auto_push")
            then (.metadata.auto_push | tostring)
            else ""
            end')
        SOURCE_EXECUTE_VERSION=$replay_execute_version
        SOURCE_LEASE_VERSION=$replay_lease_version
        SOURCE_EXECUTE_SESSION=$replay_execute_session
        SOURCE_EXECUTE_STEP=$replay_execute_step
        SOURCE_EXECUTE_HEAD=$replay_execute_head
        SOURCE_EXECUTE_ARTIFACT=$replay_execute_artifact
        SOURCE_PROOF_KEY=$replay_proof_key
        SOURCE_PROOF_CONTEXT=$replay_proof_context
        SOURCE_PROOF_HEAD=$replay_proof_head
        SOURCE_ARTIFACT_SOURCE_SHA=$(printf '%s' "$source_record" | jq -er \
            '.metadata.artifact_source_sha // ""')
        SOURCE_ARTIFACT_CLEANUP_STATE=$(printf '%s' "$source_record" | jq -er \
            '.metadata.artifact_cleanup_state // ""')
        SOURCE_ARTIFACT_SOURCE_SHA_PRESENT=$(printf '%s' "$source_record" | jq -r \
            '.metadata | has("artifact_source_sha")')
        SOURCE_ARTIFACT_CLEANUP_STATE_PRESENT=$(printf '%s' "$source_record" | jq -r \
            '.metadata | has("artifact_cleanup_state")')
        MODE=$replay_mode
        execution_evidence_matches "$replay_mode" ||
            fail_closed "closed submit replay create-only proof did not verify"
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
        selected_root=$root_id
        selected_source=$replay_source
        selected_convoy=$replay_convoy
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

    legacy_count=$(printf '%s' "$legacy_candidates" | jq -er 'length') ||
        fail_closed "could not count legacy submit history"
    if [[ "$legacy_count" -gt 0 ]]; then
        if [[ "$coherent_count" -eq 0 ]]; then
            fail_closed "only legacy v1 submit history matched the current session"
        fi
        printf '%s' "$legacy_candidates" | jq -e \
            --arg root "$selected_root" --arg source "$selected_source" \
            --arg convoy "$selected_convoy" '
            all(.[]; .root != $root or .source != $source or .convoy != $convoy)
        ' >/dev/null 2>&1 ||
            fail_closed "legacy v1 history is canonically relevant but lacks durable proof"
    fi
    partial_count=$(printf '%s' "$partial_candidates" | jq -er 'length') ||
        fail_closed "could not count partial submit history"
    if [[ "$partial_count" -gt 0 ]]; then
        if [[ "$coherent_count" -eq 0 ]]; then
            fail_closed "only partial v2 submit history matched the current session"
        fi
        printf '%s' "$partial_candidates" | jq -e \
            --arg root "$selected_root" --arg source "$selected_source" \
            --arg convoy "$selected_convoy" '
            all(.[]; .root != $root or .source != $source or .convoy != $convoy)
        ' >/dev/null 2>&1 ||
            fail_closed "partial v2 history is canonically relevant but incomplete"
    fi
    [[ "$coherent_count" -le 1 ]] ||
        fail_closed "multiple coherent closed submit replays matched"
    [[ "$coherent_count" -eq 1 ]] || return 1
    convoy_json=$(run_gc_convoy status "$selected_convoy" --json 2>/dev/null) ||
        fail_closed "could not re-read replay input convoy"
    derived_source=$(convoy_source_id "$convoy_json" "$selected_convoy") ||
        fail_closed "replay input convoy identity/schema/source changed"
    [[ "$derived_source" == "$selected_source" ]] ||
        fail_closed "replay input convoy sole source changed"
    EXPECTED_BRANCH=$CANONICAL_SOURCE_BRANCH
    load_source ||
        fail_closed "could not re-read replay source at the terminal boundary"
    evidence_matches ||
        fail_closed "replay source or submit proof changed at the terminal boundary"
    if [[ "$ACTION" == "guard" ]]; then
        replay_line=$(jq -cn \
            --arg contract "polecat-submit.v1" \
            --arg action "terminal" \
            --arg step "$STEP_BEAD_ID" \
            --arg assignee "$STEP_ASSIGNEE" \
            --arg root "$ROOT_BEAD_ID" \
            --arg convoy "$CONVOY_ID" \
            --arg source "$SOURCE_ID" \
            --arg mode "$MODE" \
            --arg branch "$CANONICAL_SOURCE_BRANCH" \
            --arg status "$SOURCE_STATUS" \
            --arg source_assignee "$SOURCE_ASSIGNEE" \
            '{contract: $contract, action: $action, step: $step,
              assignee: $assignee, root: $root, convoy: $convoy,
              source: $source, mode: $mode, branch: $branch,
              status: $status, source_assignee: $source_assignee,
              replay: true}') ||
            fail_closed "could not encode final closed submit replay"
    else
        replay_line="POLECAT_SUBMIT_COMPLETE step=$STEP_BEAD_ID assignee=$STEP_ASSIGNEE root=$ROOT_BEAD_ID convoy=$CONVOY_ID source=$SOURCE_ID mode=$MODE branch=$CANONICAL_SOURCE_BRANCH replay=true"
    fi
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
    if REPLAY_OUTPUT=$(replay_closed_step); then
        printf '%s\n' "$REPLAY_OUTPUT"
        if [[ "$ACTION" == "execute" ]]; then
            run_gc runtime drain-ack ||
                fail_closed "closed submit replay verified but drain acknowledgement failed"
            printf 'POLECAT_SUBMIT_EXECUTE_COMPLETE replay=true session=%s\n' \
                "$CURRENT_SESSION_ID"
        fi
        exit 0
    fi
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
if [[ "$ROOT_RIG_NAME" != "$RUNTIME_RIG" ]]; then
    fail_closed "workflow root rig $ROOT_RIG_NAME does not match runtime rig $RUNTIME_RIG"
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
DERIVED_SOURCE_ID=$(convoy_source_id "$CONVOY_JSON" "$CONVOY_ID") ||
    fail_closed "input convoy identity/schema/source did not verify"
safe_atom "$DERIVED_SOURCE_ID" ||
    fail_closed "the derived source id is unsafe"
if [[ "$ACTION" == "complete" && "$DERIVED_SOURCE_ID" != "$SOURCE_ID" ]]; then
    fail_closed "input convoy source is $DERIVED_SOURCE_ID, not $SOURCE_ID"
fi
SOURCE_ID=$DERIVED_SOURCE_ID
CANONICAL_SOURCE_BRANCH="polecat/$SOURCE_ID"
if [[ "$ACTION" == "execute" ]]; then
    EXPECTED_BRANCH=$CANONICAL_SOURCE_BRANCH
fi
SUBMIT_SESSION_ID=$CURRENT_SESSION_ID

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
    ' >/dev/null 2>&1 || return 1
    revalidate_convoy_membership
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
    # Membership is the final Graph authority read before the terminal step
    # transition; evidence from an earlier convoy generation is never accepted.
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
        --set-metadata "gc.polecat_submit_execute_version=$EXECUTE_VERSION" \
        --set-metadata "gc.polecat_submit_lease_version=$LEASE_EVIDENCE_VERSION" \
        --set-metadata "gc.polecat_submit_execute_session_id=$SOURCE_EXECUTE_SESSION" \
        --set-metadata "gc.polecat_submit_execute_step_id=$SOURCE_EXECUTE_STEP" \
        --set-metadata "gc.polecat_submit_execute_head_sha=$SOURCE_EXECUTE_HEAD" \
        --set-metadata "gc.polecat_submit_execute_artifact_dir=$SOURCE_EXECUTE_ARTIFACT" \
        --set-metadata "gc.polecat_submit_proof_key=$SOURCE_PROOF_KEY" \
        --set-metadata "gc.polecat_submit_proof_context=$SOURCE_PROOF_CONTEXT" \
        --set-metadata "gc.polecat_submit_proof_head=$SOURCE_PROOF_HEAD" \
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
        --arg session "$SUBMIT_SESSION_ID" \
        --argjson execute_version "$EXECUTE_VERSION" \
        --argjson lease_version "$LEASE_EVIDENCE_VERSION" \
        --arg execute_session "$SOURCE_EXECUTE_SESSION" \
        --arg execute_step "$SOURCE_EXECUTE_STEP" \
        --arg execute_head "$SOURCE_EXECUTE_HEAD" \
        --arg execute_artifact "$SOURCE_EXECUTE_ARTIFACT" \
        --arg proof_key "$SOURCE_PROOF_KEY" \
        --arg proof_context "$SOURCE_PROOF_CONTEXT" \
        --arg proof_head "$SOURCE_PROOF_HEAD" '
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
        .[0].metadata["gc.polecat_submit_session_id"] == $session and
        .[0].metadata["gc.polecat_submit_execute_version"] == $execute_version and
        .[0].metadata["gc.polecat_submit_lease_version"] == $lease_version and
        .[0].metadata["gc.polecat_submit_execute_session_id"] == $execute_session and
        .[0].metadata["gc.polecat_submit_execute_step_id"] == $execute_step and
        .[0].metadata["gc.polecat_submit_execute_head_sha"] == $execute_head and
        .[0].metadata["gc.polecat_submit_execute_artifact_dir"] == $execute_artifact and
        .[0].metadata["gc.polecat_submit_proof_key"] == $proof_key and
        .[0].metadata["gc.polecat_submit_proof_context"] == $proof_context and
        .[0].metadata["gc.polecat_submit_proof_head"] == $proof_head
    ' >/dev/null 2>&1
}

classify_terminal() {
    local candidate_mode="" candidate_kind=""
    TERMINAL_MODE=""
    TERMINAL_KIND=""
    [[ "$SOURCE_SUBMIT_CONVOY" == "$CONVOY_ID" &&
       "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" &&
       "$SOURCE_TARGET" == "$ROOT_BASE_BRANCH" ]] || return 1
    if [[ "$SOURCE_STATUS" == "closed" ]]; then
        candidate_mode="refinery"
        candidate_kind="closed"
    elif [[ ("$SOURCE_STATUS" == "open" ||
             "$SOURCE_STATUS" == "in_progress") &&
            "$SOURCE_ASSIGNEE" == "$REFINERY_TARGET" ]]; then
        candidate_mode="refinery"
        candidate_kind="refinery"
    elif [[ "$SOURCE_STATUS" == "open" &&
            -z "$SOURCE_ASSIGNEE" &&
            "$SOURCE_BRANCH_READY" == "true" &&
            "$SOURCE_HALT_REASON" == "auto_push_false" ]]; then
        candidate_mode="auto_push_false"
        candidate_kind="branch_ready"
    else
        return 1
    fi
    execution_evidence_matches "$candidate_mode" || return 1
    TERMINAL_MODE=$candidate_mode
    TERMINAL_KIND=$candidate_kind
}

prepare_execute_artifact() {
    local allow_capture=${1:-true}
    local artifact_real final_status

    [[ -n "$ROOT_RIG_NAME" && -n "$SOURCE_ARTIFACT_DIR" ]] ||
        fail_closed "execute requires exact city, rig, and source artifact context"
    case "$SOURCE_ARTIFACT_DIR" in
        /*) ;;
        *) fail_closed "source metadata.artifact_dir is not absolute" ;;
    esac
    artifact_real=$(CDPATH= cd -- "$SOURCE_ARTIFACT_DIR" 2>/dev/null && pwd -P) ||
        fail_closed "source metadata.artifact_dir is unavailable"
    [[ "$artifact_real" == "$SOURCE_ARTIFACT_DIR" ]] ||
        fail_closed "source metadata.artifact_dir is redirected"
    [[ "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" ]] ||
        fail_closed "source metadata.branch is not canonical"
    validate_registered_artifact "$SOURCE_ARTIFACT_DIR" "$artifact_real" \
        "$CANONICAL_SOURCE_BRANCH" "" false ||
        fail_closed "$ARTIFACT_VALIDATION_FAILURE"

    cd -- "$artifact_real" ||
        fail_closed "source artifact disappeared before entry"
    final_status=$("$GIT_CMD" status --porcelain --untracked-files=all) ||
        fail_closed "could not inspect final task-artifact status"
    if [[ -n "$final_status" ]]; then
        [[ "$allow_capture" == "true" ]] ||
            fail_closed "an existing submit proof binds a dirty task artifact"
        "$GIT_CMD" add -A ||
            fail_closed "could not stage remaining task-artifact changes"
        "$GIT_CMD" commit -m "chore: capture remaining work ($SOURCE_ID)" \
            -m "Capture remaining changes found by deterministic submit." ||
            fail_closed "could not commit remaining task-artifact changes"
    fi
    final_status=$("$GIT_CMD" status --porcelain --untracked-files=all) ||
        fail_closed "could not verify final task-artifact status"
    [[ -z "$final_status" ]] ||
        fail_closed "task artifact is not clean after final capture"
    EXECUTE_HEAD=$("$GIT_CMD" rev-parse --verify HEAD 2>/dev/null) ||
        fail_closed "could not resolve the clean submit head"
    is_oid "$EXECUTE_HEAD" ||
        fail_closed "the clean submit head is invalid"
    validate_registered_artifact "." "$artifact_real" \
        "$CANONICAL_SOURCE_BRANCH" "$EXECUTE_HEAD" true ||
        fail_closed "final artifact proof failed: $ARTIFACT_VALIDATION_FAILURE"
    EXECUTE_ARTIFACT=$artifact_real
}

verify_execute_artifact_in_cwd() {
    local final_cwd
    final_cwd=$(pwd -P 2>/dev/null) || return 1
    [[ "$final_cwd" == "$EXECUTE_ARTIFACT" ]] || {
        ARTIFACT_VALIDATION_FAILURE="final working directory is not the registered source artifact"
        return 1
    }
    validate_registered_artifact "." "$EXECUTE_ARTIFACT" \
        "$CANONICAL_SOURCE_BRANCH" "$EXECUTE_HEAD" true
}

execute_terminal_update() {
    local update_code=0
    load_source || return 1
    [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
       -z "$SOURCE_SUBMIT_CONVOY" &&
       "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" &&
       "$SOURCE_ARTIFACT_DIR" == "$EXECUTE_ARTIFACT" ]] || return 1
    source_policy_matches_mode "$EXECUTE_MODE" || return 1
    case "$EXECUTE_MODE" in
        auto_push_false)
            run_gc_bd update "$SOURCE_ID" \
                --status=open --assignee="" \
                --set-metadata "branch=$CANONICAL_SOURCE_BRANCH" \
                --set-metadata "target=$ROOT_BASE_BRANCH" \
                --set-metadata "gc.polecat_submit_convoy=$CONVOY_ID" \
                --set-metadata branch_ready=true \
                --set-metadata halt_reason=auto_push_false \
                --set-metadata gc.routed_to="" \
                --set-metadata "gc.polecat_submit_execute_version=$EXECUTE_VERSION" \
                --set-metadata "gc.polecat_submit_lease_version=$LEASE_EVIDENCE_VERSION" \
                --set-metadata "gc.polecat_submit_execute_session_id=$CURRENT_SESSION_ID" \
                --set-metadata "gc.polecat_submit_execute_step_id=$STEP_BEAD_ID" \
                --set-metadata "gc.polecat_submit_execute_head_sha=$EXECUTE_HEAD" \
                --set-metadata "gc.polecat_submit_execute_artifact_dir=$EXECUTE_ARTIFACT" \
                --set-metadata "gc.polecat_submit_proof_key=$EXECUTE_PROOF_KEY" \
                --set-metadata "gc.polecat_submit_proof_context=$EXECUTE_PROOF_CONTEXT" \
                --set-metadata "gc.polecat_submit_proof_head=$EXECUTE_PROOF_HEAD" \
                --unset-metadata artifact_source_sha \
                --unset-metadata artifact_cleanup_state \
                --notes "Branch ready: auto_push=false (no push, no refinery handoff)" \
                >/dev/null || update_code=$?
            ;;
        refinery)
            run_gc_bd update "$SOURCE_ID" \
                --status=open --assignee="$REFINERY_TARGET" \
                --set-metadata "branch=$CANONICAL_SOURCE_BRANCH" \
                --set-metadata "target=$ROOT_BASE_BRANCH" \
                --set-metadata "gc.polecat_submit_convoy=$CONVOY_ID" \
                --set-metadata gc.routed_to="" \
                --set-metadata "gc.polecat_submit_execute_version=$EXECUTE_VERSION" \
                --set-metadata "gc.polecat_submit_lease_version=$LEASE_EVIDENCE_VERSION" \
                --set-metadata "gc.polecat_submit_execute_session_id=$CURRENT_SESSION_ID" \
                --set-metadata "gc.polecat_submit_execute_step_id=$STEP_BEAD_ID" \
                --set-metadata "gc.polecat_submit_execute_head_sha=$EXECUTE_HEAD" \
                --set-metadata "gc.polecat_submit_execute_artifact_dir=$EXECUTE_ARTIFACT" \
                --set-metadata "gc.polecat_submit_proof_key=$EXECUTE_PROOF_KEY" \
                --set-metadata "gc.polecat_submit_proof_context=$EXECUTE_PROOF_CONTEXT" \
                --set-metadata "gc.polecat_submit_proof_head=$EXECUTE_PROOF_HEAD" \
                --unset-metadata artifact_source_sha \
                --unset-metadata artifact_cleanup_state \
                --unset-metadata branch_ready \
                --unset-metadata halt_reason \
                --notes "Implemented and deterministically submitted from $EXECUTE_HEAD" \
                >/dev/null || update_code=$?
            ;;
        *) return 1 ;;
    esac
    load_source || return 1
    MODE=$EXECUTE_MODE
    evidence_matches || return 1
    [[ "$update_code" -eq 0 ]] || return 0
}

execute_submit() {
    local auto_push_bool witness_target current_head current_status
    local initial_proof_state

    if classify_terminal; then
        EXECUTE_MODE=$TERMINAL_MODE
        MODE=$EXECUTE_MODE
    else
        [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
           -z "$SOURCE_SUBMIT_CONVOY" ]] ||
            fail_closed "execute source is neither proceedable nor exact proven terminal state"
        case "$SOURCE_AUTO_PUSH" in
            false)
                EXECUTE_MODE="auto_push_false"
                auto_push_bool=false
                ;;
            ""|true)
                EXECUTE_MODE="refinery"
                auto_push_bool=true
                ;;
            *) fail_closed "source metadata.auto_push is invalid" ;;
        esac
        prepare_submit_proof_refs && probe_submit_proof_refs ||
            fail_closed "could not inspect the create-only submit-proof namespace"
        initial_proof_state=$PROOF_REF_STATE
        [[ "$initial_proof_state" != "partial" ]] ||
            fail_closed "the existing submit-proof namespace is partial"
        if [[ "$initial_proof_state" == "complete" ]]; then
            prepare_execute_artifact false
        else
            prepare_execute_artifact true
        fi
        SOURCE_EXECUTE_HEAD=$EXECUTE_HEAD
        SOURCE_EXECUTE_ARTIFACT=$EXECUTE_ARTIFACT
        prepare_submit_proof_context "$EXECUTE_MODE" &&
            probe_submit_proof_refs ||
            fail_closed "could not derive or re-read the submit-proof context"
        if [[ "$initial_proof_state" == "complete" &&
              "$PROOF_REF_STATE" != "complete" ]]; then
            fail_closed "the retained submit proof disappeared during recovery"
        fi
        case "$PROOF_REF_STATE" in
            complete)
                verify_submit_proof ||
                    fail_closed "the retained submit proof differs from this execution"
                ;;
            partial)
                fail_closed "the submit-proof namespace became partial"
                ;;
            absent)
                witness_target="${ROOT_RIG_NAME:+$ROOT_RIG_NAME/}${ROOT_BINDING_PREFIX}witness"
                revalidate_context ||
                    fail_closed "Graph authority changed before lease submit"
                load_source ||
                    fail_closed "could not re-read source before lease submit"
                [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
                   -z "$SOURCE_SUBMIT_CONVOY" &&
                   "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" &&
                   "$SOURCE_ARTIFACT_DIR" == "$EXECUTE_ARTIFACT" ]] ||
                    fail_closed "source changed before lease submit"
                source_policy_matches_mode "$EXECUTE_MODE" ||
                    fail_closed "source auto_push policy changed before lease submit"
                # load_source reflects the still-unterminalized source and
                # therefore has empty execution-proof metadata. Restore the
                # immutable proof inputs derived from the clean artifact.
                SOURCE_EXECUTE_HEAD=$EXECUTE_HEAD
                SOURCE_EXECUTE_ARTIFACT=$EXECUTE_ARTIFACT
                revalidate_convoy_membership ||
                    fail_closed "input convoy membership changed at the lease boundary"
                verify_execute_artifact_in_cwd ||
                    fail_closed "final pre-lease artifact proof failed: $ARTIFACT_VALIDATION_FAILURE"
                run_gc gastown polecat-lease submit \
                    --source "$SOURCE_ID" \
                    --convoy "$CONVOY_ID" \
                    --base "$ROOT_BASE_BRANCH" \
                    --branch "$CANONICAL_SOURCE_BRANCH" \
                    --witness "$witness_target" \
                    --auto-push "$auto_push_bool" ||
                    fail_closed "deterministic lease submit did not succeed"
                current_status=$("$GIT_CMD" status --porcelain \
                    --untracked-files=all) ||
                    fail_closed "could not revalidate the post-lease clean tree"
                [[ -z "$current_status" &&
                   "$("$GIT_CMD" branch --show-current 2>/dev/null)" == "$CANONICAL_SOURCE_BRANCH" ]] ||
                    fail_closed "artifact branch or cleanliness changed during lease submit"
                current_head=$("$GIT_CMD" rev-parse --verify HEAD 2>/dev/null) ||
                    fail_closed "could not re-read the post-lease head"
                [[ "$current_head" == "$EXECUTE_HEAD" ]] ||
                    fail_closed "artifact head changed during lease submit"
                prepare_submit_proof_context "$EXECUTE_MODE" &&
                    verify_submit_proof ||
                    fail_closed "lease submit did not publish its create-only proof"
                ;;
        esac
        EXECUTE_PROOF_KEY=$VERIFIED_PROOF_KEY
        EXECUTE_PROOF_CONTEXT=$VERIFIED_PROOF_CONTEXT
        EXECUTE_PROOF_HEAD=$VERIFIED_PROOF_HEAD
        revalidate_context ||
            fail_closed "Graph authority changed before terminal source update"
        load_source ||
            fail_closed "could not re-read source before terminal source update"
        [[ "$SOURCE_STATUS" == "open" && -z "$SOURCE_ASSIGNEE" &&
           -z "$SOURCE_SUBMIT_CONVOY" &&
           "$SOURCE_BRANCH" == "$CANONICAL_SOURCE_BRANCH" &&
           "$SOURCE_ARTIFACT_DIR" == "$EXECUTE_ARTIFACT" ]] ||
            fail_closed "source changed before terminal source update"
        source_policy_matches_mode "$EXECUTE_MODE" ||
            fail_closed "source auto_push policy changed before terminal source update"
        revalidate_convoy_membership ||
            fail_closed "input convoy membership changed at the terminal source-update boundary"
        verify_execute_artifact_in_cwd ||
            fail_closed "final pre-terminal artifact proof failed: $ARTIFACT_VALIDATION_FAILURE"
        execute_terminal_update ||
            fail_closed "terminal source update did not persist exact execution proof"
    fi

    case "$EXECUTE_MODE" in
        auto_push_false) COMPLETION_TERMINAL="branch_ready" ;;
        refinery)
            if [[ "$SOURCE_STATUS" == "closed" ]]; then
                COMPLETION_TERMINAL="closed"
            else
                COMPLETION_TERMINAL="refinery"
            fi
            ;;
    esac
    MODE=$EXECUTE_MODE
    close_step pass "$MODE" "$COMPLETION_TERMINAL" \
        "Submit execute complete with durable lease proof on source $SOURCE_ID" ||
        fail_closed "submit execute did not persist and read back closed/pass"
    revalidate_convoy_membership ||
        fail_closed "input convoy membership changed before drain"
    load_source ||
        fail_closed "could not re-read terminal source before drain"
    evidence_matches && execution_evidence_matches "$MODE" ||
        fail_closed "terminal source or create-only proof changed before drain"
    if [[ "$MODE" == "refinery" ]]; then
        run_gc session wake "$REFINERY_TARGET" >/dev/null 2>&1 || true
        run_gc session nudge "$REFINERY_TARGET" \
            "Run 'gc prime' to check merge queue and begin processing." \
            >/dev/null 2>&1 || true
    fi
    run_gc runtime drain-ack ||
        fail_closed "submit execute completed durably but drain acknowledgement failed"
    printf 'POLECAT_SUBMIT_EXECUTE_COMPLETE step=%s root=%s convoy=%s source=%s mode=%s branch=%s head=%s\n' \
        "$STEP_BEAD_ID" "$ROOT_BEAD_ID" "$CONVOY_ID" "$SOURCE_ID" \
        "$MODE" "$CANONICAL_SOURCE_BRANCH" "$SOURCE_EXECUTE_HEAD"
}

if [[ "$ACTION" == "execute" ]]; then
    execute_submit
    exit 0
fi

if [[ "$ACTION" == "guard" ]]; then
    if [[ -n "$SOURCE_SUBMIT_CONVOY" &&
          "$SOURCE_SUBMIT_CONVOY" != "$CONVOY_ID" ]]; then
        fail_closed "source $SOURCE_ID belongs to submit generation $SOURCE_SUBMIT_CONVOY, not $CONVOY_ID"
    fi

    TERMINAL_MODE=""
    TERMINAL_KIND=""
    classify_terminal || true

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
