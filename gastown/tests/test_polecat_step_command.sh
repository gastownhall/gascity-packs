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

if [[ "${1:-}" == "bd" ]]; then
    if [[ "${2:-}" != "--rig" || "${3:-}" != "demo" ]]; then
        touch "$FAKE_STATE/unpinned-read"
        exit 79
    fi
    if [[ "${GC_NO_API:-}" != "1" ||
          "${GC_CITY_PATH:-}" != "${FAKE_EXPECT_CITY:-}" ||
          "${GC_RIG:-}" != "demo" ||
          "${GC_RIG_ROOT:-}" != "${FAKE_EXPECT_RIG_ROOT:-}" ||
          "${GC_STORE_ROOT:-}" != "${FAKE_EXPECT_RIG_ROOT:-}" ||
          "${GC_STORE_SCOPE:-}" != "rig" ]]; then
        touch "$FAKE_STATE/unpinned-read"
        exit 79
    fi
    set -- bd "${@:4}"
fi

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
    if [[ "$id" == "source-1" ]]; then
        source_count=0
        [[ ! -f "$FAKE_STATE/source-show-count" ]] ||
            source_count=$(<"$FAKE_STATE/source-show-count")
        source_count=$((source_count + 1))
        printf '%s\n' "$source_count" >"$FAKE_STATE/source-show-count"
        if [[ -n "${SOURCE_RESPONSE_MUTATION_AT:-}" &&
              "$source_count" == "$SOURCE_RESPONSE_MUTATION_AT" ]]; then
            case "${SOURCE_RESPONSE_MUTATION_KIND:-wrong-code}" in
                wrong-code)
                    jq '.beads["source-1"].metadata["gc.polecat_block_code"] =
                          "other-code"' "$FAKE_DB"
                    exit 0
                    ;;
                assigned)
                    jq '.beads["source-1"].assignee = "other-worker"' "$FAKE_DB"
                    exit 0
                    ;;
                *)
                    touch "$FAKE_STATE/unknown-call"
                    exit 93
                    ;;
            esac
        fi
        if [[ "$source_count" -eq 2 ]]; then
            case "${FINAL_SOURCE_MUTATION:-}" in
                closed|blocked|in_progress|tombstone)
                    jq --arg status "$FINAL_SOURCE_MUTATION" \
                        '.beads["source-1"].status = $status' \
                        "$FAKE_DB" >"$FAKE_DB.tmp"
                    write_db
                    ;;
                assigned)
                    jq '.beads["source-1"].assignee = "other-worker"' \
                        "$FAKE_DB" >"$FAKE_DB.tmp"
                    write_db
                    ;;
                branch-swap)
                    git -C "$FAKE_ARTIFACT" checkout -qb wrong-final-branch
                    ;;
                path-swap)
                    mv "$FAKE_ARTIFACT" "$FAKE_ARTIFACT.moved"
                    mkdir -p "$FAKE_ARTIFACT"
                    ;;
                admin-backpointer)
                    printf '%s/.git\n' "$FAKE_PROVIDER" \
                        >"$FAKE_ARTIFACT_ADMIN/gitdir"
                    ;;
                "")
                    ;;
                *)
                    touch "$FAKE_STATE/unknown-call"
                    exit 91
                    ;;
            esac
        fi
    fi
    if [[ "$id" == "root-1" ]]; then
        root_count=0
        [[ ! -f "$FAKE_STATE/root-show-count" ]] ||
            root_count=$(<"$FAKE_STATE/root-show-count")
        root_count=$((root_count + 1))
        printf '%s\n' "$root_count" >"$FAKE_STATE/root-show-count"
        if [[ -n "${ROOT_RESPONSE_MUTATION_AT:-}" &&
              "$root_count" == "$ROOT_RESPONSE_MUTATION_AT" ]]; then
            jq '.beads["root-1"].status = "closed" |
                .beads["root-1"].metadata["gc.outcome"] = "fail"' "$FAKE_DB"
            exit 0
        fi
    fi
    jq -e --arg id "$id" '[.beads[$id]] | select(.[0] != null)' "$FAKE_DB"
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "update" ]]; then
    id=${3:-}
    touch "$FAKE_STATE/update-called"
    update_count=0
    [[ ! -f "$FAKE_STATE/update-count" ]] ||
        update_count=$(<"$FAKE_STATE/update-count")
    update_count=$((update_count + 1))
    printf '%s\n' "$update_count" >"$FAKE_STATE/update-count"
    if [[ "${UPDATE_MODE:-ok}" == "fail" ||
          (-n "${FAIL_UPDATE_ID:-}" && "$id" == "$FAIL_UPDATE_ID") ||
          (-n "${FAIL_UPDATE_NUMBER:-}" &&
           "$update_count" == "$FAIL_UPDATE_NUMBER") ]]; then
        exit 84
    fi
    if [[ "${UPDATE_MODE:-ok}" == "noop" ||
          (-n "${NOOP_UPDATE_ID:-}" && "$id" == "$NOOP_UPDATE_ID") ||
          (-n "${NOOP_UPDATE_NUMBER:-}" &&
           "$update_count" == "$NOOP_UPDATE_NUMBER") ]]; then
        exit 0
    fi
    commit_then_error=false
    if [[ -n "${COMMIT_ERROR_UPDATE_NUMBER:-}" &&
          "$update_count" == "$COMMIT_ERROR_UPDATE_NUMBER" ]]; then
        commit_then_error=true
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
    [[ "$commit_then_error" != "true" ]] || exit 84
    exit 0
fi

