#!/bin/sh
#
# magi/commands/remember.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi remember <key> <value>`
# to magi_remember.py with the leading `remember` subcommand. The orchestrator
# proxies to `bd remember --key magi:<key>` with secret redaction applied
# before the bd subprocess runs.
#
# USAGE:
#   gc magi remember <key> <value>
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
    printf 'gc magi remember: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_remember.py" remember "$@"
