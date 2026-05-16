#!/bin/sh
#
# magi/doctor/check-launchd.sh
# ==============================================================================
# Description: Doctor probe for launchctl. On Darwin (macOS) launchctl is the
# system-managed scheduling daemon; magi's optional INSTALL_LAUNCHD path
# registers user-domain LaunchAgents through it. On Linux launchd does not
# exist; the probe exits 0 with an explanatory log entry.
#
# USAGE:
#   ./check-launchd.sh
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH   Gas City root (logs derive from this path)
#
# DEPENDENCIES:
#   External: launchctl (required on Darwin only)
# ==============================================================================
set -eu
VERB_LOG_DIR="${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs"
mkdir -p "${VERB_LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG_FILE="${VERB_LOG_DIR}/doctor-launchd-${STAMP}.log"
UNAME_S="$(uname -s)"
{
    printf 'check=launchd stamp=%s\n' "${STAMP}"
    printf 'uname_s=%s\n' "${UNAME_S}"
} >> "${LOG_FILE}"
case "${UNAME_S}" in
    Darwin)
        LAUNCHCTL_BIN="$(command -v launchctl || printf '')"
        if [ -z "${LAUNCHCTL_BIN}" ]; then
            printf 'result=fail reason=launchctl-missing\n' >> "${LOG_FILE}"
            printf 'launchctl missing on Darwin\n' >&2
            printf 'launchd log=%s\n' "${LOG_FILE}" >&2
            exit 1
        fi
        printf 'launchctl=%s\n' "${LAUNCHCTL_BIN}" >> "${LOG_FILE}"
        printf 'result=ok\n' >> "${LOG_FILE}"
        printf 'launchctl present at %s\n' "${LAUNCHCTL_BIN}"
        printf 'launchd log=%s\n' "${LOG_FILE}"
        exit 0
        ;;
    Linux)
        printf 'result=ok reason=not-applicable\n' >> "${LOG_FILE}"
        printf 'launchd not applicable on Linux\n'
        printf 'launchd log=%s\n' "${LOG_FILE}"
        exit 0
        ;;
    *)
        printf 'result=warn reason=unsupported-os\n' >> "${LOG_FILE}"
        printf 'unsupported OS: %s\n' "${UNAME_S}" >&2
        printf 'launchd log=%s\n' "${LOG_FILE}" >&2
        exit 2
        ;;
esac
