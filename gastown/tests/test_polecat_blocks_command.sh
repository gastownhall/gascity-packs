#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/polecat-blocks/run.sh"
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

direct_store_env_is_exact() {
    [[ "${GC_NO_API:-}" == "1" &&
       "${GC_CITY:-}" == "$FAKE_EXPECT_CITY" &&
       "${GC_CITY_PATH:-}" == "$FAKE_EXPECT_CITY" &&
       "${GC_RIG:-}" == "demo" &&
       "${GC_RIG_ROOT:-}" == "$FAKE_EXPECT_RIG_ROOT" &&
       "${GC_STORE_ROOT:-}" == "$FAKE_EXPECT_RIG_ROOT" &&
       "${GC_STORE_SCOPE:-}" == "rig" ]]
}

mail_env_is_exact() {
    [[ "${GC_NO_API:-}" == "1" &&
       "${GC_CITY:-}" == "$FAKE_EXPECT_CITY" &&
       "${GC_CITY_PATH:-}" == "$FAKE_EXPECT_CITY" &&
       "${GC_RIG:-}" == "demo" &&
       "${GC_RIG_ROOT:-}" == "$FAKE_EXPECT_RIG_ROOT" &&
       "${GC_STORE_ROOT:-}" == "$FAKE_EXPECT_CITY" &&
       "${GC_STORE_SCOPE:-}" == "city" ]]
}

if [[ "${1:-}" == "bd" ]]; then
    if [[ "${2:-}" != "--rig" || "${3:-}" != "demo" ]] ||
       ! direct_store_env_is_exact; then
        touch "$FAKE_STATE/unpinned-read"
        exit 91
    fi
    set -- bd "${@:4}"
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "list" ]]; then
    shift 2
    saw_all=false
    saw_marker=false
    saw_json=false
    saw_limit=false
    while (($#)); do
        case "$1" in
            --all)
                saw_all=true
                shift
                ;;
            --metadata-field)
                [[ "${2:-}" == "gc.polecat_block_version=1" ]] || exit 92
                saw_marker=true
                shift 2
                ;;
            --json)
                saw_json=true
                shift
                ;;
            --limit=0)
                saw_limit=true
                shift
                ;;
            *)
                touch "$FAKE_STATE/unknown-call"
                exit 93
                ;;
        esac
    done
    [[ "$saw_all" == true && "$saw_marker" == true &&
       "$saw_json" == true && "$saw_limit" == true ]] || exit 94
    if [[ "${LIST_MODE:-ok}" == "fail" ]]; then
        exit 95
    elif [[ "${LIST_MODE:-ok}" == "malformed" ]]; then
        printf '{"not":"rows"}\n'
        exit 0
    fi
    jq '[
      .beads[] |
      select(.metadata["gc.polecat_block_version"] != null and
             ((.metadata["gc.polecat_block_version"] | tostring) == "1"))
    ]' "$FAKE_DB"
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "show" ]]; then
    id=${3:-}
    [[ "${4:-}" == "--json" && $# -eq 4 ]] || exit 96
    if [[ -n "${FAIL_SHOW_ID:-}" && "$id" == "$FAIL_SHOW_ID" ]]; then
        exit 97
    fi
    jq -e --arg id "$id" '[.beads[$id]] | select(.[0] != null)' "$FAKE_DB"
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "update" ]]; then
    id=${3:-}
    shift 3
    printf '%s\n' "$id" >>"$FAKE_STATE/update-ids"
    if [[ "${UPDATE_MODE:-ok}" == "fail" ]]; then
        exit 98
    elif [[ "${UPDATE_MODE:-ok}" == "noop" ]]; then
        exit 0
    fi
    while (($#)); do
        case "$1" in
            --set-metadata)
                key=${2%%=*}
                value=${2#*=}
                case "$key" in
                    gc.polecat_block_alert_version|\
                    gc.polecat_block_alert_signature)
                        ;;
                    *)
                        touch "$FAKE_STATE/protected-mutation"
                        exit 99
                        ;;
                esac
                jq --arg id "$id" --arg key "$key" --arg value "$value" \
                    '.beads[$id].metadata[$key] = $value' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            *)
                touch "$FAKE_STATE/protected-mutation"
                exit 100
                ;;
        esac
    done
    if [[ "${UPDATE_MODE:-ok}" == "authority-drift" ]]; then
        jq --arg id "$id" '.beads[$id].status = "open"' \
            "$FAKE_DB" >"$FAKE_DB.tmp"
        write_db
    fi
    exit 0
