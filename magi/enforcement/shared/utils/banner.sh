#!/usr/bin/env bash
###############################################################################
# banner.sh - MAGI banner display functions for hook scripts
###############################################################################
_BANNER_SH_SOURCED=1
print_magi_banner() {
    local magenta1=$'\033[38;5;93m'
    local magenta2=$'\033[38;5;99m'
    local magenta3=$'\033[38;5;93m'
    local magenta4=$'\033[38;5;57m'
    local magenta5=$'\033[38;5;55m'
    local magenta6=$'\033[38;5;125m'
    local reset=$'\033[0m'
    printf "%s%s%s\n" "${magenta1}" '' "${reset}"
    printf "%s%s%s\n" "${magenta1}" '███╗   ███╗   █████╗    ██████╗   ██╗' "${reset}"
    printf "%s%s%s\n" "${magenta2}" '████╗ ████║  ██╔══██╗  ██╔════╝   ██║' "${reset}"
    printf "%s%s%s\n" "${magenta3}" '██╔████╔██║  ███████║  ██║  ███╗  ██║' "${reset}"
    printf "%s%s%s\n" "${magenta4}" '██║╚██╔╝██║  ██╔══██║  ██║   ██║  ██║' "${reset}"
    printf "%s%s%s\n" "${magenta5}" '██║ ╚═╝ ██║  ██║  ██║  ╚██████╔╝  ██║' "${reset}"
    printf "%s%s%s\n" "${magenta6}" '╚═╝     ╚═╝  ╚═╝  ╚═╝   ╚═════╝   ╚═╝' "${reset}"
}
print_magi_banner_plain() {
    cat <<'EOF'
███╗   ███╗  █████╗   ██████╗  ██╗
  ████╗ ████║ ██╔══██╗ ██╔════╝  ██║
  ██╔████╔██║ ███████║ ██║  ███╗ ██║
  ██║╚██╔╝██║ ██╔══██║ ██║   ██║ ██║
  ██║ ╚═╝ ██║ ██║  ██║ ╚██████╔╝ ██║
  ╚═╝     ╚═╝ ╚═╝  ╚═╝  ╚═════╝  ╚═╝
EOF
}
print_separator() {
    local dim=$'\033[90m'
    local reset=$'\033[0m'
    printf "%s%s%s\n" "${dim}" '════════════════════════════════════════════════════════════════════' "${reset}"
}
print_separator_plain() {
    echo '════════════════════════════════════════════════════════════════════'
}
print_session_header() {
    local version="${1:-}"
    local white=$'\033[97m'
    local dim=$'\033[90m'
    local reset=$'\033[0m'
    print_magi_banner
    printf "\n"
    if [[ -n "$version" ]]; then
        printf "%s  MAGI Processing Agent %s%s%s\n" "${white}" "${dim}" "${version}" "${reset}"
    else
        printf "%s  MAGI Processing Agent%s\n" "${white}" "${reset}"
    fi
    printf "%s  A prompt, context engineering, and spec-driven%s\n" "${white}" "${reset}"
    printf "%s  development subsystem for Claude Code.%s\n" "${white}" "${reset}"
    printf "\n"
}
