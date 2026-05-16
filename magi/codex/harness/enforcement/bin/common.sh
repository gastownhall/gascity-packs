#!/usr/bin/env bash
# shellcheck disable=SC2034 # resolve_project_paths intentionally exposes globals to hook scripts.
set -Eeuo pipefail

readonly CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
readonly CODEX_ENFORCEMENT_DIR="${CODEX_ENFORCEMENT_DIR:-${CODEX_HOME}/enforcement}"
readonly CODEX_RULES_FILE="${CODEX_RULES_FILE:-${CODEX_ENFORCEMENT_DIR}/rules/enforcement_rules.json}"
readonly CODEX_STATE_DIR="${CODEX_STATE_DIR:-${CODEX_ENFORCEMENT_DIR}/state}"
readonly CODEX_LOG_DIR="${CODEX_LOG_DIR:-${CODEX_ENFORCEMENT_DIR}/logs}"
readonly CODEX_ENV_FILE="${CODEX_ENV_FILE:-${CODEX_ENFORCEMENT_DIR}/env}"
readonly CODEX_GUIDELINES_ROOT="${CODEX_GUIDELINES_ROOT:-${CODEX_ENFORCEMENT_DIR}/guidelines/guideline_documents}"
readonly CODEX_GUIDELINES_DIR="${CODEX_GUIDELINES_DIR:-${CODEX_GUIDELINES_ROOT}/xml}"
readonly CLAUDE_GUIDELINES_DIR="${CLAUDE_GUIDELINES_DIR:-${CODEX_GUIDELINES_DIR}}"

mkdir -p "${CODEX_STATE_DIR}" "${CODEX_LOG_DIR}"

load_codex_env_defaults() {
    local line key value
    [[ -f "${CODEX_ENV_FILE}" ]] || return 0
    while IFS= read -r line || [[ -n "${line}" ]]; do
        case "${line}" in
            ""|\#*) continue ;;
            *=*) ;;
            *) continue ;;
        esac
        key="${line%%=*}"
        value="${line#*=}"
        [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        if [[ -z "${!key+x}" ]]; then
            export "${key}=${value}"
        fi
    done < "${CODEX_ENV_FILE}"
}

load_codex_env_defaults

project_key_from_path() {
    local cwd="${1:-${PWD:-/}}"
    printf '%s' "${cwd}" | sed 's|^/||' | tr '/_.' '-'
}

resolve_project_paths() {
    local cwd="${1:-${PWD:-/}}"
    PROJECT_KEY="$(project_key_from_path "${cwd}")"
    PROJECT_DIR="${CODEX_STATE_DIR}/projects/-${PROJECT_KEY}"
    PROJECT_TRACKING_DIR="${PROJECT_DIR}/tracking"
    PROJECT_ENFORCEMENT_LOG="${PROJECT_DIR}/enforcement.log"
    PROJECT_SECURITY_LOG="${PROJECT_DIR}/security.log"
    PROJECT_QUALITY_LOG="${PROJECT_DIR}/quality-verification.log"
    PROJECT_SCRATCH_DIR="${PROJECT_DIR}/scratch"
    mkdir -p "${PROJECT_TRACKING_DIR}" "${PROJECT_SCRATCH_DIR}"
}