fi

if [[ "${1:-}" == "convoy" && "${2:-}" == "status" ]]; then
    if ! direct_store_env_is_exact; then
        touch "$FAKE_STATE/cached-convoy-read"
        printf '%s\n' \
            '{"schema_version":"1","convoy":{"id":"convoy-1"},"children":[{"id":"cached-wrong-source"}]}'
        exit 0
    fi
    [[ "${3:-}" == "convoy-1" && "${4:-}" == "--json" &&
       $# -eq 4 ]] || exit 101
    if [[ "${CONVOY_MODE:-ok}" == "fail" ]]; then
        exit 102
    fi
    if [[ -n "${FAKE_CONVOY_JSON:-}" ]]; then
        printf '%s\n' "$FAKE_CONVOY_JSON"
    else
        printf '%s\n' \
            '{"schema_version":"1","convoy":{"id":"convoy-1"},"children":[{"id":"source-1"}]}'
    fi
    exit 0
fi

if [[ "${1:-}" == "mail" && "${2:-}" == "send" &&
      "${3:-}" == "mayor/" ]]; then
    if ! mail_env_is_exact; then
        touch "$FAKE_STATE/unpinned-mail"
        exit 105
    fi
    if [[ $# -ne 7 || "${4:-}" != "-s" || "${6:-}" != "-m" ]]; then
        touch "$FAKE_STATE/malformed-mail"
        exit 106
    fi
    subject=$5
    body=$7
    printf '%s' "$subject" >"$FAKE_STATE/mail.subject"
    printf '%s' "$body" >"$FAKE_STATE/mail.body"
    if ((${#subject} > 256 || ${#body} > 4096)); then
        touch "$FAKE_STATE/oversized-mail"
        exit 107
    fi
    count=0
    [[ ! -f "$FAKE_STATE/mail-count" ]] || count=$(<"$FAKE_STATE/mail-count")
    count=$((count + 1))
    printf '%s\n' "$count" >"$FAKE_STATE/mail-count"
    printf '%q ' "$@" >>"$FAKE_STATE/mail.log"
    printf '\n' >>"$FAKE_STATE/mail.log"
    [[ "${MAIL_MODE:-ok}" != "fail" ]] || exit 103
    exit 0
fi

touch "$FAKE_STATE/unknown-call"
exit 104
SH
chmod +x "$TEST_TMP/bin/gc"

CASE_DIR=""
CITY=""
RIG_ROOT=""
STATE=""
DB=""
OUTPUT=""
RUN_RC=0

new_case() {
    local name=$1
    CASE_DIR="$TEST_TMP/$name"
    CITY="$CASE_DIR/city"
    RIG_ROOT="$CASE_DIR/rig"
    STATE="$CASE_DIR/state"
    DB="$STATE/db.json"
    OUTPUT="$STATE/output"
    mkdir -p "$CITY" "$RIG_ROOT" "$STATE"
    : >"$STATE/gc.log"
    : >"$STATE/mail.log"
    : >"$STATE/update-ids"
    jq -n '{beads:{}}' >"$DB"
}

add_valid_pair() {
    jq '.beads += {
      "source-1": {
        id: "source-1",
        status: "blocked",
        assignee: "",
        metadata: {
          blocked_reason: "external access is required",
          "gc.routed_to": "human",
          "gc.polecat_block_version": "1",
          "gc.polecat_block_code": "access.required",
          "gc.polecat_block_step_ref": "mol-polecat-work.implement",
          "gc.polecat_block_step_id": "step-1",
          "gc.polecat_block_root": "root-1",
          "gc.polecat_block_previous_route": "polecat",
          "gc.polecat_block_convoy": "convoy-1"
        }
      },
      "step-1": {
        id: "step-1",
        status: "blocked",
        assignee: "demo/gastown.nux",
        metadata: {
          "gc.step_ref": "mol-polecat-work.implement",
          "gc.root_bead_id": "root-1",
          "gc.blocked_reason": "external access is required",
          "gc.polecat_block_version": "1",
          "gc.polecat_block_code": "access.required",
          "gc.polecat_block_source": "source-1",
          "gc.polecat_block_convoy": "convoy-1"
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
          "gc.var.rig_name": "demo",
          "gc.input_convoy_id": "convoy-1"
        }
      }
    }' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
}

invoke_surface() {
    PATH="$TEST_TMP/bin:$PATH" \
    GC_BIN="$TEST_TMP/bin/gc" \
    GC_CITY="${AMBIENT_GC_CITY:-}" \
    GC_CITY_PATH="$CITY" \
    GC_RIG=demo \
    GC_RIG_ROOT="$RIG_ROOT" \
    FAKE_DB="$DB" \
    FAKE_STATE="$STATE" \
    FAKE_GC_LOG="$STATE/gc.log" \
    FAKE_EXPECT_CITY="$CITY" \
    FAKE_EXPECT_RIG_ROOT="$RIG_ROOT" \
    LIST_MODE="${LIST_MODE:-ok}" \
    UPDATE_MODE="${UPDATE_MODE:-ok}" \
    MAIL_MODE="${MAIL_MODE:-ok}" \
    CONVOY_MODE="${CONVOY_MODE:-ok}" \
    FAKE_CONVOY_JSON="${FAKE_CONVOY_JSON:-}" \
    FAIL_SHOW_ID="${FAIL_SHOW_ID:-}" \
        "$COMMAND" surface
}

run_surface() {
    set +e
    invoke_surface >"$OUTPUT" 2>&1
    RUN_RC=$?
    set -e
}

mail_count() {
    if [[ -f "$STATE/mail-count" ]]; then
        cat "$STATE/mail-count"
    else
        printf '0'
    fi
}

assert_no_forbidden_operation() {
    [[ ! -e "$STATE/unpinned-read" &&
       ! -e "$STATE/cached-convoy-read" &&
       ! -e "$STATE/unpinned-mail" &&
       ! -e "$STATE/malformed-mail" &&
       ! -e "$STATE/oversized-mail" ]] ||
        fail "command used cached or unpinned authority/notification routing"
    [[ ! -e "$STATE/protected-mutation" ]] ||
        fail "command requested a protected mutation"
    ! grep -E 'gc (workflow|session|runtime) ' "$STATE/gc.log" >/dev/null ||
        fail "command attempted workflow/session/runtime recovery"
    ! grep -E 'gc bd --rig demo update .*--(status|assignee|unset-metadata)' \
        "$STATE/gc.log" >/dev/null ||
        fail "command attempted status, ownership, or block cleanup mutation"
    [[ ! -e "$STATE/unknown-call" ]] ||
        fail "command issued an unexpected gc operation"
}

assert_protected_pair_unchanged() {
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" &&
       "$(jq -r '.beads["source-1"].assignee' "$DB")" == "" &&
       "$(jq -r '.beads["step-1"].status' "$DB")" == "blocked" &&
       "$(jq -r '.beads["step-1"].assignee' "$DB")" == "demo/gastown.nux" ]] ||
        fail "surface command changed protected source/step authority"
}

test_empty_scan() {
    new_case empty
    run_surface
    [[ "$RUN_RC" -eq 0 ]] || fail "empty scan failed: $(<"$OUTPUT")"
    grep -F 'POLECAT_BLOCK_SURFACE rows=0 valid=0 partial=0 malformed=0 notified=0 deduped=0 failures=0' \
        "$OUTPUT" >/dev/null || fail "empty summary is not exact"
    [[ "$(mail_count)" -eq 0 && ! -s "$STATE/update-ids" ]] ||
        fail "empty scan notified or wrote a receipt"
    grep -F 'gc bd --rig demo list --all --metadata-field gc.polecat_block_version=1 --json --limit=0 ' \
        "$STATE/gc.log" >/dev/null ||
        fail "scan was not explicitly all-status and marker-scoped"
    assert_no_forbidden_operation
}

test_valid_pair_and_dedup() {
    new_case valid
    add_valid_pair
    run_surface
    [[ "$RUN_RC" -eq 0 ]] || fail "valid pair failed: $(<"$OUTPUT")"
    [[ "$(mail_count)" -eq 1 ]] || fail "valid pair did not mail exactly once"
    grep -F 'classification=valid' "$STATE/mail.log" >/dev/null ||
        fail "valid pair mail lacks its classification: $(<"$STATE/mail.log"); $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_block_alert_version"]' "$DB")" == "1" ]] ||
        fail "valid pair alert receipt was not recorded on source"
    signature=$(jq -r \
        '.beads["source-1"].metadata["gc.polecat_block_alert_signature"] // ""' \
        "$DB")
    [[ "$signature" =~ ^sha256:[0-9a-f]{64}$ ]] ||
        fail "valid pair receipt lacks fixed SHA-256 signature: $signature"
    assert_protected_pair_unchanged

    run_surface
    [[ "$RUN_RC" -eq 0 ]] || fail "dedup replay failed: $(<"$OUTPUT")"
    [[ "$(mail_count)" -eq 1 ]] || fail "matching receipt did not dedup mail"
    grep -F 'valid=1 partial=0 malformed=0 notified=0 deduped=1 failures=0' \
        "$OUTPUT" >/dev/null || fail "dedup summary is not exact"
    [[ "$(wc -l <"$STATE/update-ids")" -eq 1 ]] ||
        fail "dedup replay wrote a second receipt"
    assert_no_forbidden_operation
}

test_notification_failure_is_retryable() {
    new_case mail-retry
    add_valid_pair
    MAIL_MODE=fail
    run_surface
    unset MAIL_MODE
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "mail failure returned $RUN_RC instead of 75"
    [[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_block_alert_signature"] // ""' "$DB")" == "" ]] ||
        fail "mail failure wrote a suppressing receipt"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 2 ]] ||
        fail "mail failure did not retry at least once: $(<"$OUTPUT")"
    assert_protected_pair_unchanged
    assert_no_forbidden_operation
}

test_receipt_failure_is_retryable() {
    local mode
    for mode in fail noop; do
        new_case "receipt-$mode"
        add_valid_pair
        UPDATE_MODE=$mode
        run_surface
        unset UPDATE_MODE
        [[ "$RUN_RC" -eq 75 ]] ||
            fail "$mode receipt returned $RUN_RC instead of 75"
        [[ "$(mail_count)" -eq 1 ]] ||
            fail "$mode receipt failure did not send the first mail"
        [[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_block_alert_signature"] // ""' "$DB")" == "" ]] ||
            fail "$mode receipt failure appeared durable"
        run_surface
        [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 2 ]] ||
            fail "$mode receipt failure did not retry notification"
        assert_protected_pair_unchanged
        assert_no_forbidden_operation
    done
}

