#!/usr/bin/env bash
#
# magi/.common/colors.sh - Color constants for magi pack bash files
# ==============================================================================
# Sourced by every magi commands/<verb>.sh wrapper, every doctor/check-*.sh
# probe, and the gemini/openai pack-built installers. Declares the standardized
# RST + FG_/BG_/BR_/BD_/UL_ ANSI escapes per bash_guidelines.md section 4.
#
# USAGE:
#   source "${COMMON_DIR}/colors.sh"
#
# EXPORTED VARIABLES:
#   RST                                              Full reset (color + attrs)
#   FG_K FG_R FG_G FG_Y FG_B FG_M FG_C FG_W          Standard foreground colors
#   BR_K BR_R BR_G BR_Y BR_B BR_M BR_C BR_W          Bright foreground colors
#   BG_K BG_R BG_G BG_Y BG_B BG_M BG_C BG_W          Background colors
#   BD_R BD_G BD_Y BD_B BD_M BD_C BD_W               Bold foreground colors
#   UL_W                                              Underline white
#
# DEPENDENCIES:
#   Internal: none
#   External: none
# ==============================================================================
set -Eeuo pipefail
[ -n "${_SOURCED_MAGI_COLORS_SH:-}" ] && return 0
readonly _SOURCED_MAGI_COLORS_SH=1
readonly RST=$'\033[0m'
readonly FG_K=$'\033[30m'
readonly FG_R=$'\033[31m'
readonly FG_G=$'\033[32m'
readonly FG_Y=$'\033[33m'
readonly FG_B=$'\033[34m'
readonly FG_M=$'\033[35m'
readonly FG_C=$'\033[36m'
readonly FG_W=$'\033[37m'
readonly BR_K=$'\033[90m'
readonly BR_R=$'\033[91m'
readonly BR_G=$'\033[92m'
readonly BR_Y=$'\033[93m'
readonly BR_B=$'\033[94m'
readonly BR_M=$'\033[95m'
readonly BR_C=$'\033[96m'
readonly BR_W=$'\033[97m'
readonly BG_K=$'\033[40m'
readonly BG_R=$'\033[41m'
readonly BG_G=$'\033[42m'
readonly BG_Y=$'\033[43m'
readonly BG_B=$'\033[44m'
readonly BG_M=$'\033[45m'
readonly BG_C=$'\033[46m'
readonly BG_W=$'\033[47m'
readonly BD_R=$'\033[1;31m'
readonly BD_G=$'\033[1;32m'
readonly BD_Y=$'\033[1;33m'
readonly BD_B=$'\033[1;34m'
readonly BD_M=$'\033[1;35m'
readonly BD_C=$'\033[1;36m'
readonly BD_W=$'\033[1;37m'
readonly UL_W=$'\033[4;37m'
