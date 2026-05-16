#!/bin/sh
#
# magi/doctor/check-deploy-prereqs.sh
# ==============================================================================
# Description: Doctor probe for magi-pack deploy prerequisites. Requires jq,
# rsync, sed, awk, find, and chmod unconditionally. When INSTALL_REMOTE_MCP=1
# additionally requires sshpass and ssh. Writes a structured log under the
# city's runtime/packs/magi/logs directory and exits 0 on success or 1 on
# any missing required command.
#
# USAGE:
#   ./check-deploy-prereqs.sh
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH         Gas City root (logs derive from this path)
#   INSTALL_REMOTE_MCP   When 1, sshpass + ssh become required
#
# DEPENDENCIES:
#   External: jq rsync sed awk find chmod (required); sshpass ssh (conditional)
# ==============================================================================
set -eu
VERB_LOG_DIR="${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs"
mkdir -p "${VERB_LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG_FILE="${VERB_LOG_DIR}/doctor-deploy-prereqs-${STAMP}.log"
missing=0
{
    printf 'check=deploy-prereqs stamp=%s\n' "${STAMP}"
    for cmd in jq rsync sed awk find chmod; do
        resolved="$(command -v "${cmd}" || printf '')"
        if [ -z "${resolved}" ]; then
            printf 'missing: %s\n' "${cmd}"
            missing=$((missing + 1))
        else
            printf 'ok: %s -> %s\n' "${cmd}" "${resolved}"
        fi
    done
    if [ "${INSTALL_REMOTE_MCP:-0}" = "1" ]; then
        for cmd in sshpass ssh; do
            resolved="$(command -v "${cmd}" || printf '')"
            if [ -z "${resolved}" ]; then
                printf 'missing (remote-mcp): %s\n' "${cmd}"
                missing=$((missing + 1))
            else
                printf 'ok (remote-mcp): %s -> %s\n' "${cmd}" "${resolved}"
            fi
        done
    else
        printf 'skip: sshpass ssh (INSTALL_REMOTE_MCP not 1)\n'
    fi
    printf 'missing_count=%d\n' "${missing}"
    if [ "${missing}" != "0" ]; then
        printf 'result=fail\n'
    else
        printf 'result=ok\n'
    fi
} >> "${LOG_FILE}"
printf 'deploy-prereqs log=%s\n' "${LOG_FILE}"
if [ "${missing}" != "0" ]; then
    printf 'missing %d required commands; see log\n' "${missing}" >&2
    exit 1
fi
printf 'all deploy prerequisites present\n'
exit 0
