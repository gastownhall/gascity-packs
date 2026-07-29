#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/polecat-step/run.sh"
TEST_TMP=$(mktemp -d)
trap 'rm -rf "$TEST_TMP"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

mkdir -p "$TEST_TMP/bin"
cat >"$TEST_TMP/bin/gc" <<'SH'
#!/usr/bin/env bash
set -u

printf 'gc ' >>"$FAKE_GC_LOG"
printf '%q ' "$@" >>"$FAKE_GC_LOG"
printf '\n' >>"$FAKE_GC_LOG"

write_db() {
    mv "$FAKE_DB.tmp" "$FAKE_DB"
}

if [[ "${1:-}" == "bd" && "${2:-}" == "list" ]]; then
    assignee=""
    status=""
    shift 2
    while (($#)); do
        case "$1" in
            --assignee)
                assignee=$2
                shift 2
                ;;
            --status=*)
                status=${1#*=}
                shift
                ;;
            --limit=0|--json)
                shift
                ;;
            *)
                touch "$FAKE_STATE/unknown-call"
                exit 82
                ;;
        esac
    done
    if [[ "${LIST_MODE:-ok}" == "fail" ||
          (-n "${FAIL_LIST_ASSIGNEE:-}" &&
           "$assignee" == "$FAIL_LIST_ASSIGNEE") ]]; then
        exit 81
    fi
    if [[ "${LIST_MODE:-ok}" == "malformed" ]]; then
        printf '{"not":"an array"}\n'
        exit 0
    fi
    if [[ -n "${LIST_ROW_KIND:-}" &&
          "$status" == "${LIST_ROW_STATUS:-}" ]]; then
        case "$LIST_ROW_KIND" in
            wrong-assignee)
                jq --arg status "$status" \
                    '[.beads["step-good"],
                      (.beads["step-1"] |
                       .status = $status | .assignee = "foreign-actor")]' \
                    "$FAKE_DB"
                ;;
            wrong-status)
                jq --arg assignee "$assignee" --arg status "$status" \
                    '[.beads["step-good"],
                      (.beads["step-1"] |
                       .assignee = $assignee |
                       .status = (if $status == "closed"
                                  then "in_progress" else "closed" end))]' \
                    "$FAKE_DB"
                ;;
            malformed-row)
                jq '[.beads["step-good"], null]' "$FAKE_DB"
                ;;
            *)
                touch "$FAKE_STATE/unknown-call"
                exit 88
                ;;
        esac
        exit 0
    fi
    if [[ -n "${DUPLICATE_LIST_FOR_ASSIGNEE:-}" &&
          "$assignee" == "$DUPLICATE_LIST_FOR_ASSIGNEE" &&
          "$status" == "in_progress" ]]; then
        jq --arg assignee "$assignee" \
            '[.beads["step-1"] | .assignee = $assignee]' "$FAKE_DB"
        exit 0
    fi
    jq --arg assignee "$assignee" --arg status "$status" \
        '[.beads[] | select(.assignee == $assignee and .status == $status)]' \
        "$FAKE_DB"
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "show" ]]; then
    id=${3:-}
    if [[ -n "${FAIL_SHOW_ID:-}" && "$id" == "$FAIL_SHOW_ID" ]]; then
        exit 83
    fi
    jq -e --arg id "$id" '[.beads[$id]] | select(.[0] != null)' "$FAKE_DB"
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "update" ]]; then
    id=${3:-}
    touch "$FAKE_STATE/update-called"
    if [[ "${UPDATE_MODE:-ok}" == "fail" ]]; then
        exit 84
    fi
    if [[ "${UPDATE_MODE:-ok}" == "noop" ]]; then
        exit 0
    fi
    jq -e --arg id "$id" '.beads[$id] != null' "$FAKE_DB" >/dev/null ||
        exit 85
    shift 3
    while (($#)); do
        case "$1" in
            --set-metadata)
                key=${2%%=*}
                value=${2#*=}
                jq --arg id "$id" --arg key "$key" --arg value "$value" \
                    '.beads[$id].metadata[$key] = $value' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            --status=*)
                value=${1#*=}
                jq --arg id "$id" --arg value "$value" \
                    '.beads[$id].status = $value' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift
                ;;
            --append-notes)
                value=$2
                jq --arg id "$id" --arg value "$value" \
                    '.beads[$id].notes =
                      ((.beads[$id].notes // "") +
                       (if (.beads[$id].notes // "") == ""
                        then "" else "\n" end) + $value)' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            *)
                touch "$FAKE_STATE/unknown-call"
                exit 86
                ;;
        esac
    done
    exit 0
fi

touch "$FAKE_STATE/unknown-call"
exit 87
SH
chmod +x "$TEST_TMP/bin/gc"

CASE_DIR=""
DB=""
STATE=""
OUTPUT=""
RUN_RC=0

new_case() {
    local name=$1
    CASE_DIR="$TEST_TMP/$name"
    DB="$CASE_DIR/db.json"
    STATE="$CASE_DIR/state"
    OUTPUT="$CASE_DIR/output"
    mkdir -p "$STATE"
    : >"$STATE/gc.log"
    jq -n '{
      beads: {
        "step-1": {
          id: "step-1",
          status: "in_progress",
          assignee: "actor-1",
          metadata: {
            "gc.step_ref": "mol-polecat-work.load-context",
            "gc.root_bead_id": "root-1"
          }
        },
        "root-1": {
          id: "root-1",
          status: "in_progress",
          assignee: "",
          metadata: {
            "gc.kind": "workflow",
            "gc.formula_contract": "graph.v2",
            "gc.input_convoy_id": "convoy-1"
          }
        }
      }
    }' >"$DB"
}

invoke() {
    PATH="$TEST_TMP/bin:$PATH" \
    GC_BIN="$TEST_TMP/bin/gc" \
    BEADS_ACTOR="${TEST_BEADS_ACTOR-actor-1}" \
    GC_SESSION_NAME="${TEST_SESSION_NAME-}" \
    GC_SESSION_ID="${TEST_SESSION_ID-}" \
    GC_ALIAS="${TEST_ALIAS-}" \
    GC_AGENT="${TEST_GC_AGENT-}" \
    FAKE_DB="$DB" \
    FAKE_STATE="$STATE" \
    FAKE_GC_LOG="$STATE/gc.log" \
    LIST_MODE="${LIST_MODE:-ok}" \
    UPDATE_MODE="${UPDATE_MODE:-ok}" \
    FAIL_SHOW_ID="${FAIL_SHOW_ID:-}" \
    FAIL_LIST_ASSIGNEE="${FAIL_LIST_ASSIGNEE:-}" \
    DUPLICATE_LIST_FOR_ASSIGNEE="${DUPLICATE_LIST_FOR_ASSIGNEE:-}" \
    LIST_ROW_KIND="${LIST_ROW_KIND:-}" \
    LIST_ROW_STATUS="${LIST_ROW_STATUS:-}" \
        "$COMMAND" complete \
        --convoy "${TEST_CONVOY:-convoy-1}" \
        --step-ref "${TEST_STEP_REF:-mol-polecat-work.load-context}"
}

run_command() {
    set +e
    invoke >"$OUTPUT" 2>&1
    RUN_RC=$?
    set -e
}

assert_no_unknown_call() {
    [[ ! -e "$STATE/unknown-call" ]] ||
        fail "command used an unsupported or non-gc-bd operation"
}

assert_unadvanced() {
    [[ "$(jq -r '.beads["step-1"].status' "$DB")" == "in_progress" ]] ||
        fail "failure case advanced the workflow step"
    [[ "$(jq -r '.beads["step-1"].metadata["gc.outcome"] // ""' "$DB")" == "" ]] ||
        fail "failure case wrote a workflow outcome"
}

new_case happy
run_command
[[ "$RUN_RC" -eq 0 ]] || fail "happy path failed: $(<"$OUTPUT")"
[[ "$(jq -r '.beads["step-1"].status' "$DB")" == "closed" ]] ||
    fail "happy path did not close the exact step"
[[ "$(jq -r '.beads["step-1"].metadata["gc.outcome"]' "$DB")" == "pass" ]] ||
    fail "happy path did not record gc.outcome=pass"
grep -F 'POLECAT_STEP_COMPLETE step=step-1' "$OUTPUT" >/dev/null &&
    grep -F 'replay=false' "$OUTPUT" >/dev/null ||
    fail "happy path did not report verified completion"
grep -F 'gc bd update step-1' "$STATE/gc.log" >/dev/null ||
    fail "happy path did not use the invoking gc bd adapter"
assert_no_unknown_call

run_command
[[ "$RUN_RC" -eq 0 ]] || fail "idempotent replay failed: $(<"$OUTPUT")"
grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "idempotent replay was not recognized"
[[ "$(grep -cF 'gc bd update step-1' "$STATE/gc.log")" -eq 1 ]] ||
    fail "idempotent replay repeated the durable update"
assert_no_unknown_call

new_case correct-present-formula-name
jq '.beads["root-1"].metadata["gc.formula_name"] = "mol-polecat-work"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 0 ]] ||
    fail "correct present formula name was rejected: $(<"$OUTPUT")"
[[ "$(jq -r '.beads["step-1"].status' "$DB")" == "closed" ]] &&
    [[ "$(jq -r '.beads["step-1"].metadata["gc.outcome"]' "$DB")" == "pass" ]] ||
    fail "correct present formula name did not complete the step"
assert_no_unknown_call

new_case alternate-current-identity
TEST_BEADS_ACTOR=""
TEST_ALIAS=wrong-template-identity
TEST_GC_AGENT=actor-1
run_command
unset TEST_BEADS_ACTOR TEST_ALIAS TEST_GC_AGENT
[[ "$RUN_RC" -eq 0 ]] ||
    fail "alternate current identity lookup failed: $(<"$OUTPUT")"
grep -F 'gc bd list --assignee actor-1 ' "$STATE/gc.log" >/dev/null ||
    fail "alternate GC_AGENT identity was not queried"
grep -F 'gc bd list --assignee wrong-template-identity ' \
    "$STATE/gc.log" >/dev/null ||
    fail "the bounded identity set did not include GC_ALIAS"
[[ "$(jq -r '.beads["step-1"].assignee' "$DB")" == "actor-1" ]] ||
    fail "completion did not preserve the selected row's exact assignee"
assert_no_unknown_call

new_case duplicate-identities-are-deduplicated
TEST_BEADS_ACTOR=actor-1
TEST_SESSION_NAME=actor-1
TEST_SESSION_ID=actor-1
TEST_ALIAS=actor-1
TEST_GC_AGENT=actor-1
run_command
unset TEST_BEADS_ACTOR TEST_SESSION_NAME TEST_SESSION_ID TEST_ALIAS TEST_GC_AGENT
[[ "$RUN_RC" -eq 0 ]] ||
    fail "deduplicated identity lookup failed: $(<"$OUTPUT")"
[[ "$(grep -cF \
    'gc bd list --assignee actor-1 --status=in_progress ' \
    "$STATE/gc.log")" -eq 1 ]] ||
    fail "the same current identity was queried more than once"
assert_no_unknown_call

new_case ambiguous-across-current-identities
jq '.beads["step-2"] = {
      id: "step-2", status: "in_progress", assignee: "actor-2",
      metadata: {
        "gc.step_ref": "mol-polecat-work.load-context",
        "gc.root_bead_id": "root-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
TEST_SESSION_NAME=actor-2
run_command
unset TEST_SESSION_NAME
[[ "$RUN_RC" -eq 75 ]] ||
    fail "cross-identity ambiguity returned $RUN_RC instead of 75"
assert_unadvanced
[[ "$(jq -r '.beads["step-2"].status' "$DB")" == "in_progress" ]] ||
    fail "cross-identity ambiguity advanced the alternate step"
[[ ! -e "$STATE/update-called" ]] ||
    fail "cross-identity ambiguity attempted an update"
assert_no_unknown_call

new_case duplicate-id-across-current-identities
TEST_SESSION_NAME=actor-2
DUPLICATE_LIST_FOR_ASSIGNEE=actor-2
run_command
unset TEST_SESSION_NAME DUPLICATE_LIST_FOR_ASSIGNEE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "duplicate aggregate id returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "duplicate aggregate id attempted an update"
assert_no_unknown_call

new_case one-current-identity-query-fails
TEST_SESSION_NAME=actor-2
FAIL_LIST_ASSIGNEE=actor-2
run_command
unset TEST_SESSION_NAME FAIL_LIST_ASSIGNEE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "one failed identity query returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "one failed identity query attempted an update"
assert_no_unknown_call

new_case ambiguous-live
jq '.beads["step-2"] = {
      id: "step-2", status: "in_progress", assignee: "actor-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.load-context",
        "gc.root_bead_id": "root-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "ambiguous live steps returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "ambiguous live steps attempted an update"
assert_no_unknown_call

new_case wrong-root-convoy
jq '.beads["root-1"].metadata["gc.input_convoy_id"] = "other-convoy"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong root convoy returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "wrong root convoy attempted an update"
assert_no_unknown_call

new_case wrong-root-contract
jq '.beads["root-1"].metadata["gc.formula_contract"] = "graph.v1"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong root contract returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "wrong root contract attempted an update"
assert_no_unknown_call

new_case terminal-root-live
jq '.beads["root-1"].status = "closed" |
    .beads["root-1"].metadata["gc.outcome"] = "fail"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "terminal root with live step returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "terminal root with live step attempted an update"
assert_no_unknown_call

new_case wrong-present-formula-name
jq '.beads["root-1"].metadata["gc.formula_name"] = "other-workflow"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong present formula name returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "wrong present formula name attempted an update"
assert_no_unknown_call

new_case preexisting-live-fail
jq '.beads["step-1"].metadata["gc.outcome"] = "fail"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "preexisting live fail outcome returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["step-1"].status' "$DB")" == "in_progress" ]] &&
    [[ "$(jq -r '.beads["step-1"].metadata["gc.outcome"]' "$DB")" == "fail" ]] ||
    fail "preexisting live fail outcome was overwritten"
[[ ! -e "$STATE/update-called" ]] ||
    fail "preexisting live fail outcome attempted an update"
assert_no_unknown_call

new_case preexisting-live-pass
jq '.beads["step-1"].metadata["gc.outcome"] = "pass"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "preexisting live pass outcome returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["step-1"].status' "$DB")" == "in_progress" ]] &&
    [[ "$(jq -r '.beads["step-1"].metadata["gc.outcome"]' "$DB")" == "pass" ]] ||
    fail "preexisting live pass outcome was mutated"
[[ ! -e "$STATE/update-called" ]] ||
    fail "preexisting live pass outcome attempted an update"
assert_no_unknown_call

new_case preexisting-live-boolean
jq '.beads["step-1"].metadata["gc.outcome"] = false' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "preexisting boolean outcome returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["step-1"].status' "$DB")" == "in_progress" ]] &&
    [[ "$(jq -r '.beads["step-1"].metadata["gc.outcome"] | type' "$DB")" == "boolean" ]] ||
    fail "preexisting boolean outcome was mutated"
