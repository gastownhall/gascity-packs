#!/usr/bin/env bash
extract_turn_content() {
    local transcript="$1"
    if [[ ! -r "$transcript" ]]; then
        echo "(ERROR: Cannot read transcript file: $transcript)"
        return 1
    fi
    local last_user_line
    last_user_line="$(grep -n '"type":"user"' "$transcript" | \
                      grep '"userType":"external"' | \
                      grep -v '"type":"tool_result"' | \
                      tail -1 | cut -d: -f1)"
    if [[ -z "$last_user_line" ]]; then
        last_user_line="$(($(wc -l < "$transcript") - 50))"
        [[ $last_user_line -lt 1 ]] && last_user_line=1
    fi
    tail -n "+${last_user_line}" "$transcript" 2>/dev/null
}
extract_user_request() {
    local turn_data="$1"
    echo "$turn_data" | head -1 | \
        jq -r 'if .message.content then
            if (.message.content | type) == "array" then
                (.message.content[] |
                    if .type == "text" then .text
                    elif .type == "tool_result" then .content
                    else empty end)
            elif (.message.content | type) == "string" then
                .message.content
            else empty end
        else empty end' 2>/dev/null || echo "(No user message found)"
}
extract_claude_responses() {
    local turn_data="$1"
    echo "$turn_data" | \
        jq -r 'select(.type == "assistant" and .message.content) |
            if (.message.content | type) == "array" then
                .message.content[] | select(.type == "text") | .text
            elif (.message.content | type) == "string" then
                .message.content
            else empty end' 2>/dev/null || echo ""
}
extract_tools_used() {
    local turn_data="$1"
    echo "$turn_data" | \
        jq -r 'select(.type == "assistant" and .message.content) |
            if (.message.content | type) == "array" then
                .message.content[] | select(.type == "tool_use") |
                "[" + .name + "]: " + (.input | tostring)
            else empty end' 2>/dev/null || echo ""
}
extract_tool_results() {
    local turn_data="$1"
    echo "$turn_data" | \
        jq -r 'select(.toolResult) |
            "[" + .toolResult.toolName + "]: " +
            if .toolResult.error then
                "ERROR: " + .toolResult.error
            else
                (.toolResult.content // "SUCCESS")
            end' 2>/dev/null || echo ""
}
extract_written_files() {
    local turn_data="$1"
    echo "$turn_data" | jq -r '
        select(.type == "assistant" and .message.content) |
        if (.message.content | type) == "array" then
            .message.content[] |
            select(.type == "tool_use" and (.name == "Write" or .name == "Edit")) |
            .input.file_path
        else empty end' 2>/dev/null
}
extract_read_files() {
    local turn_data="$1"
    echo "$turn_data" | jq -r '
        select(.type == "assistant" and .message.content) |
        if (.message.content | type) == "array" then
            .message.content[] |
            select(.type == "tool_use" and .name == "Read") |
            .input.file_path
        else empty end' 2>/dev/null
}