#!/usr/bin/env bash
#
# magi/gemini/deploy_gemini.sh - install the magi-built Gemini harness
# ==============================================================================
# Idempotent installer for the pack-built Gemini enforcement harness. Mirrors
# the shape of codex/deploy_harness.sh. Copies the self-contained enforcement
# tree under the harness/ directory next to this script, ensures the
# gemini-hook.sh bridge is present under ${GEMINI_HOME}/enforcement/bin/, and
# writes a policies/enforcement.toml skeleton (preserving any pre-existing
# values via a timestamped backup). Safe to re-run.
#
# USAGE:
#   ./deploy_gemini.sh
#   ./deploy_gemini.sh --target=DIR
#   ./deploy_gemini.sh --dry-run
#   ./deploy_gemini.sh --non-interactive
#   ./deploy_gemini.sh --skip-prereqs
#
# ENVIRONMENT VARIABLES:
#   GEMINI_HOME                  Target Gemini home when --target is omitted.
#   INSTALL_GEMINI_HOOKS         1 to install the hook bridge (default 1).
#   INSTALL_LM_STUDIO            1 to enable LM Studio quality review wiring.
#   LM_STUDIO_HOST               OpenAI-compatible reviewer host.
#   LM_STUDIO_PORT               OpenAI-compatible reviewer port.
#   LM_STUDIO_MODEL              Reviewer model name.
#   GEMINI_TURN_CONTENT_LIMIT    Per-turn token budget hint for hook policy.
#
# DEPENDENCIES:
#   External: rsync mkdir cp date awk find chmod
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
PACK_DIR="$(cd -P -- "${SCRIPT_DIR}/.." && pwd)"
readonly PACK_DIR
readonly HARNESS_DIR="${SCRIPT_DIR}/harness"
readonly ENV_FILE="${PACK_DIR}/.env"
TS="$(date '+%Y%m%d-%H%M%S')"
readonly TS
OS_NAME="$(uname -s)"
readonly OS_NAME
case "${OS_NAME}" in
    Darwin|Linux) : ;;
    *) printf 'ERROR: unsupported OS: %s\n' "${OS_NAME}" >&2; exit 1 ;;
esac
DEPLOY_TARGET="${GEMINI_HOME:-${HOME}/.gemini}"
DRY_RUN=0
NON_INTERACTIVE=0
SKIP_PREREQS=0
for arg in "$@"; do
    case "${arg}" in
        --target=*) DEPLOY_TARGET="${arg#--target=}" ;;
        --dry-run) DRY_RUN=1 ;;
        --non-interactive) NON_INTERACTIVE=1 ;;
        --skip-prereqs) SKIP_PREREQS=1 ;;
        -h|--help)
            sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            printf 'unknown argument: %s\n' "${arg}" >&2
            exit 1
            ;;
    esac
done
readonly DEPLOY_TARGET DRY_RUN NON_INTERACTIVE SKIP_PREREQS
readonly SCRATCH_DIR="${SCRIPT_DIR}/.deploy_scratch"
readonly LOG_DIR="${SCRIPT_DIR}/.deploy_logs"
mkdir -p "${LOG_DIR}"
readonly LOG_FILE="${LOG_DIR}/deploy_gemini-${TS}.log"
if [[ -t 1 ]]; then
    readonly RST=$'\033[0m'
    readonly FG_R=$'\033[31m'
    readonly FG_G=$'\033[32m'
    readonly FG_Y=$'\033[33m'
    readonly FG_B=$'\033[34m'
    readonly FG_C=$'\033[36m'
    readonly FG_W=$'\033[37m'
    readonly BD_C=$'\033[1;36m'
else
    readonly RST=''
    readonly FG_R=''
    readonly FG_G=''
    readonly FG_Y=''
    readonly FG_B=''
    readonly FG_C=''
    readonly FG_W=''
    readonly BD_C=''