[[ ! -e "$STATE/update-called" ]] ||
    fail "preexisting boolean outcome attempted an update"
assert_no_unknown_call

new_case malformed-list
LIST_MODE=malformed
run_command
unset LIST_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "malformed list returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "malformed list attempted an update"
assert_no_unknown_call

test_list_row_integrity() {
    local phase=$1 kind=$2 requested_status=in_progress before

    new_case "list-row-${phase}-${kind}"
    if [[ "$phase" == "replay" ]]; then
        requested_status=closed
        jq '.beads["step-1"].status = "closed" |
            .beads["step-1"].metadata["gc.outcome"] = "pass" |
            .beads["step-good"] = {
              id: "step-good", status: "closed", assignee: "actor-1",
              metadata: {
                "gc.step_ref": "mol-polecat-work.load-context",
                "gc.root_bead_id": "root-1",
                "gc.outcome": "pass"
              }
            }' \
            "$DB" >"$DB.tmp"
        mv "$DB.tmp" "$DB"
    else
        jq '.beads["step-good"] = {
              id: "step-good", status: "in_progress", assignee: "actor-1",
              metadata: {
                "gc.step_ref": "mol-polecat-work.load-context",
                "gc.root_bead_id": "root-1"
              }
            }' "$DB" >"$DB.tmp"
        mv "$DB.tmp" "$DB"
    fi
    before=$(jq -cS . "$DB")

    LIST_ROW_KIND=$kind
    LIST_ROW_STATUS=$requested_status
    run_command
    unset LIST_ROW_KIND LIST_ROW_STATUS

    [[ "$RUN_RC" -eq 75 ]] ||
        fail "$phase $kind list row returned $RUN_RC instead of 75"
    [[ "$(jq -cS . "$DB")" == "$before" ]] ||
        fail "$phase $kind list row mutated workflow state"
    [[ ! -e "$STATE/update-called" ]] ||
        fail "$phase $kind list row attempted an update"
    assert_no_unknown_call
}

