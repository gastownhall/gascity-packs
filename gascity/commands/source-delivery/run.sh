#!/bin/sh
set -eu
if ! command -v python3 >/dev/null 2>&1; then
    printf "python3 is required. Install Python 3 and retry this command.\n" >&2
    exit 78
fi
: "${GC_PACK_DIR:?missing Gas City pack context}"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --city|--rig|--context|--city-url|--city-name)
            if [ "$#" -lt 2 ]; then
                printf 'Missing value for %s\n' "$1" >&2
                exit 2
            fi
            shift 2 ;;
        --city=*|--rig=*|--context=*|--city-url=*|--city-name=*) shift ;;
        gc|gascity|source-delivery) shift ;;
        *) break ;;
    esac
done
exec python3 "$GC_PACK_DIR/assets/scripts/source_delivery.py" "$@"