if [[ "${1:-}" == "convoy" && "${2:-}" == "status" ]]; then
    convoy=${3:-}
    [[ "${4:-}" == "--json" && "$#" -eq 4 ]] || {
        touch "$FAKE_STATE/unknown-call"
        exit 89
    }
    if [[ "${CONVOY_MODE:-ok}" == "fail" ]]; then
        exit 90
    fi
    if [[ "${GC_NO_API:-}" != "1" ||
          "${GC_CITY_PATH:-}" != "${FAKE_EXPECT_CITY:-}" ||
          "${GC_RIG:-}" != "demo" ||
          "${GC_RIG_ROOT:-}" != "${FAKE_EXPECT_RIG_ROOT:-}" ]]; then
        touch "$FAKE_STATE/cached-api-read"
        jq -n --arg convoy "$convoy" \
            '{schema_version: "1",
              convoy: {id: $convoy},
              children: [{id: "cached-wrong-source"}]}'
        exit 0
    fi
    convoy_count=0
    [[ ! -f "$FAKE_STATE/convoy-count" ]] ||
        convoy_count=$(<"$FAKE_STATE/convoy-count")
    convoy_count=$((convoy_count + 1))
    printf '%s\n' "$convoy_count" >"$FAKE_STATE/convoy-count"
    if [[ -n "${FAKE_CONVOY_MUTATION_AT:-}" &&
          "$convoy_count" == "$FAKE_CONVOY_MUTATION_AT" ]]; then
        printf '%s\n' \
            "${FAKE_MUTATED_CONVOY_JSON:-{\"schema_version\":\"1\",\"convoy\":{\"id\":\"convoy-1\"},\"children\":[{\"id\":\"other-source\"}]}}"
    elif [[ "$convoy_count" -eq 2 &&
          -n "${FAKE_FINAL_CONVOY_JSON:-}" ]]; then
        printf '%s\n' "$FAKE_FINAL_CONVOY_JSON"
    elif [[ -n "${FAKE_CONVOY_JSON:-}" ]]; then
        printf '%s\n' "$FAKE_CONVOY_JSON"
    else
        jq -n --arg convoy "$convoy" \
            '{schema_version: "1",
              convoy: {id: $convoy, status: "open"},
              children: [{id: "source-1"}]}'
    fi
    exit 0
fi

if [[ "${1:-}" == "runtime" && "${2:-}" == "drain-ack" &&
      "$#" -eq 2 ]]; then
    touch "$FAKE_STATE/drain-called"
    [[ "${DRAIN_MODE:-ok}" != "fail" ]] || exit 92
    exit 0
fi

if [[ "${1:-}" == "gastown" && "${2:-}" == "polecat-conflict" &&
      "${3:-}" == "stage" && "$#" -eq 3 ]]; then
    [[ "${GC_POLECAT_SOURCE_ID:-}" == "source-1" &&
       "${GC_POLECAT_SOURCE_BRANCH:-}" == "polecat/source-1" &&
       "${GC_POLECAT_ARTIFACT_DIR:-}" == "$FAKE_ARTIFACT" &&
       "${GC_POLECAT_CONVOY_ID:-}" == "convoy-1" ]] || exit 94
    touch "$FAKE_STATE/conflict-stage-called"
    printf '%s\n' "POLECAT_CONFLICT_STAGE_COMPLETE"
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
    mkdir -p "$CASE_DIR/city" "$CASE_DIR/rig"
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
            "gc.var.rig_name": "demo",
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
    GC_CITY_PATH="${TEST_CITY_PATH-$CASE_DIR/city}" \
    GC_RIG="${TEST_RIG-demo}" \
    GC_RIG_ROOT="${TEST_RIG_ROOT-$CASE_DIR/rig}" \
    FAKE_DB="$DB" \
    FAKE_STATE="$STATE" \
    FAKE_GC_LOG="$STATE/gc.log" \
    FAKE_EXPECT_CITY="${TEST_CITY_PATH-$CASE_DIR/city}" \
    FAKE_EXPECT_RIG_ROOT="${TEST_RIG_ROOT-$CASE_DIR/rig}" \
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
    assert_no_unpinned_read
}

