#!/usr/bin/env bash
#
# Daily Backup-File Sweep
# ==============================================================================
# Runs at 02:30 local time. Relocates *.old, *.backup, *.bak.*, *.gsl-bak,
# *.oldjson, *.oldmkdn, .mcp.json.bak.*, settings.json.backup.* at root
# into ~/.claude/_OLD/. Idempotent (mv -n).
# ==============================================================================
set -Eeuo pipefail
readonly CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly OLD_DIR="${CLAUDE_DIR}/_OLD"
readonly LOG_FILE="${CLAUDE_DIR}/_logs/cleanup/daily-bak-sweep.log"
mkdir -p "${OLD_DIR}" "$(dirname "${LOG_FILE}")"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${LOG_FILE}" || true; }
sweep_pattern() {
    local pattern="$1"
    local dest="$2"
    local moved=0
    shopt -s nullglob dotglob
    local matches
    eval "matches=( ${pattern} )"
    shopt -u nullglob dotglob
    local m
    for m in "${matches[@]}"; do
        [[ -e "${m}" ]] || continue
        if mv -n "${m}" "${dest}/"; then
            moved=$((moved + 1))
        fi
    done
    (( moved > 0 )) && log "swept ${moved} matching ${pattern} -> ${dest}"
    return 0
}
log "=== daily-bak-sweep start ==="
sweep_pattern "${CLAUDE_DIR}/*.old"               "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/*.backup"            "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/*.backup.*"          "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/*.bak"               "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/*.bak.*"             "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/*.gsl-bak"           "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/*.oldjson"           "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/*.oldmkdn"           "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/.mcp.json.bak.*"     "${OLD_DIR}"
sweep_pattern "${CLAUDE_DIR}/settings.json.backup.*" "${OLD_DIR}"
log "=== daily-bak-sweep done ==="
exit 0
