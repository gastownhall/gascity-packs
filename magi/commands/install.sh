#!/bin/sh
#
# magi/commands/install.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi install` to the Python
# orchestrator magi_install.py. Asserts the Gas City pack-context env vars
# (GC_CITY_PATH, GC_PACK_DIR) and exec's python3 so the orchestrator's exit
# code propagates verbatim.
#
# USAGE:
#   gc magi install [--target ...] [--home DIR] [--dry-run] [--non-interactive]
#                   [--skip-prereqs] [--bd-push] [--no-bd] [--skip-utilities]
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
    printf 'gc magi install: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_install.py" "$@"
