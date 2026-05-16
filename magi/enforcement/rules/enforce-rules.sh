#!/usr/bin/env bash
#
# Unified Enforcement Hook for Claude Code
# ==============================================================================
# This script handles deny rules, content rules, and guideline tracking
# (read-via-tool + read-via-bash-cat) using a JSON configuration file.
#
# CONFIGURATION:
#   ${MAGI_PACK_DIR}/enforcement/rules/enforcement_rules.json
#
# Logs and tracking files are per-project under ~/.claude/projects/<key>/.
# ==============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
source "${SHARED_UTILS}/block-policy.sh"
RED='\033[0;31m'
NC='\033[0m'
readonly RULES_FILE="${MAGI_PACK_DIR}/enforcement/rules/enforcement_rules.json"
if [[ -f "$RULES_FILE" ]]; then
    JQ_CHECK="$(jq '.' "$RULES_FILE" 2>&1 || printf '__INVALID__')"
    if [[ "${JQ_CHECK}" == *"__INVALID__"* ]] || [[ "${JQ_CHECK}" == *"parse error"* ]]; then
        printf '%bBLOCKED: enforcement_rules.json has invalid JSON syntax%b\n' "${RED}" "${NC}" >&2
        printf 'Run: jq . %s\n' "${RULES_FILE}" >&2
        exit 2
    fi
