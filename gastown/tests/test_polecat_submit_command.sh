#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/polecat-submit/run.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

FAKE_GC="$TMP/gc"
cat >"$FAKE_GC" <<'FAKE'
#!/usr/bin/env bash
set -euo pipefail

printf 'gc' >>"$FAKE_LOG"
printf ' %q' "$@" >>"$FAKE_LOG"
printf '\n' >>"$FAKE_LOG"

if [[ "$1" == "convoy" && "$2" == "status" ]]; then
    convoy=$3
    [[ "${FAIL_CONVOY:-}" != "$convoy" ]] || exit 1
    jq --arg id "$convoy" '.convoys[$id]' "$FAKE_DB"
    exit 0
fi

[[ "$1" == "bd" ]] || exit 90
subcommand=$2
shift 2
case "$subcommand" in
    list)
        assignee=""
        status=""
        while (($#)); do
            case "$1" in
                --assignee)
                    assignee=$2
                    shift 2
                    ;;
                --assignee=*)
                    assignee=${1#*=}
                    shift
                    ;;
                --status)
                    status=$2
                    shift 2
                    ;;
                --status=*)
                    status=${1#*=}
                    shift
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        [[ "${FAIL_LIST_IDENTITY:-}" != "$assignee" ]] || exit 1
        listed=$(jq --arg assignee "$assignee" --arg status "$status" '
          [.beads[] |
           select(.assignee == $assignee and .status == $status)]
        ' "$FAKE_DB")
        case "${INJECT_LIST_ROW_MODE:-}" in
            wrong-assignee)
                if [[ "$status" == "in_progress" && "$assignee" == "runtime-name" ]]; then
                    listed=$(printf '%s' "$listed" | jq \
                        '. + [{id:"foreign",status:"in_progress",assignee:"someone-else",metadata:{}}]')
                fi
                ;;
            wrong-status)
                if [[ "$status" == "in_progress" && "$assignee" == "runtime-name" ]]; then
                    listed=$(printf '%s' "$listed" | jq \
                        '. + [{id:"foreign",status:"closed",assignee:"runtime-name",metadata:{}}]')
                fi
                ;;
            malformed)
                if [[ "$status" == "in_progress" && "$assignee" == "runtime-name" ]]; then
                    listed=$(printf '%s' "$listed" | jq '. + ["not-an-object"]')
                fi
                ;;
            duplicate-id-across-identities)
                if [[ "$status" == "in_progress" ]]; then
                    listed=$(jq -cn --arg assignee "$assignee" \
                        '[{id:"duplicate-step",status:"in_progress",
                           assignee:$assignee,
                           metadata:{"gc.step_ref":"mol-polecat-work.submit-and-exit"}}]')
                fi
                ;;
            closed-wrong-assignee)
                if [[ "$status" == "closed" && "$assignee" == "runtime-name" ]]; then
                    listed=$(printf '%s' "$listed" | jq \
                        '. + [{id:"foreign",status:"closed",assignee:"someone-else",metadata:{}}]')
                fi
                ;;
        esac
        printf '%s\n' "$listed"
        ;;
    show)
        id=$1
        [[ "${FAIL_SHOW_ID:-}" != "$id" ]] || exit 1
        if [[ "${FAIL_FIRST_POST_UPDATE_SHOW:-}" == "$id" &&
              -e "$FAKE_DB.post-update" &&
              ! -e "$FAKE_DB.post-update-show-failed" ]]; then
            : >"$FAKE_DB.post-update-show-failed"
            exit 1
        fi
        if [[ "${CLEAR_TOKEN_ON_REVALIDATE_ROOT:-}" == "1" &&
              "$id" == "root-1" ]]; then
            if [[ -e "$FAKE_DB.root-shown" &&
                  ! -e "$FAKE_DB.token-cleared" ]]; then
                jq 'del(.beads["source-1"].metadata["gc.polecat_submit_convoy"])' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                mv "$FAKE_DB.tmp" "$FAKE_DB"
                : >"$FAKE_DB.token-cleared"
            else
                : >"$FAKE_DB.root-shown"
            fi
        fi
        jq --arg id "$id" '
          if .beads[$id] == null then [] else [.beads[$id]] end
        ' "$FAKE_DB"
        ;;
    update)
        id=$1
        shift
        [[ "${UPDATE_MODE:-}" != "fail" ]] || exit 1
        status=""
        metadata='{}'
        while (($#)); do
            case "$1" in
                --status)
                    status=$2
                    shift 2
                    ;;
                --status=*)
                    status=${1#*=}
                    shift
                    ;;
                --set-metadata)
                    pair=$2
                    shift 2
                    key=${pair%%=*}
                    value=${pair#*=}
                    metadata=$(jq -cn \
                        --argjson current "$metadata" \
                        --arg key "$key" --arg value "$value" '
                        ($value | try fromjson catch $value) as $decoded |
                        $current + {($key): $decoded}
                    ')
                    ;;
                --set-metadata=*)
                    pair=${1#*=}
                    shift
                    key=${pair%%=*}
                    value=${pair#*=}
                    metadata=$(jq -cn \
                        --argjson current "$metadata" \
                        --arg key "$key" --arg value "$value" '
                        ($value | try fromjson catch $value) as $decoded |
                        $current + {($key): $decoded}
                    ')
                    ;;
                --append-notes)
                    shift 2
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        [[ "${UPDATE_MODE:-}" != "noop" ]] || exit 0
        jq --arg id "$id" --arg status "$status" \
           --argjson metadata "$metadata" '
          if $status != "" then .beads[$id].status = $status else . end |
          .beads[$id].metadata += $metadata
        ' "$FAKE_DB" >"$FAKE_DB.tmp"
        mv "$FAKE_DB.tmp" "$FAKE_DB"
        : >"$FAKE_DB.post-update"
        [[ "${UPDATE_MODE:-}" != "apply-then-error" ]] || exit 1
        ;;
    *)
        exit 91
        ;;
esac
FAKE
chmod +x "$FAKE_GC"

new_case() {
    local name=$1
    STATE="$TMP/$name"
    mkdir -p "$STATE"
    DB="$STATE/db.json"
    LOG="$STATE/gc.log"
    OUTPUT="$STATE/output"
    jq -n '{
      beads: {
        "submit-1": {
          id: "submit-1",
          status: "in_progress",
          assignee: "session-1",
          metadata: {
            "gc.step_ref": "mol-polecat-work.submit-and-exit",
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
            "gc.formula_name": "mol-polecat-work",
            "gc.input_convoy_id": "convoy-1",
            "gc.var.base_branch": "main",
            "gc.var.rig_name": "demo",
            "gc.var.binding_prefix": "gastown."
          }
        },
        "source-1": {
          id: "source-1",
          status: "open",
          assignee: "",
          metadata: {
            branch: "polecat/source-1",
            target: "main",
            branch_ready: true,
            halt_reason: "auto_push_false"
          }
        }
      },
      convoys: {
        "convoy-1": {
          id: "convoy-1",
          children: [{id: "source-1"}]
        }
      }
    }' >"$DB"
    : >"$LOG"
}

run_submit() {
    local rc
    set +e
    BEADS_ACTOR="runtime-name" \
    GC_SESSION_NAME="runtime-name" \
    GC_SESSION_ID="${TEST_SESSION_ID-session-1}" \
    GC_ALIAS="session-1" \
    GC_AGENT="agent-name" \
    GC_RIG="${TEST_RIG-demo}" \
    GC_BIN="$FAKE_GC" \
    FAKE_DB="$DB" \
    FAKE_LOG="$LOG" \
    FAIL_LIST_IDENTITY="${FAIL_LIST_IDENTITY:-}" \
    FAIL_SHOW_ID="${FAIL_SHOW_ID:-}" \
    FAIL_FIRST_POST_UPDATE_SHOW="${FAIL_FIRST_POST_UPDATE_SHOW:-}" \
    FAIL_CONVOY="${FAIL_CONVOY:-}" \
    UPDATE_MODE="${UPDATE_MODE:-}" \
    INJECT_LIST_ROW_MODE="${INJECT_LIST_ROW_MODE:-}" \
    CLEAR_TOKEN_ON_REVALIDATE_ROOT="${CLEAR_TOKEN_ON_REVALIDATE_ROOT:-}" \
    TEST_SESSION_ID="${TEST_SESSION_ID:-session-1}" \
        bash "$COMMAND" "$@" >"$OUTPUT" 2>&1
    rc=$?
    set -e
    RUN_RC=$rc
}

assert_live_unmutated() {
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "submit step status changed unexpectedly: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["submit-1"].metadata["gc.outcome"] // ""' "$DB")" == "" ]] ||
        fail "submit outcome changed unexpectedly: $(<"$OUTPUT")"
    ! grep -F 'gc bd update submit-1' "$LOG" >/dev/null ||
        fail "submit step update was attempted unexpectedly: $(<"$OUTPUT")"
}