assert_no_unpinned_read() {
    [[ ! -e "$STATE/unpinned-read" && ! -e "$STATE/cached-api-read" ]] ||
        fail "command used an unpinned or cached/API state read"
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
grep -F 'gc bd --rig demo update step-1' "$STATE/gc.log" >/dev/null ||
    fail "happy path did not use the invoking gc bd adapter"
assert_no_unknown_call

run_command
[[ "$RUN_RC" -eq 0 ]] || fail "idempotent replay failed: $(<"$OUTPUT")"
grep -F 'replay=true' "$OUTPUT" >/dev/null ||
    fail "idempotent replay was not recognized"
[[ "$(grep -cF 'gc bd --rig demo update step-1' "$STATE/gc.log")" -eq 1 ]] ||
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
grep -F 'gc bd --rig demo list --assignee actor-1 ' "$STATE/gc.log" >/dev/null ||
    fail "alternate GC_AGENT identity was not queried"
grep -F 'gc bd --rig demo list --assignee wrong-template-identity ' \
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
    'gc bd --rig demo list --assignee actor-1 --status=in_progress ' \
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

new_case wrong-root-rig
jq '.beads["root-1"].metadata["gc.var.rig_name"] = "other-rig"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_command
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong root rig returned $RUN_RC instead of 75"
assert_unadvanced
[[ ! -e "$STATE/update-called" ]] ||
    fail "wrong root rig attempted an update"
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
        "gc.var.rig_name": "demo",
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
        "gc.var.rig_name": "demo",
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
        "gc.var.rig_name": "demo",
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
        "gc.var.rig_name": "demo",
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

EXEC_CITY=""
EXEC_RIG_ROOT=""
EXEC_PROVIDER=""
EXEC_ARTIFACT=""
EXEC_ARTIFACT_ADMIN=""

init_exec_case() {
    local name=$1
    new_case "exec-$name"
    EXEC_CITY="$CASE_DIR/city"
    EXEC_RIG_ROOT="$CASE_DIR/rig"
    EXEC_PROVIDER="$EXEC_CITY/.gc/worktrees/demo/polecats/gastown.nux"
    EXEC_ARTIFACT="$EXEC_CITY/.gc/worktrees/demo/artifacts/worktrees/source-1"

    git init -q "$EXEC_RIG_ROOT"
    git -C "$EXEC_RIG_ROOT" config user.email polecat-step@example.invalid
    git -C "$EXEC_RIG_ROOT" config user.name "Polecat Step Test"
    printf 'fixture\n' >"$EXEC_RIG_ROOT/fixture"
    git -C "$EXEC_RIG_ROOT" add fixture
    git -C "$EXEC_RIG_ROOT" commit -qm fixture
    git -C "$EXEC_RIG_ROOT" branch -M main

    mkdir -p "$(dirname "$EXEC_PROVIDER")" "$(dirname "$EXEC_ARTIFACT")"
    git -C "$EXEC_RIG_ROOT" worktree add -qb "provider-$name" \
        "$EXEC_PROVIDER" main
    git -C "$EXEC_RIG_ROOT" worktree add -qb polecat/source-1 \
        "$EXEC_ARTIFACT" main
    EXEC_ARTIFACT_ADMIN=$(git -C "$EXEC_ARTIFACT" rev-parse \
        --path-format=absolute --absolute-git-dir)

    jq --arg artifact "$EXEC_ARTIFACT" '
      .beads["step-1"].metadata["gc.step_ref"] =
        "mol-polecat-work.self-review" |
      .beads["source-1"] = {
        id: "source-1",
        status: "open",
        metadata: {
          artifact_dir: $artifact,
          branch: "polecat/source-1"
        }
      }' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
}

run_exec_from() {
    local cwd=$1
    shift
    set +e
    (
        cd "$cwd" || exit 98
        PATH="$TEST_TMP/bin:$PATH" \
        GC_BIN="$TEST_TMP/bin/gc" \
        BEADS_ACTOR=actor-1 \
        GC_SESSION_NAME="" \
        GC_SESSION_ID="" \
        GC_ALIAS="" \
        GC_AGENT="" \
        GC_CITY_PATH="$EXEC_CITY" \
        GC_RIG=demo \
        GC_RIG_ROOT="$EXEC_RIG_ROOT" \
        FAKE_DB="$DB" \
        FAKE_STATE="$STATE" \
        FAKE_GC_LOG="$STATE/gc.log" \
        FAKE_EXPECT_CITY="$EXEC_CITY" \
        FAKE_EXPECT_RIG_ROOT="$EXEC_RIG_ROOT" \
        FAKE_ARTIFACT="$EXEC_ARTIFACT" \
        FAKE_PROVIDER="$EXEC_PROVIDER" \
        FAKE_ARTIFACT_ADMIN="$EXEC_ARTIFACT_ADMIN" \
        LIST_MODE="${LIST_MODE:-ok}" \
        UPDATE_MODE="${UPDATE_MODE:-ok}" \
        FAIL_SHOW_ID="${FAIL_SHOW_ID:-}" \
        FAIL_LIST_ASSIGNEE="${FAIL_LIST_ASSIGNEE:-}" \
        DUPLICATE_LIST_FOR_ASSIGNEE="${DUPLICATE_LIST_FOR_ASSIGNEE:-}" \
        LIST_ROW_KIND="${LIST_ROW_KIND:-}" \
        LIST_ROW_STATUS="${LIST_ROW_STATUS:-}" \
        CONVOY_MODE="${CONVOY_MODE:-ok}" \
        FAKE_CONVOY_JSON="${FAKE_CONVOY_JSON:-}" \
        FAKE_FINAL_CONVOY_JSON="${FAKE_FINAL_CONVOY_JSON:-}" \
        FINAL_SOURCE_MUTATION="${FINAL_SOURCE_MUTATION:-}" \
        GIT_DIR="${TEST_GIT_DIR:-}" \
        GIT_WORK_TREE="${TEST_GIT_WORK_TREE:-}" \
        GIT_INDEX_FILE="${TEST_GIT_INDEX_FILE:-}" \
        GIT_COMMON_DIR="${TEST_GIT_COMMON_DIR:-}" \
        GIT_CONFIG_COUNT="${TEST_GIT_CONFIG_COUNT:-}" \
        GIT_CONFIG_KEY_0="${TEST_GIT_CONFIG_KEY_0:-}" \
        GIT_CONFIG_VALUE_0="${TEST_GIT_CONFIG_VALUE_0:-}" \
            "$COMMAND" exec \
            --convoy "${TEST_CONVOY:-convoy-1}" \
            --step-ref "${TEST_STEP_REF:-mol-polecat-work.self-review}" \
            -- "$@"
    ) >"$OUTPUT" 2>&1
    RUN_RC=$?
    set -e
}

set_source_artifact() {
    local path=$1
    jq --arg path "$path" \
        '.beads["source-1"].metadata.artifact_dir = $path' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
}

configure_workspace_stage() {
    jq '.beads["step-1"].metadata["gc.step_ref"] =
          "mol-polecat-work.workspace-setup"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    TEST_STEP_REF=mol-polecat-work.workspace-setup
}

expect_exec_rejection() {
    local label=$1 diagnostic=$2
    shift 2
    run_exec_from "$EXEC_PROVIDER" \
        bash -c 'touch "$1"' _ "$STATE/command-ran"
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "$label returned $RUN_RC instead of 75: $(<"$OUTPUT")"
    [[ ! -e "$STATE/command-ran" ]] ||
        fail "$label executed argv after rejecting artifact context"
    grep -F "$diagnostic" "$OUTPUT" >/dev/null ||
        fail "$label did not report $diagnostic: $(<"$OUTPUT")"
    [[ ! -e "$STATE/update-called" ]] ||
        fail "$label mutated the workflow step"
    assert_no_unknown_call
}

init_exec_case provider-home-success
literal="\$(touch $STATE/eval-ran)"
run_exec_from "$EXEC_PROVIDER" \
    bash -c 'read -r input; printf "%s|%s|%s\n" "$PWD" "$input" "$1"' \
    _ "$literal" <<<'inherited-stdin'
[[ "$RUN_RC" -eq 0 ]] ||
    fail "exec from provider home failed: $(<"$OUTPUT")"
[[ "$(<"$OUTPUT")" == "$EXEC_ARTIFACT|inherited-stdin|$literal" ]] ||
    fail "exec did not preserve artifact cwd, stdin, or literal argv: $(<"$OUTPUT")"
[[ ! -e "$STATE/eval-ran" ]] ||
    fail "exec evaluated caller argv"
[[ ! -e "$STATE/update-called" ]] ||
    fail "successful exec mutated the workflow step"
assert_no_unknown_call

other_cwd="$CASE_DIR/unrelated"
mkdir -p "$other_cwd"
run_exec_from "$other_cwd" pwd
[[ "$RUN_RC" -eq 0 && "$(<"$OUTPUT")" == "$EXEC_ARTIFACT" ]] ||
    fail "exec from unrelated cwd did not enter the artifact: $(<"$OUTPUT")"
run_exec_from "$TEST_TMP" bash -c 'exit 23'
[[ "$RUN_RC" -eq 23 ]] ||
    fail "exec did not preserve child exit status: $RUN_RC"
[[ ! -e "$STATE/update-called" ]] ||
    fail "repeat exec from another generation cwd mutated workflow state"
assert_no_unknown_call

init_exec_case poisoned-git-environment
TEST_GIT_DIR="$EXEC_ARTIFACT_ADMIN"
TEST_GIT_WORK_TREE="$EXEC_PROVIDER"
TEST_GIT_INDEX_FILE="$STATE/poison.index"
TEST_GIT_COMMON_DIR="$EXEC_RIG_ROOT/.git"
TEST_GIT_CONFIG_COUNT=1
TEST_GIT_CONFIG_KEY_0=remote.origin.url
TEST_GIT_CONFIG_VALUE_0=file:///definitely-not-the-rig-origin
run_exec_from "$EXEC_PROVIDER" bash -c '
    test -z "${GIT_DIR+x}${GIT_WORK_TREE+x}${GIT_INDEX_FILE+x}${GIT_COMMON_DIR+x}" &&
    test -z "${GIT_CONFIG_COUNT+x}${GIT_CONFIG_KEY_0+x}${GIT_CONFIG_VALUE_0+x}" &&
    test "$(git rev-parse --show-toplevel)" = "$1"
' _ "$EXEC_ARTIFACT"
unset TEST_GIT_DIR TEST_GIT_WORK_TREE TEST_GIT_INDEX_FILE TEST_GIT_COMMON_DIR
unset TEST_GIT_CONFIG_COUNT TEST_GIT_CONFIG_KEY_0 TEST_GIT_CONFIG_VALUE_0
[[ "$RUN_RC" -eq 0 ]] ||
    fail "sanitized Git environment exec failed: $(<"$OUTPUT")"
[[ ! -e "$STATE/update-called" ]] ||
    fail "sanitized Git environment exec mutated workflow state"
assert_no_unknown_call

for source_status in closed blocked in_progress tombstone; do
    init_exec_case "source-state-$source_status"
    jq --arg status "$source_status" \
        '.beads["source-1"].status = $status' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    expect_exec_rejection "source-state-$source_status" \
        "source identity, open/unassigned state, or artifact metadata did not verify"
done

init_exec_case source-assigned
jq '.beads["source-1"].assignee = "other-worker"' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
expect_exec_rejection source-assigned \
    "source identity, open/unassigned state, or artifact metadata did not verify"

init_exec_case missing-artifact
jq 'del(.beads["source-1"].metadata.artifact_dir)' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
expect_exec_rejection missing-artifact \
    "source identity, open/unassigned state, or artifact metadata did not verify"

init_exec_case provider-home
set_source_artifact "$EXEC_PROVIDER"
expect_exec_rejection provider-home \
    "source metadata.artifact_dir is not bead-scoped"

init_exec_case wrong-bead
wrong_bead="$EXEC_CITY/.gc/worktrees/demo/artifacts/worktrees/source-other"
mkdir -p "$(dirname "$wrong_bead")"
git -C "$EXEC_RIG_ROOT" worktree add -qb wrong-bead "$wrong_bead" main
set_source_artifact "$wrong_bead"
expect_exec_rejection wrong-bead \
    "source metadata.artifact_dir is not bead-scoped"

init_exec_case cross-rig
cross_rig="$EXEC_CITY/.gc/worktrees/other/artifacts/worktrees/source-1"
mkdir -p "$(dirname "$cross_rig")"
git -C "$EXEC_RIG_ROOT" worktree add -qb cross-rig "$cross_rig" main
set_source_artifact "$cross_rig"
expect_exec_rejection cross-rig \
    "source metadata.artifact_dir is outside the rig artifact layouts"

init_exec_case cross-city
cross_city="$CASE_DIR/other-city/.gc/worktrees/demo/artifacts/worktrees/source-1"
mkdir -p "$(dirname "$cross_city")"
git -C "$EXEC_RIG_ROOT" worktree add -qb cross-city "$cross_city" main
set_source_artifact "$cross_city"
expect_exec_rejection cross-city \
    "source metadata.artifact_dir is outside the rig artifact layouts"

init_exec_case symlink
symlink_artifact="$CASE_DIR/redirect/worktrees/source-1"
mkdir -p "$(dirname "$symlink_artifact")"
ln -s "$EXEC_ARTIFACT" "$symlink_artifact"
set_source_artifact "$symlink_artifact"
expect_exec_rejection symlink \
    "source metadata.artifact_dir is redirected"

init_exec_case subdir
subdir_artifact="$EXEC_ARTIFACT/subdir"
mkdir -p "$subdir_artifact"
set_source_artifact "$subdir_artifact"
expect_exec_rejection subdir \
    "source metadata.artifact_dir is not bead-scoped"

init_exec_case foreign-repository
git -C "$EXEC_RIG_ROOT" worktree remove "$EXEC_ARTIFACT"
git init -q "$EXEC_ARTIFACT"
git -C "$EXEC_ARTIFACT" config user.email foreign@example.invalid
git -C "$EXEC_ARTIFACT" config user.name "Foreign Repo"
printf 'foreign\n' >"$EXEC_ARTIFACT/foreign"
git -C "$EXEC_ARTIFACT" add foreign
git -C "$EXEC_ARTIFACT" commit -qm foreign
git -C "$EXEC_ARTIFACT" branch -M polecat/source-1
expect_exec_rejection foreign-repository \
    "source metadata.artifact_dir belongs to another repository"

init_exec_case copied-git-pointer-impostor
cp "$EXEC_PROVIDER/.git" "$EXEC_ARTIFACT/.git"
expect_exec_rejection copied-git-pointer-impostor \
    "source artifact Git admin backpointer does not match the artifact"

init_exec_case symlinked-git-pointer
mv "$EXEC_ARTIFACT/.git" "$EXEC_ARTIFACT/.git.saved"
ln -s .git.saved "$EXEC_ARTIFACT/.git"
expect_exec_rejection symlinked-git-pointer \
    "source artifact is not a registered linked Git worktree"

init_exec_case wrong-admin-backpointer
printf '%s/.git\n' "$EXEC_PROVIDER" >"$EXEC_ARTIFACT_ADMIN/gitdir"
expect_exec_rejection wrong-admin-backpointer \
    "source artifact Git admin backpointer does not match the artifact"

init_exec_case ambiguous-convoy
FAKE_CONVOY_JSON='{"schema_version":"1","convoy":{"id":"convoy-1"},"children":[{"id":"source-1"},{"id":"source-2"}]}'
expect_exec_rejection ambiguous-convoy \
    "input convoy identity/schema or sole source did not verify"
unset FAKE_CONVOY_JSON

init_exec_case convoy-id-mismatch
FAKE_CONVOY_JSON='{"schema_version":"1","convoy":{"id":"other-convoy"},"children":[{"id":"source-1"}]}'
expect_exec_rejection convoy-id-mismatch \
    "input convoy identity/schema or sole source did not verify"
unset FAKE_CONVOY_JSON

init_exec_case convoy-flat-obsolete-schema
FAKE_CONVOY_JSON='{"id":"convoy-1","children":[{"id":"source-1"}]}'
expect_exec_rejection convoy-flat-obsolete-schema \
    "input convoy identity/schema or sole source did not verify"
unset FAKE_CONVOY_JSON

init_exec_case wrong-branch
jq '.beads["source-1"].metadata.branch = "polecat/other"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
expect_exec_rejection wrong-branch \
    "source metadata.branch is not the canonical task branch"

init_exec_case workspace-default-wrong-named-branch
configure_workspace_stage
git -C "$EXEC_ARTIFACT" checkout -qb wrong-workspace-branch
run_exec_from "$EXEC_PROVIDER" gc gastown polecat-conflict stage
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong named conflict workspace returned $RUN_RC instead of 75"
grep -F "workspace transition found a wrong named branch" "$OUTPUT" >/dev/null ||
    fail "wrong named conflict workspace lacked the bounded diagnostic"
[[ ! -e "$STATE/conflict-stage-called" ]] ||
    fail "wrong named conflict workspace executed the staging child"
assert_no_unknown_call
unset TEST_STEP_REF

init_exec_case workspace-conflict-detached
configure_workspace_stage
git -C "$EXEC_ARTIFACT" checkout -q --detach
run_exec_from "$EXEC_PROVIDER" gc gastown polecat-conflict stage
[[ "$RUN_RC" -eq 0 && -e "$STATE/conflict-stage-called" ]] ||
    fail "exact detached conflict child did not execute: $(<"$OUTPUT")"
[[ ! -e "$STATE/update-called" ]] ||
    fail "detached conflict staging mutated workflow state"
assert_no_unknown_call
unset TEST_STEP_REF

init_exec_case workspace-conflict-canonical
configure_workspace_stage
run_exec_from "$EXEC_PROVIDER" gc gastown polecat-conflict stage
[[ "$RUN_RC" -eq 0 && -e "$STATE/conflict-stage-called" ]] ||
    fail "exact canonical conflict child did not execute: $(<"$OUTPUT")"
[[ ! -e "$STATE/update-called" ]] ||
    fail "canonical conflict staging mutated workflow state"
assert_no_unknown_call
unset TEST_STEP_REF

for forbidden_child in shell raw-rebase lease; do
    init_exec_case "workspace-conflict-reject-$forbidden_child"
    configure_workspace_stage
    case "$forbidden_child" in
        shell) run_exec_from "$EXEC_PROVIDER" bash -se ;;
        raw-rebase) run_exec_from "$EXEC_PROVIDER" git rebase --continue ;;
        lease)
            run_exec_from "$EXEC_PROVIDER" \
                gc gastown polecat-lease workspace
            ;;
    esac
    [[ "$RUN_RC" -eq 2 ]] ||
        fail "$forbidden_child workspace child returned $RUN_RC instead of 2"
    grep -F "workspace-setup exec accepts only exact polecat-conflict stage" \
        "$OUTPUT" >/dev/null ||
        fail "$forbidden_child workspace child lacked exact-child diagnostic"
    [[ ! -e "$STATE/update-called" && ! -e "$STATE/conflict-stage-called" ]] ||
        fail "$forbidden_child workspace child mutated or executed"
    assert_no_unknown_call
    unset TEST_STEP_REF
