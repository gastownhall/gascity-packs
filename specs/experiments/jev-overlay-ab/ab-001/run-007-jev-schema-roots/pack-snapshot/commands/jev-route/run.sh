#!/bin/sh
# gc <binding> jev-route — pick jev-build or jev-build-compact with Jev, then sling.
set -eu

if [ -z "${GC_PACK_DIR:-}" ]; then
    echo "CONFIG_REJECTED gc jev-route: missing Gas City pack context" >&2
    exit 1
fi

# gc passes its own global flags (--city <path>, --rig <name>) ahead of ours.
while [ "$#" -gt 0 ]; do
    case "$1" in
        gc|gascity-jev|jev-route|--city=*|--rig=*)
            shift
            ;;
        --city|--rig)
            if [ "$#" -lt 2 ]; then
                echo "gc jev-route: missing value for $1" >&2
                exit 2
            fi
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ] || [ "$#" -eq 0 ]; then
    cat "$GC_PACK_DIR/commands/jev-route/help.md"
    exit 0
fi

exec python3 "$GC_PACK_DIR/assets/scripts/jev_route.py" "$@"
