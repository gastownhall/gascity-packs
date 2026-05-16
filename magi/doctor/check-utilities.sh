#!/bin/sh
#
# magi/doctor/check-utilities.sh
# ==============================================================================
# Doctor probe for the pack-internal .utilities/ tree. Resolves the source via
# (1) MAGI_UTILITIES_SOURCE env var when set; (2) ${MAGI_PACK_DIR}/.utilities/
# when MAGI_PACK_DIR is set; (3) the pack-relative ../.utilities computed from
# the script's own directory. The probe passes (rc=0) when the resolved
# directory exists and is non-empty. setup_utilities.sh executability is
# checked but warn-only because the pack-internal .utilities/ surface may not
# carry setup_utilities.sh as the same external entry point.
#
# Exit semantics:
#   0  resolved directory exists and is non-empty
#   2  resolved directory is missing or empty (warn; pack still works)
#
# Logs append to ${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs/doctor-utilities-<utc>.log.
#
# USAGE:
#   ./check-utilities.sh
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH            Gas City root (logs derive from this path)
#   MAGI_PACK_DIR           Pack root override; used when MAGI_UTILITIES_SOURCE is unset
#   MAGI_UTILITIES_SOURCE   Explicit override path to the .utilities tree
#
# DEPENDENCIES:
#   External: date, find, mkdir, dirname, basename
# ==============================================================================
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PACK_ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "${PACK_ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    . "${PACK_ENV_FILE}"
    set +a
fi
VERB_LOG_DIR="${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs"
mkdir -p "${VERB_LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG_FILE="${VERB_LOG_DIR}/doctor-utilities-${STAMP}.log"
PACK_DIR_GUESS="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
if [ -n "${MAGI_UTILITIES_SOURCE:-}" ]; then
    RESOLVED_SOURCE="${MAGI_UTILITIES_SOURCE}"
    RESOLVED_VIA="env:MAGI_UTILITIES_SOURCE"
elif [ -n "${MAGI_PACK_DIR:-}" ]; then
    RESOLVED_SOURCE="${MAGI_PACK_DIR%/}/.utilities"
    RESOLVED_VIA="env:MAGI_PACK_DIR"
else
    RESOLVED_SOURCE="${PACK_DIR_GUESS}/.utilities"
    RESOLVED_VIA="computed:pack-relative"
fi
SETUP_SCRIPT="${RESOLVED_SOURCE}/setup_utilities.sh"
{
    printf 'check=utilities stamp=%s\n' "${STAMP}"
    printf 'resolved_via=%s\n' "${RESOLVED_VIA}"
    printf 'resolved_source=%s\n' "${RESOLVED_SOURCE}"
    printf 'setup_script=%s\n' "${SETUP_SCRIPT}"
} >> "${LOG_FILE}"
if [ ! -d "${RESOLVED_SOURCE}" ]; then
    printf 'result=warn reason=utilities-dir-missing\n' >> "${LOG_FILE}"
    printf 'WARN: utilities directory missing at %s (resolved_via=%s)\n' "${RESOLVED_SOURCE}" "${RESOLVED_VIA}" >&2
    printf 'utilities log=%s\n' "${LOG_FILE}" >&2
    exit 2
fi
NONEMPTY="$(find "${RESOLVED_SOURCE}" -mindepth 1 -maxdepth 2 -type f -print -quit)"
if [ -z "${NONEMPTY}" ]; then
    printf 'result=warn reason=utilities-dir-empty\n' >> "${LOG_FILE}"
    printf 'WARN: utilities directory empty at %s\n' "${RESOLVED_SOURCE}" >&2
    printf 'utilities log=%s\n' "${LOG_FILE}" >&2
    exit 2
fi
if [ ! -f "${SETUP_SCRIPT}" ]; then
    printf 'result=ok setup_warn=setup-script-missing\n' >> "${LOG_FILE}"
    printf 'INFO: setup_utilities.sh not present at %s (pack-internal mode; bootstrap-project unavailable)\n' "${SETUP_SCRIPT}" >&2
elif [ ! -x "${SETUP_SCRIPT}" ]; then
    printf 'result=ok setup_warn=setup-script-not-executable\n' >> "${LOG_FILE}"
    printf 'INFO: setup_utilities.sh present but not executable at %s\n' "${SETUP_SCRIPT}" >&2
else
    printf 'result=ok setup_executable=true\n' >> "${LOG_FILE}"
fi
printf '.utilities source=%s setup=%s resolved_via=%s\n' "${RESOLVED_SOURCE}" "${SETUP_SCRIPT}" "${RESOLVED_VIA}"
printf 'utilities log=%s\n' "${LOG_FILE}"
exit 0
