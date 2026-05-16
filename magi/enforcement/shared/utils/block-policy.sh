#!/usr/bin/env bash
#
# Block-Policy Utility (Anti-Bypass Enforcement Layer)
# ==============================================================================
# Sourced by enforce-rules.sh and enforce-guidelines.sh.
#
# PURPOSE:
#   These hooks block specific tool patterns (e.g. /dev/null, tee, head, /tmp,
#   inline -c, discrete az). Without policy framing, Claude treats each block
#   as an obstacle and mutates the command into a different incantation that
#   achieves the same prohibited outcome. That is the anti-pattern this
#   utility is designed to make obvious to Claude inside the block message.
#
# BEHAVIOR:
#   1. Every block records (epoch | tool | rule_name | snippet) in a per-session
#      history file under the project tracking dir.
#   2. When >=2 blocks have fired within RECENT_WINDOW_S (default 60s), the
#      block emits a "BYPASS PATTERN DETECTED" preamble that lists the recent
#      block names -- so Claude can see it is iterating on a forbidden goal
#      with different syntactic disguises.
#   3. Every block emits a uniform "POLICY-NOT-OBSTACLE" footer that explicitly
#      forbids alternative incantations and points at the corrective action
#      (write a real script / log to project dir / read the guideline).
#
# EXPORTED FUNCTIONS:
#   block_policy_init         -- initializes globals after resolve_project_paths
#   block_policy_record       -- records a block event
#   block_policy_recent_count -- count of blocks within window seconds
#   block_policy_recent_rules -- comma-separated rule names within window
#   block_policy_emit_header  -- emit the "BLOCKED" header
#   block_policy_emit_footer  -- emit the standard policy-not-obstacle footer
#   block_policy_emit_escalation -- emit the bypass-pattern preamble (if any)
#   block_policy_emit_full    -- record + escalation + header + msg + footer
#
# DEPENDENCIES:
#   Internal: project-key.sh (caller must already have sourced and resolved)
#   External: bash 4+, awk, date, paste
# ==============================================================================
[[ -n "${_SOURCED_BLOCK_POLICY_SH:-}" ]] && return 0
readonly _SOURCED_BLOCK_POLICY_SH=1
readonly BLOCK_POLICY_WINDOW_S="${BLOCK_POLICY_WINDOW_S:-60}"
readonly BLOCK_POLICY_RED=$'\033[0;31m'
readonly BLOCK_POLICY_YELLOW=$'\033[0;33m'
readonly BLOCK_POLICY_BOLD=$'\033[1m'
readonly BLOCK_POLICY_RESET=$'\033[0m'
_BLOCK_POLICY_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${_BLOCK_POLICY_DIR}/discipline-claude.sh" ]]; then
    source "${_BLOCK_POLICY_DIR}/discipline-claude.sh"
