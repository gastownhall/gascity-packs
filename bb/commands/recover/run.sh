#!/bin/sh
set -eu
exec "${GC_PACK_DIR:?Run through gc bb recover}/assets/run-cli.sh" recover "$@"
