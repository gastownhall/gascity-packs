#!/usr/bin/env bash
#
# magi/openai/deploy_openai.sh - configure LM Studio for OpenAI-compatible use
# ==============================================================================
# Pack-built installer that lays out an LM Studio configuration directory and
# writes a config.toml from a template, substituting host/port/model/context
# placeholders from the environment. The optional --enable-launchd flag
# installs a macOS LaunchAgent plist that starts `lms server start` on boot.
# Safe to re-run: existing config and plist files are backed up with a
# timestamped suffix before being rewritten.
#
# USAGE:
#   ./deploy_openai.sh
#   ./deploy_openai.sh --target=DIR
#   ./deploy_openai.sh --dry-run
#   ./deploy_openai.sh --non-interactive
#   ./deploy_openai.sh --skip-prereqs
#   ./deploy_openai.sh --enable-launchd
#
# ENVIRONMENT VARIABLES:
#   OPENAI_TARGET_HOME           Target config dir (default ~/.config/lm-studio-magi).
#   LM_STUDIO_HOST               OpenAI-compatible host (default localhost).
#   LM_STUDIO_PORT               OpenAI-compatible port (default 1234).
#   LM_STUDIO_MODEL              Default model name.
#   LM_STUDIO_CONTEXT            Default context window size.
#   LM_STUDIO_AUTOLOAD_MODELS    Comma-separated model ids to autoload.
#   OPENAI_API_KEY               Optional API key shim; written to config.
#   OPENAI_BASE_URL              Override base URL; defaults to host:port.
#
# DEPENDENCIES:
#   External: mkdir cp date awk sed
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
PACK_DIR="$(cd -P -- "${SCRIPT_DIR}/.." && pwd)"
readonly PACK_DIR
readonly TEMPLATES_DIR="${SCRIPT_DIR}/templates"
readonly ENV_FILE="${PACK_DIR}/.env"
TS="$(date '+%Y%m%d-%H%M%S')"
readonly TS
OS_NAME="$(uname -s)"
readonly OS_NAME
case "${OS_NAME}" in
    Darwin|Linux) : ;;
    *) printf 'ERROR: unsupported OS: %s\n' "${OS_NAME}" >&2; exit 1 ;;
esac
DEPLOY_TARGET="${OPENAI_TARGET_HOME:-${HOME}/.config/lm-studio-magi}"
DRY_RUN=0
NON_INTERACTIVE=0
SKIP_PREREQS=0
ENABLE_LAUNCHD=0
for arg in "$@"; do
    case "${arg}" in
        --target=*) DEPLOY_TARGET="${arg#--target=}" ;;
        --dry-run) DRY_RUN=1 ;;
        --non-interactive) NON_INTERACTIVE=1 ;;
        --skip-prereqs) SKIP_PREREQS=1 ;;
        --enable-launchd) ENABLE_LAUNCHD=1 ;;
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
readonly DEPLOY_TARGET DRY_RUN NON_INTERACTIVE SKIP_PREREQS ENABLE_LAUNCHD
readonly LOG_DIR="${SCRIPT_DIR}/.deploy_logs"
mkdir -p "${LOG_DIR}"
readonly LOG_FILE="${LOG_DIR}/deploy_openai-${TS}.log"
if [[ -t 1 ]]; then
    readonly RST=$'\033[0m'
    readonly FG_R=$'\033[31m'
    readonly FG_G=$'\033[32m'
    readonly FG_Y=$'\033[33m'
    readonly FG_B=$'\033[34m'
    readonly FG_C=$'\033[36m'
    readonly FG_M=$'\033[35m'
    readonly BD_C=$'\033[1;36m'
