#!/usr/bin/env bash
#
# gemini-hook.sh - stub Gemini enforcement hook target
# ==============================================================================
# Modeled on the codex enforcement hook bridge. Reads a JSON event payload on
# stdin (Gemini's hook protocol), dispatches based on the event name, and
# appends to a per-event log under ${GEMINI_HOME}/enforcement/logs/. This
# file is a stub that the pack ships so the deploy_gemini.sh installer has a
# concrete artifact to copy. Real policy decisions are loaded from
# ${GEMINI_HOME}/policies/enforcement.toml at runtime by future hook logic;
# this stub records the event without blocking. Idempotent and self-bounded.
#
# USAGE:
#   echo '{"event":"prePrompt","payload":{...}}' | gemini-hook.sh
#
# ENVIRONMENT VARIABLES:
#   GEMINI_HOME    Gemini target home; defaults to ${HOME}/.gemini
#
# DEPENDENCIES:
#   External: date awk sed
# ==============================================================================
set -Eeuo pipefail
GEMINI_HOME="${GEMINI_HOME:-${HOME}/.gemini}"
readonly GEMINI_HOME
LOG_DIR="${GEMINI_HOME}/enforcement/logs"
readonly LOG_DIR
mkdir -p "${LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
readonly STAMP
PAYLOAD_FILE="${LOG_DIR}/hook-input-${STAMP}.json"
readonly PAYLOAD_FILE
if [[ -t 0 ]]; then
    EVENT="manual"
    PAYLOAD=""
    printf '%s\n' "{}" > "${PAYLOAD_FILE}"
else
    PAYLOAD="$(cat)"
    printf '%s\n' "${PAYLOAD}" > "${PAYLOAD_FILE}"
    EVENT="$(printf '%s' "${PAYLOAD}" | sed -nE 's/.*"event"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')"
    if [[ -z "${EVENT}" ]]; then
        EVENT="unknown"
    fi
fi
readonly EVENT
EVENT_LOG="${LOG_DIR}/${EVENT}-${STAMP}.log"
readonly EVENT_LOG
{
    printf 'event=%s\n' "${EVENT}"
    printf 'stamp=%s\n' "${STAMP}"
    printf 'gemini_home=%s\n' "${GEMINI_HOME}"
    printf 'payload_file=%s\n' "${PAYLOAD_FILE}"
    printf 'pid=%s\n' "$$"
} >> "${EVENT_LOG}"
case "${EVENT}" in
    prePrompt|postPrompt|preCommand|postCommand|preTool|postTool|sessionStart|sessionEnd|manual|unknown)
        printf 'gemini-hook event=%s logged=%s\n' "${EVENT}" "${EVENT_LOG}"
        exit 0
        ;;
    *)
        printf 'gemini-hook: unrecognized event %s; logged anyway\n' "${EVENT}" >&2
        exit 0
        ;;
esac
