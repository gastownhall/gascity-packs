#!/usr/bin/env bash
#
# Inject Global Feedback Memory Hook
# ==============================================================================
# Copies global feedback_*.md, reference_*.md, and user_profile.md from the
# canonical ~/.claude/memory/ source into the current project's
# ~/.claude/projects/<key>/memory/ dir so the harness's auto-memory feature
# (which only reads the per-project dir) picks them up automatically.
#
# Behavior:
#   - Idempotent: if the project-local copy is missing OR the global copy is
#     newer (mtime), copy. Otherwise leave the project-local file alone.
#   - Self-healing: missing memory dir created. Missing MEMORY.md regenerated.
#   - Per-project deviations preserved: project-local file with newer mtime
#     wins over the global.
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
readonly GLOBAL_MEMORY_DIR="${HOME}/.claude/memory"
INPUT=$(cat)
CWD=$(printf '%s' "${INPUT}" | jq -r '.cwd // ""')
resolve_project_paths "${CWD}"
readonly PROJECT_MEMORY_DIR="${PROJECT_DIR}/memory"
mkdir -p "${PROJECT_MEMORY_DIR}"
[[ -d "${GLOBAL_MEMORY_DIR}" ]] || exit 0
file_mtime() {
    local f="$1"
    [[ -f "${f}" ]] || { printf '0'; return; }
    if [[ "$(uname -s)" == "Darwin" ]]; then
        /usr/bin/stat -f '%m' "${f}"
    else
        /usr/bin/stat -c '%Y' "${f}"
    fi
}
copy_if_newer() {
    local src="$1"
    local dst="$2"
    local src_mtime dst_mtime
    src_mtime="$(file_mtime "${src}")"
    dst_mtime="$(file_mtime "${dst}")"
    if [[ ! -f "${dst}" ]] || (( src_mtime > dst_mtime )); then
        cp -p "${src}" "${dst}"
        return 0
    fi
    return 1
}
shopt -s nullglob
for src in "${GLOBAL_MEMORY_DIR}"/feedback_*.md "${GLOBAL_MEMORY_DIR}"/reference_*.md "${GLOBAL_MEMORY_DIR}"/user_profile.md; do
    base="$(basename "${src}")"
    dst="${PROJECT_MEMORY_DIR}/${base}"
    copy_if_newer "${src}" "${dst}" || true
done
shopt -u nullglob
INDEX="${PROJECT_MEMORY_DIR}/MEMORY.md"
INDEX_TMP="${PROJECT_MEMORY_DIR}/.MEMORY.md.tmp"
generate_index() {
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
            local files=()
            shopt -s nullglob
            case "${section}" in
                user)      files=( "${PROJECT_MEMORY_DIR}/user_"*.md ) ;;
                feedback)  files=( "${PROJECT_MEMORY_DIR}/feedback_"*.md ) ;;
                project)   files=( "${PROJECT_MEMORY_DIR}/project_"*.md ) ;;
                reference) files=( "${PROJECT_MEMORY_DIR}/reference_"*.md ) ;;
            esac
            shopt -u nullglob
            (( ${#files[@]} > 0 )) || continue
            printf '## %s\n' "${label}"
            for f in "${files[@]}"; do
                local fname title desc
                fname="$(basename "${f}")"
                title="$(awk '/^name:/ { sub(/^name: */, ""); print; exit }' "${f}" || true)"
                desc="$(awk '/^description:/ { sub(/^description: */, ""); print; exit }' "${f}" || true)"
                [[ -z "${title}" ]] && title="${fname%.md}"
                [[ -z "${desc}" ]] && desc=""
                if [[ -n "${desc}" ]]; then
                    printf -- '- [%s](%s) — %s\n' "${title}" "${fname}" "${desc}"
                else
                    printf -- '- [%s](%s)\n' "${title}" "${fname}"
                fi
            done
            printf '\n'
        done
    } > "${INDEX_TMP}"
    mv -f "${INDEX_TMP}" "${INDEX}"
}
generate_index
exit 0
