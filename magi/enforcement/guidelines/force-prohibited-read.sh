#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // "default"')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')
resolve_project_paths "${CWD}"
LAST_READ_FILE="${PROJECT_TRACKING_DIR}/claude_prohibited_last_read_${SESSION_ID}"
CURRENT_TIME=$(date +%s)
if [[ -f "$LAST_READ_FILE" ]]; then
    LAST_READ=$(cat "$LAST_READ_FILE")
    TIME_DIFF=$((CURRENT_TIME - LAST_READ))
    if (( TIME_DIFF < 1800 )); then
        exit 0
    fi
fi
printf '%s' "${CURRENT_TIME}" > "$LAST_READ_FILE"
cat <<'EOF' >&2
══════════════════════════════════════════════════════════════════
MANDATORY: Read prohibited_behavior.xml before proceeding.
Use: Read tool with file_path: ${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/prohibited_behavior.xml
This is the authoritative XML enforcement source -- read the entire file (no limit).
══════════════════════════════════════════════════════════════════
EOF
printf '[%s] Forced prohibited_behavior.xml reminder at turn start\n' "$(date)" >> "${PROJECT_ENFORCEMENT_LOG}"
