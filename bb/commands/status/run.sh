#!/bin/sh
set -eu
exec "${GC_PACK_DIR:?Run through gc bb status}/assets/run-cli.sh" status "$@"
