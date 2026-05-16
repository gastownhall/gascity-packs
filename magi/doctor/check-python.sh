#!/bin/sh
#
# magi/doctor/check-python.sh
# ==============================================================================
# Description: Doctor probe that asserts python3 is on PATH and reports version
# at least 3.10. The magi pack's Python orchestrators rely on standard-library
# typing features introduced in 3.10 (PEP 604 union syntax via __future__,
# match statements) so any older interpreter is a hard failure. Writes a log
# under the city's runtime/packs/magi/logs directory.
#
# USAGE:
#   ./check-python.sh
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH   Gas City root (logs derive from this path)
#
# DEPENDENCIES:
#   External: python3 (required, version 3.10+)
# ==============================================================================
set -eu
VERB_LOG_DIR="${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs"
mkdir -p "${VERB_LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG_FILE="${VERB_LOG_DIR}/doctor-python-${STAMP}.log"
PYTHON_BIN="$(command -v python3 || printf '')"
if [ -z "${PYTHON_BIN}" ]; then
    {
        printf 'check=python stamp=%s\n' "${STAMP}"
        printf 'result=fail reason=python3-missing\n'
    } >> "${LOG_FILE}"
    printf 'python3 not found; install Python 3.10 or newer\n' >&2
    printf 'python log=%s\n' "${LOG_FILE}" >&2
    exit 1
fi
VERSION_RAW="$(${PYTHON_BIN} --version)"
VERSION_NUM="$(printf '%s' "${VERSION_RAW}" | awk '{print $2}')"
MAJOR="$(printf '%s' "${VERSION_NUM}" | awk -F. '{print $1}')"
MINOR="$(printf '%s' "${VERSION_NUM}" | awk -F. '{print $2}')"
{
    printf 'check=python stamp=%s\n' "${STAMP}"
    printf 'bin=%s\n' "${PYTHON_BIN}"
    printf 'version=%s major=%s minor=%s\n' "${VERSION_NUM}" "${MAJOR}" "${MINOR}"
} >> "${LOG_FILE}"
if [ "${MAJOR}" -lt 3 ] || { [ "${MAJOR}" -eq 3 ] && [ "${MINOR}" -lt 10 ]; }; then
    printf 'result=fail reason=version-too-old\n' >> "${LOG_FILE}"
    printf 'python3 is %s; need 3.10+\n' "${VERSION_NUM}" >&2
    printf 'python log=%s\n' "${LOG_FILE}" >&2
    exit 1
fi
printf 'result=ok\n' >> "${LOG_FILE}"
printf 'python3 %s available at %s\n' "${VERSION_NUM}" "${PYTHON_BIN}"
printf 'python log=%s\n' "${LOG_FILE}"
exit 0
