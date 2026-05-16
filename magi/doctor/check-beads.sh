#!/bin/sh
#
# magi/doctor/check-beads.sh
# ==============================================================================
# Description: Doctor probe for the bd CLI (beads). Magi treats bd as optional
# and degrades gracefully when missing: every bd write is wrapped in try_bd()
# which returns None and logs a single line when bd is not on PATH. Missing
# bd therefore surfaces as warn (rc=2), never as fail (rc=1).
#
# USAGE:
#   ./check-beads.sh
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH   Gas City root (logs derive from this path)
#
# DEPENDENCIES:
#   External: bd (optional)
# ==============================================================================
set -eu
VERB_LOG_DIR="${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs"
mkdir -p "${VERB_LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG_FILE="${VERB_LOG_DIR}/doctor-beads-${STAMP}.log"
BD_BIN="$(command -v bd || printf '')"
{
    printf 'check=beads stamp=%s\n' "${STAMP}"
    printf 'bd=%s\n' "${BD_BIN}"
} >> "${LOG_FILE}"
if [ -z "${BD_BIN}" ]; then
    printf 'result=warn reason=bd-missing\n' >> "${LOG_FILE}"
    printf 'bd not on PATH; magi will skip bd writes\n' >&2
    printf 'beads log=%s\n' "${LOG_FILE}" >&2
    exit 2
fi
BD_VERSION="$(${BD_BIN} --version 2>>"${LOG_FILE}" || printf 'unknown')"
printf 'version=%s\n' "${BD_VERSION}" >> "${LOG_FILE}"
printf 'result=ok\n' >> "${LOG_FILE}"
printf 'bd=%s (%s)\n' "${BD_BIN}" "${BD_VERSION}"
printf 'beads log=%s\n' "${LOG_FILE}"
exit 0
