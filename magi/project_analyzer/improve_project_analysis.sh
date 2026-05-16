#!/usr/bin/env bash
#
# improve_project_analysis.sh
# ==============================================================================
# Sibling tool to `analyze_project.sh`. Runs AFTER `analyze_project.sh` has
# generated `_DIRECTORY_OVERVIEW.md` files. For every directory: a three-model
# pipeline produces a verified `_IMPROVEMENTS.md`. After per-directory passes,
# a final aggregator pass produces `_PROJECT_IMPROVEMENT_BACKLOG.md` at the
# project root.
#
# Pipeline:
#   1. Draft     -- nvidia/nemotron-3-nano-omni
#   2. Verify    -- nvidia/nemotron-3-super
#   3. Aggregate -- minimax/minimax-m2.7
#
# Each model is loaded into LM Studio at startup. The engine dispatches per
# pass to the correct model.
#
# USAGE:
#   ./improve_project_analysis.sh <absolute-path-to-project>
#
# OPTIONS:
#   None. Single positional argument is the project root path.
#
# ENVIRONMENT VARIABLES:
#   LM_API_TOKEN                       Bearer token for LM Studio. Optional.
#   PROJECT_ANALYZER_DRAFT_MODEL       Override draft model (default nvidia/nemotron-3-nano-omni).
#   PROJECT_ANALYZER_VERIFY_MODEL      Override verify model (default nvidia/nemotron-3-super).
#   PROJECT_ANALYZER_AGGREGATE_MODEL   Override aggregate model (default minimax/minimax-m2.7).
#   PROJECT_ANALYZER_LM_URL            LM Studio base URL (default http://localhost:1234).
#   PROJECT_ANALYZER_FORCE             "1" to regenerate even when source hash matches.
#   PROJECT_ANALYZER_CONTEXT           Context length for model load (default 32768).
#   PROJECT_ANALYZER_SKIP_AGGREGATE    "1" to skip the project backlog pass.
#   PROJECT_ANALYZER_ONLY_AGGREGATE    "1" to skip per-dir and only run the backlog pass.
#
# DEPENDENCIES:
#   Internal: _improver.py
#   External: python3, curl, brew (macOS only, for bootstrap)
#
# This script is INTENTIONALLY ISOLATED from analyze_project.sh. Do not merge
# them, do not factor a `common.sh`. They share only the project tree on disk.
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
readonly DEFAULT_DRAFT_MODEL="nvidia/nemotron-3-nano-omni"
readonly DEFAULT_VERIFY_MODEL="nvidia/nemotron-3-super"
readonly DEFAULT_AGGREGATE_MODEL="minimax/minimax-m2.7"
readonly DEFAULT_LM_URL="http://localhost:1234"
readonly DEFAULT_CONTEXT_LENGTH="32768"
readonly OVERVIEW_FILENAME="_DIRECTORY_OVERVIEW.md"
readonly VENV_DIR="${SCRIPT_DIR}/.venv"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly WORK_DIR="${SCRIPT_DIR}/.work"
readonly ENGINE="${SCRIPT_DIR}/_improver.py"
readonly REQ_PYDANTIC="pydantic>=2,<3"
readonly LM_URL="${PROJECT_ANALYZER_LM_URL:-${DEFAULT_LM_URL}}"
readonly DRAFT_MODEL="${PROJECT_ANALYZER_DRAFT_MODEL:-${DEFAULT_DRAFT_MODEL}}"
readonly VERIFY_MODEL="${PROJECT_ANALYZER_VERIFY_MODEL:-${DEFAULT_VERIFY_MODEL}}"
readonly AGGREGATE_MODEL="${PROJECT_ANALYZER_AGGREGATE_MODEL:-${DEFAULT_AGGREGATE_MODEL}}"
readonly FORCE_FLAG="${PROJECT_ANALYZER_FORCE:-0}"
readonly CONTEXT_LENGTH="${PROJECT_ANALYZER_CONTEXT:-${DEFAULT_CONTEXT_LENGTH}}"
readonly SKIP_AGGREGATE_FLAG="${PROJECT_ANALYZER_SKIP_AGGREGATE:-0}"
readonly ONLY_AGGREGATE_FLAG="${PROJECT_ANALYZER_ONLY_AGGREGATE:-0}"
readonly RESUME_FLAG="${PROJECT_ANALYZER_RESUME:-0}"
LM_API_TOKEN="${LM_API_TOKEN:-}"
export LM_API_TOKEN
TIMESTAMP="$(date '+%Y%m%dT%H%M%S')"
readonly TIMESTAMP
readonly WRAPPER_LOG="${LOG_DIR}/improver_wrapper_${TIMESTAMP}.log"
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
verify_analyzer_ran() {
    local project_root="$1"
    local root_overview="${project_root}/${OVERVIEW_FILENAME}"
    [[ -f "${root_overview}" ]] || {
        log_error "analyzer_not_run root_overview_missing path=${root_overview}"
        log_error "remediation: run analyze_project.sh ${project_root} first"
        return 3
    }
    local overview_count
    overview_count="$(find "${project_root}" -type f -name "${OVERVIEW_FILENAME}" -print | wc -l | tr -d ' ')"
    [[ "${overview_count}" -gt 0 ]] || {
        log_error "analyzer_not_run no_overviews_found project=${project_root}"
        return 3
    }
    log_info "analyzer.outputs_present overviews=${overview_count}"
    return 0
}
preflight() {
    [[ -f "${ENGINE}" ]] || { log_error "engine.missing path=${ENGINE}"; return 3; }
    ensure_command python3 python || return 3
    ensure_command curl curl || return 3
    ensure_python_venv || return 3
    verify_lm_studio || return 3
    return 0
}
run_engine() {
    local project_root="$1"
    local project_basename
    project_basename="$(basename -- "${project_root}")"
    local engine_log="${LOG_DIR}/improver_engine_${project_basename}_${TIMESTAMP}.log"
    log_info "engine.start project=${project_root} draft=${DRAFT_MODEL} verify=${VERIFY_MODEL} aggregate=${AGGREGATE_MODEL} log=${engine_log}"
    local args=(
        "${ENGINE}"
        "${project_root}"
        "--lm-url" "${LM_URL}"
        "--draft-model" "${DRAFT_MODEL}"
        "--verify-model" "${VERIFY_MODEL}"
        "--aggregate-model" "${AGGREGATE_MODEL}"
        "--context-length" "${CONTEXT_LENGTH}"
        "--log-file" "${engine_log}"
        "--work-root" "${WORK_DIR}"
    )
    [[ "${FORCE_FLAG}" == "1" ]] && args+=("--force")
    [[ "${SKIP_AGGREGATE_FLAG}" == "1" ]] && args+=("--skip-aggregate")
    [[ "${ONLY_AGGREGATE_FLAG}" == "1" ]] && args+=("--only-aggregate")
    [[ "${RESUME_FLAG}" == "1" ]] && args+=("--resume")
    local rc=0
    "${VENV_DIR}/bin/python" "${args[@]}" || rc=$?
    if [[ ${rc} -eq 0 ]]; then
        log_info "engine.success project=${project_root}"
    else
        log_error "engine.failed project=${project_root} rc=${rc} log=${engine_log}"
    fi
    return ${rc}
}
count_outputs() {
    local project_root="$1"
    local imp_count
    imp_count="$(find "${project_root}" -type f -name "_IMPROVEMENTS.md" -print | wc -l | tr -d ' ')"
    local backlog_present="missing"
    [[ -f "${project_root}/_PROJECT_IMPROVEMENT_BACKLOG.md" ]] && backlog_present="present"
    log_info "outputs.summary improvements_files=${imp_count} project_backlog=${backlog_present}"
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
    log_info "wrapper.start project=${project_root} draft=${DRAFT_MODEL} verify=${VERIFY_MODEL} aggregate=${AGGREGATE_MODEL} lm_url=${LM_URL} force=${FORCE_FLAG} context=${CONTEXT_LENGTH} skip_aggregate=${SKIP_AGGREGATE_FLAG} only_aggregate=${ONLY_AGGREGATE_FLAG}"
    preflight || exit $?
    verify_analyzer_ran "${project_root}" || exit $?
    local rc=0
    run_engine "${project_root}" || rc=$?
    count_outputs "${project_root}"
    if [[ ${rc} -eq 0 ]]; then
        log_info "wrapper.done project=${project_root} wrapper_log=${WRAPPER_LOG}"
    else
        log_error "wrapper.failed project=${project_root} rc=${rc} wrapper_log=${WRAPPER_LOG}"
    fi
    return ${rc}
}
main "$@"
