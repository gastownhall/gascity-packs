#!/bin/sh
# LazyJJ wrapper around the shared jjw workspace setup helper.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
JJW_SETUP="$SCRIPT_DIR/../../../jjw/assets/scripts/workspace-setup.sh"

RIG_ROOT_ARG="${1:-}"
LAZYJJ_WORK_BEAD_ID="${LAZYJJ_WORK_BEAD_ID:-}"
LAZYJJ_WORK_TITLE="${LAZYJJ_WORK_TITLE:-}"
LAZYJJ_WORK_DESCRIPTION="${LAZYJJ_WORK_DESCRIPTION:-}"

cleanup_file=""
cleanup() {
    if [ -n "$cleanup_file" ]; then
        rm -f "$cleanup_file"
    fi
}
trap cleanup EXIT HUP INT TERM

next_is_bead=""
has_bead_arg=""
for arg in "$@"; do
    if [ "$next_is_bead" = "1" ]; then
        LAZYJJ_WORK_BEAD_ID="$arg"
        has_bead_arg="1"
        next_is_bead=""
        continue
    fi
    case "$arg" in
        --bead)
            next_is_bead="1"
            has_bead_arg="1"
            ;;
        --bead=*)
            LAZYJJ_WORK_BEAD_ID="${arg#--bead=}"
            has_bead_arg="1"
            ;;
    esac
done

if [ -n "$LAZYJJ_WORK_BEAD_ID" ] && [ -n "$RIG_ROOT_ARG" ] && command -v bd >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    work_json=$(cd "$RIG_ROOT_ARG" && bd show "$LAZYJJ_WORK_BEAD_ID" --json 2>/dev/null || true)
    if [ -n "$work_json" ]; then
        if [ -z "$LAZYJJ_WORK_TITLE" ]; then
            LAZYJJ_WORK_TITLE=$(printf '%s' "$work_json" | jq -r '.[0].title // empty' | tr '\n' ' ' | sed 's/[[:space:]][[:space:]]*/ /g; s/^ //; s/ $//')
        fi
        if [ -z "$LAZYJJ_WORK_DESCRIPTION" ]; then
            LAZYJJ_WORK_DESCRIPTION=$(printf '%s' "$work_json" | jq -r '.[0].description // .[0].notes // empty' | sed '/^[[:space:]]*$/d')
        fi
    fi
fi

if [ -n "$LAZYJJ_WORK_BEAD_ID" ] && [ -z "$has_bead_arg" ]; then
    set -- "$@" --bead "$LAZYJJ_WORK_BEAD_ID"
fi
if [ -n "$LAZYJJ_WORK_TITLE" ]; then
    set -- "$@" --title "$LAZYJJ_WORK_TITLE"
fi
if [ -n "$LAZYJJ_WORK_DESCRIPTION" ]; then
    cleanup_file=$(mktemp)
    printf '%s\n' "$LAZYJJ_WORK_DESCRIPTION" > "$cleanup_file"
    set -- "$@" --description-file "$cleanup_file"
fi

"$JJW_SETUP" "$@"
