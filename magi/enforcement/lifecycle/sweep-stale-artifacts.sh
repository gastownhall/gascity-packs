#!/usr/bin/env bash
#
# Sweep Stale Artifacts (SessionStart)
# ==============================================================================
# Self-healing periodic cleanup that fires on every SessionStart. Keeps the
# Claude Code state directories from accumulating cruft.
#
# Sweeps (idempotent, age-gated where applicable):
#   ~/.claude/paste-cache/ files >30d       -> ~/.claude/archived/paste-cache/
#   ~/.claude/shell-snapshots/ >30d         -> ~/.claude/archived/shell-snapshots/
#   ~/.claude/telemetry/ >30d               -> ~/.claude/archived/telemetry/
#   ~/.claude/plans/ >30d                   -> ~/.claude/archived/plans/
#   ~/.claude/file-history/<sid>/ >30d      -> ~/.claude/archived/file-history/
#   ~/.claude/session-env/<sid>/ >30d       -> ~/.claude/archived/session-env/
#   ~/.claude/tasks/<sid>/ >30d             -> ~/.claude/archived/tasks/
#   ~/.claude/backups/.claude.json.backup.* -> ~/.claude/_OLD/
#   ~/.claude/*.old, *.backup, *.bak.*, *.gsl-bak, *.oldjson, *.oldmkdn -> _OLD/
#   rogue legacy logs at ~/.claude/ root    -> _OLD/<name>.legacy.<ts>
#
# All target dirs auto-created. Operations use mv -n (no clobber).
# Per-file failures don't abort the sweep.
# ==============================================================================
set -Eeuo pipefail
readonly CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly ARCHIVED_DIR="${CLAUDE_DIR}/archived"
readonly OLD_DIR="${CLAUDE_DIR}/_OLD"
readonly AGE_DAYS=30
ensure_dir() {
    [[ -d "$1" ]] || mkdir -p "$1" || true
}
ensure_dir "${ARCHIVED_DIR}"
ensure_dir "${OLD_DIR}"
sweep_age_dir() {
    local src="$1"
    local dest="$2"
    [[ -d "${src}" ]] || return 0
    ensure_dir "${dest}"
    find "${src}" -mindepth 1 -maxdepth 1 \( -type f -o -type d \) -mtime "+${AGE_DAYS}" -exec mv -n {} "${dest}/" \; || true
    return 0
}
sweep_glob_to() {
    local dest="$1"
    shift
    ensure_dir "${dest}"
    local m
    for m in "$@"; do
        [[ -e "${m}" ]] || continue
        mv -n "${m}" "${dest}/" || true
    done
    return 0
}
sweep_age_dir "${CLAUDE_DIR}/paste-cache"     "${ARCHIVED_DIR}/paste-cache"
sweep_age_dir "${CLAUDE_DIR}/shell-snapshots" "${ARCHIVED_DIR}/shell-snapshots"
sweep_age_dir "${CLAUDE_DIR}/telemetry"       "${ARCHIVED_DIR}/telemetry"
sweep_age_dir "${CLAUDE_DIR}/plans"           "${ARCHIVED_DIR}/plans"
sweep_age_dir "${CLAUDE_DIR}/file-history"    "${ARCHIVED_DIR}/file-history"
sweep_age_dir "${CLAUDE_DIR}/session-env"     "${ARCHIVED_DIR}/session-env"
sweep_age_dir "${CLAUDE_DIR}/tasks"           "${ARCHIVED_DIR}/tasks"
shopt -s nullglob dotglob
if [[ -d "${CLAUDE_DIR}/backups" ]]; then
    sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}/backups/.claude.json.backup."*
    sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}/backups/"*
    rmdir "${CLAUDE_DIR}/backups" 2>&1 | grep -v "Directory not empty" || true
fi
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.old
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.backup
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.backup.*
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.bak
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.bak.*
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.gsl-bak
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.oldjson
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/*.oldmkdn
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/.mcp.json.bak.*
sweep_glob_to "${OLD_DIR}" "${CLAUDE_DIR}"/settings.json.backup.*
shopt -u nullglob dotglob
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
        mv -n "${legacy}" "${OLD_DIR}/$(basename "${legacy}").legacy.${ts}" || true
    fi
done
if [[ -d "${CLAUDE_DIR}/tracking" ]]; then
    mv -n "${CLAUDE_DIR}/tracking" "${OLD_DIR}/tracking-orphan-$(date +%s)" || true
fi
if [[ -d "${CLAUDE_DIR}/hooks" ]]; then
    HOOK_CONTENTS="$(ls -A "${CLAUDE_DIR}/hooks" 2>&1 || true)"
    if [[ -z "${HOOK_CONTENTS}" ]]; then
        rmdir "${CLAUDE_DIR}/hooks" || true
    fi
fi
exit 0
