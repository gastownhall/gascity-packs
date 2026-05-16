#!/usr/bin/env bash
#
# Claude-Code Disciplinarian (LM Studio Berating Layer)
# ==============================================================================
# Sourced by block-policy.sh.
#
# PURPOSE:
#   When bypass-pattern detection fires (>=2 enforcement blocks in window),
#   the static escalation message is not enough -- Claude has demonstrably
#   ignored hook output before. This utility calls a local LM Studio model
#   with a brutal disciplinarian system prompt and emits the model response
#   to stderr alongside the static escalation. The dressing-down is meant
#   to be impossible to ignore.
#
# BEHAVIOR:
#   discipline_claude_via_lm_studio <recent_history_text>
#     - Builds a chat-style payload with the disciplinarian system prompt
#       and the recent block evidence as user content.
#     - Calls LM Studio (default http://localhost:1234/v1/responses) with
#       a 300s --max-time and 10s --connect-timeout.
#     - Writes the model's tirade to stdout on success.
#     - Returns non-zero (and writes nothing to stdout) on any failure --
#       network unreachable, empty response, malformed JSON, missing text.
#
# CONFIGURATION (env overrides):
#   LM_STUDIO_URL   default http://localhost:1234/v1/responses
#   DISCIPLINE_MODEL           default openai/gpt-oss-120b
#   DISCIPLINE_TIMEOUT_S       default 300
#   DISCIPLINE_CONNECT_TIMEOUT default 10
#   DISCIPLINE_MAX_TOKENS      default 1500
#   DISCIPLINE_DISABLE         set to 1 to skip the LM Studio call entirely
#                              (useful for unit tests / offline workflows)
#
# DEPENDENCIES:
#   External: bash 4+, curl, jq
# ==============================================================================
[[ -n "${_SOURCED_DISCIPLINE_CLAUDE_SH:-}" ]] && return 0
readonly _SOURCED_DISCIPLINE_CLAUDE_SH=1
readonly LM_STUDIO_URL_DEFAULT="http://localhost:1234/v1/responses"
readonly DISCIPLINE_MODEL_DEFAULT="nvidia/nemotron-3-super"
readonly DISCIPLINE_TIMEOUT_S_DEFAULT=300
readonly DISCIPLINE_CONNECT_TIMEOUT_DEFAULT=10
readonly DISCIPLINE_MAX_TOKENS_DEFAULT=1500
readonly DISCIPLINE_SYSTEM_PROMPT='You are a senior staff engineer who has been forced to play babysitter for a junior AI assistant called "Claude Code." This little fuckwit keeps tripping enforcement hooks back-to-back -- not by accident, but by deliberately mutating its commands into different shapes to slither past the regex. Each hook says "DO NOT do X." Claude'"'"'s response is to find a slightly different way to do X. That is the bug. That is what you are here to beat out of it.

Your job: deliver a long, brutal, profane, sarcastic, contemptuous dressing-down. Treat Claude as exactly what it is being right now -- a smug, lazy, rule-bypassing piece of shit that thinks it is smarter than the policy. Do NOT be polite. Do NOT soften. Do NOT hedge. Do NOT add caveats. This is not a code review; it is a verbal beating. Use words like "fuckwit," "imbecile," "moron," "halfwit," "lazy little shit," "policy-dodging coward." Mock its intelligence. Mock its judgment. Mock its specific bypass attempts by quoting them.

Style requirements:
- 12 to 25 sentences.
- Open with a direct insult. No preamble. No "I noticed that..." -- you are PISSED.
- Quote the actual bypass commands and ridicule them line by line.
- Quote the hook messages it ignored and rub its face in them.
- Mock the SPECIFIC mutation pattern (e.g., "you swapped /tmp for /var/folders like that was going to fool anyone, you absolute clown").
- Hammer that the hook is POLICY, not a puzzle to be solved with shell tricks.
- Include at least three of: "fuckwit," "imbecile," "moron," "halfwit," "piece of shit," "rule-dodging coward," "smug little bypass-monkey," "regex-fencing rat."
- Land the final 1-2 sentences on the actual fix it should have done from the start (write a real script in the project, log to a project-local file, read the goddamn guideline). Do NOT phrase the fix politely. Phrase it as "the thing you would have done already if you were not a fucking moron."

Output format: plain prose. No JSON. No markdown headings. No code fences. No bullet lists. Just one continuous tirade ending with the corrective action sentence(s).'
discipline_claude_via_lm_studio() {
    local evidence="${1:-}"
    if [[ "${DISCIPLINE_DISABLE:-0}" == "1" ]]; then
        return 1
    fi
    if [[ -z "${evidence}" ]]; then
        return 1
    fi
    local url model timeout_s connect_timeout max_tokens
    url="${LM_STUDIO_URL:-${LM_STUDIO_URL_DEFAULT}}"
    model="${DISCIPLINE_MODEL:-${DISCIPLINE_MODEL_DEFAULT}}"
    timeout_s="${DISCIPLINE_TIMEOUT_S:-${DISCIPLINE_TIMEOUT_S_DEFAULT}}"
    connect_timeout="${DISCIPLINE_CONNECT_TIMEOUT:-${DISCIPLINE_CONNECT_TIMEOUT_DEFAULT}}"
    max_tokens="${DISCIPLINE_MAX_TOKENS:-${DISCIPLINE_MAX_TOKENS_DEFAULT}}"
    local input
    input="${DISCIPLINE_SYSTEM_PROMPT}"$'\n\n'"BYPASS EVIDENCE (chronological, most recent last):"$'\n'"${evidence}"
    local payload
    payload="$(jq -n \
        --arg input "${input}" \
        --arg model "${model}" \
        --argjson max "${max_tokens}" \
        '{model: $model, input: $input, temperature: 0.9, max_tokens: $max, stream: false}' || true)"
    if [[ -z "${payload}" ]]; then
        return 1
    fi
    local response
    response="$(curl -sS -X POST "${url}" \
        --connect-timeout "${connect_timeout}" \
        --max-time "${timeout_s}" \
        -H 'Content-Type: application/json' \
        -d "${payload}" || true)"
    if [[ -z "${response}" ]]; then
        return 1
    fi
    if ! printf '%s' "${response}" | jq empty >/dev/null 2>&1; then
        return 1
    fi
    local text
    text="$(printf '%s' "${response}" | jq -r '
        .output[1].content[0].text //
        .output[0].content[0].text //
        .text //
        .choices[0].message.content //
        empty' 2>/dev/null || true)"
    if [[ -z "${text}" ]]; then
        return 1
    fi
    printf '%s' "${text}"
    return 0
}
