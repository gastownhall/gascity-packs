#!/usr/bin/env bash
#
# Agent Routing Enforcement Hook
# ==============================================================================
# Enforces proper agent selection based on task context. Uses soft warnings for
# misrouted agents and hard blocks only for critical violations.
# Logs to per-project agent-usage.log under ~/.claude/projects/<key>/.
# ==============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'
JQ_PATH="$(command -v jq || true)"
[[ -n "${JQ_PATH}" ]] || exit 0
INPUT=$(cat)
[[ -n "$INPUT" ]] || exit 0
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // "unknown"')
[[ "$TOOL_NAME" == "Task" ]] || exit 0
SUBAGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.tool_input.subagent_type // ""')
TASK_DESCRIPTION=$(printf '%s' "$INPUT" | jq -r '.tool_input.description // ""')
PROMPT=$(printf '%s' "$INPUT" | jq -r '.tool_input.prompt // ""')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')
resolve_project_paths "${CWD}"
FULL_CONTEXT="${TASK_DESCRIPTION} ${PROMPT}"
FULL_CONTEXT_LOWER=$(printf '%s' "$FULL_CONTEXT" | tr '[:upper:]' '[:lower:]')
printf '[%s] Agent: %s | Task: %s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "${SUBAGENT_TYPE}" "${TASK_DESCRIPTION:0:80}" \
    >> "${PROJECT_AGENT_LOG}" || true
is_code_generation_task() {
    local match
    match="$(printf '%s' "$FULL_CONTEXT_LOWER" | grep -E 'write|create|implement|generate|build|add|develop|code|script|function|class|module' || true)"
    [[ -n "${match}" ]]
}
is_research_task() {
    local match
    match="$(printf '%s' "$FULL_CONTEXT_LOWER" | grep -E 'find|search|explore|understand|analyze|review|investigate|check|look|examine|locate|where|what|how|why' || true)"
    [[ -n "${match}" ]]
}
is_exploratory_agent() {
    case "$SUBAGENT_TYPE" in
        Explore|general-purpose|Plan|claude-code-guide) return 0 ;;
        *) return 1 ;;
    esac
}
warn_agent_mismatch() {
    local expected_agent="$1"
    local reason="$2"
    printf '%b[AGENT-ROUTING]%b Consider using %b%s%b agent: %s\n' \
        "${YELLOW}" "${NC}" "${CYAN}" "${expected_agent}" "${NC}" "${reason}" >&2
    printf '[%s] ADVISORY: Consider %s instead of %s\n' \
        "$(date '+%Y-%m-%d %H:%M:%S')" "${expected_agent}" "${SUBAGENT_TYPE}" \
        >> "${PROJECT_AGENT_LOG}" || true
}
block_agent_mismatch() {
    local expected_agent="$1"
    local reason="$2"
    printf '%b[AGENT-ROUTING VIOLATION]%b\n' "${RED}" "${NC}" >&2
    printf '%s\n' "${reason}" >&2
    printf 'REQUIRED: Use Task tool with %bsubagent_type="%s"%b\n' "${CYAN}" "${expected_agent}" "${NC}" >&2
    printf '[%s] BLOCKED: %s -> should be %s\n' \
        "$(date '+%Y-%m-%d %H:%M:%S')" "${SUBAGENT_TYPE}" "${expected_agent}" \
        >> "${PROJECT_ENFORCEMENT_LOG}" || true
    exit 2
}
test_pattern() {
    local pattern="$1"
    local match
    match="$(printf '%s' "$FULL_CONTEXT_LOWER" | grep -E "${pattern}" || true)"
    [[ -n "${match}" ]]
}
if is_research_task && is_exploratory_agent; then
    exit 0
fi
if is_exploratory_agent && ! is_code_generation_task; then
    exit 0
fi
if [[ "$SUBAGENT_TYPE" == "Explore" ]] && test_pattern '\.utilities|utilities/|utilities directory'; then
    block_agent_mismatch "tree-structure-documenter" \
        ".utilities/ directories require tree-structure-documenter for complete structural documentation"
fi
if is_code_generation_task && is_exploratory_agent; then
    if test_pattern '\.py$|python|pydantic|async.*python|python.*async'; then
        block_agent_mismatch "python-forge" \
            "Python code generation MUST use python-forge agent for guideline compliance"
    fi
    if test_pattern '\.rs$|rust|cargo|tokio'; then
        block_agent_mismatch "rust-forge" \
            "Rust code generation MUST use rust-forge agent for guideline compliance"
    fi
    if test_pattern '\.cs$|c#|csharp|dotnet|\.net'; then
        block_agent_mismatch "csharp-forge" \
            "C# code generation MUST use csharp-forge agent for guideline compliance"
    fi
    if test_pattern '\.sh$|bash|shell script'; then
        block_agent_mismatch "bashforge-script-generator" \
            "Bash script generation MUST use bashforge-script-generator agent"
    fi
    if test_pattern '\.tsx?$|react|typescript|next\.?js|frontend'; then
        block_agent_mismatch "frontend-developer" \
            "React/TypeScript code generation MUST use frontend-developer agent"
    fi
    if test_pattern 'yew|wasm|webassembly'; then
        block_agent_mismatch "yew-forge" \
            "Yew/WASM code generation MUST use yew-forge agent"
    fi
fi
if test_pattern 'security|vulnerability|owasp|injection|xss'; then
    case "$SUBAGENT_TYPE" in
        security-auditor|claude-code-guide|Explore|general-purpose) ;;
        *) warn_agent_mismatch "security-auditor" "Security tasks benefit from specialized security-auditor" ;;
    esac
fi
if test_pattern 'database|schema|migration|sql|postgresql|mysql'; then
    case "$SUBAGENT_TYPE" in
        database-architect|claude-code-guide|Explore|general-purpose) ;;
        *) warn_agent_mismatch "database-architect" "Database tasks benefit from database-architect" ;;
    esac
fi
if test_pattern 'performance|optimization|profiling|bottleneck'; then
    case "$SUBAGENT_TYPE" in
        performance-optimizer|claude-code-guide|Explore|general-purpose) ;;
        *) warn_agent_mismatch "performance-optimizer" "Performance tasks benefit from performance-optimizer" ;;
    esac
fi
if test_pattern 'docker|kubernetes|k8s|terraform|ci/cd|pipeline'; then
    case "$SUBAGENT_TYPE" in
        devops-engineer|claude-code-guide|Explore|general-purpose|bashforge-script-generator) ;;
        *) warn_agent_mismatch "devops-engineer" "DevOps tasks benefit from devops-engineer" ;;
    esac
fi
if test_pattern 'unit test|integration test|test coverage|pytest|jest'; then
    case "$SUBAGENT_TYPE" in
        test-engineer|claude-code-guide|Explore|general-purpose) ;;
        *) warn_agent_mismatch "test-engineer" "Testing tasks benefit from test-engineer" ;;
    esac
fi
exit 0