for list_phase in live replay; do
    for list_row_kind in wrong-assignee wrong-status malformed-row; do
        test_list_row_integrity "$list_phase" "$list_row_kind"
    done
done

new_case update-failure
UPDATE_MODE=fail
run_command
unset UPDATE_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "failed durable update returned $RUN_RC instead of 75"
assert_unadvanced
assert_no_unknown_call

new_case readback-failure
UPDATE_MODE=noop
run_command
unset UPDATE_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "unverified durable update returned $RUN_RC instead of 75"
assert_unadvanced
assert_no_unknown_call

new_case closed-fail-is-not-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "fail"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "closed/fail state returned $RUN_RC instead of 75"
[[ ! -e "$STATE/update-called" ]] ||
    fail "closed/fail state attempted an update"
assert_no_unknown_call

new_case ambiguous-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["root-2"] = {
      id: "root-2", status: "in_progress", assignee: "",
      metadata: {
        "gc.kind": "workflow",
        "gc.formula_contract": "graph.v2",
        "gc.input_convoy_id": "convoy-1"
      }
    } |
    .beads["step-2"] = {
      id: "step-2", status: "closed", assignee: "actor-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.load-context",
        "gc.root_bead_id": "root-2",
        "gc.outcome": "pass"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "ambiguous replay returned $RUN_RC instead of 75"
[[ ! -e "$STATE/update-called" ]] ||
    fail "ambiguous replay attempted an update"
assert_no_unknown_call

new_case malformed-replay-sibling
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["step-2"] = {
      id: "step-2", status: "closed", assignee: "actor-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.load-context",
        "gc.outcome": "pass"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "malformed replay sibling returned $RUN_RC instead of 75"
[[ ! -e "$STATE/update-called" ]] ||
    fail "malformed replay sibling attempted an update"
assert_no_unknown_call

new_case terminal-fail-root-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["root-1"].status = "closed" |
    .beads["root-1"].metadata["gc.outcome"] = "fail"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 0 ]] ||
    fail "terminal fail-root lost-response replay failed: $(<"$OUTPUT")"
