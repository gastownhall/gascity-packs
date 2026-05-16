#!/bin/sh
#
# magi/doctor/check-ssh.sh
# ==============================================================================
# Description: Doctor probe for sshpass + ssh. These are required only when
# INSTALL_REMOTE_MCP=1 (claude target installs MCP binaries onto a remote LSP
# host). When not required the absence is logged as a warning (rc=2). When
# required and either binary is missing the probe fails (rc=1).
#
# USAGE:
#   ./check-ssh.sh
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH         Gas City root (logs derive from this path)
#   INSTALL_REMOTE_MCP   When 1, sshpass + ssh are required (not optional)
#
# DEPENDENCIES:
#   External: sshpass ssh (conditional)
# ==============================================================================
set -eu
VERB_LOG_DIR="${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs"
mkdir -p "${VERB_LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG_FILE="${VERB_LOG_DIR}/doctor-ssh-${STAMP}.log"
REQUIRED="${INSTALL_REMOTE_MCP:-0}"
SSHPASS_BIN="$(command -v sshpass || printf '')"
SSH_BIN="$(command -v ssh || printf '')"
{
    printf 'check=ssh stamp=%s\n' "${STAMP}"
    printf 'required=%s\n' "${REQUIRED}"
    printf 'sshpass=%s\n' "${SSHPASS_BIN}"
    printf 'ssh=%s\n' "${SSH_BIN}"
} >> "${LOG_FILE}"
if [ -z "${SSHPASS_BIN}" ] || [ -z "${SSH_BIN}" ]; then
    if [ "${REQUIRED}" = "1" ]; then
        printf 'result=fail reason=missing-and-required\n' >> "${LOG_FILE}"
        printf 'sshpass and/or ssh missing while INSTALL_REMOTE_MCP=1\n' >&2
        printf 'ssh log=%s\n' "${LOG_FILE}" >&2
        exit 1
    fi
    printf 'result=warn reason=missing-but-not-required\n' >> "${LOG_FILE}"
    printf 'sshpass/ssh not on PATH (remote MCP install would fail; ok otherwise)\n' >&2
    printf 'ssh log=%s\n' "${LOG_FILE}" >&2
    exit 2
fi
printf 'result=ok\n' >> "${LOG_FILE}"
printf 'sshpass=%s ssh=%s\n' "${SSHPASS_BIN}" "${SSH_BIN}"
printf 'ssh log=%s\n' "${LOG_FILE}"
exit 0
