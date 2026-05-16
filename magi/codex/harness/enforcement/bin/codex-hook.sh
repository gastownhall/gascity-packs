#!/usr/bin/env bash
set -Eeuo pipefail

readonly EVENT="${1:-}"
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
# shellcheck disable=SC1091 # common.sh is resolved relative to the installed hook path at runtime.
source "${SCRIPT_DIR}/common.sh"

INPUT="$(cat)"
SESSION_ID="$(json_get "${INPUT}" '.session_id // "default"' "default")"
TURN_ID="$(json_get "${INPUT}" '.turn_id // "unknown"' "unknown")"
CWD="$(json_get "${INPUT}" '.cwd // env.PWD // ""' "${PWD:-}")"
TOOL_NAME="$(json_get "${INPUT}" '.tool_name // "unknown"' "unknown")"
COMMAND="$(json_get "${INPUT}" '.tool_input.command // .tool_input.cmd // ""' "")"

resolve_project_paths "${CWD}"
validate_rules_file

patch_paths() {
    awk '
        /^\*\*\* (Add|Update|Delete) File: / {
            sub(/^\*\*\* (Add|Update|Delete) File: /, "", $0)
            print $0
        }
    ' <<< "${COMMAND}"
}

patch_added_paths() {
    awk '
        /^\*\*\* Add File: / {
            sub(/^\*\*\* Add File: /, "", $0)
            print $0
        }
    ' <<< "${COMMAND}"
}

tool_matches_trigger() {
    local trigger_tool="$1"
    case "${TOOL_NAME}:${trigger_tool}" in
        "${trigger_tool}:${trigger_tool}") return 0 ;;
        exec_command:Bash|functions.exec_command:Bash) return 0 ;;
        apply_patch:Write|apply_patch:Edit) return 0 ;;
        *) return 1 ;;
    esac
}

trigger_value_for() {
    local trigger_type="$1"
    local file_path="${2:-}"
    case "${trigger_type}" in
        command)
            printf '%s' "${COMMAND}"
            ;;
        file_path)
            printf '%s' "${file_path}"
            ;;
        *)
            printf ''
            ;;
    esac
}

check_deny_rules_for_value() {
    local file_path="${1:-}"
    [[ -f "${CODEX_RULES_FILE}" ]] || return 0
    local rule_names
    rule_names="$(jq -r '.deny // {} | keys[]' "${CODEX_RULES_FILE}")"
    while IFS= read -r rule_name || [[ -n "${rule_name}" ]]; do
        [[ -n "${rule_name}" ]] || continue
        local triggers
        triggers="$(jq -c --arg rule "${rule_name}" '.deny[$rule].triggers[]?' "${CODEX_RULES_FILE}")"
        while IFS= read -r trigger || [[ -n "${trigger}" ]]; do
            [[ -n "${trigger}" ]] || continue
            local trigger_tool trigger_type trigger_pattern check_value
            trigger_tool="$(jq -r '.tool' <<< "${trigger}")"
            trigger_type="$(jq -r '.type' <<< "${trigger}")"
            trigger_pattern="$(jq -r '.pattern' <<< "${trigger}")"
            tool_matches_trigger "${trigger_tool}" || continue
            check_value="$(trigger_value_for "${trigger_type}" "${file_path}")"
            [[ -n "${check_value}" ]] || continue
            if match_regex "${check_value}" "${trigger_pattern}"; then
                local message
                message="$(jq -r --arg rule "${rule_name}" '.deny[$rule].message' "${CODEX_RULES_FILE}")"
                log_message "${PROJECT_SECURITY_LOG}" "DENY ${rule_name}: ${TOOL_NAME} ${check_value}"
                block_hook "BLOCKED: ${message}"
            fi
        done <<< "${triggers}"
    done <<< "${rule_names}"
}

