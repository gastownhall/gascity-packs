#!/usr/bin/env bash
#
# magi/.common/logging.sh - Semantic logging helpers for magi pack bash files
# ==============================================================================
# Logging helpers that respect the bash_guidelines section-4 semantic color
# mapping. Functions emit to stdout (or stderr for log_error) with the color
# matching the meaning of the message. Sourced after .common/colors.sh.
#
# USAGE:
#   source "${COMMON_DIR}/colors.sh"
#   source "${COMMON_DIR}/logging.sh"
#   log_info "loading config"
#   log_warn "value missing; using default"
#   log_error "deploy failed"
#   log_ok "deploy complete"
#   section "Prerequisites"
#
# EXPORTED FUNCTIONS:
#   log_preflight    Verifies colors.sh sourced; returns 1 on miss
#   log_info         White - neutral statements
#   log_action       Blue - actions being taken (Installing, Copying, ...)
#   log_detail       Cyan - informational details, paths, metadata
#   log_note         Magenta - important info the user must not miss
#   log_warn         Yellow - warnings (stderr)
#   log_error        Red - failures (stderr)
#   log_ok           Green - success confirmations
#   section          Bold cyan section header
#
# DEPENDENCIES:
#   Internal: .common/colors.sh
#   External: none
# ==============================================================================
set -Eeuo pipefail
[ -n "${_SOURCED_MAGI_LOGGING_SH:-}" ] && return 0
readonly _SOURCED_MAGI_LOGGING_SH=1
log_preflight() {
    [[ -n "${_SOURCED_MAGI_COLORS_SH:-}" ]] || { printf 'ERROR: magi/.common/logging.sh requires colors.sh sourced first\n' >&2; return 1; }
    [[ -n "${RST:-}" && -n "${FG_R:-}" && -n "${FG_G:-}" ]] || { printf 'ERROR: magi/.common/logging.sh missing color constants\n' >&2; return 1; }
    return 0
}
log_preflight || return 1
log_info() { printf '%b\n' "${FG_W}$*${RST}"; }
log_action() { printf '%b\n' "${FG_B}$*${RST}"; }
log_detail() { printf '%b\n' "${FG_C}$*${RST}"; }
log_note() { printf '%b\n' "${FG_M}$*${RST}"; }
log_warn() { printf '%b\n' "${FG_Y}WARN: $*${RST}" >&2; }
log_error() { printf '%b\n' "${FG_R}ERROR: $*${RST}" >&2; }
log_ok() { printf '%b\n' "${FG_G}$*${RST}"; }
section() { printf '\n%b\n' "${BD_C}== $* ==${RST}"; }