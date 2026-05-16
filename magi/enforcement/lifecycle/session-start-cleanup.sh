#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/banner.sh"
source "${SHARED_UTILS}/project-key.sh"
INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // "default"')
CONVERSATION_ID=$(printf '%s' "$INPUT" | jq -r '.conversation_id // "unknown"')
EVENT=$(printf '%s' "$INPUT" | jq -r '.hook_event_name // "unknown"')
SOURCE=$(printf '%s' "$INPUT" | jq -r '.source // "startup"')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')
resolve_project_paths "${CWD}"
printf '[%s] Session event: %s, Source: %s, Session: %s, Conversation: %s\n' \
    "$(date)" "${EVENT}" "${SOURCE}" "${SESSION_ID}" "${CONVERSATION_ID}" \
    >> "${PROJECT_ENFORCEMENT_LOG}"
rm -f "${PROJECT_TRACKING_DIR}/claude_guidelines_read_"* || true
rm -f "${PROJECT_TRACKING_DIR}/claude_guidelines_timestamp_"* || true
rm -f "${PROJECT_TRACKING_DIR}/claude_prohibited_"* || true
printf '[%s] Cleared all guideline tracking files for fresh enforcement\n' "$(date)" \
    >> "${PROJECT_ENFORCEMENT_LOG}"
printf '\n' >&2
print_magi_banner >&2
printf '\n' >&2
print_separator >&2
printf '  SESSION INITIALIZED: Guideline tracking reset.\n' >&2
printf '  All guidelines must be read again before code generation.\n' >&2
printf '  This ensures compliance after resume/compaction.\n' >&2
print_separator >&2
printf '\n' >&2
printf '  MANDATORY: Re-read ~/.claude/CLAUDE.md using the Read tool BEFORE\n' >&2
printf '  doing ANY work. This file contains critical behavioral rules:\n' >&2
printf '  - Context window management (DO NOT exceed 50%% before starting work)\n' >&2
printf '  - Testing rules (run the FULL orchestration script, not sub-scripts)\n' >&2
printf '  - Script quality standards (idempotent, self-healing, validated)\n' >&2
printf '  - XML validation requirements\n' >&2
printf '\n' >&2
printf '  Read tool -> file_path: ${HOME}/.claude/CLAUDE.md\n' >&2
printf '\n' >&2
exit 0