check_content_rules_for_patch() {
    [[ "${TOOL_NAME}" == "apply_patch" ]] || return 0
    [[ -f "${CODEX_RULES_FILE}" ]] || return 0
    local warnings=()
    local file_path rule_names
    rule_names="$(jq -r '.content_rules // {} | keys[]' "${CODEX_RULES_FILE}")"
    while IFS= read -r file_path || [[ -n "${file_path}" ]]; do
        [[ -n "${file_path}" ]] || continue
        while IFS= read -r rule_name || [[ -n "${rule_name}" ]]; do
            [[ -n "${rule_name}" ]] || continue
            local file_pattern exclude_pattern content_pattern action message
            file_pattern="$(jq -r --arg rule "${rule_name}" '.content_rules[$rule].file_pattern // ""' "${CODEX_RULES_FILE}")"
            exclude_pattern="$(jq -r --arg rule "${rule_name}" '.content_rules[$rule].exclude_pattern // ""' "${CODEX_RULES_FILE}")"
            content_pattern="$(jq -r --arg rule "${rule_name}" '.content_rules[$rule].content_pattern // ""' "${CODEX_RULES_FILE}")"
            action="$(jq -r --arg rule "${rule_name}" '.content_rules[$rule].action // "block"' "${CODEX_RULES_FILE}")"
            message="$(jq -r --arg rule "${rule_name}" '.content_rules[$rule].message // $rule' "${CODEX_RULES_FILE}")"
            [[ "${action}" != "disabled" ]] || continue
            [[ -z "${file_pattern}" ]] || match_regex "${file_path}" "${file_pattern}" || continue
            if [[ -n "${exclude_pattern}" ]] && match_regex "${file_path}" "${exclude_pattern}"; then
                continue
            fi
            [[ -n "${content_pattern}" ]] || continue
            if match_regex "${COMMAND}" "${content_pattern}"; then
                log_message "${PROJECT_SECURITY_LOG}" "CONTENT ${action}: ${rule_name} ${file_path}"
                if [[ "${action}" == "block" ]]; then
                    block_hook "BLOCKED: ${message}"
                fi
                warnings+=("${message}")
            fi
        done <<< "${rule_names}"
    done < <(patch_paths)
    if (( ${#warnings[@]} > 0 )); then
        json_system_message "$(printf '%s\n' "${warnings[@]}")"
    fi
}

check_extensionless_patch_creates() {
    [[ "${TOOL_NAME}" == "apply_patch" ]] || return 0
    local file_path base
    while IFS= read -r file_path || [[ -n "${file_path}" ]]; do
        [[ -n "${file_path}" ]] || continue
        base="${file_path##*/}"
        case "${base}" in
            ""|*.*) ;;
            *)
                log_message "${PROJECT_SECURITY_LOG}" "BLOCKED extensionless create: ${file_path}"
                block_hook "BLOCKED: Refusing to create an extensionless file: ${file_path}"
                ;;
        esac
    done < <(patch_added_paths)
}

track_guideline_reads_from_bash() {
    case "${TOOL_NAME}" in
        Bash|exec_command|functions.exec_command) ;;
        *) return 0 ;;
    esac
    local matches path
    matches="$(grep -Eo '([^[:space:]'"'"'"]*/)?[^[:space:]'"'"'"]*(guidelines|guideline_documents)[^[:space:]'"'"'"]*\.(xml|md|gsl)' <<< "${COMMAND}" || true)"
    while IFS= read -r path || [[ -n "${path}" ]]; do
        [[ -n "${path}" ]] || continue
        record_guideline_read "${SESSION_ID}" "${path}"
    done <<< "${matches}"
}

guidelines_are_stale() {
    local timestamp_file="${PROJECT_TRACKING_DIR}/guidelines_timestamp_${SESSION_ID}"
    [[ -f "${timestamp_file}" ]] || return 1
    local last_read current_time
    last_read="$(cat "${timestamp_file}")"
    current_time="$(date +%s)"
    (( current_time - last_read > 3600 ))
}

check_guideline_required_for_patch() {
    [[ "${TOOL_NAME}" == "apply_patch" ]] || return 0
    local tracking_file
    tracking_file="$(tracking_file_for "${SESSION_ID}")"
    if guidelines_are_stale; then
        rm -f "${tracking_file}" "${PROJECT_TRACKING_DIR}/guidelines_timestamp_${SESSION_ID}" || true
    fi
    local file_path lang guideline_path
    while IFS= read -r file_path || [[ -n "${file_path}" ]]; do
        [[ -n "${file_path}" ]] || continue
        lang="$(language_for_path "${file_path}")"
        [[ -n "${lang}" ]] || continue
        if [[ ! -f "${tracking_file}" ]] || ! grep -qxF "${lang}" "${tracking_file}"; then
            guideline_path="$(guideline_path_for_key "${lang}")"
            [[ -n "${guideline_path}" ]] || guideline_path="${CLAUDE_GUIDELINES_DIR}/${lang}_guidelines.xml"
            block_hook "BLOCKED: Read the ${lang} guideline before editing ${file_path}: ${guideline_path}"
        fi
    done < <(patch_paths)
}

