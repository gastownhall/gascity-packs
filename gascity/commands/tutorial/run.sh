#!/bin/sh
set -eu
if ! command -v python3 >/dev/null 2>&1; then
    printf "python3 is required. Install Python 3 and retry this command.\n" >&2
    exit 78
fi
: "${GC_PACK_DIR:?missing Gas City pack context}"
while [ "$#" -gt 0 ]; do
    case "$1" in gc|gascity|tutorial) shift ;; *) break ;; esac
done
exec python3 "$GC_PACK_DIR/assets/scripts/tutorial.py" "$@"