grep -F 'step=step-1' "$OUTPUT" >/dev/null &&
    grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "terminal fail-root replay did not select the exact closed/pass step"
[[ ! -e "$STATE/update-called" ]] ||
    fail "terminal fail-root replay attempted a duplicate update"
assert_no_unknown_call

new_case terminal-pass-root-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["root-1"].status = "closed" |
    .beads["root-1"].metadata["gc.outcome"] = "pass"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 0 ]] ||
    fail "terminal pass-root lost-response replay failed: $(<"$OUTPUT")"
grep -F 'step=step-1' "$OUTPUT" >/dev/null &&
    grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "terminal pass-root replay did not select the exact closed/pass step"
[[ ! -e "$STATE/update-called" ]] ||
    fail "terminal pass-root replay attempted a duplicate update"
assert_no_unknown_call

new_case incoherent-terminal-root-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["root-1"].status = "closed" |
    del(.beads["root-1"].metadata["gc.outcome"])' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "incoherent terminal root replay returned $RUN_RC instead of 75"
[[ ! -e "$STATE/update-called" ]] ||
    fail "incoherent terminal root replay attempted an update"
assert_no_unknown_call

new_case unreadable-replay-candidate
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["root-2"] = {
      id: "root-2", status: "in_progress", assignee: "",
      metadata: {
        "gc.kind": "workflow",
        "gc.formula_contract": "graph.v2",
        "gc.input_convoy_id": "other-convoy"
      }
    } |
    .beads["step-2"] = {
      id: "step-2", status: "closed", assignee: "actor-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.load-context",
        "gc.root_bead_id": "root-2",
        "gc.outcome": "pass"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
FAIL_SHOW_ID=root-2
run_command
unset FAIL_SHOW_ID
[[ "$RUN_RC" -eq 75 ]] ||
    fail "unreadable replay candidate returned $RUN_RC instead of 75"
[[ ! -e "$STATE/update-called" ]] ||
    fail "unreadable replay candidate attempted an update"
assert_no_unknown_call

new_case verified-other-convoy-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["root-2"] = {
      id: "root-2", status: "in_progress", assignee: "",
      metadata: {
        "gc.kind": "workflow",
        "gc.formula_contract": "graph.v2",
        "gc.input_convoy_id": "other-convoy"
      }
    } |
    .beads["step-2"] = {
      id: "step-2", status: "closed", assignee: "actor-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.load-context",
        "gc.root_bead_id": "root-2",
        "gc.outcome": "pass"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 0 ]] ||
    fail "verified other-convoy replay blocked the unique candidate: $(<"$OUTPUT")"
