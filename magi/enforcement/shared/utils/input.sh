#!/usr/bin/env bash
###############################################################################
# input.sh - JSON input parsing helpers for hook scripts
# Note: Uses printf '%s' instead of echo to safely handle special characters
#       and literal newlines in JSON input
###############################################################################
_INPUT_SH_SOURCED=1
HOOK_INPUT=""
read_hook_input() {
    HOOK_INPUT=$(cat)
    printf '%s' "$HOOK_INPUT"
}
get_json_field() {
    local field="$1"
    local default="${2:-}"
    local input="${3:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r "${field} // \"${default}\"" 2>/dev/null || printf '%s' "$default"
}
get_tool_name() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.tool_name // "unknown"' 2>/dev/null || printf '%s' "unknown"
}
get_session_id() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.session_id // "default"' 2>/dev/null || printf '%s' "default"
}
get_conversation_id() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.conversation_id // "unknown"' 2>/dev/null || printf '%s' "unknown"
}
get_file_path() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.tool_input.file_path // ""' 2>/dev/null || printf '%s' ""
}
get_command() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null || printf '%s' ""
}
get_content() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.tool_input.content // .tool_input.new_string // ""' 2>/dev/null || printf '%s' ""
}
get_cwd() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.cwd // ""' 2>/dev/null || printf '%s' ""
}
get_prompt() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.prompt // ""' 2>/dev/null || printf '%s' ""
}
get_hook_event() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.hook_event_name // "unknown"' 2>/dev/null || printf '%s' "unknown"
}
get_status() {
    local input="${1:-$HOOK_INPUT}"
    printf '%s' "$input" | jq -r '.status // 0' 2>/dev/null || printf '%s' "0"
}
