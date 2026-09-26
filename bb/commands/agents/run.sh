#!/bin/sh
set -eu
exec "${GC_PACK_DIR:?Run through gc bb agents}/assets/run-cli.sh" agents "$@"
