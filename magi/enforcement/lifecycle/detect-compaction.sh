#!/usr/bin/env bash
#
# Detect Compaction/Resume Hook
# ==============================================================================
# Detects when a conversation is compacted or resumed and clears guideline
# tracking state. Also prompts for scope file re-reading if one exists.
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // ""')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')
resolve_project_paths "${CWD}"
MATCHED="$(printf '%s' "$PROMPT" | grep -iE '(^|\s)(/compact|/resume|compacted|resumed)' || true)"
if [[ -n "${MATCHED}" ]]; then
    printf '[%s] Detected compaction/resume in prompt, clearing tracking\n' "$(date)" \
        >> "${PROJECT_ENFORCEMENT_LOG}"
    rm -f "${PROJECT_TRACKING_DIR}/claude_guidelines_read_"* || true
    rm -f "${PROJECT_TRACKING_DIR}/claude_guidelines_timestamp_"* || true
    rm -f "${PROJECT_TRACKING_DIR}/claude_prohibited_"* || true
    cat >&2 <<'EOF'
════════════════════════════════════════════════════════════════════
COMPACTION/RESUME DETECTED: Enforcement tracking reset.
All guidelines must be read again before code generation.

MANDATORY POST-COMPACTION ACTION:
You MUST re-read ~/.claude/CLAUDE.md IMMEDIATELY using the Read tool.
This file contains behavioral rules you are likely to violate after
compaction -- especially around testing full orchestration scripts,
context window management, and XML validation.

DO NOT SKIP THIS. Read it NOW before doing ANYTHING else.
  Read tool → file_path: ${HOME}/.claude/CLAUDE.md
════════════════════════════════════════════════════════════════════
EOF
    SCOPE_FILE="${PROJECT_DIR}/scope.md"
    if [[ -f "$SCOPE_FILE" ]]; then
        cat >&2 <<EOF
PROJECT SCOPE FILE DETECTED!
You MUST read the scope file to realign with project objectives:
  ${SCOPE_FILE}
Use: Read tool with file_path: ${SCOPE_FILE}
════════════════════════════════════════════════════════════════════
EOF
        printf '[%s] Scope file reminder issued: %s\n' "$(date)" "${SCOPE_FILE}" \
            >> "${PROJECT_ENFORCEMENT_LOG}"
    fi
fi