fi
log_to_file() {
    printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >> "${LOG_FILE}"
}
log_action() {
    printf '%b\n' "${FG_B}$*${RST}"
    log_to_file "ACTION: $*"
}
log_ok() {
    printf '%b\n' "${FG_G}$*${RST}"
    log_to_file "OK: $*"
}
log_warn() {
    printf '%b\n' "${FG_Y}WARN: $*${RST}" >&2
    log_to_file "WARN: $*"
}
log_error() {
    printf '%b\n' "${FG_R}ERROR: $*${RST}" >&2
    log_to_file "ERROR: $*"
}
log_detail() {
    printf '%b\n' "${FG_C}$*${RST}"
    log_to_file "DETAIL: $*"
}
section() {
    printf '\n%b\n' "${BD_C}== $* ==${RST}"
    log_to_file "SECTION: $*"
}
cleanup() {
    set +e
    if [[ -d "${SCRATCH_DIR}" ]]; then
        rm -rf "${SCRATCH_DIR}" || true
    fi
    set -e
}
trap cleanup EXIT
preflight() {
    section "Prerequisites"
    if [[ "${SKIP_PREREQS}" == "1" ]]; then
        log_warn "skipping prereq check (--skip-prereqs)"
        return 0
    fi
    local errors=0
    local cmd
    local resolved
    for cmd in rsync mkdir cp date awk find chmod; do
        resolved="$(command -v "${cmd}" || printf '')"
        if [[ -n "${resolved}" ]]; then
            log_ok "${cmd} found at ${resolved}"
        else
            log_error "missing required command: ${cmd}"
            errors=$((errors + 1))
        fi
    done
    if (( errors > 0 )); then
        log_error "preflight failed (${errors} errors)"
        exit 3
    fi
}
load_env() {
    if [[ "${MAGI_PACK_ENV_LOADED:-0}" == "1" ]]; then
        log_action "pack .env already loaded by magi"
        return 0
    fi
    if [[ -f "${ENV_FILE}" ]]; then
        log_action "loading ${ENV_FILE}"
        set -a
        # shellcheck disable=SC1090
        source "${ENV_FILE}"
        set +a
    else
        log_detail ".env not found; using inherited env and defaults"
    fi
}
run_mkdir() {
    local path="$1"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] mkdir -p ${path}"
    else
        mkdir -p "${path}"
    fi
}
run_cp() {
    local src="$1" dst="$2"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] cp -a ${src} ${dst}"
    else
        cp -a "${src}" "${dst}"
    fi
}
run_rsync() {
    local src="$1" dst="$2"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] rsync -a --exclude=.DS_Store ${src} ${dst}"
    else
        rsync -a --exclude='.DS_Store' "${src}" "${dst}"
    fi
}
backup_existing() {
    local path="$1"
    if [[ -e "${path}" ]]; then
        local backup_path="${path}_backup-${TS}"
        if [[ "${DRY_RUN}" == "1" ]]; then
            log_detail "[dry-run] cp -a ${path} ${backup_path}"
        else
            cp -a "${path}" "${backup_path}"
            log_detail "backed up existing ${path} -> ${backup_path}"
        fi
    fi
}
ensure_target_layout() {
    section "Target layout"
    run_mkdir "${DEPLOY_TARGET}"
    run_mkdir "${DEPLOY_TARGET}/enforcement"
    run_mkdir "${DEPLOY_TARGET}/enforcement/bin"
    run_mkdir "${DEPLOY_TARGET}/enforcement/logs"
    run_mkdir "${DEPLOY_TARGET}/policies"
}
install_hook_bridge() {
    section "Hook bridge"
    if [[ "${INSTALL_GEMINI_HOOKS:-1}" != "1" ]]; then
        log_warn "INSTALL_GEMINI_HOOKS != 1; skipping hook bridge"
        return 0
    fi
    local src="${HARNESS_DIR}/enforcement/bin/gemini-hook.sh"
    local dst="${DEPLOY_TARGET}/enforcement/bin/gemini-hook.sh"
    if [[ ! -f "${src}" ]]; then
        log_error "hook source missing: ${src}"
        return 1
    fi
    backup_existing "${dst}"
    run_cp "${src}" "${dst}"
    if [[ "${DRY_RUN}" != "1" ]]; then
        chmod 0755 "${dst}"
    else
        log_detail "[dry-run] chmod 0755 ${dst}"
    fi
    log_ok "hook bridge installed at ${dst}"
}
install_policy_template() {
    section "Policy template"
    local src="${HARNESS_DIR}/policies/enforcement.toml"
    local dst="${DEPLOY_TARGET}/policies/enforcement.toml"
    if [[ ! -f "${src}" ]]; then
        log_error "policy template missing: ${src}"
        return 1
    fi
    if [[ -f "${dst}" ]]; then
        backup_existing "${dst}"
        log_detail "existing policy retained; magi did not overwrite"
        log_detail "review backup vs ${src} to merge"
    else
        run_cp "${src}" "${dst}"
        log_ok "policy template installed at ${dst}"
    fi
}
write_runtime_env() {
    section "Runtime env"
    local env_dst="${DEPLOY_TARGET}/enforcement/env.runtime"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] would write ${env_dst}"
        return 0
    fi
    backup_existing "${env_dst}"
    {
        printf '# Generated by magi deploy_gemini.sh at %s\n' "${TS}"
        printf 'GEMINI_HOME=%s\n' "${DEPLOY_TARGET}"
        printf 'INSTALL_LM_STUDIO=%s\n' "${INSTALL_LM_STUDIO:-0}"
        printf 'LM_STUDIO_HOST=%s\n' "${LM_STUDIO_HOST:-localhost}"
        printf 'LM_STUDIO_PORT=%s\n' "${LM_STUDIO_PORT:-1234}"
        printf 'LM_STUDIO_MODEL=%s\n' "${LM_STUDIO_MODEL:-}"
        printf 'GEMINI_TURN_CONTENT_LIMIT=%s\n' "${GEMINI_TURN_CONTENT_LIMIT:-8192}"
    } > "${env_dst}"
    chmod 0600 "${env_dst}"
    log_ok "runtime env written to ${env_dst}"
}
main() {
    section "deploy_gemini.sh starting"
    log_detail "target=${DEPLOY_TARGET} dry_run=${DRY_RUN} non_interactive=${NON_INTERACTIVE}"
    log_detail "log_file=${LOG_FILE}"
    load_env
    preflight
    ensure_target_layout
    install_hook_bridge
    install_policy_template
    write_runtime_env
    section "deploy_gemini.sh complete"
    log_ok "Gemini harness installed at ${DEPLOY_TARGET}"
}
main "$@"