check_sshpass_warning() {
    [[ "${TOOL_NAME}" == "Bash" ]] || return 0
    local ssh_hit scp_hit
    ssh_hit="$(grep -E '(^|[[:space:]])ssh[[:space:]]+[^|;&]*@' <<< "${COMMAND}" || true)"
    scp_hit="$(grep -E '(^|[[:space:]])scp[[:space:]]+' <<< "${COMMAND}" || true)"
    if [[ -n "${ssh_hit}${scp_hit}" ]] && ! grep -qE 'sshpass' <<< "${COMMAND}"; then
        json_system_message "WARNING: SSH/SCP command detected without sshpass. Use sshpass for non-interactive automation."
    fi
}

handle_pre_tool_use() {
    track_guideline_reads_from_bash
    check_deny_rules_for_value
    if [[ "${TOOL_NAME}" == "apply_patch" ]]; then
        local file_path
        while IFS= read -r file_path || [[ -n "${file_path}" ]]; do
            [[ -n "${file_path}" ]] || continue
            check_deny_rules_for_value "${file_path}"
        done < <(patch_paths)
        check_extensionless_patch_creates
        check_guideline_required_for_patch
        check_content_rules_for_patch
    fi
    check_sshpass_warning
    log_message "${PROJECT_ENFORCEMENT_LOG}" "PreToolUse ${TOOL_NAME} turn=${TURN_ID}"
}

handle_permission_request() {
    handle_pre_tool_use
}

handle_user_prompt_submit() {
    rm -f "${PROJECT_TRACKING_DIR}/extensionless_warned_${SESSION_ID}" || true
    local prompt current_time last_file last_read time_diff context=""
    prompt="$(json_get "${INPUT}" '.prompt // ""' "")"
    current_time="$(date +%s)"
    last_file="${PROJECT_TRACKING_DIR}/prohibited_last_reminder_${SESSION_ID}"
    if [[ -f "${last_file}" ]]; then
        last_read="$(cat "${last_file}")"
        time_diff=$((current_time - last_read))
    else
        time_diff=999999
    fi
    if (( time_diff > 1800 )); then
        printf '%s' "${current_time}" > "${last_file}"
        context="${context}Reminder: review prohibited behavior before enforcement-sensitive work: ${CODEX_GUIDELINES_DIR}/prohibited_behavior.xml"$'\n'
    fi
    if match_regex "${prompt}" '(^|\s)(/compact|/resume|compacted|resumed)'; then
        rm -f "${PROJECT_TRACKING_DIR}/guidelines_read_"* "${PROJECT_TRACKING_DIR}/guidelines_timestamp_"* || true
        context="${context}Compaction/resume detected. Guideline tracking was reset; re-read relevant guidelines before editing."$'\n'
    fi
    log_message "${PROJECT_ENFORCEMENT_LOG}" "UserPromptSubmit turn=${TURN_ID}"
    if [[ -n "${context}" ]]; then
        json_additional_context "UserPromptSubmit" "${context}"
    fi
    return 0
}

handle_session_start() {
    local source context
    source="$(json_get "${INPUT}" '.source // "startup"' "startup")"
    log_message "${PROJECT_ENFORCEMENT_LOG}" "SessionStart source=${source} session=${SESSION_ID}"
    context="Codex enforcement is active for this session. Guidelines live at ${CODEX_GUIDELINES_DIR}. Before editing code, inspect the relevant guideline file; Bash commands that read guideline files are tracked by the Codex enforcement hook."
    json_additional_context "SessionStart" "${context}"
}

handle_post_tool_use() {
    log_message "${PROJECT_ENFORCEMENT_LOG}" "PostToolUse ${TOOL_NAME} turn=${TURN_ID}"
}