grep -F 'step=step-1' "$OUTPUT" >/dev/null &&
    grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "verified other-convoy replay selected the wrong candidate"
[[ ! -e "$STATE/update-called" ]] ||
    fail "verified replay attempted a duplicate update"
assert_no_unknown_call

new_case terminal-other-convoy-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass" |
    .beads["root-2"] = {
      id: "root-2", status: "closed", assignee: "",
      metadata: {
        "gc.kind": "workflow",
        "gc.formula_contract": "graph.v2",
        "gc.input_convoy_id": "other-convoy",
        "gc.outcome": "fail"
      }
    } |
    .beads["step-2"] = {
      id: "step-2", status: "closed", assignee: "actor-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.load-context",
        "gc.root_bead_id": "root-2",
        "gc.outcome": "pass"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 0 ]] ||
    fail "terminal other-convoy history poisoned replay: $(<"$OUTPUT")"
grep -F 'step=step-1' "$OUTPUT" >/dev/null &&
    grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "terminal other-convoy replay selected the wrong candidate"
[[ ! -e "$STATE/update-called" ]] ||
    fail "terminal other-convoy replay attempted a duplicate update"
assert_no_unknown_call

new_case alternate-current-identity-replay
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].assignee = "actor-2" |
    .beads["step-1"].metadata["gc.outcome"] = "pass"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
TEST_SESSION_NAME=actor-2
run_command
unset TEST_SESSION_NAME
[[ "$RUN_RC" -eq 0 ]] ||
    fail "alternate current identity replay failed: $(<"$OUTPUT")"
grep -F 'step=step-1' "$OUTPUT" >/dev/null &&
    grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "alternate current identity replay was not selected"
[[ ! -e "$STATE/update-called" ]] ||
    fail "alternate current identity replay attempted a duplicate update"
assert_no_unknown_call

new_case submit-bypass
TEST_STEP_REF=mol-polecat-work.submit-and-exit
run_command
unset TEST_STEP_REF
[[ "$RUN_RC" -eq 2 ]] ||
    fail "submit bypass returned $RUN_RC instead of usage exit 2"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "submit bypass attempted an update"
assert_no_unknown_call

new_case unsupported-step
TEST_STEP_REF=mol-polecat-work.not-a-step
run_command
unset TEST_STEP_REF
[[ "$RUN_RC" -eq 2 ]] ||
    fail "unsupported step returned $RUN_RC instead of usage exit 2"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "unsupported step attempted an update"
assert_no_unknown_call

echo "polecat step command tests passed"
