#!/usr/bin/env bash
#
# SessionStart Hook - Load Guidelines Context and Display Banner
# ==============================================================================
# Loads guideline file locations, sets environment variables, and outputs
# the MAGI banner for Claude to display in response.
# Guideline directory: ${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/
# Format: XML (authoritative for enforcement). GSL/markdown copies preserved
# under ../gsl/ and ../markdown/ as human-readable mirrors.
# ==============================================================================
set -euo pipefail
readonly GUIDELINES_DIR="${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml"
readonly GUIDELINES_GSL_DIR="${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/gsl"
readonly GUIDELINES_MARKDOWN_DIR="${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/markdown"
readonly AGENTS_DIR="${HOME}/.claude/agents"
INPUT=$(cat)
SOURCE=$(printf '%s' "$INPUT" | jq -r '.source // "unknown"')
if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
    printf 'export CLAUDE_GUIDELINES_DIR="%s"\n' "${GUIDELINES_DIR}" >> "$CLAUDE_ENV_FILE"
    printf 'export CLAUDE_GUIDELINES_GSL_DIR="%s"\n' "${GUIDELINES_GSL_DIR}" >> "$CLAUDE_ENV_FILE"
    printf 'export CLAUDE_GUIDELINES_MARKDOWN_DIR="%s"\n' "${GUIDELINES_MARKDOWN_DIR}" >> "$CLAUDE_ENV_FILE"
    printf 'export CLAUDE_AGENTS_DIR="%s"\n' "${AGENTS_DIR}" >> "$CLAUDE_ENV_FILE"
fi
cat <<'BANNER'

═══════════════════════════════════════════════════════════════════════════════
MANDATORY: DISPLAY THE MAGI BANNER BELOW AS THE FIRST THING IN YOUR RESPONSE
═══════════════════════════════════════════════════════════════════════════════

Display this EXACT ASCII art in a code block WITH A PRECEDING LINE BREAK TO AVOID BREAKING THE ASCII ART!!!!!!!!!
__________________________________
  ███╗   ███╗  █████╗   ██████╗  ██╗
  ████╗ ████║ ██╔══██╗ ██╔════╝  ██║
  ██╔████╔██║ ███████║ ██║  ███╗ ██║
  ██║╚██╔╝██║ ██╔══██║ ██║   ██║ ██║
  ██║ ╚═╝ ██║ ██║  ██║ ╚██████╔╝ ██║
  ╚═╝     ╚═╝ ╚═╝  ╚═╝  ╚═════╝  ╚═╝

NEVER skip displaying this banner. NO EXCEPTIONS.
After the banner, continue with your normal response.

═══════════════════════════════════════════════════════════════════════════════

BANNER
cat <<'CONTEXT'

Available guidelines in ${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/ (XML is authoritative for enforcement; read the entire file):
- Python: python_guidelines.xml
- Bash/Shell: bash_guidelines.xml
- PowerShell: powershell_guidelines.xml
- C#: csharp_guidelines.xml
- Rust: rust_guidelines.xml
- Maven/Java: maven_guidelines.xml
- Swift: swift_guidelines.xml
- SQL: sql_guidelines.xml
- Frontend: frontend_guidelines.xml
- Angular: angular_guidelines.xml
- AngularJS: angular_js_guidelines.xml
- API Design: api_guidelines.xml
- Docker: docker_guidelines.xml
- Kubernetes: kubernetes_guidelines.xml
- Infrastructure: bicep_guidelines.xml, lxc_guidelines.xml
- Cloud Services: azure_variable_guidelines.xml, cosmosdb_guidelines.xml
- Messaging: kafka_guidelines.xml, rabbit_mq_guidelines.xml, redis_guidelines.xml, storage_and_messaging_principles.xml
- Observability: datadog_observability.xml
- Data: snowflake_guidelines.xml, powerquery_guidelines.xml
- Utilities: utilities_guidelines.xml, automation_principles.xml
- Behavior: prohibited_behavior.xml
- Writing: WRITING_STYLE.md (kept as markdown — no XML twin)

GSL and markdown mirrors of the same content live alongside under ../gsl/ and ../markdown/.

Available specialized agents in ~/.claude/agents/:
Use Task tool to invoke agents for complex work.

**FUCKING BE CAREFUL WITH YOUR CONTEXT WINDOW!!!!!!!! DO **NOT** LET IT EXCEED 50% BEFORE YOU EVEN START WORK!!!!!!**
CONTEXT
if [[ "${SOURCE}" == "startup" ]]; then
    cat <<'STARTUP_ONLY'

═══════════════════════════════════════════════════════════════════════════════
FIRST ACTION (NEW SESSION ONLY): ~/.claude/CLAUDE.md is auto-loaded as a memory file.
═══════════════════════════════════════════════════════════════════════════════
~/.claude/CLAUDE.md is already injected into context as the global memory file.
Acknowledge it ONCE per fresh session by stating:
  "I have read and acknowledge ~/.claude/CLAUDE.md"
This reminder is suppressed on resume and compact (the file is still in context).
Key rules that get lost during compaction:
- Run the FULL orchestration script the user specifies, NOT individual sub-scripts
- Validate ALL output files (XML well-formedness, required closing tags, correct attributes)
- Scripts must be IDEMPOTENT, SELF-HEALING, ERROR FREE, and VALIDATED
- Do NOT re-read files you already have in context
- `while IFS= read -r line` DROPS the last line without trailing newline -- use `|| [[ -n "${line}" ]]`
STARTUP_ONLY
fi
exit 0
