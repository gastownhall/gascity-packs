#!/usr/bin/env bash
# Execute the polecat startup claim contract against the complete schema-v1
# action/reason matrix from Gas City's schemas/hook/result.schema.json.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PROMPT="$ROOT/gastown/agents/polecat/prompt.template.md"
AGENT_TOML="$ROOT/gastown/agents/polecat/agent.toml"
FOLLOWING_MOL="$ROOT/gastown/template-fragments/following-mol.template.md"
TMP_ROOT=$(mktemp -d)
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

count_calls() {
    local pattern=$1
    awk -v pattern="$pattern" 'index($0, pattern) == 1 { count++ } END { print count + 0 }' "$GC_CALLS"
}

extract_contract() {
    sed -n '/# BEGIN POLECAT_CLAIM_CONTRACT/,/# END POLECAT_CLAIM_CONTRACT/p' \
        "$PROMPT" >"$CONTRACT"
    [[ -s "$CONTRACT" ]] || fail "POLECAT_CLAIM_CONTRACT region not found"
    bash -n "$CONTRACT" || fail "claim contract is not valid Bash"
    [[ "$(grep -c '# BEGIN POLECAT_CLAIM_CONTRACT' "$PROMPT")" == "1" ]] ||
        fail "claim contract must appear exactly once"
}

write_stubs() {
    mkdir -p "$BIN"
    cat >"$BIN/gc" <<'SH'
#!/usr/bin/env bash
noun="${1:-}"
verb="${2:-}"
{
    printf 'CALL:%s:%s' "$noun" "$verb"
    for arg in "${@:3}"; do printf ' %s' "$arg"; done
    printf '\n'
} >>"$GC_CALLS"
case "$noun:$verb" in
    "hook:--claim")
        printf '%s' "${HOOK_JSON:-}"
        exit "${HOOK_CODE:-0}"
        ;;
    "bd:show")
        printf '%s' "${GC_STUB_SHOW_JSON:-}"
        exit "${GC_STUB_SHOW_CODE:-0}"
        ;;
    "bd:update")
        exit "${UPDATE_CODE:-0}"
        ;;
    "mail:send")
        exit 0
        ;;
    "runtime:drain-ack")
        exit 0
        ;;
esac
exit 64
SH
    cat >"$BIN/sleep" <<'SH'
#!/usr/bin/env bash
exit 0
SH
    chmod +x "$BIN/gc" "$BIN/sleep"
}

setup_case() {
    CASE_DIR=$(mktemp -d "$TMP_ROOT/case.XXXXXX")
    BIN="$CASE_DIR/bin"
    GC_CALLS="$CASE_DIR/calls"
    CONTRACT="$CASE_DIR/contract.sh"
    OUT="$CASE_DIR/out"
    : >"$GC_CALLS"
    write_stubs
    extract_contract
}

run_contract_as() {
    local identity_field=$1 identity_value=$2 hook_json=$3
    local hook_code=${4:-0} show_json=${5:-'[]'}
    local show_code=${6:-0} update_code=${7:-0} rc=0
    local beads_actor="" session_name="" session_id="" alias="" agent=""
    case "$identity_field" in
        BEADS_ACTOR) beads_actor=$identity_value ;;
        GC_SESSION_NAME) session_name=$identity_value ;;
        GC_SESSION_ID) session_id=$identity_value ;;
        GC_ALIAS) alias=$identity_value ;;
        GC_AGENT) agent=$identity_value ;;
        *) fail "unsupported identity field in test: $identity_field" ;;
    esac
    HOOK_JSON="$hook_json" HOOK_CODE="$hook_code" \
        GC_STUB_SHOW_JSON="$show_json" GC_STUB_SHOW_CODE="$show_code" \
        UPDATE_CODE="$update_code" \
        GC_CALLS="$GC_CALLS" PATH="$BIN:$PATH" \
        BEADS_ACTOR="$beads_actor" GC_SESSION_NAME="$session_name" \
        GC_SESSION_ID="$session_id" GC_ALIAS="$alias" GC_AGENT="$agent" \
        bash "$CONTRACT" >"$OUT" 2>&1 || rc=$?
    echo "$rc"
}

run_contract() {
    run_contract_as BEADS_ACTOR "rig/gastown.polecat-1" "$@"
}

drain_json() {
    jq -cn --arg reason "$1" \
        '{schema_version:"1",ok:true,command:"hook",action:"drain",
          reason:$reason,drain_acknowledged:true}'
}

