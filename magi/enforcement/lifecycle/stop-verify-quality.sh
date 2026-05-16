#!/usr/bin/env bash
#
# Stop hook - quality verification via LM Studio
# ==============================================================================
# When SKIP_QUALITY_CHECK=1 (current default), short-circuits with approve.
# Otherwise sends turn content to LM Studio for review.
# All scratch files live under the per-project .scratch dir, not /tmp.
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
OS="$(uname -s)"
readonly OS
[[ "${OS}" == "Darwin" || "${OS}" == "Linux" ]] || { printf 'ERROR: Unsupported OS: %s\n' "${OS}" >&2; exit 1; }
readonly LM_STUDIO_HOST="${LM_STUDIO_HOST:-localhost}"
readonly LM_STUDIO_PORT="${LM_STUDIO_PORT:-1234}"
readonly LM_STUDIO_MODEL="${LM_STUDIO_MODEL:-nvidia/nemotron-3-super}"
readonly LM_STUDIO_URL="http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1/responses"
readonly MAX_POST_HOOK_ATTEMPTS=3
readonly SKIP_QUALITY_CHECK="${SKIP_QUALITY_CHECK:-0}"
INPUT_RAW="$(cat)"
if command -v jq >/dev/null 2>&1; then
    CWD="$(printf '%s' "${INPUT_RAW}" | jq -r '.cwd // ""')"
else
    CWD="${PWD:-/}"
fi
resolve_project_paths "${CWD}"
LOG_FILE="${PROJECT_QUALITY_LOG}"
SCRATCH="${PROJECT_SCRATCH_DIR}"
mkdir -p "${SCRATCH}"
DEBUG_FILE="${SCRATCH}/stop-hook-debug-$$.log"
HASH_FILE="${SCRATCH}/file-hashes-$$"
ATTEMPT_TRACKING_DIR="${PROJECT_TRACKING_DIR}"
SCAN_DIRS=(
    "${MAGI_PACK_DIR}/enforcement"
    "${SCRATCH}"
)
if [[ -f "${SHARED_UTILS}/filesystem.sh" ]]; then
    source "${SHARED_UTILS}/filesystem.sh"
fi
if [[ -f "${SHARED_UTILS}/lm_studio.sh" ]]; then
    source "${SHARED_UTILS}/lm_studio.sh"
fi
if [[ -f "${SHARED_UTILS}/transcript.sh" ]]; then
    source "${SHARED_UTILS}/transcript.sh"
