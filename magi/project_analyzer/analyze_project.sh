#!/usr/bin/env bash
#
# analyze_project.sh
# ==============================================================================
# Entry point for project_analyzer. Walks a target project bottom-up and writes
# a `_DIRECTORY_OVERVIEW.md` into every directory using a local LM Studio
# server. Output files use a fixed structure suitable for LLM navigation.
#
# USAGE:
#   ./analyze_project.sh <absolute-path-to-project>
#
# OPTIONS:
#   None. Single positional argument is the project root path.
#
# ENVIRONMENT VARIABLES:
#   LM_API_TOKEN              Bearer token for LM Studio. Optional.
#   PROJECT_ANALYZER_MODEL    Model key. Default: qwen/qwen3-coder-next.
#   PROJECT_ANALYZER_LM_URL   LM Studio base URL. Default: http://localhost:1234.
#   PROJECT_ANALYZER_FORCE    "1" to regenerate even when source hash matches.
#   PROJECT_ANALYZER_CONTEXT  Context length for model load. Default: 32768.
#
# DEPENDENCIES:
#   Internal: _analyzer.py
#   External: python3 (3.10+), tree, jq, curl, brew (macOS only, for bootstrap)
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
OS="$(uname -s)"
readonly OS
[[ "${OS}" == "Darwin" || "${OS}" == "Linux" ]] || { printf 'ERROR: Unsupported OS: %s\n' "${OS}" >&2; exit 1; }
if ((BASH_VERSINFO[0] < 4)); then
    printf 'ERROR: This script requires bash 4.0+ (found %s)\n' "${BASH_VERSION}" >&2
    exit 1