work_json() {
    jq -cn --arg reason "$1" --arg assignee "${2:-rig/gastown.polecat-1}" \
        --arg route "${3:-rig/gastown.polecat}" \
        '{schema_version:"1",ok:true,command:"hook",action:"work",
          reason:$reason,bead_id:"ki-work",assignee:$assignee,
          route:$route}
         | if $route == "__omit" then del(.route) else . end'
}

show_json() {
    jq -cn --arg status "$1" --arg assignee "${2:-rig/gastown.polecat-1}" \
        '[{id:"ki-work",status:$status,assignee:$assignee,
           metadata:{"gc.routed_to":"rig/gastown.polecat"}}]'
}

assert_fail_closed_without_mutation() {
    local context=$1
    [[ "$(count_calls "CALL:mail:send")" == "1" ]] ||
        fail "$context: expected exactly one witness escalation"
    [[ "$(count_calls "CALL:bd:update")" == "0" ]] ||
        fail "$context: mutated the bead"
    [[ "$(count_calls "CALL:runtime:drain-ack")" == "0" ]] ||
        fail "$context: manually drain-acked an uncertain result"
    ! grep -q 'CLAIMED_BEAD_ID=' "$OUT" ||
        fail "$context: emitted a work receipt"
    grep -q 'CLAIM_INFRA_FAILURE' "$OUT" ||
        fail "$context: did not surface CLAIM_INFRA_FAILURE"
}

test_structural_contract() {
    setup_case
    grep -q 'gc hook --claim --drain-ack --json' "$CONTRACT" ||
        fail "claim must request transactional drain acknowledgement"
    ! grep -q 'gc runtime drain-ack' "$CONTRACT" ||
        fail "contract must not manually acknowledge a structured drain"
    ! grep -q -- '--status=open --assignee=""' "$CONTRACT" ||
        fail "contract must not release through an unconfirmed store context"
    for reason in claimed existing_assignment ready_assignment \
                  no_work claims_errored stale_session; do
        grep -q "\"$reason\"" "$CONTRACT" ||
            fail "schema-v1 reason $reason is absent from the contract"
    done
}

