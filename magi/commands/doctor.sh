#!/bin/sh
#
# magi/commands/doctor.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi doctor` to the Python
# orchestrator magi_doctor.py. The orchestrator discovers every doctor
# subdirectory under <pack-root>/doctor/, invokes each check-*.sh probe,
# aggregates results, and emits a summary bead labeled verb:doctor.
#
# USAGE:
#   gc magi doctor [--json] [--no-bd]
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
    printf 'gc magi doctor: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_doctor.py" "$@"
