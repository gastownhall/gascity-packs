#!/bin/sh
set -eu
exec "${GC_PACK_DIR:?Run through gc bb bind}/assets/run-cli.sh" bind "$@"
