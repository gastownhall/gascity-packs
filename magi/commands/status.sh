#!/bin/sh
#
# magi/commands/status.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi status` to the Python
# orchestrator magi_status.py. Status reads state.json under the city's
# runtime/packs/magi directory and, when bd is on PATH, surfaces open beads
# labeled pack:magi.
#
# USAGE:
#   gc magi status [--json] [--target NAME]
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
    printf 'gc magi status: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_status.py" "$@"