done

init_exec_case workspace-conflict-wrong-metadata
configure_workspace_stage
jq '.beads["source-1"].metadata.branch = "polecat/wrong"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_exec_from "$EXEC_PROVIDER" gc gastown polecat-conflict stage
[[ "$RUN_RC" -eq 75 ]] ||
    fail "wrong metadata conflict child returned $RUN_RC instead of 75"
grep -F "source metadata.branch is not the canonical task branch" \
    "$OUTPUT" >/dev/null ||
    fail "wrong metadata conflict child lacked the bounded diagnostic"
[[ ! -e "$STATE/conflict-stage-called" ]] ||
    fail "wrong metadata conflict child executed"
assert_no_unknown_call
unset TEST_STEP_REF

for final_source_state in closed blocked in_progress tombstone; do
    init_exec_case "final-source-$final_source_state"
    FINAL_SOURCE_MUTATION=$final_source_state
    expect_exec_rejection "final-source-$final_source_state" \
        "source identity, open/unassigned state, or artifact context changed before exec"
    unset FINAL_SOURCE_MUTATION
done

init_exec_case final-source-assigned
FINAL_SOURCE_MUTATION=assigned
expect_exec_rejection final-source-assigned \
    "source identity, open/unassigned state, or artifact context changed before exec"
unset FINAL_SOURCE_MUTATION