fi
# shellcheck disable=SC2329 # Invoked by the EXIT trap.
cleanup() {
    local rc=$?
    set +e
    [[ -n "${HASH_FILE:-}" ]] && rm -f "${HASH_FILE}" || true
    if [[ "${DEBUG_HOOK:-0}" != "1" ]]; then
        [[ -n "${DEBUG_FILE:-}" ]] && rm -f "${DEBUG_FILE}" || true
    fi
    exit "${rc}"
}
trap cleanup EXIT
has_function() {
    declare -F "$1" >/dev/null
}
log_message() {
    local level="$1"
    shift
    local message="$*"
    {
        printf '[%s] [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${level}" "${message}" >> "${LOG_FILE}"
    } || true
    [[ "${DEBUG_HOOK:-0}" == "1" ]] && printf '[%s] %s\n' "${level}" "${message}" >&2
    return 0
}
short_circuit_approve() {
    local reason="$1"
    log_message "INFO" "${reason}"
    if has_function format_decision_json; then
        format_decision_json "approve" "${reason}"
    else
        jq -n --arg decision "approve" --arg reason "${reason}" '{decision: $decision, reason: $reason}'
    fi
    exit 0
}
preflight() {
    local errors=0
    local jq_p curl_p
    jq_p="$(command -v jq || true)"
    curl_p="$(command -v curl || true)"
    [[ -n "${jq_p}" ]] || { printf 'ERROR: Missing command: jq\n' >&2; errors=$((errors + 1)); }
    [[ -n "${curl_p}" ]] || { printf 'ERROR: Missing command: curl\n' >&2; errors=$((errors + 1)); }
    [[ -w "${LOG_FILE%/*}" ]] || mkdir -p "${LOG_FILE%/*}" || { printf 'ERROR: Cannot write to log directory\n' >&2; errors=$((errors + 1)); }
    if ! curl -s --connect-timeout 30 --max-time 200 "http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1/models" > "${SCRATCH}/lm-probe.out"; then
        log_message "WARN" "LM Studio not reachable at ${LM_STUDIO_HOST}:${LM_STUDIO_PORT}"
        if [[ "${SKIP_QUALITY_CHECK}" == "1" ]]; then
            short_circuit_approve "Quality check skipped - LM Studio unreachable"
        fi
    fi
    rm -f "${SCRATCH}/lm-probe.out" || true
    (( errors == 0 )) || return 1
    return 0
}
build_turn_content() {
    local transcript="$1"
    local turn_content=""
    local full_turn user_msg claude_text tool_calls tool_results
    full_turn="$(extract_turn_content "${transcript}")" || return 1
    turn_content="=== USER REQUEST ===\n"
    user_msg="$(extract_user_request "${full_turn}")"
    turn_content="${turn_content}${user_msg}\n\n"
    turn_content="${turn_content}=== CLAUDE'S RESPONSES ===\n"
    claude_text="$(extract_claude_responses "${full_turn}")"
    if [[ -n "${claude_text}" ]]; then
        turn_content="${turn_content}${claude_text}\n\n"
    else
        turn_content="${turn_content}(No responses)\n\n"
    fi
    turn_content="${turn_content}=== TOOLS USED ===\n"
    tool_calls="$(extract_tools_used "${full_turn}")"
    if [[ -n "${tool_calls}" ]]; then
        turn_content="${turn_content}${tool_calls}\n\n"
    else
        turn_content="${turn_content}(No tools used)\n\n"
    fi
    turn_content="${turn_content}=== TOOL RESULTS ===\n"
    tool_results="$(extract_tool_results "${full_turn}")"
    if [[ -n "${tool_results}" ]]; then
        turn_content="${turn_content}${tool_results}\n\n"
    else
        turn_content="${turn_content}(No results)\n\n"
    fi
    turn_content="${turn_content}=== FILES AFFECTED ===\n"
    local read_files=() written_files=()
    while IFS= read -r file_path; do
        [[ -n "${file_path}" && "${file_path}" != "null" ]] && written_files+=("${file_path}")
    done < <(extract_written_files "${full_turn}")
    while IFS= read -r file_path; do
        [[ -n "${file_path}" && "${file_path}" != "null" ]] && read_files+=("${file_path}")
    done < <(extract_read_files "${full_turn}")
    local fs_changes changed_on_disk=() new_on_disk=() deleted_on_disk=()
    fs_changes="$(detect_file_changes "${HASH_FILE}" "${SCAN_DIRS[@]}")"
    while IFS= read -r line; do
        local files
        if [[ "${line}" == CHANGED:* ]]; then
            files="${line#CHANGED:}"
            if [[ -n "${files}" ]]; then
                local changed_array=()
                IFS=' ' read -ra changed_array <<< "${files}"
                changed_on_disk+=("${changed_array[@]}")
            fi
        elif [[ "${line}" == NEW:* ]]; then
            files="${line#NEW:}"
            if [[ -n "${files}" ]]; then
                local new_array=()
                IFS=' ' read -ra new_array <<< "${files}"
                new_on_disk+=("${new_array[@]}")
            fi
        elif [[ "${line}" == DELETED:* ]]; then
            files="${line#DELETED:}"
            if [[ -n "${files}" ]]; then
                local deleted_array=()
                IFS=' ' read -ra deleted_array <<< "${files}"
                deleted_on_disk+=("${deleted_array[@]}")
            fi
        fi
    done <<< "${fs_changes}"
    local all_files=() unique_files=() seen_files=""
    all_files+=("${read_files[@]}")
    all_files+=("${written_files[@]}")
    all_files+=("${changed_on_disk[@]}")
    all_files+=("${new_on_disk[@]}")
    for file in "${all_files[@]}"; do
        if [[ "${seen_files}" != *"|${file}|"* ]]; then
            unique_files+=("${file}")
            seen_files="${seen_files}|${file}|"
        fi
    done
    if [[ ${#unique_files[@]} -gt 0 ]]; then
        turn_content="${turn_content}\n--- FILE DETECTION SOURCES ---\n"
        turn_content="${turn_content}Tool-reported files: ${#written_files[@]} write/edit, ${#read_files[@]} read\n"
        turn_content="${turn_content}Filesystem-detected: ${#new_on_disk[@]} new, ${#changed_on_disk[@]} modified, ${#deleted_on_disk[@]} deleted\n"
        turn_content="${turn_content}\n--- ACTUAL FILE CONTENTS ---\n"
        local file_count=0
        local max_files=20
        for file_path in "${unique_files[@]}"; do
            ((file_count++))
            if [[ ${file_count} -gt ${max_files} ]]; then
                turn_content="${turn_content}\n[Truncated - showing first ${max_files} files of ${#unique_files[@]}]\n"
                break
            fi
            local detection_source="[via: "
            if file_in_array "${file_path}" "${written_files[@]}"; then
                detection_source="${detection_source}tool-write"
            elif file_in_array "${file_path}" "${read_files[@]}"; then
                detection_source="${detection_source}tool-read"
            elif file_in_array "${file_path}" "${new_on_disk[@]}"; then
                detection_source="${detection_source}fs-new"
            elif file_in_array "${file_path}" "${changed_on_disk[@]}"; then
                detection_source="${detection_source}fs-modified"
            elif file_in_array "${file_path}" "${deleted_on_disk[@]}"; then
                detection_source="${detection_source}fs-deleted"
            fi
            detection_source="${detection_source}]"
            turn_content="${turn_content}\n[${file_path}] ${detection_source}:\n"
            if file_in_array "${file_path}" "${deleted_on_disk[@]}"; then
                turn_content="${turn_content}(File was deleted)\n"
            else
                turn_content="${turn_content}$(read_file_limited "${file_path}" 500)\n"
            fi
        done
    else
        turn_content="${turn_content}(No files affected - verified via both tool calls and filesystem monitoring)\n"
    fi
    printf '%b' "${turn_content}"
}
get_attempt_count() {
    local session_id="$1"
    local attempt_file="${ATTEMPT_TRACKING_DIR}/quality_attempts_${session_id}"
    if [[ -f "${attempt_file}" ]]; then
        local stored_count stored_time current_time
        stored_count="$(cut -d: -f1 "${attempt_file}" || printf '0')"
        stored_time="$(cut -d: -f2 "${attempt_file}" || printf '0')"
        current_time="$(date +%s)"
        if (( current_time - stored_time > 300 )); then
            printf '0'
            return
        fi
        printf '%s' "${stored_count}"
    else
        printf '0'
    fi
}
set_attempt_count() {
    local session_id="$1" count="$2"
    local attempt_file="${ATTEMPT_TRACKING_DIR}/quality_attempts_${session_id}"
    printf '%s:%s' "${count}" "$(date +%s)" > "${attempt_file}"
}
main() {
    local session_id
    session_id="$(printf '%s' "${INPUT_RAW}" | jq -r '.session_id // .conversation_id // "default"' || printf 'default')"
    local POST_HOOK_ATTEMPTS
    POST_HOOK_ATTEMPTS="$(get_attempt_count "${session_id}")"
    POST_HOOK_ATTEMPTS=$((POST_HOOK_ATTEMPTS + 1))
    set_attempt_count "${session_id}" "${POST_HOOK_ATTEMPTS}"
    if (( POST_HOOK_ATTEMPTS > MAX_POST_HOOK_ATTEMPTS )); then
        log_message "WARN" "Recursion limit exceeded (attempt ${POST_HOOK_ATTEMPTS}/${MAX_POST_HOOK_ATTEMPTS}), approving to prevent infinite loop"
        jq -n --arg decision "approve" --arg reason "Recursion limit exceeded - auto-approving (attempt ${POST_HOOK_ATTEMPTS})" '{decision: $decision, reason: $reason}'
        exit 0
    fi
    if [[ "${SKIP_QUALITY_CHECK}" == "1" ]]; then
        short_circuit_approve "Quality check skipped via environment variable"
    fi
    log_message "INFO" "Starting quality check (attempt ${POST_HOOK_ATTEMPTS}/${MAX_POST_HOOK_ATTEMPTS})"
    preflight || { log_message "ERROR" "Preflight check failed"; exit 1; }
    if has_function store_file_hashes; then
        store_file_hashes "${HASH_FILE}" "${SCAN_DIRS[@]}"
    fi
    local transcript_path
    transcript_path="$(printf '%s' "${INPUT_RAW}" | jq -r '.transcript_path // ""' || printf '')"
    if [[ -z "${transcript_path}" || ! -f "${transcript_path}" ]]; then
        log_message "WARN" "No transcript available - creating minimal fallback"
        transcript_path="${SCRATCH}/empty-transcript-$$.jsonl"
        printf '%s\n' '{"type":"user","userType":"external","message":{"content":"[No transcript available]"}}' > "${transcript_path}"
    fi
    log_message "INFO" "Processing transcript: ${transcript_path} (attempt ${POST_HOOK_ATTEMPTS}/${MAX_POST_HOOK_ATTEMPTS})"
    if ! has_function build_turn_content; then
        log_message "WARN" "build_turn_content helper missing - approving"
        short_circuit_approve "build_turn_content helper missing"
    fi
    local turn_content
    turn_content="$(build_turn_content "${transcript_path}")" || {
        log_message "ERROR" "Failed to build turn content"
        if has_function format_decision_json; then
            format_decision_json "block" "ERROR: Failed to extract turn content for review"
        fi
        exit 1
    }
    local review lm_status decision formatted_review
    if review="$(send_to_lm_studio "${turn_content}" "${LM_STUDIO_URL}" "${LM_STUDIO_MODEL}")"; then
        lm_status=0
    else
        lm_status=$?
    fi
    formatted_review="═══════════════════════════════════════════════════════════════
LM Studio Quality Review (Attempt ${POST_HOOK_ATTEMPTS}/${MAX_POST_HOOK_ATTEMPTS}):
═══════════════════════════════════════════════════════════════
${review:-ERROR: Failed to get review from LM Studio}
═══════════════════════════════════════════════════════════════"
    if (( lm_status == 0 )); then
        decision="$(determine_decision "${review}")"
        log_message "INFO" "Review completed with decision: ${decision}"
    else
        log_message "ERROR" "LM Studio review failed with status ${lm_status}"
        if (( POST_HOOK_ATTEMPTS >= 2 )); then
            log_message "WARN" "Multiple failures, approving to prevent blocking"
            decision="approve"
            formatted_review="${formatted_review}

Note: Approved after ${POST_HOOK_ATTEMPTS} failed attempts to prevent blocking"
        else
            decision="block"
        fi
    fi
    format_decision_json "${decision}" "${formatted_review}"
    if [[ "${decision}" == "block" ]]; then
        printf 'BLOCKED: Quality review failed - see reason above\n' >&2
        exit 2
    fi
    exit 0
}
main "$@"