set_generation_token() {
    local convoy=${1:-convoy-1}
    jq --arg convoy "$convoy" \
        '.beads["source-1"].metadata["gc.polecat_submit_convoy"] = $convoy' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
}

new_case guard-proceed-alternate-identity
run_submit guard
[[ "$RUN_RC" -eq 0 ]] || fail "guard proceed failed: $(<"$OUTPUT")"
grep -F '"action":"proceed"' "$OUTPUT" >/dev/null &&
    grep -F '"assignee":"session-1"' "$OUTPUT" >/dev/null ||
    fail "guard did not select the exact alternate assignee: $(<"$OUTPUT")"
assert_live_unmutated
[[ "$(grep -c -- '--assignee session-1' "$LOG")" -eq 1 ]] ||
    fail "deduplicated identity was queried more than once"

new_case guard-missing-exact-session-id
TEST_SESSION_ID=""
run_submit guard
unset TEST_SESSION_ID
[[ "$RUN_RC" -eq 75 ]] ||
    fail "missing GC_SESSION_ID returned $RUN_RC instead of 75"
assert_live_unmutated

new_case guard-terminal-auto-push-false
set_generation_token
run_submit guard
[[ "$RUN_RC" -eq 0 ]] ||
    fail "branch-ready terminal guard failed: $(<"$OUTPUT")"