test_partial_contracts_surface_without_recovery() {
    new_case source-only
    add_valid_pair
    jq 'del(.beads["step-1"])' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "source-only partial did not surface: $(<"$OUTPUT")"
    grep -F 'partial=1' "$OUTPUT" >/dev/null ||
        fail "source-only contract was not classified partial"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "source-only surfacing changed source status"

    new_case step-only
    add_valid_pair
    jq 'del(.beads["source-1"])' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "step-only partial did not surface: $(<"$OUTPUT")"
    grep -F 'partial=1' "$OUTPUT" >/dev/null ||
        fail "step-only contract was not classified partial"
    [[ "$(jq -r '.beads["step-1"].metadata["gc.polecat_block_alert_version"]' "$DB")" == "1" &&
       "$(jq -r '.beads["step-1"].status' "$DB")" == "blocked" ]] ||
        fail "step-only alert receipt/status did not verify"
    assert_no_forbidden_operation
}

test_malformed_and_duplicate_pairs_surface() {
    new_case mismatched
    add_valid_pair
    jq '.beads["step-1"].metadata["gc.blocked_reason"] = "different"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "mismatched pair did not surface: $(<"$OUTPUT")"
    grep -F 'malformed=1' "$OUTPUT" >/dev/null ||
        fail "mismatched pair was not classified malformed"
    assert_protected_pair_unchanged

    new_case missing-route-provenance
    add_valid_pair
    jq 'del(.beads["source-1"].metadata["gc.polecat_block_previous_route"])' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "missing source route provenance did not surface: $(<"$OUTPUT")"
    grep -F 'malformed=1' "$OUTPUT" >/dev/null ||
        fail "missing source route provenance was not classified malformed"
    assert_protected_pair_unchanged

    new_case duplicate
    add_valid_pair
    jq '.beads["step-2"] =
        (.beads["step-1"] | .id = "step-2")' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "duplicate pair did not surface: $(<"$OUTPUT")"
    grep -F 'malformed=1' "$OUTPUT" >/dev/null ||
        fail "duplicate pair was not classified malformed"
    assert_protected_pair_unchanged
    assert_no_forbidden_operation
}

