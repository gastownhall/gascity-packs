#!/bin/sh
# Gas City doctor: 0 healthy, 1 warning, 2 error; first stdout line is the summary.
set -eu
if ! command -v node >/dev/null 2>&1; then
    echo "Node.js 22+ is required for the BB provider"
    exit 1
fi
exec "${GC_PACK_DIR:?}/assets/run-cli.sh" doctor