init_exec_case final-convoy-id-mismatch
FAKE_FINAL_CONVOY_JSON='{"schema_version":"1","convoy":{"id":"wrong-convoy"},"children":[{"id":"source-1"}]}'
expect_exec_rejection final-convoy-id-mismatch \
    "input convoy identity/schema/source changed before exec"
unset FAKE_FINAL_CONVOY_JSON

init_exec_case final-branch-swap
FINAL_SOURCE_MUTATION=branch-swap
expect_exec_rejection final-branch-swap \
    "final artifact proof failed: source artifact is not on the canonical task branch"
unset FINAL_SOURCE_MUTATION

init_exec_case final-admin-backpointer-swap
FINAL_SOURCE_MUTATION=admin-backpointer
expect_exec_rejection final-admin-backpointer-swap \
    "final artifact proof failed: source artifact Git admin backpointer does not match the artifact"
unset FINAL_SOURCE_MUTATION

init_exec_case final-path-swap
FINAL_SOURCE_MUTATION=path-swap
expect_exec_rejection final-path-swap \
    "final artifact proof failed"
unset FINAL_SOURCE_MUTATION

init_exec_case closed-step
jq '.beads["step-1"].status = "closed" |
    .beads["step-1"].metadata["gc.outcome"] = "pass"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
