#!/bin/sh
#
# magi/commands/uninstall.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi uninstall` to the Python
# orchestrator magi_uninstall.py. Asserts the Gas City pack-context env vars
# and exec's python3 so the orchestrator's exit code propagates verbatim.
#
# USAGE:
#   gc magi uninstall [--target ...] [--yes] [--dry-run] [--really-purge]
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
    printf 'gc magi uninstall: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_uninstall.py" "$@"
