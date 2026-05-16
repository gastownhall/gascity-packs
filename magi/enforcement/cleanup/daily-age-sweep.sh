#!/usr/bin/env bash
#
# Daily Age Sweep
# ==============================================================================
# Runs at 03:00 local time. Ages out files/dirs in CC state directories and
# moves them to ~/.claude/archived/<dir>/. Idempotent.
#
# Age gates:
#   30 days: paste-cache, shell-snapshots, telemetry, plans
#    7 days: file-history, session-env, tasks  (UUID-named, accumulate fast)
# ==============================================================================
set -Eeuo pipefail
readonly CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly ARCHIVED_DIR="${CLAUDE_DIR}/archived"
readonly LOG_DIR="${CLAUDE_DIR}/_logs/cleanup"
readonly LOG_FILE="${LOG_DIR}/daily-age-sweep.log"
mkdir -p "${ARCHIVED_DIR}" "${LOG_DIR}"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${LOG_FILE}" || true; }
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
    log "swept ${moved} from ${src} (>${age}d) -> ${dest}"
    return 0
}
log "=== daily-age-sweep start ==="
sweep_age_dir "${CLAUDE_DIR}/paste-cache"     "${ARCHIVED_DIR}/paste-cache"     30
sweep_age_dir "${CLAUDE_DIR}/shell-snapshots" "${ARCHIVED_DIR}/shell-snapshots" 30
sweep_age_dir "${CLAUDE_DIR}/telemetry"       "${ARCHIVED_DIR}/telemetry"       30
sweep_age_dir "${CLAUDE_DIR}/plans"           "${ARCHIVED_DIR}/plans"           30
sweep_age_dir "${CLAUDE_DIR}/file-history"    "${ARCHIVED_DIR}/file-history"     7
sweep_age_dir "${CLAUDE_DIR}/session-env"     "${ARCHIVED_DIR}/session-env"      7
sweep_age_dir "${CLAUDE_DIR}/tasks"           "${ARCHIVED_DIR}/tasks"            7
log "=== daily-age-sweep done ==="
exit 0
