#!/usr/bin/env bash
###############################################################################
# checks.sh - Dependency check functions for hook scripts
###############################################################################
_CHECKS_SH_SOURCED=1
load_remote_env() {
    local env_file="$HOME/.claude/enforcement/env.remote"
    if [[ ! -f "$env_file" ]]; then
        echo "ERROR: remote env file not found: $env_file" >&2
        return 1
    fi
    # shellcheck source=/dev/null
    source "$env_file"
    if [[ -z "${LM_STUDIO_HOST:-${LM_STUDIO_HOST_IP:-}}" ]]; then
        echo "ERROR: LM_STUDIO_HOST not defined in $env_file" >&2
        return 1
    fi
    if [[ -z "${LM_STUDIO_PORT:-}" ]]; then
        echo "ERROR: LM_STUDIO_PORT not defined in $env_file" >&2
        return 1
    fi
    LM_STUDIO_HOST_IP="${LM_STUDIO_HOST:-${LM_STUDIO_HOST_IP:-}}"
    CLAUDE_WATCHDOG_ENABLED="${CLAUDE_WATCHDOG_ENABLED:-0}"
    export LM_STUDIO_HOST_IP
    export LM_STUDIO_PORT
    export CLAUDE_WATCHDOG_ENABLED
    return 0
}
get_lm_studio_host() { echo "${LM_STUDIO_HOST_IP:-}"; }
get_lm_studio_port() { echo "${LM_STUDIO_PORT:-}"; }
is_watchdog_enabled() { [[ "${CLAUDE_WATCHDOG_ENABLED:-0}" == "1" ]]; }
has_command() { command -v "$1" >/dev/null 2>&1; }
require_jq() {
    if ! has_command jq; then
        if [[ -n "${RED:-}" ]] && [[ -n "${NC:-}" ]]; then
            echo -e "${RED}ERROR: jq is required but not installed${NC}" >&2
        else
            echo "ERROR: jq is required but not installed" >&2
        fi
        return 1
    fi
    return 0
}
require_command() {
    local cmd="$1"
    local msg="${2:-${cmd} is required but not installed}"
    if ! has_command "$cmd"; then
        if [[ -n "${RED:-}" ]] && [[ -n "${NC:-}" ]]; then
            echo -e "${RED}ERROR: ${msg}${NC}" >&2
        else
            echo "ERROR: ${msg}" >&2
        fi
        return 1
    fi
    return 0
}
check_file_exists() {
    local file="$1"
    [[ -f "$file" ]]
}
check_dir_exists() {
    local dir="$1"
    [[ -d "$dir" ]]
}
ensure_dir_exists() {
    local dir="$1"
    mkdir -p "$dir" 2>/dev/null || true
}
validate_json_file() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        return 1
    fi
    if ! jq '.' "$file" >/dev/null 2>&1; then
        return 1
    fi
    return 0
}