log_message() {
    local file="$1"
    local msg="$2"
    { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${msg}" >> "${file}"; } 2>/dev/null || true
}

json_get() {
    local input="$1"
    local query="$2"
    local fallback="${3:-}"
    printf '%s' "${input}" | jq -r "${query}" 2>/dev/null || printf '%s' "${fallback}"
}

match_regex() {
    local text="$1"
    local pattern="$2"
    PATTERN="${pattern}" perl -0ne '
        BEGIN { $pattern = $ENV{"PATTERN"}; $hit = 0; }
        if (/$pattern/m) { $hit = 1; }
        END { exit($hit ? 0 : 1); }
    ' <<< "${text}" 2>/dev/null
}

json_system_message() {
    local message="$1"
    jq -n --arg systemMessage "${message}" '{systemMessage: $systemMessage}'
}

json_additional_context() {
    local event="$1"
    local context="$2"
    jq -n \
        --arg event "${event}" \
        --arg context "${context}" \
        '{hookSpecificOutput: {hookEventName: $event, additionalContext: $context}}'
}

block_hook() {
    local message="$1"
    printf '%s\n' "${message}" >&2
    exit 2
}

validate_rules_file() {
    [[ -f "${CODEX_RULES_FILE}" ]] || return 0
    if ! jq empty "${CODEX_RULES_FILE}" >/dev/null 2>&1; then
        block_hook "BLOCKED: Codex enforcement rules file has invalid JSON: ${CODEX_RULES_FILE}"
    fi
}

tracking_file_for() {
    local session_id="$1"
    printf '%s/guidelines_read_%s' "${PROJECT_TRACKING_DIR}" "${session_id}"
}

guideline_key_for_path() {
    local path="$1"
    local base stem key
    base="${path##*/}"
    stem="${base%.*}"
    [[ -f "${CODEX_RULES_FILE}" ]] || return 0
    key="$(jq -r --arg base "${base}" --arg stem "${stem}" '
        .guideline_enforcements // {}
        | to_entries[]
        | select(
            .value.guideline_file == $base
            or (.value.guideline_file | sub("\\.[^.]+$"; "")) == $stem
          )
        | .value.tracking_key
    ' "${CODEX_RULES_FILE}" 2>/dev/null | head -n 1)"
    printf '%s' "${key}"
}

record_guideline_read() {
    local session_id="$1"
    local path="$2"
    local key tracking_file
    key="$(guideline_key_for_path "${path}")"
    [[ -n "${key}" ]] || return 0
    tracking_file="$(tracking_file_for "${session_id}")"
    printf '%s\n' "${key}" >> "${tracking_file}"
    date +%s > "${PROJECT_TRACKING_DIR}/guidelines_timestamp_${session_id}"
    log_message "${PROJECT_ENFORCEMENT_LOG}" "Tracked guideline read: ${key} (${path})"
}

guideline_path_for_key() {
    local key="$1"
    local guideline_file
    guideline_file="$(jq -r --arg key "${key}" '
        .guideline_enforcements // {}
        | to_entries[]
        | select(.value.tracking_key == $key)
        | .value.guideline_file
    ' "${CODEX_RULES_FILE}" 2>/dev/null | head -n 1)"
    [[ -n "${guideline_file}" && "${guideline_file}" != "null" ]] || return 0
    if [[ "${guideline_file}" == WRITING_STYLE.md ]]; then
        printf '%s/%s' "${CODEX_GUIDELINES_ROOT}" "${guideline_file}"
    else
        printf '%s/%s' "${CODEX_GUIDELINES_DIR}" "${guideline_file}"
    fi
}

language_for_path() {
    local path="$1"
    case "${path}" in
        *.py) printf 'python' ;;
        *.sh|*.bash) printf 'bash' ;;
        *.cs|*.csproj) printf 'csharp' ;;
        *.rs) printf 'rust' ;;
        pom.xml|*.java) printf 'maven' ;;
        *.tsx|*.ts|*.jsx|*.js|*.css|*.html) printf 'frontend' ;;
        *.ps1|*.psm1) printf 'powershell' ;;
        *.swift) printf 'swift' ;;
        *.sql) printf 'sql' ;;
        *.bicep) printf 'bicep' ;;
        *.vue) printf 'vue_nuxt' ;;
        *.pq|*.pqm) printf 'powerquery' ;;
        *.php) printf 'wordpress' ;;
        Dockerfile*|*.dockerfile) printf 'docker' ;;
        *.yaml|*.yml) printf 'kubernetes' ;;
        *) printf '' ;;
    esac
}
