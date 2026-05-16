#!/usr/bin/env bash
#
# History Per Project Hook
# ==============================================================================
# Separates global history.jsonl entries into project-specific history files.
# Project key collapse matches the Claude Code harness rules: '/', '_', and '.'
# all collapse to '-'. Earlier versions omitted the '.' collapse, which caused
# history files to land in a sibling bucket (e.g. -Users-<u>-.scripts vs the
# corrected -Users-<u>--scripts form).
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
OS="$(uname -s)"
readonly OS
[[ "${OS}" == "Darwin" || "${OS}" == "Linux" ]] || { printf 'ERROR: Unsupported OS: %s\n' "${OS}" >&2; exit 1; }
readonly PROJECT_DIR_INPUT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
resolve_project_paths "${PROJECT_DIR_INPUT}"
readonly CLAUDE_HOME="${MAGI_PACK_DIR}"
readonly GLOBAL_HISTORY="${CLAUDE_HOME}/history.jsonl"
readonly PROJECT_HISTORY="${PROJECT_DIR}/history.jsonl"
readonly TEMP_GLOBAL="${PROJECT_DIR}/.history-global.tmp"
readonly TEMP_PROJECT="${PROJECT_DIR}/.history-project.tmp"
preflight() {
    JQ_PATH="$(command -v jq || true)"
    [[ -n "${JQ_PATH}" ]] || exit 0
    [[ -d "${CLAUDE_HOME}" ]] || exit 0
}
read_hook_input() {
    local input
    input="$(cat)"
    [[ -n "${input}" ]] || exit 0
    local sid
    sid="$(printf '%s' "${input}" | jq -r '.session_id // empty' || true)"
    [[ -n "${sid}" ]] || exit 0
}
process_history() {
    [[ -f "${GLOBAL_HISTORY}" ]] || return 0
    local line_count=0 moved_count=0
    : > "${TEMP_GLOBAL}"
    if [[ -f "${PROJECT_HISTORY}" ]]; then
        cp "${PROJECT_HISTORY}" "${TEMP_PROJECT}"
    else
        : > "${TEMP_PROJECT}"
    fi
    while IFS= read -r line || [[ -n "${line}" ]]; do
        line_count=$((line_count + 1))
        local match
        match="$(printf '%s' "${line}" | jq -e --arg dir "${PROJECT_DIR_INPUT}" '.project == $dir or .cwd == $dir' 2>&1 || true)"
        if [[ "${match}" == "true" ]]; then
            printf '%s\n' "${line}" >> "${TEMP_PROJECT}"
            moved_count=$((moved_count + 1))
        else
            printf '%s\n' "${line}" >> "${TEMP_GLOBAL}"
        fi
    done < "${GLOBAL_HISTORY}"
    [[ -s "${TEMP_PROJECT}" ]] && mv -f "${TEMP_PROJECT}" "${PROJECT_HISTORY}"
    rm -f "${TEMP_PROJECT}" || true
    mv -f "${TEMP_GLOBAL}" "${GLOBAL_HISTORY}"
    printf 'History separation: processed %d lines, moved %d to project\n' "${line_count}" "${moved_count}"
}
cleanup() {
    local rc=$?
    set +e
    rm -f "${TEMP_GLOBAL}" "${TEMP_PROJECT}" || true
    exit "${rc}"
}
trap cleanup EXIT
main() {
    read_hook_input
    preflight
    process_history
}
main "$@"
