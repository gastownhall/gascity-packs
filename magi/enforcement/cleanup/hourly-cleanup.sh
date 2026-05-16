#!/usr/bin/env bash
#
# Hourly Cleanup
# ==============================================================================
# Runs every hour at :00. Drains short-lived junk and catches rogue files
# that should never appear at root.
#
# Actions:
#   - Drain ~/.claude/backups/.claude.json.backup.* -> ~/.claude/_OLD/
#   - Catch rogue legacy logs (enforcement.log, security.log, etc.) at root
#     -> ~/.claude/_OLD/<name>.legacy.<ts>
#   - Drain stray ~/.claude/tracking/ -> ~/.claude/_OLD/tracking-orphan-<ts>
#   - Aggressive aging (>7d) for session-env/, tasks/, file-history/
# ==============================================================================
set -Eeuo pipefail
readonly CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly OLD_DIR="${CLAUDE_DIR}/_OLD"
readonly ARCHIVED_DIR="${CLAUDE_DIR}/archived"
readonly LOG_FILE="${CLAUDE_DIR}/_logs/cleanup/hourly-cleanup.log"
mkdir -p "${OLD_DIR}" "${ARCHIVED_DIR}" "$(dirname "${LOG_FILE}")"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${LOG_FILE}" || true; }
log "=== hourly-cleanup start ==="
if [[ -d "${CLAUDE_DIR}/backups" ]]; then
    shopt -s nullglob dotglob
    matches=( "${CLAUDE_DIR}/backups/.claude.json.backup."* "${CLAUDE_DIR}/backups/"* )
    shopt -u nullglob dotglob
    moved=0
    for m in "${matches[@]}"; do
        [[ -e "${m}" ]] || continue
        if mv -n "${m}" "${OLD_DIR}/"; then
            moved=$((moved + 1))
        fi
    done
    (( moved > 0 )) && log "drained backups/ (${moved} files) -> _OLD/"
    rmdir "${CLAUDE_DIR}/backups" 2>&1 | grep -v "Directory not empty" || true
fi
ROGUE_LEGACY_LOGS=(
    "${CLAUDE_DIR}/enforcement.log"
    "${CLAUDE_DIR}/security.log"
    "${CLAUDE_DIR}/quality-verification.log"
    "${CLAUDE_DIR}/agent-usage.log"
    "${CLAUDE_DIR}/guideline_tracking_unknown"
)
for legacy in "${ROGUE_LEGACY_LOGS[@]}"; do
    if [[ -f "${legacy}" ]]; then
        ts="$(date +%s)"
        if mv -n "${legacy}" "${OLD_DIR}/$(basename "${legacy}").legacy.${ts}"; then
            log "rogue log relocated: $(basename "${legacy}") -> _OLD/"
        fi
    fi
done
if [[ -d "${CLAUDE_DIR}/tracking" ]]; then
    ts="$(date +%s)"
    if mv -n "${CLAUDE_DIR}/tracking" "${OLD_DIR}/tracking-orphan-${ts}"; then
        log "stray tracking/ moved -> _OLD/tracking-orphan-${ts}"
    fi
fi
sweep_age_dir() {
    local src="$1"
    local dest="$2"
    local age="$3"
    [[ -d "${src}" ]] || return 0
    mkdir -p "${dest}" || true
    local moved=0
    while IFS= read -r -d '' item || [[ -n "${item:-}" ]]; do
        [[ -n "${item}" ]] || continue
        if mv -n "${item}" "${dest}/"; then
            moved=$((moved + 1))
        fi
    done < <(find "${src}" -mindepth 1 -maxdepth 1 \( -type f -o -type d \) -mtime "+${age}" -print0)
    (( moved > 0 )) && log "aged ${moved} from ${src} (>${age}d) -> ${dest}"
    return 0
}
sweep_age_dir "${CLAUDE_DIR}/file-history" "${ARCHIVED_DIR}/file-history" 7
sweep_age_dir "${CLAUDE_DIR}/session-env"  "${ARCHIVED_DIR}/session-env"  7
sweep_age_dir "${CLAUDE_DIR}/tasks"        "${ARCHIVED_DIR}/tasks"        7
log "=== hourly-cleanup done ==="
exit 0