test_root_and_convoy_mismatch_surface() {
    new_case wrong-root
    add_valid_pair
    jq '.beads["root-1"].metadata["gc.var.rig_name"] = "other"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "wrong root did not surface: $(<"$OUTPUT")"
    grep -F 'diagnostic=root_contract_mismatch' "$STATE/mail.log" >/dev/null ||
        fail "wrong root lacks exact diagnostic"

    new_case wrong-convoy
    add_valid_pair
    FAKE_CONVOY_JSON='{"schema_version":"1","convoy":{"id":"other"},"children":[{"id":"source-1"}]}'
    run_surface
    unset FAKE_CONVOY_JSON
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "wrong convoy did not surface: $(<"$OUTPUT")"
    grep -F 'diagnostic=convoy_contract_mismatch' "$STATE/mail.log" >/dev/null ||
        fail "wrong convoy lacks exact diagnostic"
    assert_protected_pair_unchanged
    assert_no_forbidden_operation
}

test_all_status_and_liveness_independent_surface() {
    new_case all-status
    add_valid_pair
    jq '.beads["source-1"].status = "tombstone" |
        .beads["step-1"].status = "suspended" |
        .beads["step-1"].assignee = "demo/quarantined-owner"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "nonstandard-status/quarantined-owner rows were silent: $(<"$OUTPUT")"
    grep -F 'malformed=1' "$OUTPUT" >/dev/null ||
        fail "nonstandard-status rows were not surfaced malformed"
    ! grep -F 'gc session ' "$STATE/gc.log" >/dev/null ||
        fail "session liveness incorrectly gated durable block visibility"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "tombstone" &&
       "$(jq -r '.beads["step-1"].status' "$DB")" == "suspended" ]] ||
        fail "all-status surfacing attempted recovery"
    assert_no_forbidden_operation
}

