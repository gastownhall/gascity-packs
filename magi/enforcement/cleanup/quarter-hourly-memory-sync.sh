#!/usr/bin/env bash
#
# Quarter-Hourly Memory Sync
# ==============================================================================
# Runs every 15 minutes. Syncs the canonical ~/.claude/memory/ feedback library
# into every existing ~/.claude/projects/<key>/memory/ dir. Newer per-project
# files are preserved (mtime-based copy_if_newer).
# Each project's MEMORY.md is regenerated from frontmatter. Idempotent.
# ==============================================================================
set -Eeuo pipefail
readonly CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly GLOBAL_MEMORY="${CLAUDE_DIR}/memory"
readonly PROJECTS_DIR="${CLAUDE_DIR}/projects"
readonly LOG_FILE="${CLAUDE_DIR}/_logs/cleanup/quarter-hourly-memory-sync.log"
mkdir -p "$(dirname "${LOG_FILE}")"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${LOG_FILE}" || true; }
[[ -d "${GLOBAL_MEMORY}" ]] || { log "no global memory dir, abort"; exit 0; }
[[ -d "${PROJECTS_DIR}" ]] || { log "no projects dir, abort"; exit 0; }
file_mtime() {
    local f="$1"
    [[ -f "${f}" ]] || { printf '0'; return; }
    if [[ "$(uname -s)" == "Darwin" ]]; then
        /usr/bin/stat -f '%m' "${f}"
    else
        stat -c '%Y' "${f}"
    fi
}
copy_if_newer() {
    local src="$1"
    local dst="$2"
    local sm dm
    sm="$(file_mtime "${src}")"
    dm="$(file_mtime "${dst}")"
    if [[ ! -f "${dst}" ]] || (( sm > dm )); then
        cp -p "${src}" "${dst}"
        return 0
    fi
    return 1
}
regenerate_index() {
    local mem_dir="$1"
    local index="${mem_dir}/MEMORY.md"
    local tmp="${mem_dir}/.MEMORY.md.tmp.$$"
    {
        printf '# Memory Index\n\n'
        for section in user feedback project reference; do
            local label
            case "${section}" in
                user)      label="User" ;;
                feedback)  label="Feedback" ;;
                project)   label="Project" ;;
                reference) label="Reference" ;;
            esac
            shopt -s nullglob
            local files=()
            case "${section}" in
                user)      files=( "${mem_dir}/user_"*.md ) ;;
                feedback)  files=( "${mem_dir}/feedback_"*.md ) ;;
                project)   files=( "${mem_dir}/project_"*.md ) ;;
                reference) files=( "${mem_dir}/reference_"*.md ) ;;
            esac
            shopt -u nullglob
            (( ${#files[@]} > 0 )) || continue
            printf '## %s\n' "${label}"
            local f
            for f in "${files[@]}"; do
                local fname title desc
                fname="$(basename "${f}")"
                title="$(awk '/^name:/ { sub(/^name: */, ""); print; exit }' "${f}" || true)"
                desc="$(awk '/^description:/ { sub(/^description: */, ""); print; exit }' "${f}" || true)"
                [[ -z "${title}" ]] && title="${fname%.md}"
                if [[ -n "${desc}" ]]; then
                    printf -- '- [%s](%s) — %s\n' "${title}" "${fname}" "${desc}"
                else
                    printf -- '- [%s](%s)\n' "${title}" "${fname}"
                fi
            done
            printf '\n'
        done
    } > "${tmp}"
    mv -f "${tmp}" "${index}"
}
sync_into_project() {
    local proj_dir="$1"
    local proj_mem="${proj_dir}/memory"
    mkdir -p "${proj_mem}"
    shopt -s nullglob
    local globals=( "${GLOBAL_MEMORY}"/feedback_*.md "${GLOBAL_MEMORY}"/reference_*.md "${GLOBAL_MEMORY}"/user_profile.md )
    shopt -u nullglob
    local copied=0
    local src
    for src in "${globals[@]}"; do
        [[ -f "${src}" ]] || continue
        local base="${src##*/}"
        local dst="${proj_mem}/${base}"
        if copy_if_newer "${src}" "${dst}"; then
            copied=$((copied + 1))
        fi
    done
    regenerate_index "${proj_mem}"
    return 0
}
log "=== memory-sync start ==="
projects_synced=0
for proj in "${PROJECTS_DIR}"/-*; do
    [[ -d "${proj}" ]] || continue
    sync_into_project "${proj}"
    projects_synced=$((projects_synced + 1))
done
log "synced ${projects_synced} project memory dirs"
log "=== memory-sync done ==="
exit 0