fi
readonly DEFAULT_MODEL="qwen/qwen3-coder-next"
readonly DEFAULT_LM_URL="http://localhost:1234"
readonly DEFAULT_CONTEXT_LENGTH="32768"
readonly VENV_DIR="${SCRIPT_DIR}/.venv"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly WORK_DIR="${SCRIPT_DIR}/.work"
readonly ENGINE="${SCRIPT_DIR}/_analyzer.py"
readonly REQ_PYDANTIC="pydantic>=2,<3"
readonly LM_URL="${PROJECT_ANALYZER_LM_URL:-${DEFAULT_LM_URL}}"
readonly MODEL="${PROJECT_ANALYZER_MODEL:-${DEFAULT_MODEL}}"
readonly FORCE_FLAG="${PROJECT_ANALYZER_FORCE:-0}"
readonly CONTEXT_LENGTH="${PROJECT_ANALYZER_CONTEXT:-${DEFAULT_CONTEXT_LENGTH}}"
LM_API_TOKEN="${LM_API_TOKEN:-}"
export LM_API_TOKEN
readonly TIMESTAMP="$(date '+%Y%m%dT%H%M%S')"
readonly WRAPPER_LOG="${LOG_DIR}/wrapper_${TIMESTAMP}.log"
log_ts() { date '+%Y-%m-%dT%H:%M:%S%z'; }
log_info() { printf '[%s] [INFO]  %s\n' "$(log_ts)" "$*" | tee -a "${WRAPPER_LOG}"; }
log_warn() { printf '[%s] [WARN]  %s\n' "$(log_ts)" "$*" | tee -a "${WRAPPER_LOG}" >&2; }
log_error() { printf '[%s] [ERROR] %s\n' "$(log_ts)" "$*" | tee -a "${WRAPPER_LOG}" >&2; }
on_error() {
    local rc=$? line="${BASH_LINENO[0]}" cmd="${BASH_COMMAND}"
    printf '[%s] [ERROR] wrapper.crashed rc=%d line=%d cmd=%q\n' "$(log_ts)" "${rc}" "${line}" "${cmd}" | tee -a "${WRAPPER_LOG}" >&2
}
trap on_error ERR
command_exists() {
    local cmd_path
    cmd_path="$(command -v "$1" || true)"
    [[ -n "${cmd_path}" ]]
}
ensure_command() {
    local cmd="$1" pkg="${2:-$1}"
    command_exists "${cmd}" && return 0
    log_warn "missing.command name=${cmd} attempting_install_via=${OS}"
    case "${OS}" in
        Darwin)
            command_exists brew || { log_error "homebrew.missing install ${cmd} manually."; return 3; }
            brew install "${pkg}" >> "${WRAPPER_LOG}" 2>&1 || { log_error "brew.install_failed pkg=${pkg}"; return 3; }
            ;;
        Linux)
            if command_exists apt-get; then
                sudo apt-get update >> "${WRAPPER_LOG}" 2>&1 && sudo apt-get install -y "${pkg}" >> "${WRAPPER_LOG}" 2>&1 || { log_error "apt.install_failed pkg=${pkg}"; return 3; }
            elif command_exists dnf; then
                sudo dnf install -y "${pkg}" >> "${WRAPPER_LOG}" 2>&1 || { log_error "dnf.install_failed pkg=${pkg}"; return 3; }
            else
                log_error "no_supported_pkg_manager install ${cmd} manually."
                return 3
            fi
            ;;
    esac
    command_exists "${cmd}" || { log_error "post_install.binary_missing name=${cmd}"; return 3; }
    log_info "install.success name=${cmd}"
    return 0
}
ensure_python_venv() {
    if [[ ! -d "${VENV_DIR}" ]]; then
        log_info "venv.create path=${VENV_DIR}"
        python3 -m venv "${VENV_DIR}" >> "${WRAPPER_LOG}" 2>&1 || { log_error "venv.create_failed path=${VENV_DIR}"; return 3; }
    fi
    local pip="${VENV_DIR}/bin/pip"
    [[ -x "${pip}" ]] || { log_error "venv.pip_missing path=${pip}"; return 3; }
    "${pip}" install --quiet --upgrade pip >> "${WRAPPER_LOG}" 2>&1 || log_warn "pip.self_upgrade_failed continuing"
    "${pip}" install --quiet "${REQ_PYDANTIC}" >> "${WRAPPER_LOG}" 2>&1 || { log_error "pip.install_failed dep=${REQ_PYDANTIC}"; return 3; }
    return 0
}
verify_lm_studio() {
    local probe_body="${WORK_DIR}/lm_probe_${TIMESTAMP}.body"
    local probe_status
    local probe_url="${LM_URL}/api/v1/models"
    if probe_status="$(curl --silent --show-error --connect-timeout 5 --max-time 30 --output "${probe_body}" --write-out '%{http_code}' --header "Authorization: Bearer ${LM_API_TOKEN}" "${probe_url}")"; then
        :
    else
        local rc=$?
        rm -f "${probe_body}"
        log_error "lmstudio.unreachable url=${LM_URL} rc=${rc}; start with: lms server start"
        return 3
    fi
    rm -f "${probe_body}"
    [[ "${probe_status}" == "200" ]] || { log_error "lmstudio.unhealthy url=${LM_URL} http=${probe_status}"; return 3; }
    log_info "lmstudio.reachable url=${LM_URL}"
    return 0
}
preflight() {
    [[ -f "${ENGINE}" ]] || { log_error "engine.missing path=${ENGINE}"; return 3; }
    ensure_command python3 python || return 3
    ensure_command tree tree || return 3
    ensure_command jq jq || return 3
    ensure_command curl curl || return 3
    ensure_python_venv || return 3
    verify_lm_studio || return 3
    return 0
}
run_engine() {
    local project_root="$1"
    local project_basename
    project_basename="$(basename -- "${project_root}")"
    local engine_log="${LOG_DIR}/engine_${project_basename}_${TIMESTAMP}.log"
    log_info "engine.start project=${project_root} model=${MODEL} log=${engine_log}"
    local args=("${ENGINE}" "${project_root}" "--lm-url" "${LM_URL}" "--model" "${MODEL}" "--context-length" "${CONTEXT_LENGTH}" "--log-file" "${engine_log}")
    [[ "${FORCE_FLAG}" == "1" ]] && args+=("--force")
    local rc=0
    "${VENV_DIR}/bin/python" "${args[@]}" || rc=$?
    if [[ ${rc} -eq 0 ]]; then
        log_info "engine.success project=${project_root}"
    else
        log_error "engine.failed project=${project_root} rc=${rc} log=${engine_log}"
    fi
    return ${rc}
}
count_overviews() {
    local project_root="$1"
    local count=0
    while IFS= read -r -d '' _; do
        count=$((count + 1))
    done < <(find "${project_root}" -type f -name "_DIRECTORY_OVERVIEW.md" -print0)
    printf '%d\n' "${count}"
}
usage() {
    printf 'USAGE: %s <absolute-path-to-project>\n' "${BASH_SOURCE[0]}" >&2
    return 2
}
main() {
    mkdir -p "${LOG_DIR}" "${WORK_DIR}"
    : >> "${WRAPPER_LOG}"
    [[ $# -eq 1 ]] || { usage; exit 2; }
    local project_root="$1"
    [[ "${project_root:0:1}" == "/" ]] || { log_error "path.not_absolute path=${project_root}"; exit 2; }
    [[ -d "${project_root}" ]] || { log_error "path.not_directory path=${project_root}"; exit 2; }
    project_root="$(cd -P -- "${project_root}" && pwd)"
    log_info "wrapper.start project=${project_root} model=${MODEL} lm_url=${LM_URL} force=${FORCE_FLAG} context=${CONTEXT_LENGTH}"
    preflight || exit $?
    local rc=0
    run_engine "${project_root}" || rc=$?
    local overview_count
    overview_count="$(count_overviews "${project_root}")"
    if [[ ${rc} -eq 0 ]]; then
        log_info "wrapper.done project=${project_root} overviews=${overview_count} wrapper_log=${WRAPPER_LOG}"
    else
        log_error "wrapper.failed project=${project_root} rc=${rc} overviews=${overview_count} wrapper_log=${WRAPPER_LOG}"
    fi
    return ${rc}
}
main "$@"
