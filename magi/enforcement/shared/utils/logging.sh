#!/usr/bin/env bash
###############################################################################
# logging.sh - Standard logging functions for all hook scripts
###############################################################################
_LOGGING_SH_SOURCED=1
_get_script_name() {
    local script_path="${BASH_SOURCE[2]:-${BASH_SOURCE[1]:-unknown}}"
    basename "$script_path" .sh
}
log_debug() {
    local script_name
    script_name=$(_get_script_name)
    echo "[DEBUG] ${script_name}: $*" >&2
}
log_info() {
    local script_name
    script_name=$(_get_script_name)
    echo "[INFO] ${script_name}: $*" >&2
}
log_warning() {
    local script_name
    script_name=$(_get_script_name)
    echo "[WARNING] ${script_name}: $*" >&2
}
log_error() {
    local script_name
    script_name=$(_get_script_name)
    echo "[ERROR] ${script_name}: $*" >&2
}
die() {
    local exit_code="${2:-1}"
    log_error "$1"
    exit "$exit_code"
}
log_to_file() {
    local log_file="$1"
    shift
    local msg="$*"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${msg}" >> "${log_file}" 2>/dev/null || true
}
