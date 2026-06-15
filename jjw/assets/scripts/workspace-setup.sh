#!/bin/sh
# workspace-setup.sh - jjw-backed jj workspace creation for Gas City agents.
#
# Usage: workspace-setup.sh <rig-root> <target-dir> <agent-name> [--sync]

set -eu

RIG_ROOT="${1:?usage: workspace-setup.sh <rig-root> <target-dir> <agent-name> [--sync]}"
WT="${2:?missing target-dir}"
AGENT="${3:?missing agent-name}"
shift 3

SYNC=""
WORK_BEAD_ID=""
WORK_TITLE=""
WORK_DESCRIPTION_FILE=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --sync)
            SYNC="--sync"
            shift
            ;;
        --bead)
            WORK_BEAD_ID="${2:-}"
            shift 2
            ;;
        --title)
            WORK_TITLE="${2:-}"
            shift 2
            ;;
        --description)
            WORK_DESCRIPTION_FILE=$(mktemp)
            printf '%s\n' "${2:-}" > "$WORK_DESCRIPTION_FILE"
            shift 2
            ;;
        --description-file)
            WORK_DESCRIPTION_FILE="${2:-}"
            shift 2
            ;;
        --bead=*)
            WORK_BEAD_ID="${1#--bead=}"
            shift
            ;;
        --title=*)
            WORK_TITLE="${1#--title=}"
            shift
            ;;
        --description=*)
            WORK_DESCRIPTION_FILE=$(mktemp)
            printf '%s\n' "${1#--description=}" > "$WORK_DESCRIPTION_FILE"
            shift
            ;;
        --description-file=*)
            WORK_DESCRIPTION_FILE="${1#--description-file=}"
            shift
            ;;
        *)
            echo "jjw workspace-setup: unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# pre_start may launch with cwd already set to WT. First-time setup may stage
# and remove WT, so move to a stable directory before any jj/jjw command.
cd "$RIG_ROOT"

log_step() {
    printf 'jjw workspace-setup: %s\n' "$*" >&2
}

run_best_effort() {
    step="${1:?missing step}"
    shift
    set +e
    "$@"
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
        log_step "$step failed (exit $rc)"
    fi
    return 0
}

ensure_jjw() {
    if command -v jjw >/dev/null 2>&1; then
        return 0
    fi
    "$SCRIPT_DIR/install-jjw.sh"
    if command -v jjw >/dev/null 2>&1; then
        return 0
    fi
    install_dir="${GC_JJW_INSTALL_DIR:-${HOME:-}/.local/bin}"
    if [ -x "$install_dir/jjw" ]; then
        PATH="$install_dir:$PATH"
        export PATH
        return 0
    fi
    echo "jjw workspace-setup: jjw install completed but jjw is not executable" >&2
    exit 1
}

relpath() {
    python3 - "$1" "$2" <<'PY'
import os, sys
print(os.path.relpath(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])))
PY
}

workspace_name_component() {
    printf '%s' "$1" | sed 's/[^A-Za-z0-9._-]/-/g; s/^-*//; s/-*$//'
}

resolve_base_revset() {
    if jj -R "$RIG_ROOT" log -r 'default@' --no-graph -T '' >/dev/null 2>&1; then
        printf '%s\n' 'default@'
        return 0
    fi
    for candidate in main master trunk; do
        if jj -R "$RIG_ROOT" log -r "$candidate@origin" --no-graph -T '' >/dev/null 2>&1; then
            printf '%s\n' "$candidate@origin"
            return 0
        fi
    done
    printf '%s\n' '@'
}

write_workspace_runtime_files() {
    mkdir -p "$WT/.beads"
    echo "$RIG_ROOT/.beads" > "$WT/.beads/redirect"

    if [ ! -f "$WT/.jjignore" ]; then
        cat > "$WT/.jjignore" <<'JJIGNORE'
.beads/redirect
.beads/hooks/
.beads/formulas/
.logs/
.claude/
.codex/
.gemini/
.opencode/
.github/hooks/
.github/copilot-instructions.md
__pycache__/
state.json
JJIGNORE
    fi
}

write_work_seed_description() {
    desc_file="$1"
    title="$WORK_TITLE"
    if [ -z "$title" ]; then
        title="$WORK_BEAD_ID"
    fi

    {
        if [ -n "$WORK_BEAD_ID" ]; then
            printf 'work: %s %s\n' "$WORK_BEAD_ID" "$title"
        elif [ -n "$title" ]; then
            printf 'work: %s\n' "$title"
        else
            return 1
        fi
        if [ -n "$WORK_DESCRIPTION_FILE" ] && [ -s "$WORK_DESCRIPTION_FILE" ]; then
            printf '\n'
            sed '/^[[:space:]]*$/d' "$WORK_DESCRIPTION_FILE"
            printf '\n'
        fi
    } > "$desc_file"
}

