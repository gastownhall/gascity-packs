#!/usr/bin/env bash
#
# Hourly History Partition
# ==============================================================================
# Reads ~/.claude/history.jsonl and partitions every entry into the
# corresponding ~/.claude/projects/<key>/history.jsonl based on .project field.
# Anything without a project field stays at root (rare).
# ==============================================================================
set -Eeuo pipefail
readonly CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly GLOBAL_HISTORY="${CLAUDE_DIR}/history.jsonl"
readonly PROJECTS_DIR="${CLAUDE_DIR}/projects"
readonly LOG_FILE="${CLAUDE_DIR}/_logs/cleanup/hourly-history-partition.log"
readonly WORK_DIR="${CLAUDE_DIR}/_logs/cleanup/.history-work"
mkdir -p "${PROJECTS_DIR}" "$(dirname "${LOG_FILE}")" "${WORK_DIR}"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${LOG_FILE}" || true; }
project_key_from_path() {
    local cwd="${1:-}"
    [[ -z "${cwd}" ]] && { printf ''; return; }
    printf '%s' "${cwd}" | sed 's|^/||' | tr '/_.' '-'
}
log "=== hourly-history-partition start ==="
[[ -f "${GLOBAL_HISTORY}" ]] || { log "no global history.jsonl, skipping"; exit 0; }
[[ -s "${GLOBAL_HISTORY}" ]] || { log "global history.jsonl empty, skipping"; exit 0; }
JQ_PATH="$(command -v jq || true)"
[[ -n "${JQ_PATH}" ]] || { log "jq not available, abort"; exit 0; }
KEEP_FILE="${WORK_DIR}/keep.jsonl"
: > "${KEEP_FILE}"
total=0
moved=0
SEEN_BUCKETS_FILE="${WORK_DIR}/seen-buckets.txt"; : > "${SEEN_BUCKETS_FILE}"
while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -n "${line}" ]] || continue
    total=$((total + 1))
    project_path="$(printf '%s' "${line}" | jq -r '.project // .cwd // ""' 2>&1 || true)"
    if [[ -z "${project_path}" || "${project_path}" == "null" ]]; then
        printf '%s\n' "${line}" >> "${KEEP_FILE}"
        continue
    fi
    key="$(project_key_from_path "${project_path}")"
    [[ -z "${key}" ]] && { printf '%s\n' "${line}" >> "${KEEP_FILE}"; continue; }
    bucket="${PROJECTS_DIR}/-${key}"
    mkdir -p "${bucket}" || { printf '%s\n' "${line}" >> "${KEEP_FILE}"; continue; }
    printf '%s\n' "${line}" >> "${bucket}/history.jsonl"
    moved=$((moved + 1))
    printf "%s\n" "${key}" >> "${SEEN_BUCKETS_FILE}"
done < "${GLOBAL_HISTORY}"
mv -f "${KEEP_FILE}" "${GLOBAL_HISTORY}"
unique_buckets="$(sort -u "${SEEN_BUCKETS_FILE}" | wc -l | tr -d ' ')"
rm -f "${SEEN_BUCKETS_FILE}" || true
log "partitioned ${moved}/${total} entries across ${unique_buckets} project buckets"
log "=== hourly-history-partition done ==="
exit 0