expect_exec_rejection closed-step \
    "no unique live step matches this exec request"

init_exec_case load-context-exec
TEST_STEP_REF=mol-polecat-work.load-context
jq '.beads["step-1"].metadata["gc.step_ref"] =
      "mol-polecat-work.load-context"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_exec_from "$EXEC_PROVIDER" true
unset TEST_STEP_REF
[[ "$RUN_RC" -eq 2 ]] ||
    fail "load-context exec returned $RUN_RC instead of usage exit 2"
[[ ! -e "$STATE/update-called" ]] ||
    fail "load-context exec mutated the workflow step"
assert_no_unknown_call

init_block_case() {
    local name=$1
    new_case "block-$name"
    jq '
      .beads["step-1"].metadata["gc.step_ref"] =
        "mol-polecat-work.workspace-setup" |
      .beads["source-1"] = {
        id: "source-1",
        status: "open",
        assignee: "",
        metadata: {
          "gc.routed_to": "gastown.polecat"
        }
      }' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
}

run_block() {
    set +e
    PATH="$TEST_TMP/bin:$PATH" \
    GC_BIN="$TEST_TMP/bin/gc" \
    BEADS_ACTOR=actor-1 \
    GC_SESSION_NAME="" \
    GC_SESSION_ID="" \
    GC_ALIAS="" \
    GC_AGENT="" \
    GC_CITY_PATH="$CASE_DIR/city" \
    GC_RIG=demo \
    GC_RIG_ROOT="$CASE_DIR/rig" \
    FAKE_DB="$DB" \
    FAKE_STATE="$STATE" \
    FAKE_GC_LOG="$STATE/gc.log" \
    FAKE_EXPECT_CITY="$CASE_DIR/city" \
    FAKE_EXPECT_RIG_ROOT="$CASE_DIR/rig" \
    LIST_MODE="${LIST_MODE:-ok}" \
    UPDATE_MODE="${UPDATE_MODE:-ok}" \
    FAIL_UPDATE_ID="${FAIL_UPDATE_ID:-}" \
    FAIL_UPDATE_NUMBER="${FAIL_UPDATE_NUMBER:-}" \
    NOOP_UPDATE_ID="${NOOP_UPDATE_ID:-}" \
    NOOP_UPDATE_NUMBER="${NOOP_UPDATE_NUMBER:-}" \
    COMMIT_ERROR_UPDATE_NUMBER="${COMMIT_ERROR_UPDATE_NUMBER:-}" \
    FAIL_SHOW_ID="${FAIL_SHOW_ID:-}" \
    FAIL_LIST_ASSIGNEE="${FAIL_LIST_ASSIGNEE:-}" \
    DUPLICATE_LIST_FOR_ASSIGNEE="${DUPLICATE_LIST_FOR_ASSIGNEE:-}" \
    LIST_ROW_KIND="${LIST_ROW_KIND:-}" \
    LIST_ROW_STATUS="${LIST_ROW_STATUS:-}" \
    CONVOY_MODE="${CONVOY_MODE:-ok}" \
    FAKE_CONVOY_JSON="${FAKE_CONVOY_JSON:-}" \
    FAKE_FINAL_CONVOY_JSON="${FAKE_FINAL_CONVOY_JSON:-}" \
    FAKE_CONVOY_MUTATION_AT="${FAKE_CONVOY_MUTATION_AT:-}" \
    FAKE_MUTATED_CONVOY_JSON="${FAKE_MUTATED_CONVOY_JSON:-}" \
    ROOT_RESPONSE_MUTATION_AT="${ROOT_RESPONSE_MUTATION_AT:-}" \
    SOURCE_RESPONSE_MUTATION_AT="${SOURCE_RESPONSE_MUTATION_AT:-}" \
    SOURCE_RESPONSE_MUTATION_KIND="${SOURCE_RESPONSE_MUTATION_KIND:-}" \
    DRAIN_MODE="${DRAIN_MODE:-ok}" \
        "$COMMAND" block \
        --convoy "${TEST_CONVOY:-convoy-1}" \
        --step-ref "${TEST_STEP_REF:-mol-polecat-work.workspace-setup}" \
        --code "${TEST_BLOCK_CODE:-workspace.artifact-invalid}" \
        --reason "${TEST_BLOCK_REASON:-canonical artifact failed validation}" \
        >"$OUTPUT" 2>&1
    RUN_RC=$?
    set -e
}