test_fresh_session_enters_the_scripted_contract() {
    local nudge restart
    nudge=$(python3 -c '
import sys
import tomllib
with open(sys.argv[1], "rb") as handle:
    print(tomllib.load(handle)["nudge"])
' "$AGENT_TOML")
    [[ "$nudge" == *"Startup Protocol"* ]] ||
        fail "fresh-session nudge does not enter the Startup Protocol"
    [[ "$nudge" == *"POLECAT_CLAIM_CONTRACT"* ]] ||
        fail "fresh-session nudge does not name the complete scripted contract"
    [[ "$nudge" == *"first operational action"* ]] ||
        fail "fresh-session nudge does not make the claim contract the first operational action"
    [[ "$nudge" == *"CLAIMED_BEAD_ID"* ]] ||
        fail "fresh-session nudge does not gate continuation on a work receipt"
    [[ "$nudge" != *"gc hook --claim"* ]] ||
        fail "fresh-session nudge still invites a raw claim-hook bypass"
    [[ "$nudge" == *"formula, workspace, metadata, or source"* ]] ||
        fail "fresh-session nudge does not gate formula/workspace/source access"

    grep -qF \
        '**After the Startup Protocol prints `CLAIMED_BEAD_ID`: read your formula' \
        "$PROMPT" ||
        fail "work protocol does not place recipe reading after confirmed claim"
    grep -qF 'The scripted claim block is always the first operational action.' "$PROMPT" ||
        fail "work protocol does not make the scripted claim block first"
    ! grep -qF '**FIRST: Read your formula steps.**' "$PROMPT" ||
        fail "prompt still tells a fresh polecat to read formula steps before claiming"
    grep -qF '`{{ cmd }} prime` may reload this prompt only' "$PROMPT" ||
        fail "prime recovery is not limited to prompt restoration"
    grep -qF 'After prompt restoration, run the Startup Protocol' "$PROMPT" ||
        fail "prime/new-session recovery does not return to the startup contract"
    grep -qF '**Restart / resume:**' "$PROMPT" ||
        fail "restart guidance is missing"
    restart=$(sed -n '/^\*\*Restart \/ resume:\*\*/,/^\*\*Claim ->/p' "$PROMPT")
    [[ -n "$restart" ]] ||
        fail "could not extract restart guidance"
    grep -qF 'Do not substitute a separate convoy lookup, metadata' "$PROMPT" ||
        fail "restart guidance still permits a competing ownership path"
    grep -qF 'Only after `CLAIMED_BEAD_ID` may you re-read formula steps' "$PROMPT" ||
        fail "restart guidance does not gate formula/workspace/source access"
    ! grep -qF 'FIRST action on restart' "$PROMPT" ||
        fail "manual restart verification still competes as a first action"
    [[ "$restart" != *'CONVOY_STATUS=$(gc convoy status'* ]] ||
        fail "manual convoy resume path still bypasses the startup contract"
    ! grep -qF 'The new session re-reads formula steps' "$PROMPT" ||
        fail "context-restart guidance still reads formula steps before claiming"
    grep -qF 'your first operational action is the' "$PROMPT" ||
        fail "startup protocol does not account for prompt-only restoration"

    grep -qF 'complete `POLECAT_CLAIM_CONTRACT` as its first operational action' \
        "$FOLLOWING_MOL" ||
        fail "shared restart guidance does not route polecats through the complete claim contract"
    grep -qF 'waits for' "$FOLLOWING_MOL" &&
        grep -qF '`CLAIMED_BEAD_ID`' "$FOLLOWING_MOL" ||
        fail "shared restart guidance does not wait for a claim receipt"
    ! grep -qF 'On crash or restart, re-read your formula steps' "$FOLLOWING_MOL" ||
        fail "shared restart guidance still sends polecats to formula steps first"
}

test_all_structured_drains_are_terminal() {
    local reason marker rc
    while read -r reason marker; do
        setup_case
        rc=$(run_contract "$(drain_json "$reason")")
        [[ "$rc" == "0" ]] || fail "$reason drain exited $rc"
        grep -q "$marker" "$OUT" || fail "$reason drain omitted marker $marker"
        [[ "$(count_calls "CALL:hook:--claim --drain-ack --json")" == "1" ]] ||
            fail "$reason drain retried the hook"
        [[ "$(count_calls "CALL:bd:show")" == "0" ]] ||
            fail "$reason drain tried to read a bead"
        [[ "$(count_calls "CALL:mail:send")" == "0" ]] ||
            fail "$reason drain escalated an intentional terminal result"
        [[ "$(count_calls "CALL:runtime:drain-ack")" == "0" ]] ||
            fail "$reason drain manually acknowledged after the hook already did"
    done <<'CASES'
no_work NO_ROUTED_WORK
claims_errored CLAIM_DEFERRED
stale_session STALE_SESSION_DRAINED
CASES
}

test_complete_work_reason_status_matrix() {
    local reason status route rc
    while read -r reason status route; do
        setup_case
        rc=$(run_contract "$(work_json "$reason" "rig/gastown.polecat-1" "$route")" \
            0 "$(show_json "$status")")
        [[ "$rc" == "0" ]] || fail "$reason/$status exited $rc: $(cat "$OUT")"
        grep -q 'CLAIMED_BEAD_ID=ki-work' "$OUT" ||
            fail "$reason/$status emitted no work receipt"
        grep -q "CLAIMED_REASON=$reason" "$OUT" ||
            fail "$reason/$status emitted the wrong reason"
        [[ "$(count_calls "CALL:hook:--claim --drain-ack --json")" == "1" ]] ||
            fail "$reason/$status called the hook more than once"
        [[ "$(count_calls "CALL:bd:show")" == "1" ]] ||
            fail "$reason/$status did not confirm through one direct read"
        [[ "$(count_calls "CALL:bd:update")" == "1" ]] ||
            fail "$reason/$status did not stamp observability metadata"
        [[ "$(count_calls "CALL:mail:send")" == "0" ]] ||
            fail "$reason/$status escalated valid work"
    done <<'CASES'
claimed in_progress rig/gastown.polecat
existing_assignment in_progress __omit
ready_assignment open __omit
CASES
}

test_all_runtime_identity_fields_are_accepted() {
    local field value rc
    while read -r field value; do
        setup_case
        rc=$(run_contract_as "$field" "$value" \
            "$(work_json ready_assignment "$value" __omit)" 0 \
            "$(show_json open "$value")")
        [[ "$rc" == "0" ]] ||
            fail "$field-owned ready assignment exited $rc: $(cat "$OUT")"
        grep -q "CLAIMED_ASSIGNEE=$value" "$OUT" ||
            fail "$field-owned ready assignment was not accepted"
    done <<'CASES'
BEADS_ACTOR actor-1
GC_SESSION_NAME session-name-1
GC_SESSION_ID session-id-1
GC_ALIAS alias-1
GC_AGENT agent-1
CASES
}

test_wrong_reason_status_pairs_fail_closed() {
    local reason status rc
    while read -r reason status; do
        setup_case
        rc=$(run_contract "$(work_json "$reason")" 0 "$(show_json "$status")")
        [[ "$rc" == "1" ]] || fail "$reason/$status mismatch exited $rc"
        [[ "$(count_calls "CALL:bd:show")" == "3" ]] ||
            fail "$reason/$status mismatch did not bound direct-read retries at 3"
        assert_fail_closed_without_mutation "$reason/$status mismatch"
    done <<'CASES'
claimed open
existing_assignment open
ready_assignment in_progress
CASES
}

test_receipt_and_direct_assignee_mismatches_fail_closed() {
    local rc

    setup_case
    rc=$(run_contract "$(work_json claimed other/polecat)" 0 \
        "$(show_json in_progress other/polecat)")
    [[ "$rc" == "1" ]] || fail "foreign receipt exited $rc"
    [[ "$(count_calls "CALL:bd:show")" == "0" ]] ||
        fail "foreign receipt was trusted enough to read work"
    assert_fail_closed_without_mutation "foreign receipt"

    setup_case
    rc=$(run_contract "$(work_json claimed)" 0 \
        "$(show_json in_progress other/polecat)")
    [[ "$rc" == "1" ]] || fail "direct assignee mismatch exited $rc"
    [[ "$(count_calls "CALL:bd:show")" == "3" ]] ||
        fail "direct assignee mismatch did not bound retries at 3"
    assert_fail_closed_without_mutation "direct assignee mismatch"
}

test_hook_errors_and_malformed_results_fail_closed_once() {
    local name code payload rc
    while IFS='|' read -r name code payload; do
        setup_case
        rc=$(run_contract "$payload" "$code")
        [[ "$rc" == "1" ]] || fail "$name exited $rc"
        [[ "$(count_calls "CALL:hook:--claim --drain-ack --json")" == "1" ]] ||
            fail "$name retried the hook"
        [[ "$(count_calls "CALL:bd:show")" == "0" ]] ||
            fail "$name read a bead without a valid work receipt"
        assert_fail_closed_without_mutation "$name"
    done <<'CASES'
nonzero|1|
empty|0|
not-json|0|not-json
empty-object|0|{}
wrong-schema|0|{"schema_version":1,"ok":true,"command":"hook","action":"drain","reason":"no_work","drain_acknowledged":true}
unknown-reason|0|{"schema_version":"1","ok":true,"command":"hook","action":"drain","reason":"future","drain_acknowledged":true}
unacknowledged-drain|0|{"schema_version":"1","ok":true,"command":"hook","action":"drain","reason":"no_work","drain_acknowledged":false}
wrong-pair|0|{"schema_version":"1","ok":true,"command":"hook","action":"work","reason":"no_work","bead_id":"ki-work","assignee":"rig/gastown.polecat-1"}
CASES
}

test_unreadable_direct_projection_is_never_released() {
    setup_case
    local rc
    rc=$(run_contract "$(work_json claimed)" 0 '[]' 1)
    [[ "$rc" == "1" ]] || fail "unreadable direct projection exited $rc"
    [[ "$(count_calls "CALL:bd:show")" == "3" ]] ||
        fail "unreadable projection did not retry exactly 3 times"
    assert_fail_closed_without_mutation "unreadable direct projection"
}

test_observability_stamp_is_best_effort() {
    setup_case
    local rc
    rc=$(run_contract "$(work_json existing_assignment)" 0 \
        "$(show_json in_progress)" 0 1)
    [[ "$rc" == "0" ]] || fail "metadata stamp failure invalidated confirmed work"
    grep -q 'WARN metadata stamp failed' "$OUT" ||
        fail "metadata stamp failure was not reported"
    grep -q 'CLAIMED_BEAD_ID=ki-work' "$OUT" ||
        fail "confirmed work was hidden after metadata stamp failure"
    [[ "$(count_calls "CALL:mail:send")" == "0" ]] ||
        fail "best-effort observability failure escalated the claim"
}

test_structural_contract
test_fresh_session_enters_the_scripted_contract
test_all_structured_drains_are_terminal
test_complete_work_reason_status_matrix
test_all_runtime_identity_fields_are_accepted
test_wrong_reason_status_pairs_fail_closed
test_receipt_and_direct_assignee_mismatches_fail_closed
test_hook_errors_and_malformed_results_fail_closed_once
test_unreadable_direct_projection_is_never_released
test_observability_stamp_is_best_effort

echo "polecat claim contract tests passed"
