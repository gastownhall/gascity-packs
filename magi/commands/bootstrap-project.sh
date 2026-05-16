#!/bin/sh
#
# magi/commands/bootstrap-project.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi bootstrap-project` to
# magi_bootstrap_project.py. The orchestrator wraps
# ${MAGI_UTILITIES_SOURCE}/setup_utilities.sh -y against a target project
# root (default: GC_CITY_PATH) and verifies the resulting .utilities symlink.
#
# USAGE:
#   gc magi bootstrap-project [<project-path>] [--dry-run] [--no-bd]
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH            Gas City root (required)
#   GC_PACK_DIR             Pack root for magi (required)
#   MAGI_UTILITIES_SOURCE   Override path to the .utilities tree
#
# DEPENDENCIES:
#   External: python3
# ==============================================================================
set -eu
if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_PACK_DIR:-}" ]; then
    printf 'gc magi bootstrap-project: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_bootstrap_project.py" "$@"