grep -F '"action":"terminal"' "$OUTPUT" >/dev/null ||
    fail "branch-ready terminal guard did not report terminal state"
assert_live_unmutated

new_case guard-current-token-incomplete
jq '.beads["source-1"].metadata.branch_ready = false |
    del(.beads["source-1"].metadata.halt_reason)' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "incomplete current-token guard returned $RUN_RC instead of 75"
assert_live_unmutated

new_case guard-token-mismatch-no-overwrite
set_generation_token stale-convoy
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "stale generation guard returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_submit_convoy"]' "$DB")" == "stale-convoy" ]] ||
    fail "guard overwrote the stale source generation token"
! grep -F 'gc bd update source-1' "$LOG" >/dev/null ||
    fail "guard attempted to mutate the source generation token"
assert_live_unmutated

new_case guard-hq-empty-rig
jq '.beads["root-1"].metadata["gc.var.rig_name"] = "" |
    .beads["source-1"].assignee = "gastown.refinery" |
    .beads["source-1"].metadata["gc.polecat_submit_convoy"] = "convoy-1"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
TEST_RIG=""
run_submit guard
unset TEST_RIG
[[ "$RUN_RC" -eq 0 ]] ||
    fail "HQ empty-rig guard failed: $(<"$OUTPUT")"
grep -F '"action":"terminal"' "$OUTPUT" >/dev/null ||
    fail "HQ empty-rig context did not derive its refinery"
assert_live_unmutated

