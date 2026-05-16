#!/usr/bin/env bash
set -euo pipefail
_SECURITY_SH_SOURCED=1
has_path_traversal() {
    local path="$1"
    if echo "$path" | grep -q '\.\./'; then
        return 0
    fi
    return 1
}
is_sensitive_file() {
    local path="$1"
    case "$path" in
        *.env|*.env.*)
            return 0
            ;;
        */.git/*|*/secrets/*|*/credentials/*|*/.ssh/*)
            return 0
            ;;
        *_key|*_key.*|*.key|*.pem|*.crt|*.p12|*.pfx)
            return 0
            ;;
        *password*|*secret*|*token*|*api_key*|*apikey*)
            return 0
            ;;
    esac
    return 1
}
validate_file_path() {
    local path="$1"
    local error_msg=""
    if has_path_traversal "$path"; then
        error_msg="Path traversal detected in: $path"
        echo "$error_msg" >&2
        return 1
    fi
    if [[ ! "$path" =~ ^/ ]] && [[ ! "$path" =~ ^\~ ]]; then
        error_msg="Path must be absolute: $path"
        echo "$error_msg" >&2
        return 1
    fi
    return 0
}
sanitize_json_string() {
    local input="$1"
    local sanitized
    sanitized=$(echo "$input" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | tr '\n' ' ' | tr '\r' ' ')
    echo "$sanitized"
}
get_project_safe_path() {
    local path="$1"
    if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
        if [[ "$path" == "${CLAUDE_PROJECT_DIR}"* ]]; then
            return 0
        fi
    fi
    return 1
}
