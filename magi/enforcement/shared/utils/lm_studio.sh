#!/usr/bin/env bash
[[ -n "${__LM_STUDIO_UTILS_LOADED:-}" ]] && return 0
__LM_STUDIO_UTILS_LOADED=1
readonly SIMPLE_MODEL="qwen/qwen3-next-80b"
readonly MODERATE_MODEL="glm-4.6"
readonly COMPLEX_MODEL="openai/gpt-oss-120b"
readonly STATE_FILE="/tmp/lm_studio_state_$$"
readonly MAX_RETRIES=3
readonly RETRY_DELAY=2
get_complexity_model() {
    local content="$1"
    local line_count word_count complexity_score
    line_count="$(printf '%s' "${content}" | wc -l | tr -d ' ')"
    word_count="$(printf '%s' "${content}" | wc -w | tr -d ' ')"
    complexity_score=0
    [[ ${line_count} -gt 2000 ]] && ((complexity_score += 3))
    [[ ${line_count} -gt 1000 ]] && ((complexity_score += 2))
    [[ ${line_count} -gt 500 ]] && ((complexity_score += 1))
    [[ ${word_count} -gt 20000 ]] && ((complexity_score += 3))
    [[ ${word_count} -gt 10000 ]] && ((complexity_score += 2))
    [[ ${word_count} -gt 5000 ]] && ((complexity_score += 1))
    printf '%s' "${content}" | grep -qE '(class|function|def|impl|struct|trait|interface)' && ((complexity_score += 2))
    printf '%s' "${content}" | grep -qE '(ERROR|FAIL|WARNING|CRITICAL|SEVERE)' && ((complexity_score += 2))
    printf '%s' "${content}" | grep -q 'FILES AFFECTED' && ((complexity_score += 1))
    local num_files
    num_files="$(printf '%s' "${content}" | grep -c '^\[/.*\]:$' || true)"
    [[ ${num_files} -gt 20 ]] && ((complexity_score += 3))
    [[ ${num_files} -gt 10 ]] && ((complexity_score += 2))
    [[ ${num_files} -gt 0 ]] && ((complexity_score += 1))
    local model
    if [[ ${complexity_score} -le 3 ]]; then
        model="${SIMPLE_MODEL}"
    elif [[ ${complexity_score} -le 7 ]]; then
        model="${MODERATE_MODEL}"
    else
        model="${COMPLEX_MODEL}"
    fi
    [[ "${DEBUG_HOOK:-0}" == "1" ]] && printf 'Model selection: score=%d, model=%s\n' "${complexity_score}" "${model}" >&2
    printf '%s' "${model}"
}
load_conversation_state() {
    local state_file="$1"
    if [[ -f "${state_file}" ]] && [[ -s "${state_file}" ]]; then
        cat "${state_file}"
    else
        printf ''
    fi
}
save_conversation_state() {
    local state_file="$1"
    local response_id="$2"
    printf '%s' "${response_id}" > "${state_file}"
}
send_to_lm_studio() {
    local content="$1"
    local lm_studio_url="${2:-http://localhost:1234/v1/responses}"
    local model_override="${3:-}"
    local selected_model
    if [[ -n "${model_override}" ]]; then
        selected_model="${model_override}"
    else
        selected_model="$(get_complexity_model "${content}")"
    fi
    local system_prompt="You are an AI code reviewer analyzing a Claude Code session turn. Review the user request, Claude's responses, tools used, tool results, and ACTUAL FILE CONTENTS that were affected. Files are detected via BOTH tool calls AND filesystem monitoring to catch any modifications. Look for: violations of coding standards, non-deterministic language (should/would/could/might), incomplete implementations, errors in the actual code, poor communication, guideline violations, unhandled edge cases, security issues, or quality problems. Check that Claude actually did what was requested. Be harsh but constructive. Focus on THIS specific turn only. IMPORTANT: Guidelines exist in both .md (markdown) and .xml (structured XML) formats in ${MAGI_PACK_DIR}/guidelines/. Reading EITHER format satisfies the guideline requirement for a given language. XML guidelines contain the same rules as markdown but in a structured format with severity levels and enforcement attributes. Do NOT flag reading an XML guideline file as a violation - it is equivalent to reading the markdown version."
    local previous_response_id
    previous_response_id="$(load_conversation_state "${STATE_FILE}")"
    local attempt=1
    local response review
    while [[ ${attempt} -le ${MAX_RETRIES} ]]; do
        [[ "${DEBUG_HOOK:-0}" == "1" ]] && printf 'Attempt %d/%d with model %s\n' "${attempt}" "${MAX_RETRIES}" "${selected_model}" >&2
        local payload
        if [[ -n "${previous_response_id}" ]]; then
            payload="$(jq -n \
                --arg input "${system_prompt}\n\n${content}" \
                --arg model "${selected_model}" \
                --arg prev_id "${previous_response_id}" \
                '{
                    model: $model,
                    input: $input,
                    previous_response_id: $prev_id,
                    temperature: 0.1,
                    max_tokens: 10000,
                    stream: false
                }' 2>/dev/null)"
        else
            payload="$(jq -n \
                --arg input "${system_prompt}\n\n${content}" \
                --arg model "${selected_model}" \
                '{
                    model: $model,
                    input: $input,
                    temperature: 0.1,
                    max_tokens: 10000,
                    stream: false
                }' 2>/dev/null)"
        fi
        if [[ -z "${payload}" ]]; then
            printf 'ERROR: Failed to create LM Studio payload\n'
            return 1
        fi
        response="$(curl -s -X POST "${lm_studio_url}" \
            --connect-timeout 600 \
            --max-time 600 \
            -H "Content-Type: application/json" \
            -d "${payload}" 2>&1)"
        local curl_exit_code=$?
        if [[ ${curl_exit_code} -ne 0 ]]; then
            if [[ ${attempt} -eq ${MAX_RETRIES} ]]; then
                printf 'ERROR: Failed to reach LM Studio at %s after %d attempts (exit code: %d)\n' "${lm_studio_url}" "${MAX_RETRIES}" "${curl_exit_code}"
                return 1
            fi
            sleep "${RETRY_DELAY}"
            ((attempt++))
            continue
        fi
        if [[ -z "${response}" ]]; then
            if [[ ${attempt} -eq ${MAX_RETRIES} ]]; then
                printf 'ERROR: LM Studio returned empty response after %d attempts\n' "${MAX_RETRIES}"
                return 1
            fi
            sleep "${RETRY_DELAY}"
            ((attempt++))
            continue
        fi
        if ! printf '%s' "${response}" | jq empty 2>/dev/null; then
            if [[ ${attempt} -eq ${MAX_RETRIES} ]]; then
                printf 'ERROR: LM Studio returned invalid JSON after %d attempts\n' "${MAX_RETRIES}"
                return 1
            fi
            sleep "${RETRY_DELAY}"
            ((attempt++))
            continue
        fi
        local response_id
        response_id="$(printf '%s' "${response}" | jq -r '.id // empty' 2>/dev/null)"
        if [[ -n "${response_id}" ]]; then
            save_conversation_state "${STATE_FILE}" "${response_id}"
        fi
        review="$(printf '%s' "${response}" | jq -r '
            .output[1].content[0].text //
            .output[0].content[0].text //
            .text //
            .choices[0].message.content //
            empty' 2>/dev/null)"
        if [[ -z "${review}" ]]; then
            local error_msg
            error_msg="$(printf '%s' "${response}" | jq -r '.error.message // empty' 2>/dev/null)"
            if [[ -n "${error_msg}" ]]; then
                if [[ ${attempt} -eq ${MAX_RETRIES} ]]; then
                    printf 'ERROR: LM Studio returned error after %d attempts: %s\n' "${MAX_RETRIES}" "${error_msg}"
                    return 1
                fi
                if [[ "${selected_model}" == "${SIMPLE_MODEL}" ]]; then
                    selected_model="${MODERATE_MODEL}"
                    [[ "${DEBUG_HOOK:-0}" == "1" ]] && printf 'Upgrading model from simple to moderate due to error\n' >&2
                elif [[ "${selected_model}" == "${MODERATE_MODEL}" ]]; then
                    selected_model="${COMPLEX_MODEL}"
                    [[ "${DEBUG_HOOK:-0}" == "1" ]] && printf 'Upgrading model from moderate to complex due to error\n' >&2
                fi
                sleep "${RETRY_DELAY}"
                ((attempt++))
                continue
            else
                if [[ ${attempt} -eq ${MAX_RETRIES} ]]; then
                    printf 'ERROR: Could not extract review from LM Studio response after %d attempts\n' "${MAX_RETRIES}"
                    return 1
                fi
                sleep "${RETRY_DELAY}"
                ((attempt++))
                continue
            fi
        fi
        printf '%s' "${review}"
        return 0
    done
    printf 'ERROR: Failed to get valid response from LM Studio after %d attempts\n' "${MAX_RETRIES}"
    return 1
}
determine_decision() {
    local review="$1"
    local lower_review
    lower_review="$(printf '%s' "${review}" | tr '[:upper:]' '[:lower:]')"
    if printf '%s' "${lower_review}" | grep -qE '\b(pass|passed|approve|approved|accept|accepted|success|successful)\b|perfect execution|no issues found|no violations found|looks good|fully compliant|all checks pass'; then
        printf 'approve'
        return 0
    fi
    if printf '%s' "${lower_review}" | grep -qE '\b(fail|failed|block|blocked|reject|rejected|deny|denied|halt|halted|abort|aborted)\b'; then
        printf 'block'
        return 0
    fi
    if printf '%s' "${lower_review}" | grep -qE '^error:'; then
        printf 'block'
        return 0
    fi
    if printf '%s' "${lower_review}" | grep -qE 'critical failure|critical error|critical issue|\bsevere\b|\bdangerous\b|\bunsafe\b'; then
        printf 'block'
        return 0
    fi
    if printf '%s' "${lower_review}" | grep -qE 'quality violation|guideline violation|standard violation|\bmust fix\b|unacceptable'; then
        printf 'block'
        return 0
    fi
    if printf '%s' "${lower_review}" | grep -qE 'security risk|vulnerability|injection|unsafe code|malicious'; then
        printf 'block'
        return 0
    fi
    printf 'approve'
}
format_decision_json() {
    local decision="$1"
    local reason="$2"
    jq -n \
        --arg decision "${decision}" \
        --arg reason "${reason}" \
        '{decision: $decision, reason: $reason}'
}
cleanup_lm_studio_state() {
    [[ -f "${STATE_FILE:-}" ]] && rm -f "${STATE_FILE}" || true
}