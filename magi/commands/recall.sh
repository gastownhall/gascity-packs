#!/bin/sh
#
# magi/commands/recall.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi recall <key>` to
# magi_remember.py with the leading `recall` subcommand. Proxies to bd recall
# with the magi: key prefix and prints the recalled value to stdout.
#
# USAGE:
#   gc magi recall <key>
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH   Gas City root (required)
#   GC_PACK_DIR    Pack root for magi (required)
#
# DEPENDENCIES:
#   External: python3
# ==============================================================================
set -eu
if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_PACK_DIR:-}" ]; then
    printf 'gc magi recall: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_remember.py" recall "$@"
