#!/usr/bin/env bash
###############################################################################
# main.sh - Main utility loader for hook scripts
# ==============================================================================
# Central utility loader that sources all common utility modules for hook
# scripts. Includes colors, paths, logging, checks, security, and enforcement
# settings.
#
# USAGE:
#   source "${UTILS_DIR}/main.sh"
#
# DEPENDENCIES:
#   Requires: colors.sh, paths.sh, logging.sh, checks.sh, security.sh,
#             enforcement-settings.sh, input.sh, banner.sh
# ==============================================================================
set -euo pipefail
_MAIN_SH_SOURCED=1
_UTILS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ -z "${_COLORS_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/colors.sh" ]]; then
    source "${_UTILS_DIR}/colors.sh"
fi
if [[ -z "${_PATHS_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/paths.sh" ]]; then
    source "${_UTILS_DIR}/paths.sh"
fi
if [[ -z "${_SECURITY_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/security.sh" ]]; then
    source "${_UTILS_DIR}/security.sh"
fi
if [[ -z "${_LOGGING_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/logging.sh" ]]; then
    source "${_UTILS_DIR}/logging.sh"
fi
if [[ -z "${_CHECKS_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/checks.sh" ]]; then
    source "${_UTILS_DIR}/checks.sh"
fi
if [[ -z "${_ENFORCEMENT_SETTINGS_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/enforcement-settings.sh" ]]; then
    source "${_UTILS_DIR}/enforcement-settings.sh"
fi
if [[ -z "${_INPUT_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/input.sh" ]]; then
    source "${_UTILS_DIR}/input.sh"
fi
if [[ -z "${_BANNER_SH_SOURCED:-}" ]] && [[ -f "${_UTILS_DIR}/banner.sh" ]]; then
    source "${_UTILS_DIR}/banner.sh"
fi
