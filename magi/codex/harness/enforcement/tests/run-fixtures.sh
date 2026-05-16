#!/usr/bin/env bash
set -Eeuo pipefail

readonly HOOK="${HOME}/.codex/enforcement/bin/codex-hook.sh"
readonly CWD="${HOME}/.codex/enforcement"
readonly STOP_TRANSCRIPT="${HOME}/.codex/enforcement/tests/fixtures/stop-transcript.jsonl"
readonly TEST_TMP_DIR="${HOME}/.codex/enforcement/state/test-tmp"
mkdir -p "${TEST_TMP_DIR}"

make_temp_file() {
    local path="${TEST_TMP_DIR}/fixture.$$.$RANDOM"
    : > "${path}"
    printf '%s' "${path}"
}

run_expect() {
    local name="$1"
    local event="$2"
    local expected="$3"
    local input="$4"
    local contains="${5:-}"
    local stdout_file stderr_file rc
    stdout_file="$(make_temp_file)"
    stderr_file="$(make_temp_file)"
    set +e
    printf '%s' "${input}" | "${HOOK}" "${event}" > "${stdout_file}" 2> "${stderr_file}"
    rc=$?
    set -e
    if [[ "${rc}" != "${expected}" ]]; then
        printf 'FAIL %s: expected rc=%s got rc=%s\n' "${name}" "${expected}" "${rc}" >&2
        printf 'stdout:\n' >&2
        sed -n '1,80p' "${stdout_file}" >&2
        printf 'stderr:\n' >&2
        sed -n '1,80p' "${stderr_file}" >&2
        rm -f "${stdout_file}" "${stderr_file}"
        return 1
    fi
    if [[ -n "${contains}" ]] && ! grep -qF "${contains}" "${stdout_file}"; then
        printf 'FAIL %s: stdout did not contain %s\n' "${name}" "${contains}" >&2
        printf 'stdout:\n' >&2
        sed -n '1,80p' "${stdout_file}" >&2
        printf 'stderr:\n' >&2
        sed -n '1,80p' "${stderr_file}" >&2
        rm -f "${stdout_file}" "${stderr_file}"
        return 1
    fi
    printf 'PASS %s\n' "${name}"
    rm -f "${stdout_file}" "${stderr_file}"
}

run_stop_unreachable_expect_block() {
    local stdout_file stderr_file rc input
    stdout_file="$(make_temp_file)"
    stderr_file="$(make_temp_file)"
    input="$(jq -n --arg cwd "${CWD}" --arg transcript "${STOP_TRANSCRIPT}" --arg session_id "fixture-stop-unreachable-$$" '{session_id:$session_id, cwd:$cwd, hook_event_name:"Stop", transcript_path:$transcript}')"
    set +e
    printf '%s' "${input}" | LM_STUDIO_HOST=127.0.0.1 LM_STUDIO_PORT=9 CODEX_MAX_QUALITY_ATTEMPTS=3 "${HOOK}" "Stop" > "${stdout_file}" 2> "${stderr_file}"
    rc=$?
    set -e
    if [[ "${rc}" != "0" ]] || ! grep -qF '"decision": "block"' "${stdout_file}"; then
        printf 'FAIL stop blocks when verifier unreachable: expected rc=0 and decision=block, got rc=%s\n' "${rc}" >&2
        printf 'stdout:\n' >&2
        sed -n '1,80p' "${stdout_file}" >&2
        printf 'stderr:\n' >&2
        sed -n '1,80p' "${stderr_file}" >&2
        rm -f "${stdout_file}" "${stderr_file}"
        return 1
    fi
    printf 'PASS stop blocks when verifier unreachable\n'
    rm -f "${stdout_file}" "${stderr_file}"
}

run_stop_skip_expect_continue() {
    local stdout_file stderr_file rc input
    stdout_file="$(make_temp_file)"
    stderr_file="$(make_temp_file)"
    input="$(jq -n --arg cwd "${CWD}" '{session_id:"fixture-stop-skip", cwd:$cwd, hook_event_name:"Stop", last_assistant_message:"done"}')"
    set +e
    printf '%s' "${input}" | CODEX_SKIP_QUALITY_CHECK=1 "${HOOK}" "Stop" > "${stdout_file}" 2> "${stderr_file}"
    rc=$?
    set -e
    if [[ "${rc}" != "0" ]] || ! grep -qF '"continue": true' "${stdout_file}"; then
        printf 'FAIL stop skip emits json: expected rc=0 and continue=true, got rc=%s\n' "${rc}" >&2
        printf 'stdout:\n' >&2
        sed -n '1,80p' "${stdout_file}" >&2
        printf 'stderr:\n' >&2
        sed -n '1,80p' "${stderr_file}" >&2
        rm -f "${stdout_file}" "${stderr_file}"
        return 1
    fi
    printf 'PASS stop skip emits json\n'
    rm -f "${stdout_file}" "${stderr_file}"
}

run_expect "blocks python -c" "PreToolUse" 2 "$(jq -n --arg cwd "${CWD}" '{session_id:"fixture", cwd:$cwd, hook_event_name:"PreToolUse", tool_name:"Bash", tool_input:{command:"python -c \"print(1)\""}}')"

run_expect "tracks guideline read" "PreToolUse" 0 "$(jq -n --arg cwd "${CWD}" --arg guideline "${HOME}/.codex/enforcement/guidelines/guideline_documents/xml/bash_guidelines.xml" '{session_id:"fixture", cwd:$cwd, hook_event_name:"PreToolUse", tool_name:"Bash", tool_input:{command:("sed -n '\''1,120p'\'' " + $guideline)}}')"

run_expect "tracks python guideline read" "PreToolUse" 0 "$(jq -n --arg cwd "${CWD}" --arg guideline "${HOME}/.codex/enforcement/guidelines/guideline_documents/xml/python_guidelines.xml" '{session_id:"fixture-python", cwd:$cwd, hook_event_name:"PreToolUse", tool_name:"Bash", tool_input:{command:("sed -n '\''1,120p'\'' " + $guideline)}}')"

run_expect "blocks extensionless add" "PreToolUse" 2 "$(jq -n --arg cwd "${CWD}" --arg patch '*** Begin Patch
*** Add File: runbook
+hello
*** End Patch
' '{session_id:"fixture", cwd:$cwd, hook_event_name:"PreToolUse", tool_name:"apply_patch", tool_input:{command:$patch}}')"

run_expect "blocks forbidden patch content" "PreToolUse" 2 "$(jq -n --arg cwd "${CWD}" --arg patch '*** Begin Patch
*** Add File: test.py
+from typing import Any
+x: Any = 1
*** End Patch
' '{session_id:"fixture-python", cwd:$cwd, hook_event_name:"PreToolUse", tool_name:"apply_patch", tool_input:{command:$patch}}')"

run_stop_skip_expect_continue

run_stop_unreachable_expect_block