else
    readonly RST=''
    readonly FG_R=''
    readonly FG_G=''
    readonly FG_Y=''
    readonly FG_B=''
    readonly FG_C=''
    readonly FG_M=''
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
log_note() {
    printf '%b\n' "${FG_M}$*${RST}"
    log_to_file "NOTE: $*"
}
section() {
    printf '\n%b\n' "${BD_C}== $* ==${RST}"
    log_to_file "SECTION: $*"
}
preflight() {
    section "Prerequisites"
    if [[ "${SKIP_PREREQS}" == "1" ]]; then
        log_warn "skipping prereq check (--skip-prereqs)"
        return 0
    fi
    local errors=0
    local cmd
    local resolved
    for cmd in mkdir cp date awk sed; do
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
    local lms_resolved
    lms_resolved="$(command -v lms || printf '')"
    if [[ -n "${lms_resolved}" ]]; then
        log_detail "lms CLI present at ${lms_resolved}"
    else
        log_warn "lms CLI not on PATH; LaunchAgent will fail until LM Studio is installed"
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
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] mkdir -p ${DEPLOY_TARGET}"
        log_detail "[dry-run] mkdir -p ${DEPLOY_TARGET}/logs"
    else
        mkdir -p "${DEPLOY_TARGET}"
        mkdir -p "${DEPLOY_TARGET}/logs"
    fi
    log_ok "target layout ensured at ${DEPLOY_TARGET}"
}
render_config() {
    section "Config template"
    local src="${TEMPLATES_DIR}/lmstudio.config.toml"
    local dst="${DEPLOY_TARGET}/config.toml"
    if [[ ! -f "${src}" ]]; then
        log_error "config template missing: ${src}"
        return 1
    fi
    local host="${LM_STUDIO_HOST:-localhost}"
    local port="${LM_STUDIO_PORT:-1234}"
    local model="${LM_STUDIO_MODEL:-}"
    local context="${LM_STUDIO_CONTEXT:-8192}"
    backup_existing "${dst}"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] render ${src} -> ${dst} host=${host} port=${port} model=${model} context=${context}"
        return 0
    fi
    sed \
        -e "s|__LM_STUDIO_HOST__|${host}|g" \
        -e "s|\"__LM_STUDIO_PORT__\"|${port}|g" \
        -e "s|__LM_STUDIO_MODEL__|${model}|g" \
        -e "s|\"__LM_STUDIO_CONTEXT__\"|${context}|g" \
        "${src}" > "${dst}"
    chmod 0644 "${dst}"
    log_ok "config rendered at ${dst}"
}
write_env_runtime() {
    section "Runtime env"
    local env_dst="${DEPLOY_TARGET}/env.runtime"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] would write ${env_dst}"
        return 0
    fi
    backup_existing "${env_dst}"
    {
        printf '# Generated by magi deploy_openai.sh at %s\n' "${TS}"
        printf 'OPENAI_TARGET_HOME=%s\n' "${DEPLOY_TARGET}"
        printf 'LM_STUDIO_HOST=%s\n' "${LM_STUDIO_HOST:-localhost}"
        printf 'LM_STUDIO_PORT=%s\n' "${LM_STUDIO_PORT:-1234}"
        printf 'LM_STUDIO_MODEL=%s\n' "${LM_STUDIO_MODEL:-}"
        printf 'LM_STUDIO_CONTEXT=%s\n' "${LM_STUDIO_CONTEXT:-8192}"
        printf 'LM_STUDIO_AUTOLOAD_MODELS=%s\n' "${LM_STUDIO_AUTOLOAD_MODELS:-}"
        if [[ -n "${OPENAI_BASE_URL:-}" ]]; then
            printf 'OPENAI_BASE_URL=%s\n' "${OPENAI_BASE_URL}"
        else
            printf 'OPENAI_BASE_URL=http://%s:%s/v1\n' "${LM_STUDIO_HOST:-localhost}" "${LM_STUDIO_PORT:-1234}"
        fi
    } > "${env_dst}"
    chmod 0600 "${env_dst}"
    log_ok "runtime env written to ${env_dst}"
}
install_launchd_plist() {
    section "LaunchAgent (optional)"
    if [[ "${ENABLE_LAUNCHD}" != "1" ]]; then
        log_detail "launchd integration not requested (--enable-launchd absent)"
        return 0
    fi
    if [[ "${OS_NAME}" != "Darwin" ]]; then
        log_warn "launchd is Darwin-only; skipping plist install on ${OS_NAME}"
        return 0
    fi
    local src="${TEMPLATES_DIR}/com.user.lm-studio-magi.plist"
    if [[ ! -f "${src}" ]]; then
        log_error "plist template missing: ${src}"
        return 1
    fi
    local agent_dir="${HOME}/Library/LaunchAgents"
    local dst="${agent_dir}/com.${USER}.lm-studio-magi.plist"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log_detail "[dry-run] mkdir -p ${agent_dir}"
        log_detail "[dry-run] render ${src} -> ${dst}"
        return 0
    fi
    mkdir -p "${agent_dir}"
    backup_existing "${dst}"
    local lms_path
    lms_path="$(command -v lms || printf '/usr/local/bin/lms')"
    local port="${LM_STUDIO_PORT:-1234}"
    sed \
        -e "s|__USER__|${USER}|g" \
        -e "s|__LMS_PATH__|${lms_path}|g" \
        -e "s|__LM_STUDIO_PORT__|${port}|g" \
        "${src}" > "${dst}"
    chmod 0644 "${dst}"
    log_ok "LaunchAgent plist written to ${dst}"
    log_note "load via: launchctl bootstrap gui/$(id -u) ${dst}"
}
main() {
    section "deploy_openai.sh starting"
    log_detail "target=${DEPLOY_TARGET} dry_run=${DRY_RUN} non_interactive=${NON_INTERACTIVE} enable_launchd=${ENABLE_LAUNCHD}"
    log_detail "log_file=${LOG_FILE}"
    load_env
    preflight
    ensure_target_layout
    render_config
    write_env_runtime
    install_launchd_plist
    section "deploy_openai.sh complete"
    log_ok "LM Studio (OpenAI-compat) config rendered at ${DEPLOY_TARGET}"
}
main "$@"
