#!/usr/bin/env bash
#
# Enforcement Cache Management
# ==============================================================================
# Manages guideline enforcement cache to prevent redundant reads within sessions.
# Cache lives under the per-project directory (computed via project-key.sh).
# ==============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
resolve_project_paths "${CLAUDE_PROJECT_DIR:-${PWD:-/}}"
CACHE_FILE="${PROJECT_DIR}/enforcement-cache.json"
[[ -f "${CACHE_FILE}" ]] || printf '{}\n' > "${CACHE_FILE}"
get_file_hash() {
    local file="$1"
    local sha256_path shasum_path
    sha256_path="$(command -v sha256sum || true)"
    shasum_path="$(command -v shasum || true)"
    if [[ -n "${sha256_path}" ]]; then
        sha256sum "${file}" | cut -d' ' -f1
    elif [[ -n "${shasum_path}" ]]; then
        shasum -a 256 "${file}" | cut -d' ' -f1
    else
        printf 'NOHASH'
    fi
}
cache_guideline() {
    local guideline_path="$1"
    local current_hash guideline_name
    current_hash="$(get_file_hash "${guideline_path}")"
    guideline_name="$(basename "${guideline_path}")"
    jq --arg name "${guideline_name}" \
       --arg hash "${current_hash}" \
       --arg path "${guideline_path}" \
       --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       '.[$name] = {hash: $hash, path: $path, timestamp: $timestamp}' \
       "${CACHE_FILE}" > "${CACHE_FILE}.tmp" && \
    mv "${CACHE_FILE}.tmp" "${CACHE_FILE}"
}
is_cached() {
    local guideline_path="$1"
    local guideline_name cached_hash current_hash exists
    guideline_name="$(basename "${guideline_path}")"
    exists="$(jq -e --arg name "${guideline_name}" 'has($name)' "${CACHE_FILE}" 2>&1 || true)"
    [[ "${exists}" == "true" ]] || return 1
    cached_hash="$(jq -r --arg name "${guideline_name}" '.[$name].hash' "${CACHE_FILE}" 2>&1 || printf '')"
    current_hash="$(get_file_hash "${guideline_path}")"
    [[ "${cached_hash}" == "${current_hash}" ]]
}
clear_cache() {
    printf '{}\n' > "${CACHE_FILE}"
}