test_changed_signature_notifies_again() {
    new_case changed-signature
    add_valid_pair
    run_surface
    [[ "$RUN_RC" -eq 0 ]] || fail "initial signature failed"
    jq '.beads["source-1"].metadata.blocked_reason = "new blocker" |
        .beads["step-1"].metadata["gc.blocked_reason"] = "new blocker"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 2 ]] ||
        fail "changed exact signature was incorrectly deduped"
    assert_protected_pair_unchanged
    assert_no_forbidden_operation
}

test_stale_gc_city_cannot_redirect_notification() {
    local stale_city
    new_case stale-city
    add_valid_pair
    stale_city="$CASE_DIR/stale-valid-city"
    mkdir -p "$stale_city"
    printf '[city]\nname = "stale-valid-city"\n' >"$stale_city/city.toml"
    AMBIENT_GC_CITY=$stale_city
    run_surface
    unset AMBIENT_GC_CITY
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "stale valid GC_CITY redirected or suppressed Mayor mail: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_block_alert_version"]' "$DB")" == "1" ]] ||
        fail "stale valid GC_CITY prevented exact receipt persistence"
    assert_protected_pair_unchanged
    assert_no_forbidden_operation
}

test_hostile_malformed_metadata_is_bounded() {
    local hostile signature
    new_case hostile-malformed
    add_valid_pair
    hostile=$'BAD\r\n\t'
    hostile+=$(printf 'X%.0s' {1..20000})
    jq --arg hostile "$hostile" '
        del(.beads["source-1"]) |
        .beads["step-1"].assignee = $hostile |
        .beads["step-1"].metadata["gc.polecat_block_source"] = $hostile |
        .beads["step-1"].metadata["gc.blocked_reason"] = $hostile
    ' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"

    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "hostile malformed marker was not surfaced safely: $(<"$OUTPUT")"
    grep -F 'partial=1' "$OUTPUT" >/dev/null ||
        fail "hostile surviving row was not classified partial"
    signature=$(jq -r \
        '.beads["step-1"].metadata["gc.polecat_block_alert_signature"] // ""' \
        "$DB")
    [[ "$signature" =~ ^sha256:[0-9a-f]{64}$ ]] ||
        fail "hostile marker receipt is not a bounded SHA-256 signature"
    python3 - "$STATE/mail.subject" "$STATE/mail.body" <<'PY'
import pathlib
import sys

subject = pathlib.Path(sys.argv[1]).read_bytes()
body = pathlib.Path(sys.argv[2]).read_bytes()
if len(subject) > 256 or len(body) > 4096:
    raise SystemExit("bounded mail exceeded its byte budget")
if any(byte < 32 or byte == 127 for byte in subject):
    raise SystemExit("subject contains control bytes")
if any((byte < 32 and byte != 10) or byte == 127 for byte in body):
    raise SystemExit("body contains unsafe control bytes")
if b"X" * 100 in subject or b"X" * 100 in body:
    raise SystemExit("unbounded hostile metadata leaked into Mayor mail")
if b"row_count=1 row_ids=step-1" not in body:
    raise SystemExit("bounded mail lacks row-count/identifier diagnostics")
PY
    run_surface
    [[ "$RUN_RC" -eq 0 && "$(mail_count)" -eq 1 ]] ||
        fail "hostile marker fixed digest did not deduplicate replay"
    assert_no_forbidden_operation
}

test_scan_failure_is_fail_closed() {
    local mode
    for mode in fail malformed; do
        new_case "scan-$mode"
        LIST_MODE=$mode
        run_surface
        unset LIST_MODE
        [[ "$RUN_RC" -eq 75 ]] ||
            fail "$mode scan returned $RUN_RC instead of 75"
        [[ "$(mail_count)" -eq 0 && ! -s "$STATE/update-ids" ]] ||
            fail "$mode scan guessed at notifications or receipts"
        assert_no_forbidden_operation
    done
}

test_empty_scan
test_valid_pair_and_dedup
test_notification_failure_is_retryable
test_receipt_failure_is_retryable
test_partial_contracts_surface_without_recovery
test_malformed_and_duplicate_pairs_surface
test_root_and_convoy_mismatch_surface
test_all_status_and_liveness_independent_surface
test_changed_signature_notifies_again
test_stale_gc_city_cannot_redirect_notification
test_hostile_malformed_metadata_is_bounded
test_scan_failure_is_fail_closed

echo "polecat block surfacing command tests passed"
