#!/usr/bin/env bash
# shellcheck disable=SC2034 # This file intentionally exposes globals to sourcing scripts.
#
# Project Key Resolution Utility
# ==============================================================================
# Single canonical implementation of the cwd -> Claude Code projects/<key>
# directory mapping. The harness collapses '/', '_', and '.' into '-' when
# computing project subdirectories. Earlier hook implementations omitted the
# '.' collapse, which is why some projects had history.jsonl in a different
# bucket from their session transcripts (.scripts vs --scripts).
# ==============================================================================
project_key_from_path() {
    local cwd="${1:-}"
    [[ -z "${cwd}" ]] && cwd="$(pwd)"
    printf '%s' "${cwd}" | sed 's|^/||' | tr '/_.' '-'
}
project_dir_from_path() {
    local cwd="${1:-}"
    local key
    key="$(project_key_from_path "${cwd}")"
    printf '%s/.claude/projects/-%s' "${HOME}" "${key}"
}
ensure_project_dir() {
    local dir="$1"
    [[ -d "${dir}" ]] || mkdir -p "${dir}" || return 1
    [[ -d "${dir}/tracking" ]] || mkdir -p "${dir}/tracking" || true
    return 0
}
resolve_project_paths() {
    local cwd="${1:-${CLAUDE_PROJECT_DIR:-${PWD:-/}}}"
    PROJECT_KEY="$(project_key_from_path "${cwd}")"
    PROJECT_DIR="$(project_dir_from_path "${cwd}")"
    PROJECT_TRACKING_DIR="${PROJECT_DIR}/tracking"
    PROJECT_ENFORCEMENT_LOG="${PROJECT_DIR}/enforcement.log"
    PROJECT_SECURITY_LOG="${PROJECT_DIR}/security.log"
    PROJECT_QUALITY_LOG="${PROJECT_DIR}/quality-verification.log"
    PROJECT_AGENT_LOG="${PROJECT_DIR}/agent-usage.log"
    PROJECT_SCRATCH_DIR="${PROJECT_DIR}/.scratch"
    ensure_project_dir "${PROJECT_DIR}"
}