seed_current_change_from_work_metadata() {
    if [ -z "$WORK_BEAD_ID" ] && [ -z "$WORK_TITLE" ]; then
        return 0
    fi
    if ! jj -R "$WT" root >/dev/null 2>&1; then
        return 0
    fi

    current_change=$(jj -R "$WT" log -r @ --no-graph --template 'change_id' 2>/dev/null || true)
    if [ -z "$current_change" ]; then
        return 0
    fi
    if ! jj -R "$WT" log -r 'no_description' --no-graph --template 'change_id ++ "\n"' 2>/dev/null | grep -q "$current_change"; then
        return 0
    fi

    desc_file=$(mktemp)
    if write_work_seed_description "$desc_file"; then
        jj -R "$WT" describe --stdin < "$desc_file"
    fi
    rm -f "$desc_file"
}

install_workspace_excludes() {
    if ! jj -R "$WT" root >/dev/null 2>&1; then
        return 0
    fi
    git_dir=$(jj -R "$WT" git root 2>/dev/null || true)
    if [ -z "$git_dir" ] || [ ! -d "$git_dir" ]; then
        return 0
    fi
    exclude_file="$git_dir/info/exclude"
    mkdir -p "$(dirname "$exclude_file")"
    touch "$exclude_file"
    if grep -q "# Gas City workspace infrastructure" "$exclude_file" 2>/dev/null; then
        return 0
    fi
    cat >> "$exclude_file" <<'EXCLUDE'

# Gas City workspace infrastructure
.beads/redirect
.beads/hooks/
.beads/formulas/
.logs/
.claude/
.codex/
.gemini/
.opencode/
.github/hooks/
.github/copilot-instructions.md
__pycache__/
state.json
EXCLUDE
}

restore_stage() {
    if [ -n "${STAGE:-}" ] && [ -d "$STAGE" ]; then
        mkdir -p "$WT"
        find "$STAGE" -mindepth 1 -maxdepth 1 | while read -r f; do
            mv "$f" "$WT/" 2>/dev/null || true
        done
        rmdir "$STAGE" 2>/dev/null || true
    fi
}

prepare_jjw_config() {
    config_path="$RIG_ROOT/.jjw.yaml"
    workspace_dir="${GC_JJW_WORKSPACE_DIR:-$(relpath "$(dirname "$WT")" "$RIG_ROOT")}"
    default_branch="${GC_JJW_DEFAULT_BRANCH:-main}"
    bookmark_pattern="${GC_JJW_BOOKMARK_PATTERN:-gc/{name}}"
    manage="${GC_JJW_MANAGE_CONFIG:-true}"

    if [ "$manage" = "false" ]; then
        if [ ! -f "$config_path" ]; then
            echo "jjw workspace-setup: $config_path missing and GC_JJW_MANAGE_CONFIG=false" >&2
            exit 1
        fi
        return 0
    fi

    if [ -f "$config_path" ] && ! grep -q "Generated by Gas City jjw pack" "$config_path"; then
        if [ "$manage" != "overwrite" ]; then
            echo "jjw workspace-setup: $config_path exists and is not Gas City-managed" >&2
            echo "jjw workspace-setup: set GC_JJW_MANAGE_CONFIG=overwrite to replace it" >&2
            exit 1
        fi
    fi

    cat > "$config_path" <<EOF
# Generated by Gas City jjw pack. Safe to edit, but set
# GC_JJW_MANAGE_CONFIG=false if this file should not be rewritten by pre_start.
version: 1
workspace_dir: "$workspace_dir"
bookmark_pattern: "$bookmark_pattern"
default_branch: "$default_branch"
EOF
}

refresh_existing_workspace() {
    write_workspace_runtime_files
    install_workspace_excludes
    run_best_effort "update stale workspace state" jj -R "$WT" workspace update-stale >/dev/null 2>&1
    seed_current_change_from_work_metadata
    if [ "$SYNC" = "--sync" ]; then
        run_best_effort "sync workspace git state" jj -R "$WT" git fetch 2>/dev/null
    fi
}

ensure_jjw
REVSET=$(resolve_base_revset)
WORKSPACE_NAME=$(workspace_name_component "$(basename "$WT")")
prepare_jjw_config

if [ -d "$WT/.jj" ]; then
    refresh_existing_workspace
    exit 0
fi

mkdir -p "$(dirname "$WT")"

STAGE=""
if [ -d "$WT" ] && [ "$(find "$WT" -mindepth 1 -maxdepth 1 | head -n 1)" ]; then
    STAGE=$(mktemp -d "$(dirname "$WT")/.gascity-workspace-stage.XXXXXX")
    find "$WT" -mindepth 1 -maxdepth 1 -exec mv {} "$STAGE"/ \;
    trap 'restore_stage' EXIT HUP INT TERM
fi
rmdir "$WT" 2>/dev/null || true

if ! jjw create "$WORKSPACE_NAME" --revision "$REVSET" >/dev/null; then
    echo "jjw workspace-setup: failed to create workspace $WORKSPACE_NAME at $WT from $RIG_ROOT (revset $REVSET)" >&2
    restore_stage
    exit 1
fi

if [ ! -d "$WT/.jj" ]; then
    echo "jjw workspace-setup: jjw reported success but $WT/.jj is missing" >&2
    restore_stage
    exit 1
fi

restore_stage
trap - EXIT HUP INT TERM
write_workspace_runtime_files
install_workspace_excludes
seed_current_change_from_work_metadata

if [ "$SYNC" = "--sync" ]; then
    run_best_effort "sync workspace git state" jj -R "$WT" git fetch 2>/dev/null
fi
