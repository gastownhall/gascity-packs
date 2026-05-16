#!/usr/bin/env bash
#
# Session Tracker Hook
# ==============================================================================
# Logs Claude Code session start/end events to a TSV file for session tracking.
# This log lives globally at ~/.claude/sessions/session-log.tsv -- it is the
# canonical session-id -> project mapping audit trail and intentionally
# stays at the global location (not per-project).
# ==============================================================================
set -Eeuo pipefail
OS="$(uname -s)"
readonly OS
[[ "${OS}" == "Darwin" || "${OS}" == "Linux" ]] || { printf 'ERROR: Unsupported OS: %s\n' "${OS}" >&2; exit 1; }
readonly SESSION_DIR="${HOME}/.claude/sessions"
readonly SESSION_LOG="${SESSION_DIR}/session-log.tsv"
preflight() {
    local jq_path
    jq_path="$(command -v jq || true)"
    [[ -n "${jq_path}" ]] || { printf 'ERROR: jq is required but not installed\n' >&2; exit 1; }
    mkdir -p "${SESSION_DIR}"
    return 0
}
parse_input() {
    local input
    input="$(cat)"
    [[ -n "${input}" ]] || { printf 'ERROR: No input received on stdin\n' >&2; exit 1; }
    SESSION_ID="$(printf '%s' "${input}" | jq -r '.session_id // "unknown"')"
    CWD="$(printf '%s' "${input}" | jq -r '.cwd // "unknown"')"
    EVENT_NAME="$(printf '%s' "${input}" | jq -r '.hook_event_name // "unknown"')"
    TRANSCRIPT="$(printf '%s' "${input}" | jq -r '.transcript_path // ""')"
    if [[ "${EVENT_NAME}" == "SessionStart" ]]; then
        EVENT_TYPE="start"
        DETAIL="$(printf '%s' "${input}" | jq -r '.source // "unknown"')"
    elif [[ "${EVENT_NAME}" == "SessionEnd" ]]; then
        EVENT_TYPE="end"
        DETAIL="$(printf '%s' "${input}" | jq -r '.reason // "unknown"')"
    else
        EVENT_TYPE="unknown"
        DETAIL="unknown"
    fi
    return 0
}
write_header() {
    [[ -f "${SESSION_LOG}" ]] && return 0
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "TIMESTAMP" "EVENT" "DETAIL" "SESSION_ID" "DIRECTORY" "TRANSCRIPT" \
        > "${SESSION_LOG}"
    return 0
}
append_entry() {
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "${timestamp}" "${EVENT_TYPE}" "${DETAIL}" "${SESSION_ID}" "${CWD}" "${TRANSCRIPT}" \
        >> "${SESSION_LOG}"
    return 0
}
main() {
    preflight
    parse_input
    write_header
    append_entry
}
main "$@"