attempt_count_for_quality() {
    local attempt_file="${PROJECT_TRACKING_DIR}/quality_attempts_${SESSION_ID}"
    local stored_count stored_time current_time
    if [[ ! -f "${attempt_file}" ]]; then
        printf '0'
        return 0
    fi
    IFS=: read -r stored_count stored_time < "${attempt_file}" || true
    stored_count="${stored_count:-0}"
    stored_time="${stored_time:-0}"
    current_time="$(date +%s)"
    if (( current_time - stored_time > 300 )); then
        printf '0'
    else
        printf '%s' "${stored_count}"
    fi
}

set_quality_attempt_count() {
    local count="$1"
    printf '%s:%s' "${count}" "$(date +%s)" > "${PROJECT_TRACKING_DIR}/quality_attempts_${SESSION_ID}"
}

clear_quality_attempt_count() {
    rm -f "${PROJECT_TRACKING_DIR}/quality_attempts_${SESSION_ID}" || true
}

latest_codex_transcript() {
    local explicit session_dir candidate
    explicit="$(json_get "${INPUT}" '.transcript_path // .transcriptPath // ""' "")"
    if [[ -n "${explicit}" && -f "${explicit}" ]]; then
        printf '%s' "${explicit}"
        return 0
    fi

    session_dir="${CODEX_HOME}/sessions"
    [[ -d "${session_dir}" ]] || return 1

    candidate="$(
        find "${session_dir}" -name 'rollout-*.jsonl' -print 2>/dev/null \
            | sort \
            | while IFS= read -r path; do
                if jq -e --arg session_id "${SESSION_ID}" '
                    select(.type == "session_meta" and ((.payload.id // .session_id // "") == $session_id))
                ' "${path}" >/dev/null 2>&1; then
                    printf '%s\n' "${path}"
                fi
            done \
            | sed -n '$p'
    )"
    if [[ -n "${candidate}" && -f "${candidate}" ]]; then
        printf '%s' "${candidate}"
        return 0
    fi

    find "${session_dir}" -name 'rollout-*.jsonl' -print 2>/dev/null | sort | sed -n '$p'
}

limit_chars() {
    local max_chars="$1"
    awk -v max_chars="${max_chars}" '
        BEGIN { total = 0 }
        total < max_chars {
            remaining = max_chars - total
            if (length($0) > remaining) {
                print substr($0, 1, remaining)
                print "[truncated]"
                total = max_chars
                next
            }
            print
            total += length($0) + 1
        }
    '
}

extract_codex_turn_content() {
    local transcript="$1"
    jq -r -s '
        def text_content($content):
            if $content == null then ""
            elif ($content | type) == "string" then $content
            elif ($content | type) == "array" then
                [$content[]? | .text? // .input_text? // .output_text? // empty] | join("\n")
            else ($content | tostring) end;

        def compact_json($value):
            if $value == null then ""
            elif ($value | type) == "string" then $value
            else ($value | tojson) end;

        def command_text($payload):
            if ($payload.command? | type) == "array" then ($payload.command | map(tostring) | join(" "))
            else ($payload.command? // "" | tostring) end;

        . as $rows
        | ([range(0; length) as $i
            | select(
                $rows[$i].type == "response_item"
                and $rows[$i].payload.type == "message"
                and $rows[$i].payload.role == "user"
              )
            | $i
          ] | last // 0) as $start
        | $rows[$start:][]
        | if .type == "response_item" and .payload.type == "message" and .payload.role == "user" then
              "=== USER REQUEST ===\n" + text_content(.payload.content)
          elif .type == "event_msg" and .payload.type == "user_message" then
              "=== USER REQUEST ===\n" + (.payload.message // "")
          elif .type == "response_item" and .payload.type == "message" and .payload.role == "assistant" then
              "=== ASSISTANT RESPONSE ===\n" + text_content(.payload.content)
          elif .type == "event_msg" and .payload.type == "agent_message" then
              "=== ASSISTANT UPDATE ===\n" + (.payload.message // "")
          elif .type == "response_item" and (.payload.type == "function_call" or .payload.type == "custom_tool_call") then
              "=== TOOL CALL ===\n[" + (.payload.name // "unknown") + "]\n"
              + compact_json(.payload.arguments // .payload.input // "")
          elif .type == "response_item" and (.payload.type == "function_call_output" or .payload.type == "custom_tool_call_output") then
              "=== TOOL RESULT ===\n[" + (.payload.call_id // "unknown") + "]\n"
              + compact_json(.payload.output // "")
          elif .type == "event_msg" and .payload.type == "exec_command_end" then
              "=== COMMAND RESULT ===\ncmd: " + command_text(.payload)
              + "\nexit: " + ((.payload.exit_code // "unknown") | tostring)
              + "\noutput:\n" + ((.payload.aggregated_output // .payload.stdout // .payload.stderr // "") | tostring)
          else empty end
    ' "${transcript}" | limit_chars "${CODEX_TURN_CONTENT_LIMIT:-70000}"
}

collect_patch_files_from_transcript() {
    local transcript="$1"
    jq -r -s '
        def patch_input:
            if .payload.type == "custom_tool_call" then (.payload.input // "")
            else ((.payload.arguments // "{}" | fromjson? // {}) | .command // .cmd // "")
            end;

        . as $rows
        | ([range(0; length) as $i
            | select(
                $rows[$i].type == "response_item"
                and $rows[$i].payload.type == "message"
                and $rows[$i].payload.role == "user"
              )
            | $i
          ] | last // 0) as $start
        | $rows[$start:][]
        | select(.type == "response_item")
        | select((.payload.type == "function_call" or .payload.type == "custom_tool_call") and .payload.name == "apply_patch")
        | patch_input
    ' "${transcript}" \
        | awk '
            /^\*\*\* (Add|Update|Delete) File: / {
                sub(/^\*\*\* (Add|Update|Delete) File: /, "", $0)
                print $0
            }
        ' \
        | awk '!seen[$0]++'
}

read_file_limited_for_quality() {
    local path="$1"
    local max_lines="${2:-500}"
    [[ -f "${path}" ]] || return 1
    sed -n "1,${max_lines}p" "${path}" 2>/dev/null || return 1
}

append_affected_files() {
    local transcript="$1"
    local file_path resolved file_count=0 max_files=20
    printf '\n=== FILES AFFECTED ===\n'
    while IFS= read -r file_path || [[ -n "${file_path}" ]]; do
        [[ -n "${file_path}" ]] || continue
        ((file_count++))
        if (( file_count > max_files )); then
            printf '\n[Truncated - showing first %s affected files]\n' "${max_files}"
            break
        fi
        if [[ "${file_path}" == /* ]]; then
            resolved="${file_path}"
        else
            resolved="${CWD%/}/${file_path}"
        fi
        printf '\n[%s]\n' "${resolved}"
        if [[ -e "${resolved}" ]]; then
            read_file_limited_for_quality "${resolved}" 500 || printf '(Unable to read file)\n'
        else
            printf '(File does not exist on disk; likely deleted or patch failed)\n'
        fi
    done < <(collect_patch_files_from_transcript "${transcript}")

    if (( file_count == 0 )); then
        printf '(No apply_patch file paths detected in the current Codex turn)\n'
    fi
}

build_codex_quality_context() {
    local transcript="$1"
    extract_codex_turn_content "${transcript}"
    append_affected_files "${transcript}"
}

send_quality_review() {
    local turn_content="$1"
    local prompt payload response review
    prompt="You are a strict quality verification hook for Codex.

Review the current Codex turn below. Decide whether the assistant is trying to finish with incomplete work, false claims, unverified claims, missing tests for changes, ignored errors, unsafe commands, or failure to satisfy the user's explicit request.

Reply with exactly one leading token:
PASS: concise reason
BLOCK: concise reason and concrete remediation

Current turn:
${turn_content}"

    payload="$(jq -n \
        --arg model "${LM_STUDIO_MODEL:-nvidia/nemotron-3-super}" \
        --arg input "${prompt}" \
        '{model:$model,input:$input,temperature:0.1,max_tokens:1800,stream:false}')"
    response="$(curl -s -X POST "http://${LM_STUDIO_HOST:-localhost}:${LM_STUDIO_PORT:-1234}/v1/responses" \
        --connect-timeout "${LM_STUDIO_CONNECT_TIMEOUT:-3}" \
        --max-time "${LM_STUDIO_MAX_TIME:-75}" \
        -H "Content-Type: application/json" \
        -d "${payload}")"
    review="$(jq -r '
        .output[0].content[0].text
        // .output[1].content[0].text
        // .choices[0].message.content
        // .message.content
        // empty
    ' <<< "${response}" 2>/dev/null || true)"
    [[ -n "${review}" ]] || return 1
    printf '%s' "${review}"
}

quality_decision_from_review() {
    local review="$1"
    if match_regex "${review}" '^[[:space:]]*(BLOCK|FAIL|FAILED|REJECT)([^A-Za-z]|$)'; then
        printf 'block'
    else
        printf 'approve'
    fi
}

emit_quality_approve() {
    local reason="$1"
    jq -n --arg reason "${reason}" '{continue: true, suppressOutput: true, reason: $reason}'
}

emit_quality_block() {
    local reason="$1"
    jq -n --arg reason "${reason}" '{decision: "block", reason: $reason}'
}

handle_stop() {
    local max_attempts="${CODEX_MAX_QUALITY_ATTEMPTS:-3}"
    local attempt_count transcript_path turn_content review decision formatted_reason
    log_message "${PROJECT_ENFORCEMENT_LOG}" "Stop turn=${TURN_ID}"
    if [[ "${CODEX_SKIP_QUALITY_CHECK:-0}" == "1" || "${SKIP_QUALITY_CHECK:-0}" == "1" ]]; then
        emit_quality_approve "Quality check skipped by environment variable"
        return 0
    fi

    attempt_count="$(attempt_count_for_quality)"
    attempt_count=$((attempt_count + 1))
    set_quality_attempt_count "${attempt_count}"
    if (( attempt_count > max_attempts )); then
        log_message "${PROJECT_QUALITY_LOG}" "Recursion limit exceeded attempt=${attempt_count}/${max_attempts}; approving"
        clear_quality_attempt_count
        emit_quality_approve "Quality recursion limit exceeded; approving to avoid an infinite Stop loop"
        return 0
    fi

    transcript_path="$(latest_codex_transcript || true)"
    if [[ -z "${transcript_path}" || ! -f "${transcript_path}" ]]; then
        log_message "${PROJECT_QUALITY_LOG}" "No transcript available for Stop quality review"
        if (( attempt_count >= 2 )); then
            clear_quality_attempt_count
            emit_quality_approve "No transcript available after repeated quality attempts"
        else
            emit_quality_block "Quality review could not run: no Codex transcript was available"
        fi
        return 0
    fi

    log_message "${PROJECT_QUALITY_LOG}" "Starting quality review attempt=${attempt_count}/${max_attempts} transcript=${transcript_path}"
    turn_content="$(build_codex_quality_context "${transcript_path}")" || {
        log_message "${PROJECT_QUALITY_LOG}" "Failed to build quality context from transcript=${transcript_path}"
        emit_quality_block "Quality review could not extract current turn context"
        return 0
    }

    if review="$(send_quality_review "${turn_content}")"; then
        decision="$(quality_decision_from_review "${review}")"
        formatted_reason="LM Studio Quality Review (attempt ${attempt_count}/${max_attempts}):
${review}"
        log_message "${PROJECT_QUALITY_LOG}" "Quality review decision=${decision}"
    else
        formatted_reason="LM Studio quality review failed at http://${LM_STUDIO_HOST:-localhost}:${LM_STUDIO_PORT:-1234}/v1/responses (attempt ${attempt_count}/${max_attempts})"
        log_message "${PROJECT_QUALITY_LOG}" "${formatted_reason}"
        if (( attempt_count >= 2 )); then
            clear_quality_attempt_count
            emit_quality_approve "${formatted_reason}; approving after repeated verifier failures"
            return 0
        fi
        emit_quality_block "${formatted_reason}"
        return 0
    fi

    if [[ "${decision}" == "block" ]]; then
        emit_quality_block "${formatted_reason}"
    else
        clear_quality_attempt_count
        emit_quality_approve "${formatted_reason}"
    fi
}

case "${EVENT}" in
    SessionStart) handle_session_start ;;
    UserPromptSubmit) handle_user_prompt_submit ;;
    PreToolUse) handle_pre_tool_use ;;
    PermissionRequest) handle_permission_request ;;
    PostToolUse) handle_post_tool_use ;;
    Stop) handle_stop ;;
    *) block_hook "Unknown Codex hook event: ${EVENT}" ;;
esac
