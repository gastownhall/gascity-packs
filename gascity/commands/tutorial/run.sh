#!/bin/sh
set -eu
: "${GC_PACK_DIR:?missing Gas City pack context}"
while [ "$#" -gt 0 ]; do
    case "$1" in gc|gascity|tutorial) shift ;; *) break ;; esac
done
exec python3 "$GC_PACK_DIR/assets/scripts/tutorial.py" "$@"
