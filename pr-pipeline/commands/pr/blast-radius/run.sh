#!/bin/sh
# gc <binding> pr blast-radius — sling a coding agent the
# mol-pr-blast-radius formula to map the impact surface of a change.
#
# Usage:
#   gc <binding> pr blast-radius "<scope>" [--key <id>] [--rig <name>] [--agent <name>]
#
# Environment (set by gc):
#   GC_CITY_PATH   absolute city root
#   GC_PACK_DIR    absolute pack directory
#   GC_PACK_NAME   pack name ("pr-pipeline")
#   GC_CITY_NAME   city workspace name
#   GC_RIG         current rig (when running inside a rig session)

set -eu

if [ -z "${GC_PACK_DIR:-}" ]; then
    echo "gc pr-pipeline pr blast-radius: missing Gas City pack context" >&2
    exit 1
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ] || [ -z "${1:-}" ]; then
    cat "$GC_PACK_DIR/commands/pr/blast-radius/help.md"
    [ -z "${1:-}" ] && exit 2 || exit 0
fi

SCOPE="$1"
shift

RIG=""
AGENT="polecat"
KEY=""

while [ $# -gt 0 ]; do
    case "$1" in
        --rig)        RIG="$2"; shift 2 ;;
        --rig=*)      RIG="${1#--rig=}"; shift ;;
        --agent)      AGENT="$2"; shift 2 ;;
        --agent=*)    AGENT="${1#--agent=}"; shift ;;
        --key)        KEY="$2"; shift 2 ;;
        --key=*)      KEY="${1#--key=}"; shift ;;
        *)
            echo "gc pr-pipeline pr blast-radius: unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if [ -z "$RIG" ]; then
    RIG="${GC_RIG:-}"
fi

if [ -z "$RIG" ]; then
    echo "gc pr-pipeline pr blast-radius: --rig <name> required (or set GC_RIG)" >&2
    exit 2
fi

if ! command -v gc >/dev/null 2>&1; then
    echo "gc pr-pipeline pr blast-radius: gc binary not in PATH" >&2
    exit 1
fi

if [ -n "$KEY" ]; then
    exec gc sling "$RIG/$AGENT" mol-pr-blast-radius --formula \
        --var "scope=$SCOPE" --var "key=$KEY"
else
    exec gc sling "$RIG/$AGENT" mol-pr-blast-radius --formula \
        --var "scope=$SCOPE"
fi
