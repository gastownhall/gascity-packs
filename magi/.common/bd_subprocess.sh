#!/usr/bin/env bash
#
# magi/.common/bd_subprocess.sh - bd shell wrapper for magi pack
# ==============================================================================
# Thin bash wrapper for the `bd` CLI used by ready.sh and any other pack-local
# bash that needs to call bd without going through a Python orchestrator. The
# bd_call helper checks PATH for bd, invokes it when present, warns and exits
# 0 (graceful degradation) when bd is missing. Mirrors the Python try_bd
# semantics so behavior is consistent across bash and Python entrypoints.
#
# USAGE:
#   source "${COMMON_DIR}/bd_subprocess.sh"
#   bd_call ready --label pack:magi --json
#
# EXPORTED FUNCTIONS:
#   bd_preflight   Confirms colors.sh + logging.sh sourced
#   bd_present     Returns 0 when bd resolves on PATH; 1 otherwise
#   bd_call ...    Invokes bd with the supplied argv when present
#
# DEPENDENCIES:
#   Internal: colors.sh, logging.sh
#   External: bd (optional; graceful degradation when missing)
# ==============================================================================
set -Eeuo pipefail
[[ -n "${_SOURCED_MAGI_BD_SUBPROCESS_SH:-}" ]] && return 0
readonly _SOURCED_MAGI_BD_SUBPROCESS_SH=1
bd_preflight() {
    [[ -n "${_SOURCED_MAGI_COLORS_SH:-}" ]] || { printf 'ERROR: bd_subprocess.sh requires colors.sh sourced first\n' >&2; return 1; }
    [[ -n "${_SOURCED_MAGI_LOGGING_SH:-}" ]] || { printf 'ERROR: bd_subprocess.sh requires logging.sh sourced first\n' >&2; return 1; }
    return 0
}
bd_preflight || return 1
bd_present() {
    local resolved
    resolved="$(command -v bd || printf '')"
    [[ -n "${resolved}" ]] || return 1
    return 0
}
bd_call() {
    bd_present && { bd "$@"; return $?; }
    log_warn "bd not on PATH; skipping bd call: bd $*"
    return 0
}