#!/usr/bin/env bash
#
# Merge Dotted-Key Project Dirs Into Double-Dash Equivalents
# ==============================================================================
# One-shot (also safe to run repeatedly). For every project dir that contains
# a "-." sequence (the old dotted-key form that pre-dated the '.' -> '-'
# collapse rule), finds the corresponding "--" form (current double-dash
# form) and merges the dotted dir's contents using rsync (no overwrite). Then
# archives the dotted dir to _OLD/.
#
# User-agnostic: the glob and substitution operate on the project-key shape
# ("-.") rather than any particular username, so the script runs correctly
# under any account on any host. The project-key collapse rule is documented
# in `enforcement/shared/utils/project-key.sh`.
# ==============================================================================
set -Eeuo pipefail
readonly CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly PROJECTS_DIR="${CLAUDE_DIR}/projects"
readonly OLD_DIR="${CLAUDE_DIR}/_OLD"
readonly LOG_FILE="${CLAUDE_DIR}/_logs/cleanup/merge-dotted-projects.log"
mkdir -p "${OLD_DIR}" "$(dirname "${LOG_FILE}")"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "${LOG_FILE}"; }
log "=== merge-dotted-projects start ==="
RSYNC_PATH="$(command -v rsync || true)"
[[ -n "${RSYNC_PATH}" ]] || { log "rsync not available, abort"; exit 1; }
merged=0
# The glob "*-.*" matches any project-key containing the dotted form.
# Globs without matches expand to themselves under shell defaults; the
# [[ -d ... ]] guard on the next line skips that case safely.
for dotted in "${PROJECTS_DIR}"/*-.*; do
    [[ -d "${dotted}" ]] || continue
    base="$(basename "${dotted}")"
    # Convert every "-." (old dotted form) to "--" (current double-dash
    # form). The pattern is account-agnostic; it transforms the project-key
    # shape regardless of which user generated it.
    target_base="$(printf '%s' "${base}" | sed 's|-\.|--|g')"
    target="${PROJECTS_DIR}/${target_base}"
    if [[ ! -d "${target}" ]]; then
        log "no double-dash target for ${base} -- renaming dotted to double-dash"
        mv "${dotted}" "${target}"
        merged=$((merged + 1))
        continue
    fi
    log "merging ${base} -> ${target_base}"
    rsync -a --ignore-existing "${dotted}/" "${target}/"
    pre_count=$(find "${dotted}" -mindepth 1 | wc -l | tr -d ' ')
    archive_dest="${OLD_DIR}/projects-dotted-merged/${base}"
    mkdir -p "$(dirname "${archive_dest}")"
    if [[ ! -d "${archive_dest}" ]]; then
        mv "${dotted}" "${archive_dest}"
        merged=$((merged + 1))
        log "  archived ${pre_count} entries from ${base} -> _OLD/projects-dotted-merged/"
    else
        ts="$(date +%s)"
        mv "${dotted}" "${archive_dest}-${ts}"
        merged=$((merged + 1))
        log "  archive existed; archived as ${base}-${ts}"
    fi
done
log "merged: ${merged}"
log "=== merge-dotted-projects done ==="
exit 0