new_case guard-ambiguous
jq '.beads["submit-2"] = {
      id: "submit-2",
      status: "in_progress",
      assignee: "agent-name",
      metadata: {
        "gc.step_ref": "mol-polecat-work.submit-and-exit",
        "gc.root_bead_id": "root-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "ambiguous guard returned $RUN_RC instead of 75"
assert_live_unmutated

new_case guard-query-failure
FAIL_LIST_IDENTITY=runtime-name
run_submit guard
unset FAIL_LIST_IDENTITY
[[ "$RUN_RC" -eq 75 ]] ||
    fail "query failure returned $RUN_RC instead of 75"
assert_live_unmutated

for injected_mode in wrong-assignee wrong-status malformed duplicate-id-across-identities; do
    new_case "guard-list-contract-$injected_mode"
    INJECT_LIST_ROW_MODE=$injected_mode
    run_submit guard
    unset INJECT_LIST_ROW_MODE
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "live list contract $injected_mode returned $RUN_RC instead of 75"
    assert_live_unmutated
done

new_case guard-closed-list-contract-mismatch
jq '.beads["submit-1"].status = "closed" |
    .beads["submit-1"].metadata["gc.outcome"] = "pass"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
INJECT_LIST_ROW_MODE=closed-wrong-assignee
run_submit guard
unset INJECT_LIST_ROW_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "closed list contract mismatch returned $RUN_RC instead of 75"
! grep -F 'gc bd update' "$LOG" >/dev/null ||
    fail "closed list contract mismatch attempted a mutation"

new_case guard-missing-root-base
jq 'del(.beads["root-1"].metadata["gc.var.base_branch"])' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "missing root base returned $RUN_RC instead of 75"
assert_live_unmutated

new_case guard-terminal-refinery
jq '.beads["source-1"].assignee = "demo/gastown.refinery"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit guard
[[ "$RUN_RC" -eq 0 ]] || fail "terminal guard failed: $(<"$OUTPUT")"
grep -F '"action":"terminal"' "$OUTPUT" >/dev/null ||
    fail "terminal guard did not report terminal state"
assert_live_unmutated

new_case guard-refinery-wrong-target
jq '.beads["source-1"].assignee = "demo/gastown.refinery" |
    .beads["source-1"].metadata.target = "release"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong-target refinery guard returned $RUN_RC instead of 75"
assert_live_unmutated

new_case guard-refinery-wrong-branch
jq '.beads["source-1"].assignee = "demo/gastown.refinery" |
    .beads["source-1"].metadata.branch = "polecat/other-source"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong-branch refinery guard returned $RUN_RC instead of 75"
assert_live_unmutated

new_case guard-conflicting-source
jq '.beads["source-1"].assignee = "demo/other.owner"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "conflicting guard returned $RUN_RC instead of 75"
grep -F 'POLECAT_SUBMIT_CONFLICT' "$OUTPUT" >/dev/null ||
    fail "conflicting guard did not report the conflict"
assert_live_unmutated

new_case complete-auto-push-false
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "auto_push_false completion failed: $(<"$OUTPUT")"
grep -F 'POLECAT_SUBMIT_COMPLETE' "$OUTPUT" >/dev/null &&
    grep -F 'mode=auto_push_false' "$OUTPUT" >/dev/null ||
    fail "auto_push_false completion output was incomplete"
[[ "$(jq -r '.beads["submit-1"].metadata["gc.outcome"]' "$DB")" == "pass" ]] ||
    fail "auto_push_false completion did not persist pass"

new_case complete-wrong-evidence
jq '.beads["source-1"].metadata.branch_ready = false' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong evidence returned $RUN_RC instead of 75"
assert_live_unmutated

new_case complete-wrong-target
jq '.beads["source-1"].metadata.target = "release"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong target returned $RUN_RC instead of 75"
assert_live_unmutated

new_case complete-missing-target
jq 'del(.beads["source-1"].metadata.target)' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "missing target returned $RUN_RC instead of 75"
assert_live_unmutated

new_case complete-refinery
jq '.beads["source-1"].status = "in_progress" |
    .beads["source-1"].assignee = "demo/gastown.refinery"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode refinery
[[ "$RUN_RC" -eq 0 ]] ||
    fail "refinery completion failed: $(<"$OUTPUT")"
grep -F 'mode=refinery' "$OUTPUT" >/dev/null ||
    fail "refinery completion did not report its evidence mode"

new_case complete-wrong-convoy-source
set_generation_token
run_submit complete \
    --convoy other-convoy --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong convoy returned $RUN_RC instead of 75"
assert_live_unmutated

new_case complete-readback-failure
set_generation_token
UPDATE_MODE=noop
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
unset UPDATE_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "completion readback failure returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
    fail "noop completion unexpectedly changed the submit step"

new_case complete-apply-then-error
set_generation_token
UPDATE_MODE=apply-then-error
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
unset UPDATE_MODE
[[ "$RUN_RC" -eq 0 ]] ||
    fail "applied update with lost response did not verify: $(<"$OUTPUT")"
[[ "$(jq -r '.beads["submit-1"].metadata["gc.polecat_submit_version"]' "$DB")" == "1" &&
   "$(jq -r '.beads["submit-1"].metadata["gc.polecat_submit_session_id"]' "$DB")" == "session-1" ]] ||
    fail "applied update did not persist versioned replay evidence"
jq -e '.beads["submit-1"].metadata["gc.polecat_submit_version"] |
       type == "number" and . == 1' "$DB" >/dev/null ||
    fail "fake store did not preserve real bd numeric version typing"

new_case complete-source-race-before-close
set_generation_token
CLEAR_TOKEN_ON_REVALIDATE_ROOT=1
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
unset CLEAR_TOKEN_ON_REVALIDATE_ROOT
[[ "$RUN_RC" -eq 75 ]] ||
    fail "source token race returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_submit_convoy"] // ""' "$DB")" == "" ]] ||
    fail "source-race fixture did not clear the token"
assert_live_unmutated