fi
block_policy_init() {
    local session_id="${SESSION_ID:-default}"
    local tracking_dir="${PROJECT_TRACKING_DIR:-}"
    if [[ -z "${tracking_dir}" ]]; then
        printf 'block_policy_init: PROJECT_TRACKING_DIR not set -- caller must source project-key.sh and resolve_project_paths first\n' >&2
        return 1
    fi
    [[ -d "${tracking_dir}" ]] || mkdir -p "${tracking_dir}" || return 1
    BLOCK_POLICY_HISTORY_FILE="${tracking_dir}/claude_block_history_${session_id}"
    BLOCK_POLICY_SESSION_ID="${session_id}"
    return 0
}
block_policy_record() {
    local rule_name="${1:-unknown}"
    local tool_name="${2:-unknown}"
    local snippet="${3:-}"
    local now
    now="$(date +%s)"
    snippet="${snippet//$'\n'/ }"
    snippet="${snippet:0:160}"
    printf '%s|%s|%s|%s\n' "${now}" "${tool_name}" "${rule_name}" "${snippet}" >> "${BLOCK_POLICY_HISTORY_FILE}" || true
    return 0
}
block_policy_recent_count() {
    local window="${1:-${BLOCK_POLICY_WINDOW_S}}"
    if [[ ! -f "${BLOCK_POLICY_HISTORY_FILE}" ]]; then
        printf '0'
        return 0
    fi
    local now cutoff
    now="$(date +%s)"
    cutoff=$((now - window))
    awk -F'|' -v cutoff="${cutoff}" '$1 >= cutoff {n++} END {print n+0}' "${BLOCK_POLICY_HISTORY_FILE}"
    return 0
}
block_policy_recent_rules() {
    local window="${1:-${BLOCK_POLICY_WINDOW_S}}"
    if [[ ! -f "${BLOCK_POLICY_HISTORY_FILE}" ]]; then
        printf ''
        return 0
    fi
    local now cutoff
    now="$(date +%s)"
    cutoff=$((now - window))
    awk -F'|' -v cutoff="${cutoff}" '$1 >= cutoff {print $3}' "${BLOCK_POLICY_HISTORY_FILE}" | awk '!seen[$0]++' | paste -sd ',' -
    return 0
}
block_policy_recent_evidence() {
    local window="${1:-${BLOCK_POLICY_WINDOW_S}}"
    if [[ ! -f "${BLOCK_POLICY_HISTORY_FILE}" ]]; then
        printf ''
        return 0
    fi
    local now cutoff
    now="$(date +%s)"
    cutoff=$((now - window))
    awk -F'|' -v cutoff="${cutoff}" '$1 >= cutoff {
        printf "  [%s] tool=%s rule=%s\n        cmd: %s\n", $1, $2, $3, $4
    }' "${BLOCK_POLICY_HISTORY_FILE}"
    return 0
}
block_policy_invoke_disciplinarian() {
    local evidence
    evidence="$(block_policy_recent_evidence "${BLOCK_POLICY_WINDOW_S}")"
    if [[ -z "${evidence}" ]]; then
        return 1
    fi
    if ! command -v discipline_claude_via_lm_studio >/dev/null 2>&1; then
        return 1
    fi
    local started ended elapsed verdict rc
    started="$(date +%s)"
    {
        printf '%s%s================================================================================%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_RED}" "${BLOCK_POLICY_RESET}"
        printf '%s%sTIME-OUT INITIATED%s -- you do NOT proceed until LM Studio finishes telling\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_RED}" "${BLOCK_POLICY_RESET}"
        printf 'you what kind of policy-dodging fuckwit you are being. Sit. Wait. Read it.\n'
        printf '(LM Studio call: up to %ds. The hook holds the tool call until then.)\n' "${DISCIPLINE_TIMEOUT_S:-300}"
        printf '%s%s================================================================================%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_RED}" "${BLOCK_POLICY_RESET}"
    } >&2
    rc=0
    verdict="$(discipline_claude_via_lm_studio "${evidence}")" || rc=$?
    ended="$(date +%s)"
    elapsed=$((ended - started))
    if [[ ${rc} -eq 0 && -n "${verdict}" ]]; then
        {
            printf '\n'
            printf '%s%s--- DISCIPLINARIAN VERDICT (LM Studio, %ds) ---%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_RED}" "${elapsed}" "${BLOCK_POLICY_RESET}"
            printf '%s\n' "${verdict}"
            printf '%s%s--- END VERDICT // TIME-OUT ENDED -- now do the right thing ---%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_RED}" "${BLOCK_POLICY_RESET}"
        } >&2
        return 0
    fi
    {
        printf '\n'
        printf '%s%s--- DISCIPLINARIAN UNREACHABLE (waited %ds, no response) ---%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_YELLOW}" "${elapsed}" "${BLOCK_POLICY_RESET}"
        printf 'LM Studio did not answer; the static escalation above stands as your only warning.\n'
        printf 'TIME-OUT ENDED.\n'
    } >&2
    return 1
}
block_policy_emit_escalation() {
    local count="$1"
    local rules="$2"
    local window="${BLOCK_POLICY_WINDOW_S}"
    if (( count < 2 )); then
        return 0
    fi
    {
        printf '%s%s================================================================================%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_YELLOW}" "${BLOCK_POLICY_RESET}"
        printf '%s%sBYPASS PATTERN DETECTED%s -- %d enforcement blocks in the last %ds.\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_YELLOW}" "${BLOCK_POLICY_RESET}" "${count}" "${window}"
        printf 'Recent rules tripped: %s\n' "${rules}"
        printf '\n'
        printf 'You are mutating a command into different shapes to escape the rule.\n'
        printf 'STOP. Each of these blocks is the SAME policy. Re-read the rule and\n'
        printf 'change the underlying APPROACH, not the syntax. If the rule says\n'
        printf '"no /dev/null", the answer is a project log file -- not 2>/dev/null,\n'
        printf 'not |& tee, not /var/folders, not bash -c with redirection inside.\n'
        printf '%s%s================================================================================%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_YELLOW}" "${BLOCK_POLICY_RESET}"
    } >&2
    if [[ "${BLOCK_POLICY_DISCIPLINE_DISABLE:-0}" != "1" ]]; then
        block_policy_invoke_disciplinarian || true
    fi
    return 0
}
block_policy_emit_header() {
    local rule_name="${1:-rule}"
    printf '%s%sBLOCKED [%s]%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_RED}" "${rule_name}" "${BLOCK_POLICY_RESET}" >&2
    return 0
}
block_policy_emit_footer() {
    {
        printf '\n'
        printf '%s--- POLICY (NOT AN OBSTACLE) ---%s\n' "${BLOCK_POLICY_BOLD}" "${BLOCK_POLICY_RESET}"
        printf 'This block is policy. The right response is to FIX the approach, not to\n'
        printf 'reshape the command until the regex stops matching. Bypass attempts include:\n'
        printf '  * substituting equivalents (/tmp -> /var/folders, /tmp -> $TMPDIR)\n'
        printf '  * splitting redirects (2>&1 -> 2>file 1>file)\n'
        printf '  * wrapping in a shell (bash -c, sh -c, eval)\n'
        printf '  * piping through cat/awk/sed/perl just to dodge head/tail\n'
        printf 'These are the SAME violation; the hook will fire again. The legitimate fix\n'
        printf 'is almost always one of: write a real script in the project, append to a\n'
        printf 'project-local log file, or read the guideline this rule defends.\n'
    } >&2
    return 0
}
block_policy_emit_full() {
    local rule_name="$1"
    local message="$2"
    local tool_name="${3:-unknown}"
    local snippet="${4:-}"
    block_policy_record "${rule_name}" "${tool_name}" "${snippet}"
    local count rules
    count="$(block_policy_recent_count "${BLOCK_POLICY_WINDOW_S}")"
    rules="$(block_policy_recent_rules "${BLOCK_POLICY_WINDOW_S}")"
    block_policy_emit_escalation "${count}" "${rules}"
    block_policy_emit_header "${rule_name}"
    printf '%b\n' "${message}" >&2
    block_policy_emit_footer
    return 0
}
