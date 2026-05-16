#!/usr/bin/env bash
#
# Extensionless File Enforcement Hook
# ==============================================================================
# Blocks creation (Write tool) of files whose basename has no extension.
# Emits a one-shot per-turn warning when Claude Reads or Edits an existing
# extensionless file. The Edit warning is suppressed if the same path was
# already warned-on in the current turn (Read first, Edit second within a
# single turn produces exactly one warning).
#
# Definition of "no extension":
#   basename has zero `.` characters (e.g., Makefile, runbook, tree).
#   Dotfiles such as .gitignore, .env, .bashrc all contain a `.` and are
#   therefore allowed to be created -- they are intentional named conventions.
#
# Per-turn tracking file: ${PROJECT_TRACKING_DIR}/extensionless_warned_${SESSION_ID}
#   Reset by the companion UserPromptSubmit hook
#   (clear-extensionless-tracking.sh) at the start of every new turn.
#
# Exit codes:
#   0 -- allow tool call (with possible stderr warning)
#   2 -- block Write of an extensionless filename
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
[[ -f "${SHARED_UTILS}/project-key.sh" ]] || { printf 'ERROR: Missing utility: %s/project-key.sh\n' "${SHARED_UTILS}" >&2; exit 1; }
source "${SHARED_UTILS}/project-key.sh"
readonly RED='\033[0;31m'
readonly YELLOW='\033[0;33m'
readonly NC='\033[0m'
INPUT="$(cat)"
TOOL_NAME="$(printf '%s' "${INPUT}" | jq -r '.tool_name // "unknown"')"
FILE_PATH="$(printf '%s' "${INPUT}" | jq -r '.tool_input.file_path // ""')"
SESSION_ID="$(printf '%s' "${INPUT}" | jq -r '.session_id // "default"')"
CWD="$(printf '%s' "${INPUT}" | jq -r '.cwd // ""')"
case "${TOOL_NAME}" in
    Write|Read|Edit) ;;
    *) exit 0 ;;
esac
[[ -n "${FILE_PATH}" ]] || exit 0
BASENAME="${FILE_PATH##*/}"
case "${BASENAME}" in
    *.*) exit 0 ;;
    "") exit 0 ;;
esac
resolve_project_paths "${CWD}"
WARN_FILE="${PROJECT_TRACKING_DIR}/extensionless_warned_${SESSION_ID}"
LOG_FILE="${PROJECT_ENFORCEMENT_LOG}"
log_msg() {
    local msg="$1"
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${msg}" >> "${LOG_FILE}" || true
}
emit_notice() {
    local verb="$1" path="$2"
    printf '%bNOTICE:%b You are %s a file that has no extension: %s\n' "${YELLOW}" "${NC}" "${verb}" "${path}" >&2
    printf 'If this is a critical component of the project you are working on, you will\n' >&2
    printf 'not be able to create files without extensions in the future. Please heavily\n' >&2
    printf 'consider adding an extension to this file.\n' >&2
}
record_warned() {
    local path="$1"
    printf '%s\n' "${path}" >> "${WARN_FILE}"
}
already_warned() {
    local path="$1"
    [[ -f "${WARN_FILE}" ]] || return 1
    grep -qxF -- "${path}" "${WARN_FILE}"
}
case "${TOOL_NAME}" in
    Write)
        log_msg "BLOCKED extensionless create (Write): ${FILE_PATH}"
        printf '%bBLOCKED:%b Refusing to create file without an extension: %s\n' "${RED}" "${NC}" "${FILE_PATH}" >&2
        printf '\n' >&2
        printf 'WHY: Extensionless files break syntax highlighting, language servers, indexers,\n' >&2
        printf '     formatters, linters, and CI tooling that key off file extensions.\n' >&2
        printf '\n' >&2
        printf 'FIX: Add an explicit extension that reflects the file type:\n' >&2
        printf '       documentation -> .md\n' >&2
        printf '       shell scripts -> .sh / .bash\n' >&2
        printf '       config        -> .yaml / .toml / .json / .ini / .conf\n' >&2
        printf '       data / notes  -> .txt / .csv / .log\n' >&2
        printf '\n' >&2
        printf 'If you genuinely need a tool-conventional extensionless file (Makefile,\n' >&2
        printf 'Dockerfile, LICENSE), ask the user to create it manually. Do not retry\n' >&2
        printf 'with another extensionless name.\n' >&2
        exit 2
        ;;
    Read)
        if ! already_warned "${FILE_PATH}"; then
            record_warned "${FILE_PATH}"
            log_msg "WARN extensionless read: ${FILE_PATH}"
            emit_notice "reading from" "${FILE_PATH}"
        fi
        exit 0
        ;;
    Edit)
        if already_warned "${FILE_PATH}"; then
            exit 0
        fi
        record_warned "${FILE_PATH}"
        log_msg "WARN extensionless edit: ${FILE_PATH}"
        emit_notice "editing" "${FILE_PATH}"
        exit 0
        ;;
esac
exit 0