new_case complete-response-loss-terminal-root-replay
set_generation_token
UPDATE_MODE=apply-then-error
FAIL_FIRST_POST_UPDATE_SHOW=submit-1
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
unset UPDATE_MODE FAIL_FIRST_POST_UPDATE_SHOW
[[ "$RUN_RC" -eq 75 ]] ||
    fail "lost update/readback response returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "closed" ]] ||
    fail "response-loss fixture did not apply the closed transition"
jq '.beads["root-1"].status = "closed" |
    .beads["root-1"].metadata["gc.outcome"] = "pass"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
: >"$LOG"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "terminal-root closed replay failed: $(<"$OUTPUT")"
grep -F 'POLECAT_SUBMIT_COMPLETE' "$OUTPUT" >/dev/null &&
    grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "terminal-root replay did not report exact replay"
! grep -F 'gc bd update' "$LOG" >/dev/null ||
    fail "closed replay attempted a second mutation"

new_case guard-corrupt-refinery-terminal-replay
jq '.beads["source-1"].assignee = "demo/gastown.refinery"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode refinery
[[ "$RUN_RC" -eq 0 ]] ||
    fail "corrupt refinery replay setup did not complete: $(<"$OUTPUT")"
jq '.beads["submit-1"].metadata["gc.polecat_submit_terminal"] = "branch_ready"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
: >"$LOG"
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "refinery/branch_ready replay corruption returned $RUN_RC instead of 75"
! grep -F 'gc bd update' "$LOG" >/dev/null ||
    fail "corrupt refinery replay attempted a mutation"

new_case complete-closed-fail-root-replay
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "closed/fail root replay setup did not complete: $(<"$OUTPUT")"
jq '.beads["root-1"].status = "closed" |
    .beads["root-1"].metadata["gc.outcome"] = "fail"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
: >"$LOG"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "closed/fail terminal-root replay failed: $(<"$OUTPUT")"
grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "closed/fail terminal-root replay did not report replay"
! grep -F 'gc bd update' "$LOG" >/dev/null ||
    fail "closed/fail terminal-root replay attempted a mutation"

new_case complete-replay-source-token-mismatch
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "replay token-mismatch setup did not complete: $(<"$OUTPUT")"
set_generation_token other-convoy
: >"$LOG"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "replay source token mismatch returned $RUN_RC instead of 75"
! grep -F 'gc bd update' "$LOG" >/dev/null ||
    fail "replay source token mismatch attempted a mutation"

new_case guard-stale-same-source-new-root
jq '.beads["root-2"] = (.beads["root-1"] |
      .id = "root-2" |
      .metadata["gc.input_convoy_id"] = "convoy-2") |
    .beads["submit-1"].metadata["gc.root_bead_id"] = "root-2" |
    .convoys["convoy-2"] = {
      id: "convoy-2",
      children: [{id: "source-1"}]
    } |
    .beads["source-1"].metadata["gc.polecat_submit_convoy"] = "convoy-1"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "same-source/new-root stale token returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_submit_convoy"]' "$DB")" == "convoy-1" ]] ||
    fail "new root overwrote the prior source generation token"
assert_live_unmutated

new_case guard-duplicate-closed-replay
jq '.beads["source-1"].assignee = "demo/gastown.refinery"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode refinery
[[ "$RUN_RC" -eq 0 ]] ||
    fail "duplicate replay setup did not close: $(<"$OUTPUT")"
jq '.beads["submit-2"] = (.beads["submit-1"] | .id = "submit-2")' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
: >"$LOG"
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "duplicate coherent replay returned $RUN_RC instead of 75"
! grep -F 'gc bd update' "$LOG" >/dev/null ||
    fail "duplicate replay attempted a mutation"

new_case guard-old-session-replay-ignored
jq '.beads["source-1"].assignee = "demo/gastown.refinery"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
set_generation_token
TEST_SESSION_ID=session-old
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode refinery
unset TEST_SESSION_ID
[[ "$RUN_RC" -eq 0 ]] ||
    fail "old-session replay setup did not close: $(<"$OUTPUT")"
TEST_SESSION_ID=session-new
: >"$LOG"
run_submit guard
unset TEST_SESSION_ID
[[ "$RUN_RC" -eq 75 ]] ||
    fail "different current session reused old replay evidence"
! grep -F 'gc bd update' "$LOG" >/dev/null ||
    fail "ignored old-session replay attempted a mutation"

new_case invalid-branch-api
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch other/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 2 ]] ||
    fail "invalid branch API returned $RUN_RC instead of 2"
assert_live_unmutated

echo "polecat submit command tests passed"