fi
INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // "unknown"')
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""')
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')
CONTENT=$(printf '%s' "$INPUT" | jq -r '.tool_input.content // .tool_input.new_string // ""')
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // "default"')
CONVERSATION_ID=$(printf '%s' "$INPUT" | jq -r '.conversation_id // "unknown"')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')
resolve_project_paths "${CWD}"
TRACKING_FILE="${PROJECT_DIR}/guideline_tracking_${CONVERSATION_ID}"
LOG_FILE="${PROJECT_DIR}/${CONVERSATION_ID}-enforcement.log"
block_policy_init
log_message() {
    local msg="$1"
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${msg}" >> "${LOG_FILE}" || true
}
check_deny_rules() {
    [[ -f "$RULES_FILE" ]] || return 0
    local deny_rules
    deny_rules=$(jq -r '.deny // {}' "$RULES_FILE")
    [[ -z "$deny_rules" || "$deny_rules" == "{}" ]] && return 0
    local rule_names
    rule_names=$(printf '%s' "$deny_rules" | jq -r 'keys[]')
    while IFS= read -r rule_name || [[ -n "${rule_name}" ]]; do
        [[ -z "$rule_name" ]] && continue
        local rule triggers
        rule=$(printf '%s' "$deny_rules" | jq -r ".\"${rule_name}\"")
        triggers=$(printf '%s' "$rule" | jq -c '.triggers[]')
        while IFS= read -r trigger || [[ -n "${trigger}" ]]; do
            [[ -z "$trigger" ]] && continue
            local trigger_tool trigger_pattern trigger_type
            trigger_tool=$(printf '%s' "$trigger" | jq -r '.tool')
            trigger_pattern=$(printf '%s' "$trigger" | jq -r '.pattern')
            trigger_type=$(printf '%s' "$trigger" | jq -r '.type')
            [[ "$trigger_tool" != "$TOOL_NAME" ]] && continue
            local check_value=""
            if [[ "$trigger_type" == "command" ]]; then
                check_value="$COMMAND"
            elif [[ "$trigger_type" == "file_path" ]]; then
                check_value="$FILE_PATH"
            fi
            if [[ -n "$check_value" ]]; then
                local match
                match="$(printf '%s' "$check_value" | grep -E "$trigger_pattern" || true)"
                if [[ -n "${match}" ]]; then
                    local message
                    message=$(printf '%s' "$rule" | jq -r '.message')
                    log_message "DENY: Rule '${rule_name}' triggered for ${TOOL_NAME}: ${check_value}"
                    block_policy_emit_full "deny:${rule_name}" "${message}" "${TOOL_NAME}" "${check_value}"
                    exit 2
                fi
            fi
        done <<< "$triggers"
    done <<< "$rule_names"
    return 0
}
check_content_rules() {
    [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]] || return 0
    [[ -n "$CONTENT" ]] || return 0
    [[ -f "$RULES_FILE" ]] || return 0
    local content_rules
    content_rules=$(jq -r '.content_rules // {}' "$RULES_FILE")
    [[ -z "$content_rules" || "$content_rules" == "{}" ]] && return 0
    local rule_names
    rule_names=$(printf '%s' "$content_rules" | jq -r 'keys[]')
    while IFS= read -r rule_name || [[ -n "${rule_name}" ]]; do
        [[ -z "$rule_name" ]] && continue
        local rule file_pattern exclude_pattern content_pattern action message
        rule=$(printf '%s' "$content_rules" | jq -r ".\"${rule_name}\"")
        file_pattern=$(printf '%s' "$rule" | jq -r '.file_pattern')
        exclude_pattern=$(printf '%s' "$rule" | jq -r '.exclude_pattern // ""')
        content_pattern=$(printf '%s' "$rule" | jq -r '.content_pattern')
        action=$(printf '%s' "$rule" | jq -r '.action')
        message=$(printf '%s' "$rule" | jq -r '.message')
        if [[ -n "$file_pattern" ]]; then
            local fmatch
            fmatch="$(printf '%s' "$FILE_PATH" | grep -E "$file_pattern" || true)"
            [[ -z "${fmatch}" ]] && continue
        fi
        if [[ -n "$exclude_pattern" ]]; then
            local emat
            emat="$(printf '%s' "$FILE_PATH" | grep -E "$exclude_pattern" || true)"
            [[ -n "${emat}" ]] && continue
        fi
        local cmatch
        cmatch="$(printf '%s' "$CONTENT" | grep -E "$content_pattern" || true)"
        if [[ -n "${cmatch}" ]]; then
            if [[ "$action" == "block" ]]; then
                log_message "CONTENT BLOCK: Rule '${rule_name}' triggered for ${FILE_PATH}"
                block_policy_emit_full "content:${rule_name}" "${message}" "${TOOL_NAME}" "${FILE_PATH}"
                exit 2
            elif [[ "$action" == "warn" ]]; then
                log_message "CONTENT WARN: Rule '${rule_name}' triggered for ${FILE_PATH}"
                printf '%b\n' "${message}" >&2
            fi
        fi
    done <<< "$rule_names"
    return 0
}
track_guideline_read() {
    [[ "$TOOL_NAME" == "Read" ]] || return 0
    [[ -f "$RULES_FILE" ]] || return 0
    local limit min_lines
    limit=$(printf '%s' "$INPUT" | jq -r '.tool_input.limit // 0')
    min_lines=$(jq -r '.guideline_tracking.min_lines_required // 100' "$RULES_FILE")
    if [[ "$limit" != "0" && "$limit" != "null" ]]; then
        if (( limit < min_lines )) && [[ "$FILE_PATH" == *"guideline"* ]]; then
            log_message "BYPASS ATTEMPT: Read only ${limit} lines of ${FILE_PATH}"
            printf '[%s] BYPASS ATTEMPT: Read only %s lines of %s\n' \
                "$(date)" "${limit}" "${FILE_PATH}" >> "${PROJECT_SECURITY_LOG}"
            return 0
        fi
    fi
    case "$FILE_PATH" in
        *guidelines*|*guideline_documents*) ;;
        *) return 0 ;;
    esac
    local enforcements rule_names
    enforcements=$(jq -r '.guideline_enforcements // {}' "$RULES_FILE")
    rule_names=$(printf '%s' "$enforcements" | jq -r 'keys[]')
    while IFS= read -r rule_name || [[ -n "${rule_name}" ]]; do
        [[ -z "$rule_name" ]] && continue
        local rule guideline_file tracking_key
        rule=$(printf '%s' "$enforcements" | jq -r ".\"${rule_name}\"")
        guideline_file=$(printf '%s' "$rule" | jq -r '.guideline_file')
        tracking_key=$(printf '%s' "$rule" | jq -r '.tracking_key')
        local base_name="${guideline_file%.*}"
        local md_name="${base_name}.md"
        local xml_name="${base_name}.xml"
        local gsl_name="${base_name}.gsl"
        local lower_md lower_xml lower_gsl
        lower_md="$(printf '%s' "${md_name}" | tr '[:upper:]' '[:lower:]')"
        lower_xml="$(printf '%s' "${xml_name}" | tr '[:upper:]' '[:lower:]')"
        lower_gsl="$(printf '%s' "${gsl_name}" | tr '[:upper:]' '[:lower:]')"
        case "$FILE_PATH" in
            */${md_name}|*/${xml_name}|*/${gsl_name}|*/${lower_md}|*/${lower_xml}|*/${lower_gsl})
                printf '%s\n' "$tracking_key" >> "$TRACKING_FILE"
                log_message "Tracked guideline read: ${tracking_key} via Read tool"
                return 0
                ;;
        esac
    done <<< "$rule_names"
    return 0
}
track_bash_cat_guideline() {
    [[ "$TOOL_NAME" == "Bash" ]] || return 0
    local cat_match
    cat_match="$(printf '%s' "$COMMAND" | grep -E '^cat\s+.*(guidelines|guideline_documents)/.*\.(md|xml|gsl)\s*$' || true)"
    if [[ -z "${cat_match}" ]]; then
        local hint
        hint="$(printf '%s' "$COMMAND" | grep -E '(guidelines|guideline_documents).*\.(md|xml|gsl|txt)' || true)"
        if [[ -n "${hint}" ]]; then
            log_message "POTENTIAL BYPASS: Bash command on guidelines: ${COMMAND}"
            printf '[%s] POTENTIAL BYPASS: Bash command on guidelines: %s\n' \
                "$(date)" "${COMMAND}" >> "${PROJECT_SECURITY_LOG}"
        fi
        return 0
    fi
    local track_via_cat
    track_via_cat=$(jq -r '.guideline_tracking.track_via_bash_cat // true' "$RULES_FILE")
    [[ "$track_via_cat" == "true" ]] || return 0
    local enforcements rule_names
    enforcements=$(jq -r '.guideline_enforcements // {}' "$RULES_FILE")
    rule_names=$(printf '%s' "$enforcements" | jq -r 'keys[]')
    while IFS= read -r rule_name || [[ -n "${rule_name}" ]]; do
        [[ -z "$rule_name" ]] && continue
        local rule guideline_file tracking_key base_name
        rule=$(printf '%s' "$enforcements" | jq -r ".\"${rule_name}\"")
        guideline_file=$(printf '%s' "$rule" | jq -r '.guideline_file')
        tracking_key=$(printf '%s' "$rule" | jq -r '.tracking_key')
        base_name="${guideline_file%.*}"
        local cm
        cm="$(printf '%s' "$COMMAND" | grep -E "/${base_name}\.(md|xml|gsl)" || true)"
        if [[ -n "${cm}" ]]; then
            printf '%s\n' "$tracking_key" >> "$TRACKING_FILE"
            log_message "Tracked guideline read: ${tracking_key} via Bash cat"
            return 0
        fi
    done <<< "$rule_names"
    return 0
}
check_guideline_enforcement() {
    [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]] || return 0
    [[ -f "$RULES_FILE" ]] || return 0
    local enforcements rule_names
    enforcements=$(jq -r '.guideline_enforcements // {}' "$RULES_FILE")
    rule_names=$(printf '%s' "$enforcements" | jq -r 'keys[]')
    while IFS= read -r rule_name || [[ -n "${rule_name}" ]]; do
        [[ -z "$rule_name" ]] && continue
        local rule triggers tracking_key message required_for_all
        rule=$(printf '%s' "$enforcements" | jq -r ".\"${rule_name}\"")
        tracking_key=$(printf '%s' "$rule" | jq -r '.tracking_key')
        message=$(printf '%s' "$rule" | jq -r '.message')
        required_for_all=$(printf '%s' "$rule" | jq -r '.required_for_all // false')
        triggers=$(printf '%s' "$rule" | jq -c '.triggers // []')
        local triggered=false
        if [[ "$triggers" != "[]" && "$triggers" != "null" ]]; then
            local items
            items=$(printf '%s' "$triggers" | jq -c '.[]')
            while IFS= read -r trigger || [[ -n "${trigger}" ]]; do
                [[ -z "$trigger" ]] && continue
                local trigger_tool trigger_pattern
                trigger_tool=$(printf '%s' "$trigger" | jq -r '.tool')
                trigger_pattern=$(printf '%s' "$trigger" | jq -r '.pattern')
                [[ "$trigger_tool" != "$TOOL_NAME" ]] && continue
                local hit
                hit="$(printf '%s' "$FILE_PATH" | grep -E "$trigger_pattern" || true)"
                if [[ -n "${hit}" ]]; then
                    triggered=true
                    break
                fi
            done <<< "$items"
        fi
        if [[ "$triggered" == "true" || "$required_for_all" == "true" ]]; then
            if [[ ! -f "$TRACKING_FILE" ]] || ! grep -qE "^${tracking_key}$" "$TRACKING_FILE"; then
                log_message "ENFORCEMENT: ${rule_name} not satisfied for ${FILE_PATH}"
                block_policy_emit_full "guideline:${rule_name}" "${message}" "${TOOL_NAME}" "${FILE_PATH}"
                exit 2
            fi
        fi
    done <<< "$rule_names"
    return 0
}
JQ_PATH="$(command -v jq || true)"
if [[ -z "${JQ_PATH}" ]]; then
    printf '%bERROR:%b jq is required but not installed\n' "${RED}" "${NC}" >&2
    exit 1
fi
check_deny_rules
check_content_rules
track_guideline_read
track_bash_cat_guideline
check_guideline_enforcement
log_message "Tool: ${TOOL_NAME}, File: ${FILE_PATH}, Command: ${COMMAND:0:50}"
exit 0
