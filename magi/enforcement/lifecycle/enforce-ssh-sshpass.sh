#!/usr/bin/env bash
set -Eeuo pipefail
INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // "unknown"')
if [[ "$TOOL_NAME" == "Bash" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
    COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')
    FILE_CONTENT=$(printf '%s' "$INPUT" | jq -r '.tool_input.content // ""')
    NEW_STRING=$(printf '%s' "$INPUT" | jq -r '.tool_input.new_string // ""')
    CONTENT_TO_CHECK="${COMMAND}${FILE_CONTENT}${NEW_STRING}"
    SSH_HIT="$(printf '%s' "$CONTENT_TO_CHECK" | grep -E '(^|\s)ssh\s+[^|;&]*@' || true)"
    if [[ -n "${SSH_HIT}" ]]; then
        SSHPASS_HIT="$(printf '%s' "$CONTENT_TO_CHECK" | grep -E 'sshpass' || true)"
        if [[ -z "${SSHPASS_HIT}" ]]; then
            printf 'WARNING: SSH command detected without sshpass. Use sshpass for non-interactive SSH in automation.\n' >&2
            printf 'Example: sshpass -p "$PASSWORD" ssh user@host command\n' >&2
        fi
    fi
    SCP_HIT="$(printf '%s' "$CONTENT_TO_CHECK" | grep -E '(^|\s)scp\s+' || true)"
    if [[ -n "${SCP_HIT}" ]]; then
        SSHPASS_HIT="$(printf '%s' "$CONTENT_TO_CHECK" | grep -E 'sshpass' || true)"
        if [[ -z "${SSHPASS_HIT}" ]]; then
            printf 'WARNING: SCP command detected without sshpass. Use sshpass for non-interactive SCP in automation.\n' >&2
            printf 'Example: sshpass -p "$PASSWORD" scp file user@host:/path/\n' >&2
        fi
    fi
fi