assert_block_contract() {
    jq -e \
      --arg code "${TEST_BLOCK_CODE:-workspace.artifact-invalid}" \
      --arg reason "${TEST_BLOCK_REASON:-canonical artifact failed validation}" '
      .beads["source-1"].status == "blocked" and
      .beads["source-1"].assignee == "" and
      .beads["source-1"].metadata["gc.routed_to"] == "human" and
      .beads["source-1"].metadata["gc.polecat_block_previous_route"] ==
        "gastown.polecat" and
      .beads["source-1"].metadata.blocked_reason == $reason and
      .beads["source-1"].metadata["gc.polecat_block_code"] == $code and
      (.beads["source-1"].metadata["gc.polecat_block_version"] |
       tostring) == "1" and
      .beads["source-1"].metadata["gc.polecat_block_step_ref"] ==
        "mol-polecat-work.workspace-setup" and
      .beads["source-1"].metadata["gc.polecat_block_step_id"] ==
        "step-1" and
      .beads["source-1"].metadata["gc.polecat_block_root"] == "root-1" and
      .beads["source-1"].metadata["gc.polecat_block_convoy"] ==
        "convoy-1" and
      .beads["step-1"].status == "blocked" and
      .beads["step-1"].assignee == "actor-1" and
      .beads["step-1"].metadata["gc.blocked_reason"] == $reason and
      .beads["step-1"].metadata["gc.polecat_block_code"] == $code and
      (.beads["step-1"].metadata["gc.polecat_block_version"] |
       tostring) == "1" and
      .beads["step-1"].metadata["gc.polecat_block_source"] ==
        "source-1" and
      .beads["step-1"].metadata["gc.polecat_block_convoy"] ==
        "convoy-1" and
      .beads["root-1"].status == "in_progress" and
      ((.beads["root-1"].metadata | has("gc.outcome")) | not)
    ' "$DB" >/dev/null ||
        fail "durable source/step block contract did not verify"
}

assert_block_not_terminal() {
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" != "closed" &&
       "$(jq -r '.beads["step-1"].status' "$DB")" != "closed" &&
       "$(jq -r '.beads["step-1"].metadata["gc.outcome"] // ""' "$DB")" == "" ]] ||
        fail "block path terminalized source or workflow step"
}

init_block_case success
run_block
[[ "$RUN_RC" -eq 0 ]] ||
    fail "block success returned $RUN_RC: $(<"$OUTPUT")"
assert_block_contract
[[ -e "$STATE/drain-called" ]] ||
    fail "durable block did not acknowledge drain"
rg -q 'POLECAT_STEP_BLOCKED .*code=workspace\.artifact-invalid replay=false' \
    "$OUTPUT" ||
    fail "fresh block did not report its exact code and replay state"
assert_block_not_terminal
assert_no_unknown_call

updates_before_replay=$(<"$STATE/update-count")
run_block
[[ "$RUN_RC" -eq 0 ]] ||
    fail "blocked replay returned $RUN_RC: $(<"$OUTPUT")"
[[ "$(<"$STATE/update-count")" -eq "$updates_before_replay" ]] ||
    fail "blocked replay performed another durable mutation"
rg -q 'POLECAT_STEP_BLOCKED .*replay=true' "$OUTPUT" ||
    fail "blocked replay was not reported explicitly"
assert_block_contract
assert_no_unknown_call

init_block_case drain-retry
DRAIN_MODE=fail
run_block
unset DRAIN_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "failed drain after durable block returned $RUN_RC instead of 75"
assert_block_contract
updates_before_replay=$(<"$STATE/update-count")
run_block
[[ "$RUN_RC" -eq 0 ]] ||
    fail "drain-only blocked replay failed: $(<"$OUTPUT")"
[[ "$(<"$STATE/update-count")" -eq "$updates_before_replay" ]] ||
    fail "drain-only replay rewrote durable block state"
assert_no_unknown_call

for failure_number in 1 2 3 4; do
    init_block_case "write-failure-$failure_number"
    FAIL_UPDATE_NUMBER=$failure_number
    run_block
    unset FAIL_UPDATE_NUMBER
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "write failure $failure_number returned $RUN_RC instead of 75"
    [[ ! -e "$STATE/drain-called" ]] ||
        fail "write failure $failure_number drained before complete readback"
    assert_block_not_terminal
    run_block
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "write failure $failure_number did not converge on retry: $(<"$OUTPUT")"
    assert_block_contract
    assert_no_unknown_call
done

for noop_number in 1 2 3 4; do
    init_block_case "write-noop-$noop_number"
    NOOP_UPDATE_NUMBER=$noop_number
    run_block
    unset NOOP_UPDATE_NUMBER
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "write no-op $noop_number returned $RUN_RC instead of 75"
    [[ ! -e "$STATE/drain-called" ]] ||
        fail "write no-op $noop_number drained before exact readback"
    assert_block_not_terminal
    run_block
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "write no-op $noop_number did not converge on retry: $(<"$OUTPUT")"
    assert_block_contract
    assert_no_unknown_call
done

