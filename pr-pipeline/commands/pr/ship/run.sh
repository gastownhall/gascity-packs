#!/bin/sh
# gc <binding> pr ship — sling a coding agent the mol-pr-ship formula
# to run the pre-push gate (simplify → review → contributor check).
# STOPS at a readiness report. Never pushes, never opens a PR.
#
# Usage:
#   gc <binding> pr ship [--branch <name>] [--skip-simplify] [--rig <name>] [--agent <name>]
#
# Environment (set by gc):
#   GC_CITY_PATH   absolute city root
#   GC_PACK_DIR    absolute pack directory
#   GC_PACK_NAME   pack name ("pr-pipeline")
#   GC_CITY_NAME   city workspace name
#   GC_RIG         current rig (when running inside a rig session)

set -eu

if [ -z "${GC_PACK_DIR:-}" ]; then
    echo "gc pr-pipeline pr ship: missing Gas City pack context" >&2
    exit 1
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat "$GC_PACK_DIR/commands/pr/ship/help.md"
    exit 0
fi

RIG=""
AGENT="polecat"
BRANCH=""
SKIP_SIMPLIFY="false"

while [ $# -gt 0 ]; do
    case "$1" in
        --branch)         BRANCH="$2"; shift 2 ;;
        --branch=*)       BRANCH="${1#--branch=}"; shift ;;
        --skip-simplify)  SKIP_SIMPLIFY="true"; shift ;;
        --rig)            RIG="$2"; shift 2 ;;
        --rig=*)          RIG="${1#--rig=}"; shift ;;
        --agent)          AGENT="$2"; shift 2 ;;
        --agent=*)        AGENT="${1#--agent=}"; shift ;;
        *)
            echo "gc pr-pipeline pr ship: unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if [ -z "$RIG" ]; then
    RIG="${GC_RIG:-}"
fi

if [ -z "$RIG" ]; then
    echo "gc pr-pipeline pr ship: --rig <name> required (or set GC_RIG)" >&2
    exit 2
fi

if ! command -v gc >/dev/null 2>&1; then
    echo "gc pr-pipeline pr ship: gc binary not in PATH" >&2
    exit 1
fi

exec gc sling "$RIG/$AGENT" mol-pr-ship --formula \
    --var "branch=$BRANCH" \
    --var "skip_simplify=$SKIP_SIMPLIFY"
