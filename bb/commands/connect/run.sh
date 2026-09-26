#!/bin/sh
set -eu
exec "${GC_PACK_DIR:?Run through gc bb connect}/assets/run-cli.sh" connect "$@"