for commit_error_number in 1 2 3 4; do
    init_block_case "commit-error-$commit_error_number"
    COMMIT_ERROR_UPDATE_NUMBER=$commit_error_number
    run_block
    unset COMMIT_ERROR_UPDATE_NUMBER
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "commit-then-error $commit_error_number returned $RUN_RC instead of 75"
    [[ ! -e "$STATE/drain-called" ]] ||
        fail "commit-then-error $commit_error_number drained before retry proof"
    assert_block_not_terminal
    run_block
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "commit-then-error $commit_error_number did not converge: $(<"$OUTPUT")"
    assert_block_contract
    [[ "$(jq -r '.beads["source-1"].notes' "$DB" |
        rg -c '^BLOCKED \[workspace\.artifact-invalid\] ')" -eq 1 ]] ||
        fail "commit-then-error $commit_error_number duplicated the source incident note"
    assert_no_unknown_call
done

init_block_case conflicting-source-signature
jq '.beads["source-1"].metadata["gc.polecat_block_convoy"] =
      "other-convoy"' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_block
[[ "$RUN_RC" -eq 75 ]] ||
    fail "conflicting source signature returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" &&
   "$(jq -r '.beads["step-1"].status' "$DB")" == "in_progress" &&
   ! -e "$STATE/drain-called" ]] ||
    fail "conflicting source signature changed status or drained"
assert_no_unknown_call

init_block_case conflicting-step-signature
jq '.beads["step-1"].metadata["gc.polecat_block_source"] =
      "other-source"' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_block
[[ "$RUN_RC" -eq 75 ]] ||
    fail "conflicting step signature returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" &&
   "$(jq -r '.beads["step-1"].status' "$DB")" == "in_progress" &&
   ! -e "$STATE/drain-called" ]] ||
    fail "conflicting step signature changed status or drained"
assert_no_unknown_call

init_block_case convoy-drift-before-status
FAKE_CONVOY_MUTATION_AT=2
run_block
unset FAKE_CONVOY_MUTATION_AT
[[ "$RUN_RC" -eq 75 ]] ||
    fail "convoy drift before status returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" &&
   "$(jq -r '.beads["step-1"].status' "$DB")" == "in_progress" &&
   ! -e "$STATE/drain-called" ]] ||
    fail "convoy drift before status changed status or drained"
assert_no_unknown_call

for drift_call in 3 4; do
    init_block_case "convoy-drift-$drift_call"
    FAKE_CONVOY_MUTATION_AT=$drift_call
    run_block
    unset FAKE_CONVOY_MUTATION_AT
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "convoy drift at read $drift_call returned $RUN_RC instead of 75"
    [[ ! -e "$STATE/drain-called" ]] ||
        fail "convoy drift at read $drift_call drained before final proof"
    assert_block_not_terminal
    run_block
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "convoy drift at read $drift_call did not converge: $(<"$OUTPUT")"
    assert_block_contract
    assert_no_unknown_call
done

for root_drift_call in 3 4; do
    init_block_case "root-drift-$root_drift_call"
    ROOT_RESPONSE_MUTATION_AT=$root_drift_call
    run_block
    unset ROOT_RESPONSE_MUTATION_AT
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "root drift at read $root_drift_call returned $RUN_RC instead of 75"
    [[ ! -e "$STATE/drain-called" ]] ||
        fail "root drift at read $root_drift_call drained before final proof"
    run_block
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "root drift at read $root_drift_call did not converge: $(<"$OUTPUT")"
    assert_block_contract
    assert_no_unknown_call
done

for source_drift_call in 5 6; do
    init_block_case "source-drift-$source_drift_call"
    SOURCE_RESPONSE_MUTATION_AT=$source_drift_call
    run_block
    unset SOURCE_RESPONSE_MUTATION_AT
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "source drift at read $source_drift_call returned $RUN_RC instead of 75"
    [[ ! -e "$STATE/drain-called" ]] ||
        fail "source drift at read $source_drift_call drained before final proof"
    run_block
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "source drift at read $source_drift_call did not converge: $(<"$OUTPUT")"
    assert_block_contract
    assert_no_unknown_call
done

init_block_case conflicting-block-replay
run_block
[[ "$RUN_RC" -eq 0 ]] ||
    fail "conflicting replay fixture could not establish block"
updates_before_replay=$(<"$STATE/update-count")
rm -f "$STATE/drain-called"
TEST_BLOCK_CODE=workspace.different-incident
TEST_BLOCK_REASON='different deterministic incident'
run_block
unset TEST_BLOCK_CODE TEST_BLOCK_REASON
[[ "$RUN_RC" -eq 75 ]] ||
    fail "conflicting blocked replay returned $RUN_RC instead of 75"
[[ ! -e "$STATE/drain-called" &&
   "$(<"$STATE/update-count")" -eq "$updates_before_replay" ]] ||
    fail "conflicting blocked replay mutated state or acknowledged drain"
assert_block_contract
assert_no_unknown_call

init_block_case invalid-code
TEST_BLOCK_CODE='bad code'
run_block
unset TEST_BLOCK_CODE
[[ "$RUN_RC" -eq 2 ]] ||
    fail "unsafe block code returned $RUN_RC instead of usage exit 2"
[[ ! -e "$STATE/update-called" && ! -e "$STATE/drain-called" ]] ||
    fail "unsafe block code mutated state or drained"
assert_no_unknown_call

for control_reason in $'bad\001reason' $'bad\177reason'; do
    init_block_case invalid-reason-control
    TEST_BLOCK_REASON=$control_reason
    run_block
    unset TEST_BLOCK_REASON
    [[ "$RUN_RC" -eq 2 ]] ||
        fail "control-bearing block reason returned $RUN_RC instead of usage exit 2"
    [[ ! -e "$STATE/update-called" && ! -e "$STATE/drain-called" ]] ||
        fail "control-bearing block reason mutated state or drained"
    assert_no_unknown_call
done

echo "polecat step command tests passed"
