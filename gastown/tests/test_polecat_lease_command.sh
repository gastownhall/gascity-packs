#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/polecat-lease/run.sh"
TEST_TMP=$(mktemp -d)
trap 'rm -rf "$TEST_TMP"' EXIT
REAL_GIT=$(command -v git)

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

mkdir -p "$TEST_TMP/bin"
cat >"$TEST_TMP/bin/gc" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

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
                exit 91
                ;;
        esac
    done
    if [[ -n "${FAIL_BD_LIST_ASSIGNEE:-}" &&
          "$assignee" == "$FAIL_BD_LIST_ASSIGNEE" &&
          ( -z "${FAIL_BD_LIST_STATUS:-}" ||
            "$status" == "$FAIL_BD_LIST_STATUS" ) ]]; then
        exit 96
    fi
    if [[ -n "${WRONG_BD_LIST_ASSIGNEE:-}" &&
          "$assignee" == "$WRONG_BD_LIST_ASSIGNEE" &&
          "$status" == "in_progress" ]]; then
        jq '[.beads["workspace-1"]]' "$FAKE_DB"
        exit 0
    fi
    if [[ -n "${DUPLICATE_BD_LIST_ASSIGNEE:-}" &&
          "$assignee" == "$DUPLICATE_BD_LIST_ASSIGNEE" &&
          "$status" == "in_progress" ]]; then
        jq --arg assignee "$assignee" \
            '[.beads["workspace-1"] | .assignee = $assignee]' "$FAKE_DB"
        exit 0
    fi
    jq --arg assignee "$assignee" --arg status "$status" \
        '[.beads[] | select(.assignee == $assignee and .status == $status)]' \
        "$FAKE_DB"
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "show" ]]; then
    id=${3:-}
    if [[ -e "$FAKE_STATE/race-fired" &&
          ! -e "$FAKE_STATE/terminal-authority-drift-fired" ]]; then
        case "${TERMINAL_AUTHORITY_DRIFT:-}:$id" in
            step:submit-1)
                jq '.beads["submit-1"].assignee = "other-runtime"' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                touch "$FAKE_STATE/terminal-authority-drift-fired"
                ;;
            root:root-1)
                jq '.beads["root-1"].metadata["gc.var.binding_prefix"] = "other."' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                touch "$FAKE_STATE/terminal-authority-drift-fired"
                ;;
        esac
    fi
    jq -e --arg id "$id" '[.beads[$id]] | select(.[0] != null)' "$FAKE_DB"
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "update" ]]; then
    id=${3:-}
    jq -e --arg id "$id" '.beads[$id] != null' "$FAKE_DB" >/dev/null
    if [[ -n "${FAIL_ALL_BD_UPDATE_MATCH:-}" &&
          " $* " == *"$FAIL_ALL_BD_UPDATE_MATCH"* ]]; then
        exit 94
    fi
    if [[ -f "$FAKE_STATE/fail-update-once" &&
          " $* " == *"$(<"$FAKE_STATE/fail-update-once")"* ]]; then
        rm -f "$FAKE_STATE/fail-update-once"
        exit 94
    fi
    shift 3
    while (($#)); do
        case "$1" in
            --status=*)
                value=${1#*=}
                jq --arg id "$id" --arg value "$value" \
                    '.beads[$id].status = $value' "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift
                ;;
            --status)
                value=$2
                jq --arg id "$id" --arg value "$value" \
                    '.beads[$id].status = $value' "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            --assignee=*)
                value=${1#*=}
                jq --arg id "$id" --arg value "$value" \
                    '.beads[$id].assignee = $value' "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift
                ;;
            --assignee)
                value=$2
                jq --arg id "$id" --arg value "$value" \
                    '.beads[$id].assignee = $value' "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            --set-metadata)
                key=${2%%=*}
                value=${2#*=}
                jq --arg id "$id" --arg key "$key" --arg value "$value" \
                    '.beads[$id].metadata[$key] =
                        (if $value == "true" then true
                         elif $value == "false" then false
                         else $value
                         end)' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            --unset-metadata)
                key=$2
                jq --arg id "$id" --arg key "$key" \
                    'del(.beads[$id].metadata[$key])' \
                    "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            --append-notes|--notes)
                value=$2
                jq --arg id "$id" --arg value "$value" \
                    '.beads[$id].notes =
                        ((.beads[$id].notes // "") +
                         (if (.beads[$id].notes // "") == "" then "" else "\n" end) +
                         $value)' "$FAKE_DB" >"$FAKE_DB.tmp"
                write_db
                shift 2
                ;;
            *)
                exit 92
                ;;
        esac
    done
    exit 0
fi

if [[ "${1:-}" == "convoy" && "${2:-}" == "status" &&
      "${3:-}" == "convoy-1" && "${4:-}" == "--json" ]]; then
    printf '%s\n' '{"children":[{"id":"source-1"}]}'
    exit 0
fi

if [[ "${1:-}" == "mail" && "${2:-}" == "send" ]]; then
    if [[ -e "$FAKE_STATE/fail-mail-once" ]]; then
        rm -f "$FAKE_STATE/fail-mail-once"
        exit 94
    fi
    touch "$FAKE_STATE/mail-sent"
    exit 0
fi

if [[ "${1:-}" == "runtime" && "${2:-}" == "drain-ack" ]]; then
    if [[ -e "$FAKE_STATE/fail-drain-once" ]]; then
        rm -f "$FAKE_STATE/fail-drain-once"
        exit 94
    fi
    touch "$FAKE_STATE/drained"
    exit 0
fi

exit 93
SH

cat >"$TEST_TMP/bin/git" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "ls-remote" && "${GIT_LS_REMOTE_UNREADABLE:-0}" == "1" ]]; then
    exit 128
fi

if [[ "${1:-}" == "ls-remote" &&
      -n "${GIT_MOVE_BRANCH_AFTER_LS_REMOTE_TO:-}" &&
      ! -e "$FAKE_STATE/ls-remote-branch-move-fired" ]]; then
    output=$("$REAL_GIT" "$@")
    remote_code=$?
    touch "$FAKE_STATE/ls-remote-branch-move-fired"
    "$REAL_GIT" update-ref refs/heads/polecat/source-1 \
        "$GIT_MOVE_BRANCH_AFTER_LS_REMOTE_TO"
    printf '%s\n' "$output"
    exit "$remote_code"
fi

if [[ "${1:-}" == "rebase" && "${GIT_REBASE_RESPONSE_LOST:-0}" == "1" &&
      ! -e "$FAKE_STATE/rebase-response-lost-fired" ]]; then
    touch "$FAKE_STATE/rebase-response-lost-fired"
    "$REAL_GIT" "$@"
    exit 1
fi

if [[ "${1:-}" == "push" ]]; then
    printf '%q ' "$@" >>"$GIT_PUSH_LOG"
    printf '\n' >>"$GIT_PUSH_LOG"
    if [[ -n "${GIT_RACER_WORK:-}" && ! -e "$FAKE_STATE/race-fired" ]]; then
        touch "$FAKE_STATE/race-fired"
        "$REAL_GIT" -C "$GIT_RACER_WORK" push -q origin polecat/source-1
    fi
    if [[ -n "${GIT_REDIRECT_ORIGIN:-}" &&
          ! -e "$FAKE_STATE/redirect-fired" ]]; then
        touch "$FAKE_STATE/redirect-fired"
        "$REAL_GIT" config remote.origin.pushurl "$GIT_REDIRECT_ORIGIN"
    fi
    if [[ "${GIT_PUSH_RESPONSE_LOST:-0}" == "1" &&
          ! -e "$FAKE_STATE/response-lost-fired" ]]; then
        touch "$FAKE_STATE/response-lost-fired"
        "$REAL_GIT" "$@"
        if [[ -n "${GIT_MOVE_BRANCH_AFTER_PUSH_TO:-}" ]]; then
            "$REAL_GIT" update-ref refs/heads/polecat/source-1 \
                "$GIT_MOVE_BRANCH_AFTER_PUSH_TO"
        fi
        exit 1
    fi
    if [[ -n "${GIT_MOVE_BRANCH_AFTER_PUSH_TO:-}" &&
          ! -e "$FAKE_STATE/branch-move-fired" ]]; then
        touch "$FAKE_STATE/branch-move-fired"
        "$REAL_GIT" "$@"
        push_code=$?
        "$REAL_GIT" update-ref refs/heads/polecat/source-1 \
            "$GIT_MOVE_BRANCH_AFTER_PUSH_TO"
        exit "$push_code"
    fi
fi

if [[ "${1:-}" == "update-ref" && "${2:-}" == "--stdin" ]]; then
    payload=$(cat)
    if [[ -n "${GIT_TX_BARRIER_MATCH:-}" &&
          "$payload" == *"$GIT_TX_BARRIER_MATCH"* ]]; then
        mkdir -p "$GIT_TX_BARRIER_DIR"
        touch "$GIT_TX_BARRIER_DIR/$$"
        barrier_loops=0
        while [[ "$(find "$GIT_TX_BARRIER_DIR" -type f | wc -l)" -lt 2 ]]; do
            barrier_loops=$((barrier_loops + 1))
            [[ "$barrier_loops" -lt 200 ]] || exit 95
            sleep 0.05
        done
    fi
    if [[ -n "${GIT_FAIL_TX_MATCH:-}" &&
          "$payload" == *"$GIT_FAIL_TX_MATCH"* &&
          ! -e "$FAKE_STATE/transaction-failure-fired" ]]; then
        touch "$FAKE_STATE/transaction-failure-fired"
        exit 1
    fi
    if [[ "${GIT_FAIL_CLEANUP_ONCE:-0}" == "1" &&
          "$payload" == *"delete refs/gascity/polecat-push-leases/"* &&
          ! -e "$FAKE_STATE/cleanup-failure-fired" ]]; then
        touch "$FAKE_STATE/cleanup-failure-fired"
        exit 1
    fi
    printf '%s\n' "$payload" | exec "$REAL_GIT" "$@"
fi

exec "$REAL_GIT" "$@"
SH
chmod +x "$TEST_TMP/bin/gc" "$TEST_TMP/bin/git"

CASE_DIR=""
ORIGIN=""
SEED=""
CITY_ROOT=""
RIG_ROOT=""
WORK=""
STATE=""
DB=""
PUSH_LOG=""
OUTPUT=""
RUN_RC=0

new_case() {
    local name=$1 rejection=${2:-false}
    CASE_DIR="$TEST_TMP/$name"
    ORIGIN="$CASE_DIR/origin.git"
    SEED="$CASE_DIR/seed"
    CITY_ROOT="$CASE_DIR/city"
    RIG_ROOT="$CASE_DIR/rig"
    WORK="$CITY_ROOT/.gc/worktrees/rig/artifacts/worktrees/source-1"
    STATE="$CASE_DIR/state"
    DB="$STATE/db.json"
    PUSH_LOG="$STATE/push.log"
    OUTPUT="$STATE/output"

    mkdir -p "$STATE"
    "$REAL_GIT" init --bare -q "$ORIGIN"
    "$REAL_GIT" init -q -b main "$SEED"
    "$REAL_GIT" -C "$SEED" config user.name "Lease Test"
    "$REAL_GIT" -C "$SEED" config user.email "lease-test@example.invalid"
    printf 'base\n' >"$SEED/base.txt"
    "$REAL_GIT" -C "$SEED" add base.txt
    "$REAL_GIT" -C "$SEED" commit -q -m base
    "$REAL_GIT" -C "$SEED" remote add origin "$ORIGIN"
    "$REAL_GIT" -C "$SEED" push -q -u origin main
    "$REAL_GIT" --git-dir="$ORIGIN" symbolic-ref HEAD refs/heads/main

    "$REAL_GIT" -C "$SEED" switch -q -c polecat/source-1
    printf 'feature\n' >"$SEED/feature.txt"
    "$REAL_GIT" -C "$SEED" add feature.txt
    "$REAL_GIT" -C "$SEED" commit -q -m feature
    "$REAL_GIT" -C "$SEED" push -q -u origin polecat/source-1

    "$REAL_GIT" clone -q "$ORIGIN" "$RIG_ROOT"
    "$REAL_GIT" -C "$RIG_ROOT" config user.name "Lease Test"
    "$REAL_GIT" -C "$RIG_ROOT" config user.email "lease-test@example.invalid"
    mkdir -p "$(dirname "$WORK")"
    "$REAL_GIT" -C "$RIG_ROOT" worktree add -q \
        -b polecat/source-1 "$WORK" origin/polecat/source-1

    if [[ "$rejection" == "true" ]]; then
        "$REAL_GIT" -C "$SEED" switch -q main
        printf 'new base\n' >"$SEED/new-base.txt"
        "$REAL_GIT" -C "$SEED" add new-base.txt
        "$REAL_GIT" -C "$SEED" commit -q -m new-base
        "$REAL_GIT" -C "$SEED" push -q origin main
    fi

    jq -n \
      --arg rejection "$([[ "$rejection" == "true" ]] && printf rejected)" \
      --arg artifact_dir "$WORK" '
      {
        beads: {
          "source-1": {
            id: "source-1", status: "open", assignee: "",
            metadata: ({branch: "polecat/source-1", artifact_dir: $artifact_dir} +
                       (if $rejection == "" then {}
                        else {rejection_reason: $rejection} end))
          },
          "workspace-1": {
            id: "workspace-1", status: "in_progress", assignee: "actor-1",
            metadata: {
              "gc.step_ref": "mol-polecat-work.workspace-setup",
              "gc.root_bead_id": "root-1"
            }
          },
          "submit-1": {
            id: "submit-1", status: "in_progress", assignee: "actor-1",
            metadata: {
              "gc.step_ref": "mol-polecat-work.submit-and-exit",
              "gc.root_bead_id": "root-1"
            }
          },
          "root-1": {
            id: "root-1", status: "in_progress", assignee: "",
            metadata: {
              "gc.kind": "workflow",
              "gc.formula_contract": "graph.v2",
              "gc.input_convoy_id": "convoy-1",
              "gc.var.base_branch": "main",
              "gc.var.rig_name": "rig",
              "gc.var.binding_prefix": ""
            }
          }
        }
      }' >"$DB"
    : >"$PUSH_LOG"
    : >"$STATE/gc.log"
}

move_case_worktree() {
    local destination=$1
    mkdir -p "$(dirname "$destination")"
    "$REAL_GIT" -C "$RIG_ROOT" worktree move "$WORK" "$destination"
    WORK=$destination
    jq --arg path "$WORK" \
        '.beads["source-1"].metadata.artifact_dir = $path' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
}

invoke_lease() {
    local action=$1
    shift
    (
        cd "$WORK"
        PATH="$TEST_TMP/bin:$PATH" \
        GC_BIN="$TEST_TMP/bin/gc" \
        GC_CITY_PATH="$CITY_ROOT" \
        GC_RIG=rig \
        GC_RIG_ROOT="$RIG_ROOT" \
        BEADS_ACTOR="${LEASE_BEADS_ACTOR-actor-1}" \
        GC_SESSION_NAME="${LEASE_GC_SESSION_NAME-}" \
        GC_SESSION_ID="${LEASE_GC_SESSION_ID-}" \
        GC_ALIAS="${LEASE_GC_ALIAS-}" \
        GC_AGENT="${LEASE_GC_AGENT-}" \
        FAKE_DB="$DB" \
        FAKE_STATE="$STATE" \
        FAKE_GC_LOG="$STATE/gc.log" \
        WRONG_BD_LIST_ASSIGNEE="${WRONG_BD_LIST_ASSIGNEE:-}" \
        DUPLICATE_BD_LIST_ASSIGNEE="${DUPLICATE_BD_LIST_ASSIGNEE:-}" \
        TERMINAL_AUTHORITY_DRIFT="${TERMINAL_AUTHORITY_DRIFT:-}" \
        GIT_PUSH_LOG="$PUSH_LOG" \
        REAL_GIT="$REAL_GIT" \
        "$COMMAND" "$action" \
            --source source-1 \
            --convoy convoy-1 \
            --base main \
            --branch polecat/source-1 \
            --witness "${LEASE_WITNESS:-rig/witness}" \
            "$@"
    )
}

run_lease() {
    set +e
    invoke_lease "$@" >"$OUTPUT" 2>&1
    RUN_RC=$?
    set -e
}

namespace_count() {
    "$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-push-leases | wc -l
}

remote_feature_oid() {
    "$REAL_GIT" --git-dir="$ORIGIN" rev-parse refs/heads/polecat/source-1
}

local_feature_oid() {
    "$REAL_GIT" -C "$WORK" rev-parse refs/heads/polecat/source-1
}

assert_no_unconditional_force() {
    ! rg -n '(^|[[:space:]])(--force|-f)([[:space:]]|$)' "$PUSH_LOG" >/dev/null ||
        fail "unconditional force option was used"
}

prepare_rebased() {
    local name=$1
    new_case "$name" true
    ORIGINAL_REMOTE=$(remote_feature_oid)
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "$name: workspace recovery failed: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "$name: rebased namespace does not contain five refs"
    [[ "$(jq -r '.beads["source-1"].metadata.rejection_reason // ""' "$DB")" == "" ]] ||
        fail "$name: rejection metadata was not cleared after published rebase"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_state' "$DB")" == "rebased" ]] ||
        fail "$name: rebased metadata mirror did not verify"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_manual_pending | type' "$DB")" == "boolean" ]] ||
        fail "$name: fake bd did not preserve real boolean metadata typing"
}

test_normal_push() {
    new_case normal false
    printf 'normal update\n' >>"$WORK/feature.txt"
    "$REAL_GIT" -C "$WORK" add feature.txt
    "$REAL_GIT" -C "$WORK" commit -q -m normal-update
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 ]] || fail "normal push failed: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "normal push did not publish the exact local branch"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "normal push unexpectedly created rejection lease refs"
    ! rg -n -- '--force-with-lease' "$PUSH_LOG" >/dev/null ||
        fail "normal push unexpectedly used force-with-lease"
    assert_no_unconditional_force
}

test_rebased_exact_lease_push() {
    prepare_rebased rebased-push
    printf 'review fix\n' >>"$WORK/feature.txt"
    "$REAL_GIT" -C "$WORK" add feature.txt
    "$REAL_GIT" -C "$WORK" commit -q -m review-fix
    SUBMIT=$(local_feature_oid)
    : >"$PUSH_LOG"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "leased submit failed: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$SUBMIT" ]] ||
        fail "leased submit did not publish frozen submit"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "verified leased submit did not clean refs"
    [[ "$(jq -r '[.beads["source-1"].metadata |
        to_entries[] | select(.key | startswith("polecat_push_lease_"))] |
        length' "$DB")" -eq 0 ]] ||
        fail "verified leased submit did not clear mirror metadata"
    rg -n -- "--force-with-lease=refs/heads/polecat/source-1:$ORIGINAL_REMOTE" \
        "$PUSH_LOG" >/dev/null ||
        fail "leased submit did not use exact expected SHA"
    rg -n -- 'refs/gascity/polecat-push-leases/[0-9a-f]+/submit:refs/heads/polecat/source-1' \
        "$PUSH_LOG" >/dev/null ||
        fail "leased submit did not push the immutable submit ref"
    assert_no_unconditional_force
}

test_rejected_auto_push_false_stops_before_freeze() {
    prepare_rebased rejected-no-push
    BEFORE=$(remote_feature_oid)
    run_lease submit --auto-push false
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "rejected auto_push=false did not stop safely: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$BEFORE" ]] ||
        fail "rejected auto_push=false changed the remote"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "rejected auto_push=false froze submit or lost recovery refs"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_state' "$DB")" == "rebased" ]] ||
        fail "rejected auto_push=false changed the rebased mirror phase"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "rejected auto_push=false closed the only authorized Graph step"
    [[ ! -e "$STATE/drained" ]] ||
        fail "rejected auto_push=false drained the live recovery step"
}

make_racer() {
    RACER="$CASE_DIR/racer"
    "$REAL_GIT" clone -q "$ORIGIN" "$RACER"
    "$REAL_GIT" -C "$RACER" config user.name "Lease Racer"
    "$REAL_GIT" -C "$RACER" config user.email "lease-racer@example.invalid"
    "$REAL_GIT" -C "$RACER" switch -q polecat/source-1
    printf 'race\n' >"$RACER/race.txt"
    "$REAL_GIT" -C "$RACER" add race.txt
    "$REAL_GIT" -C "$RACER" commit -q -m race
    RACER_OID=$("$REAL_GIT" -C "$RACER" rev-parse HEAD)
}

test_remote_race_terminalizes() {
    prepare_rebased remote-race
    make_racer
    : >"$PUSH_LOG"
    set +e
    (
        export GIT_RACER_WORK="$RACER"
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    race_rc=$?
    set -e
    [[ "$race_rc" -eq 64 ]] ||
        fail "remote race did not return hard-conflict status: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$RACER_OID" ]] ||
        fail "remote race overwrote competing work"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "remote race did not block source"
    [[ "$(jq -r '.beads["source-1"].assignee' "$DB")" == "" ]] ||
        fail "remote race did not leave source unassigned"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "closed" ]] ||
        fail "remote race did not close exact submit step"
    [[ "$(jq -r '.beads["submit-1"].metadata["gc.outcome"]' "$DB")" == "fail" ]] ||
        fail "remote race did not record failed Graph outcome"
    [[ -e "$STATE/mail-sent" && -e "$STATE/drained" ]] ||
        fail "remote race did not notify and drain after terminalization"
    [[ "$(namespace_count)" -eq 6 ]] ||
        fail "remote race did not preserve all recovery refs"
    source_line=$(rg -n '^gc bd update source-1 .*--status=blocked' \
        "$STATE/gc.log" | cut -d: -f1) ||
        fail "remote race did not log source terminalization"
    mail_line=$(rg -n '^gc mail send rig/witness .*--notify' \
        "$STATE/gc.log" | cut -d: -f1) ||
        fail "remote race did not log durable Witness notification"
    step_line=$(rg -n '^gc bd update submit-1 .*gc\.outcome=fail' \
        "$STATE/gc.log" | cut -d: -f1) ||
        fail "remote race did not log failed submit-step outcome"
    drain_line=$(rg -n '^gc runtime drain-ack' \
        "$STATE/gc.log" | cut -d: -f1) ||
        fail "remote race did not log drain acknowledgement"
    [[ "$source_line" -lt "$mail_line" && "$mail_line" -lt "$step_line" &&
       "$step_line" -lt "$drain_line" ]] ||
        fail "hard conflict did not order source, durable witness, step, then drain"
    assert_no_unconditional_force
}

test_terminalization_revalidates_graph_authority() {
    local drift race_rc

    for drift in step root; do
        prepare_rebased "terminal-${drift}-drift"
        make_racer
        : >"$PUSH_LOG"
        set +e
        (
            export GIT_RACER_WORK="$RACER"
            export TERMINAL_AUTHORITY_DRIFT="$drift"
            run_lease submit --auto-push true
            exit "$RUN_RC"
        )
        race_rc=$?
        set -e

        [[ "$race_rc" -eq 64 ]] ||
            fail "$drift drift conflict returned $race_rc instead of 64: $(<"$OUTPUT")"
        [[ -e "$STATE/terminal-authority-drift-fired" ]] ||
            fail "$drift drift fixture did not fire before terminalization"
        [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" &&
           "$(jq -r '.beads["source-1"].assignee' "$DB")" == "" ]] ||
            fail "$drift drift mutated source state from stale Graph authority"
        ! rg -q '^gc bd update source-1 .*--status=blocked' "$STATE/gc.log" ||
            fail "$drift drift attempted to block the source"
        [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
            fail "$drift drift notified or drained without current Graph authority"
        rg -q 'Graph authority changed before hard terminalization' "$OUTPUT" ||
            fail "$drift drift did not report the authority failure"
    done
}

test_unreadable_is_indeterminate() {
    new_case unreadable true
    set +e
    (
        export GIT_LS_REMOTE_UNREADABLE=1
        run_lease workspace
        exit "$RUN_RC"
    )
    unreadable_rc=$?
    set -e
    [[ "$unreadable_rc" -eq 75 ]] ||
        fail "unreadable remote was not indeterminate: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "unreadable remote mutated source state"
    [[ "$(jq -r '.beads["workspace-1"].status' "$DB")" == "in_progress" ]] ||
        fail "unreadable remote closed the workflow step"
    [[ ! -e "$STATE/drained" ]] ||
        fail "unreadable remote drained the worker"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "unreadable remote created an authorization lease"
}

test_capture_mirror_crash_recovery() {
    new_case capture-mirror-crash true
    printf '%s' 'polecat_push_lease_ref=' >"$STATE/fail-update-once"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "capture mirror failure was not indeterminate: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 4 ]] ||
        fail "capture mirror failure did not preserve four authoritative refs"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_ref // ""' "$DB")" == "" ]] ||
        fail "capture mirror failure partially wrote metadata"

    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "capture mirror restart did not recover: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "capture mirror restart did not publish rebase state"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_state' "$DB")" == "rebased" ]] ||
        fail "capture mirror restart did not reconstruct metadata"
}

test_rebase_mirror_crash_recovery() {
    new_case rebase-mirror-crash true
    printf '%s' 'polecat_push_lease_state=rebased' >"$STATE/fail-update-once"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "rebase mirror failure was not indeterminate: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "rebase mirror failure did not preserve published rebase refs"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_state' "$DB")" == "captured" ]] ||
        fail "rebase mirror failure did not leave the prior durable phase"

    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "rebase mirror restart did not recover: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_state' "$DB")" == "rebased" ]] ||
        fail "rebase mirror restart did not advance the stale mirror"
    [[ "$(jq -r '.beads["source-1"].metadata.rejection_reason // ""' "$DB")" == "" ]] ||
        fail "rebase mirror restart did not finish source metadata"
}

test_submit_mirror_crash_recovery() {
    prepare_rebased submit-mirror-crash
    printf '%s' 'polecat_push_lease_state=submit-frozen' >"$STATE/fail-update-once"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "submit mirror failure was not indeterminate: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 6 ]] ||
        fail "submit mirror failure did not preserve the frozen submit ref"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_state' "$DB")" == "rebased" ]] ||
        fail "submit mirror failure did not leave the prior durable phase"

    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "submit mirror restart did not recover: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "submit mirror restart did not publish the frozen branch"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "submit mirror restart did not clean refs"
}

test_push_response_lost_recovery() {
    prepare_rebased push-response-lost
    set +e
    (
        export GIT_PUSH_RESPONSE_LOST=1
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    response_rc=$?
    set -e
    [[ "$response_rc" -eq 0 ]] ||
        fail "lost push response was not recovered: $(<"$OUTPUT")"
    [[ -e "$STATE/response-lost-fired" ]] ||
        fail "lost-response fixture did not fire"
    [[ "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "lost-response recovery did not verify the remote"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "lost-response recovery did not clean refs"
}

test_cleanup_transaction_retry() {
    prepare_rebased cleanup-transaction
    set +e
    (
        export GIT_FAIL_CLEANUP_ONCE=1
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    cleanup_rc=$?
    set -e
    [[ "$cleanup_rc" -eq 75 ]] ||
        fail "cleanup transaction failure was not indeterminate: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 6 ]] ||
        fail "failed cleanup transaction changed authoritative refs"
    [[ "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "cleanup failure fixture did not occur after verified push"

    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "cleanup transaction retry did not recover: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "cleanup transaction retry left refs"
}

test_metadata_cleanup_restart() {
    prepare_rebased metadata-cleanup
    printf '%s' '--unset-metadata polecat_push_lease_ref' >"$STATE/fail-update-once"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "metadata cleanup failure was not indeterminate: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "metadata cleanup failure did not occur after atomic ref cleanup"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_submit_sha // ""' "$DB")" != "" ]] ||
        fail "metadata cleanup fixture did not preserve the stale mirror"

    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "metadata-only cleanup restart did not recover: $(<"$OUTPUT")"
    [[ "$(jq -r '[.beads["source-1"].metadata |
        to_entries[] | select(.key | startswith("polecat_push_lease_"))] |
        length' "$DB")" -eq 0 ]] ||
        fail "metadata-only cleanup restart left mirror keys"
}

test_unpublished_rebase_requires_explicit_publish() {
    new_case unpublished-rebase true
    set +e
    (
        export GIT_REBASE_RESPONSE_LOST=1
        run_lease workspace
        exit "$RUN_RC"
    )
    rebase_rc=$?
    set -e
    [[ "$rebase_rc" -eq 75 ]] ||
        fail "lost rebase response was not indeterminate: $(<"$OUTPUT")"
    [[ -e "$STATE/rebase-response-lost-fired" ]] ||
        fail "lost-rebase-response fixture did not fire"
    [[ "$(namespace_count)" -eq 4 ]] ||
        fail "unpublished rebase changed the captured lease phase"
    [[ -z "$("$REAL_GIT" -C "$WORK" branch --show-current)" ]] ||
        fail "unpublished rebase was not left detached"

    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "restart guessed at an unpublished rebase candidate: $(<"$OUTPUT")"
    rg -n 'publish-rebase explicitly' "$OUTPUT" >/dev/null ||
        fail "restart did not explain explicit rebase publication"

    run_lease publish-rebase
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "explicit rebase publication failed: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "explicit rebase publication did not create rebased phase"
    [[ "$("$REAL_GIT" -C "$WORK" branch --show-current)" == "polecat/source-1" ]] ||
        fail "explicit rebase publication did not restore the branch"
}

test_frozen_push_url() {
    prepare_rebased frozen-push-url
    REDIRECT="$CASE_DIR/redirect.git"
    "$REAL_GIT" init --bare -q "$REDIRECT"
    set +e
    (
        export GIT_REDIRECT_ORIGIN="$REDIRECT"
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    redirect_rc=$?
    set -e
    [[ "$redirect_rc" -eq 0 ]] ||
        fail "frozen push URL submit failed: $(<"$OUTPUT")"
    [[ -e "$STATE/redirect-fired" ]] ||
        fail "push URL redirection fixture did not fire"
    [[ "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "origin config race redirected the frozen push"
    ! "$REAL_GIT" --git-dir="$REDIRECT" show-ref --verify --quiet \
        refs/heads/polecat/source-1 ||
        fail "mutable origin pushurl received the frozen push"
}

advance_remote() {
    make_racer
    "$REAL_GIT" -C "$RACER" push -q origin polecat/source-1
    [[ "$(remote_feature_oid)" == "$RACER_OID" ]] ||
        fail "remote-advance fixture did not publish racer"
}

test_mail_failure_retries_before_step_close() {
    prepare_rebased mail-retry
    advance_remote
    touch "$STATE/fail-mail-once"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "mail failure conflict did not return hard status: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "mail failure did not preserve blocked source"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "step closed before durable mail succeeded"
    [[ ! -e "$STATE/drained" ]] ||
        fail "mail failure drained before terminalization completed"

    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "mail retry did not retain hard status: $(<"$OUTPUT")"
    [[ -e "$STATE/mail-sent" && -e "$STATE/drained" ]] ||
        fail "mail retry did not complete notification and drain"
    [[ "$(jq -r '.beads["submit-1"].metadata["gc.failure_reason"]' "$DB")" == "push_lease_conflict" ]] ||
        fail "mail retry did not close the exact step with a reason"
}

test_closed_step_drain_retry() {
    prepare_rebased drain-retry
    advance_remote
    touch "$STATE/fail-drain-once"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "drain failure did not request an indeterminate retry: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "closed" ]] ||
        fail "drain failure fixture did not first close the exact step"
    [[ ! -e "$STATE/drained" ]] ||
        fail "drain failure fixture unexpectedly acknowledged drain"

    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "closed-step terminal recovery did not retain hard status: $(<"$OUTPUT")"
    [[ -e "$STATE/drained" ]] ||
        fail "closed-step terminal recovery did not retry drain"
}

test_mirror_tamper_is_hard() {
    prepare_rebased mirror-tamper
    jq '.beads["source-1"].metadata.polecat_push_lease_expected_sha =
        "0000000000000000000000000000000000000000"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "lease mirror tamper was not hard: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "lease mirror tamper did not block source"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "lease mirror tamper changed authoritative refs"
}

lease_ref_with_suffix() {
    local suffix=$1
    "$REAL_GIT" -C "$WORK" for-each-ref --format='%(refname)' \
        refs/gascity/polecat-push-leases | rg "/$suffix$"
}

test_auto_push_authority() {
    new_case auto-push-authority false
    jq '.beads["source-1"].metadata.auto_push = false' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    BEFORE=$(remote_feature_oid)
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "caller overrode source auto_push=false: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$BEFORE" ]] ||
        fail "auto_push authorization failure changed the remote"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] &&
        [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "auto_push authorization failure terminalized Graph state"
    [[ ! -e "$STATE/drained" ]] ||
        fail "auto_push authorization failure drained the worker"
}

test_graph_base_authority() {
    new_case graph-base-authority false
    jq '.beads["root-1"].metadata["gc.var.base_branch"] = "release"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "caller base was not bound to the Graph root: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "Graph base authorization failure mutated source"
}

test_artifact_dir_authority() {
    new_case artifact-dir-authority false
    jq --arg path "$SEED" '.beads["source-1"].metadata.artifact_dir = $path' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "command accepted a different source artifact_dir: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "artifact_dir authorization failure mutated source"
}

test_legacy_work_dir_is_not_lease_authority() {
    new_case legacy-work-dir-not-authority false
    jq '.beads["source-1"].metadata |=
        (.work_dir = .artifact_dir | del(.artifact_dir))' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "lease accepted deprecated work_dir authority: $(<"$OUTPUT")"
    rg -q 'source metadata has no recorded artifact_dir' "$OUTPUT" ||
        fail "missing artifact_dir did not produce a precise diagnostic"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "missing artifact_dir mutated source state"
}

assert_artifact_binding_rejected() {
    local label=$1
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "$label artifact binding returned $RUN_RC instead of 75: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "$label artifact binding created lease authority"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "$label artifact binding mutated source state"
}

test_artifact_dir_containment_matrix() {
    local destination original redirected provider legacy

    new_case artifact-cross-city false
    destination="$CASE_DIR/other-city/.gc/worktrees/rig/artifacts/worktrees/source-1"
    move_case_worktree "$destination"
    assert_artifact_binding_rejected "same-repository cross-city"

    new_case artifact-cross-rig false
    destination="$CITY_ROOT/.gc/worktrees/other/artifacts/worktrees/source-1"
    move_case_worktree "$destination"
    assert_artifact_binding_rejected "same-city cross-rig"

    new_case artifact-wrong-bead false
    destination="$CITY_ROOT/.gc/worktrees/rig/artifacts/worktrees/source-other"
    move_case_worktree "$destination"
    assert_artifact_binding_rejected "wrong-bead"

    new_case artifact-wrong-namespace false
    destination="$CITY_ROOT/.gc/worktrees/rig/refinery/worktrees/source-1"
    move_case_worktree "$destination"
    assert_artifact_binding_rejected "wrong-namespace"

    new_case artifact-provider-home false
    destination="$CITY_ROOT/.gc/worktrees/rig/polecats/gastown.nux"
    move_case_worktree "$destination"
    assert_artifact_binding_rejected "provider-home"

    new_case artifact-symlink-redirect false
    original=$WORK
    redirected="$CASE_DIR/redirected/worktrees/source-1"
    mkdir -p "$(dirname "$redirected")"
    "$REAL_GIT" -C "$RIG_ROOT" worktree move "$original" "$redirected"
    ln -s "$redirected" "$original"
    assert_artifact_binding_rejected "symlink-redirected"

    new_case artifact-foreign-repository false
    "$REAL_GIT" -C "$RIG_ROOT" worktree remove "$WORK"
    "$REAL_GIT" init -q -b polecat/source-1 "$WORK"
    "$REAL_GIT" -C "$WORK" config user.name "Foreign Lease Test"
    "$REAL_GIT" -C "$WORK" config user.email "foreign@example.invalid"
    printf 'foreign\n' >"$WORK/foreign.txt"
    "$REAL_GIT" -C "$WORK" add foreign.txt
    "$REAL_GIT" -C "$WORK" commit -q -m foreign
    assert_artifact_binding_rejected "foreign-repository"

    new_case artifact-valid-provider-nested false
    original=$WORK
    provider="$CITY_ROOT/.gc/worktrees/rig/polecats/gastown.nux"
    legacy="$provider/worktrees/source-1"
    "$REAL_GIT" -C "$RIG_ROOT" worktree remove "$original"
    mkdir -p "$(dirname "$provider")"
    "$REAL_GIT" -C "$RIG_ROOT" worktree add -q \
        -b provider-home "$provider" origin/main
    mkdir -p "$(dirname "$legacy")"
    "$REAL_GIT" -C "$RIG_ROOT" worktree add -q \
        "$legacy" polecat/source-1
    WORK=$legacy
    jq --arg path "$WORK" \
        '.beads["source-1"].metadata.artifact_dir = $path' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "valid provider-nested artifact_dir was rejected: $(<"$OUTPUT")"
}

test_runtime_identity_deduplication() {
    new_case runtime-identity-deduplication false
    LEASE_GC_SESSION_NAME=actor-1
    LEASE_GC_SESSION_ID=actor-1
    LEASE_GC_ALIAS=actor-1
    LEASE_GC_AGENT=actor-1
    run_lease workspace
    unset LEASE_GC_SESSION_NAME LEASE_GC_SESSION_ID LEASE_GC_ALIAS LEASE_GC_AGENT
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "deduplicated runtime identity lookup failed: $(<"$OUTPUT")"
    [[ "$(rg -c -F \
        'gc bd list --assignee actor-1 --status=in_progress ' \
        "$STATE/gc.log")" -eq 1 ]] ||
        fail "equivalent runtime identities issued duplicate live-step queries"
}

test_runtime_identity_query_rows_are_exact() {
    new_case runtime-identity-wrong-assignee false
    LEASE_GC_ALIAS=actor-alias
    WRONG_BD_LIST_ASSIGNEE=actor-alias
    run_lease workspace
    unset LEASE_GC_ALIAS WRONG_BD_LIST_ASSIGNEE
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "wrong-assignee list response returned $RUN_RC instead of 75"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "wrong-assignee list response created lease authority"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "wrong-assignee list response mutated source state"

    new_case runtime-identity-duplicate-id false
    LEASE_GC_ALIAS=actor-alias
    DUPLICATE_BD_LIST_ASSIGNEE=actor-alias
    run_lease workspace
    unset LEASE_GC_ALIAS DUPLICATE_BD_LIST_ASSIGNEE
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "duplicate aggregate step id returned $RUN_RC instead of 75"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "duplicate aggregate step id created lease authority"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "duplicate aggregate step id mutated source state"
}

test_live_graph_state_is_active_and_outcome_free() {
    new_case live-step-preexisting-outcome false
    jq '.beads["workspace-1"].metadata["gc.outcome"] = "pass"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "preexisting live-step outcome returned $RUN_RC instead of 75"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "preexisting live-step outcome created lease authority"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "preexisting live-step outcome mutated source state"

    new_case terminal-live-root false
    jq '.beads["root-1"].status = "closed" |
        .beads["root-1"].metadata["gc.outcome"] = "fail"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "terminal target root returned $RUN_RC instead of 75"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "terminal target root created lease authority"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "terminal target root mutated source state"
}

test_alternate_identity_live_and_closed_recovery() {
    LEASE_GC_ALIAS=actor-alias
    prepare_rebased alternate-identity-recovery
    jq '.beads["submit-1"].assignee = "actor-alias"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    advance_remote
    touch "$STATE/fail-drain-once"

    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "alternate live identity did not reach verified drain retry: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "closed" ]] ||
        fail "alternate exact assignee was not used to close the live step"
    [[ ! -e "$STATE/drained" ]] ||
        fail "alternate live identity fixture unexpectedly acknowledged drain"

    run_lease submit --auto-push true
    unset LEASE_GC_ALIAS
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "alternate closed identity was not recovered: $(<"$OUTPUT")"
    [[ -e "$STATE/drained" ]] ||
        fail "alternate closed identity recovery did not retry drain"
}

test_closed_recovery_root_classification() {
    new_case terminal-other-root-recovery false
    jq '.beads["source-1"] |=
          (.status = "blocked" |
           .metadata["gc.routed_to"] = "human" |
           .metadata.polecat_halt_reason = "push_lease_conflict") |
        .beads["workspace-1"] |=
          (.status = "closed" |
           .metadata["gc.outcome"] = "fail" |
           .metadata["gc.failure_class"] = "hard" |
           .metadata["gc.failure_reason"] = "push_lease_conflict") |
        .beads["root-1"] |=
          (.status = "closed" | .metadata["gc.outcome"] = "fail") |
        .beads["root-2"] = {
          id: "root-2", status: "closed", assignee: "",
          metadata: {
            "gc.kind": "workflow",
            "gc.formula_contract": "graph.v2",
            "gc.input_convoy_id": "other-convoy",
            "gc.var.base_branch": "other-base",
            "gc.outcome": "pass"
          }
        } |
        .beads["workspace-2"] = {
          id: "workspace-2", status: "closed", assignee: "actor-1",
          metadata: {
            "gc.step_ref": "mol-polecat-work.workspace-setup",
            "gc.root_bead_id": "root-2",
            "gc.outcome": "fail",
            "gc.failure_class": "hard",
            "gc.failure_reason": "push_lease_conflict"
          }
        }' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "terminal other-convoy history blocked exact recovery: $(<"$OUTPUT")"
    [[ -e "$STATE/drained" ]] ||
        fail "exact closed hard-recovery did not retry drain"

    new_case malformed-history-recovery false
    jq '.beads["source-1"] |=
          (.status = "blocked" |
           .metadata["gc.routed_to"] = "human" |
           .metadata.polecat_halt_reason = "push_lease_conflict") |
        .beads["workspace-1"] |=
          (.status = "closed" |
           .metadata["gc.outcome"] = "fail" |
           .metadata["gc.failure_class"] = "hard" |
           .metadata["gc.failure_reason"] = "push_lease_conflict") |
        .beads["root-2"] = {
          id: "root-2", status: "closed", assignee: "",
          metadata: {
            "gc.kind": "workflow",
            "gc.input_convoy_id": "other-convoy",
            "gc.var.base_branch": "main",
            "gc.outcome": "fail"
          }
        } |
        .beads["workspace-2"] = {
          id: "workspace-2", status: "closed", assignee: "actor-1",
          metadata: {
            "gc.step_ref": "mol-polecat-work.workspace-setup",
            "gc.root_bead_id": "root-2",
            "gc.outcome": "fail",
            "gc.failure_class": "hard",
            "gc.failure_reason": "push_lease_conflict"
          }
        }' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "malformed historical root returned $RUN_RC instead of 75"
    [[ ! -e "$STATE/drained" ]] ||
        fail "malformed historical root recovery acknowledged drain"
}

test_closed_recovery_target_root_state_matrix() {
    local state name

    new_case incoherent-target-root-recovery false
    jq '.beads["source-1"] |=
          (.status = "blocked" |
           .metadata["gc.routed_to"] = "human" |
           .metadata.polecat_halt_reason = "push_lease_conflict") |
        .beads["workspace-1"] |=
          (.status = "closed" |
           .metadata["gc.outcome"] = "fail" |
           .metadata["gc.failure_class"] = "hard" |
           .metadata["gc.failure_reason"] = "push_lease_conflict")' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"

    while IFS= read -r state; do
        name=$(printf '%s' "$state" | jq -r '.name')
        jq --argjson state "$state" '
            .beads["root-1"].status = $state.status |
            if ($state | has("outcome"))
            then .beads["root-1"].metadata["gc.outcome"] = $state.outcome
            else del(.beads["root-1"].metadata["gc.outcome"])
            end' "$DB" >"$DB.tmp"
        mv "$DB.tmp" "$DB"
        rm -f "$STATE/drained"

        run_lease workspace
        [[ "$RUN_RC" -eq 75 ]] ||
            fail "$name target recovery root returned $RUN_RC instead of 75: $(<"$OUTPUT")"
        [[ ! -e "$STATE/drained" ]] ||
            fail "$name target recovery root acknowledged drain"
        [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
            fail "$name target recovery root changed source state"
        [[ "$(jq -r '.beads["workspace-1"].status' "$DB")" == "closed" ]] ||
            fail "$name target recovery root changed closed recovery step"
    done <<'EOF'
{"name":"closed-pass","status":"closed","outcome":"pass"}
{"name":"open-without-outcome","status":"open"}
{"name":"closed-without-outcome","status":"closed"}
{"name":"active-fail","status":"in_progress","outcome":"fail"}
EOF
}

test_ambiguous_runtime_identity_steps_fail_closed() {
    new_case ambiguous-runtime-identities false
    jq '.beads["workspace-2"] = {
          id: "workspace-2",
          status: "in_progress",
          assignee: "actor-alias",
          metadata: {
            "gc.step_ref": "mol-polecat-work.workspace-setup",
            "gc.root_bead_id": "root-1"
          }
        }' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    LEASE_GC_ALIAS=actor-alias
    run_lease workspace
    unset LEASE_GC_ALIAS
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "ambiguous runtime identity steps did not fail closed: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "ambiguous runtime identity steps created lease authority"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "ambiguous runtime identity steps mutated source state"
}

test_unreadable_runtime_identity_query_fails_closed() {
    new_case unreadable-runtime-identity-live false
    LEASE_GC_ALIAS=actor-alias
    export FAIL_BD_LIST_ASSIGNEE=actor-alias
    export FAIL_BD_LIST_STATUS=in_progress
    run_lease workspace
    unset FAIL_BD_LIST_ASSIGNEE FAIL_BD_LIST_STATUS LEASE_GC_ALIAS
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "unreadable live identity query did not fail closed: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "unreadable live identity query created lease authority"

    new_case unreadable-runtime-identity-closed false
    jq '.beads["workspace-1"] |=
        (.status = "closed" |
         .metadata["gc.outcome"] = "fail" |
         .metadata["gc.failure_class"] = "hard" |
         .metadata["gc.failure_reason"] = "push_lease_conflict")' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    LEASE_GC_ALIAS=actor-alias
    export FAIL_BD_LIST_ASSIGNEE=actor-alias
    export FAIL_BD_LIST_STATUS=closed
    run_lease workspace
    unset FAIL_BD_LIST_ASSIGNEE FAIL_BD_LIST_STATUS LEASE_GC_ALIAS
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "unreadable closed identity query did not fail closed: $(<"$OUTPUT")"
    [[ ! -e "$STATE/drained" ]] ||
        fail "unreadable closed identity query acknowledged drain"
}

test_witness_authority() {
    new_case witness-authority false
    set +e
    (
        export LEASE_WITNESS=mayor/
        run_lease workspace
        exit "$RUN_RC"
    )
    witness_rc=$?
    set -e
    [[ "$witness_rc" -eq 75 ]] ||
        fail "caller-selected witness target was accepted: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "witness authorization failure mutated source"
    [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
        fail "witness authorization failure notified or drained"
}

test_unchanged_transaction_failures() {
    new_case capture-transaction-failure true
    set +e
    (
        export GIT_FAIL_TX_MATCH="/context "
        run_lease workspace
        exit "$RUN_RC"
    )
    capture_rc=$?
    set -e
    [[ "$capture_rc" -eq 75 && "$(namespace_count)" -eq 0 ]] ||
        fail "failed capture transaction was not an unchanged indeterminate state: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "failed capture transaction blocked source"

    new_case publish-transaction-failure true
    set +e
    (
        export GIT_FAIL_TX_MATCH="/rebased "
        run_lease workspace
        exit "$RUN_RC"
    )
    publish_rc=$?
    set -e
    [[ "$publish_rc" -eq 75 && "$(namespace_count)" -eq 4 ]] ||
        fail "failed publish transaction did not preserve captured state: $(<"$OUTPUT")"
    run_lease publish-rebase
    [[ "$RUN_RC" -eq 0 && "$(namespace_count)" -eq 5 ]] ||
        fail "failed publish transaction was not explicitly recoverable: $(<"$OUTPUT")"

    prepare_rebased freeze-transaction-failure
    set +e
    (
        export GIT_FAIL_TX_MATCH="/submit "
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    freeze_rc=$?
    set -e
    [[ "$freeze_rc" -eq 75 && "$(namespace_count)" -eq 5 ]] ||
        fail "failed freeze transaction did not preserve rebased state: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "failed freeze transaction blocked source"
}

test_leased_remote_missing_is_hard() {
    prepare_rebased leased-remote-missing
    "$REAL_GIT" --git-dir="$ORIGIN" update-ref -d \
        refs/heads/polecat/source-1
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "missing leased remote was not hard: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "missing leased remote did not block source"
    [[ -e "$STATE/mail-sent" && -e "$STATE/drained" ]] ||
        fail "missing leased remote did not terminalize and drain"
    [[ "$(namespace_count)" -eq 6 ]] ||
        fail "missing leased remote did not preserve frozen recovery refs"
}

test_context_ref_mismatch_is_hard() {
    prepare_rebased context-mismatch
    context_ref=$(lease_ref_with_suffix context)
    wrong_context=$(printf 'wrong-context\n' |
        "$REAL_GIT" -C "$WORK" hash-object -w --stdin)
    "$REAL_GIT" -C "$WORK" update-ref "$context_ref" "$wrong_context"
    run_lease workspace
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "authoritative context mismatch was not hard: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "authoritative context mismatch did not block source"
}

test_symbolic_lease_ref_is_hard_and_preserved() {
    prepare_rebased symbolic-lease-ref
    expected_ref=$(lease_ref_with_suffix expected)
    expected_oid=$("$REAL_GIT" -C "$WORK" rev-parse "$expected_ref")
    helper_ref=refs/gascity/test-symbolic-target
    "$REAL_GIT" -C "$WORK" update-ref "$helper_ref" "$expected_oid"
    "$REAL_GIT" -C "$WORK" update-ref -d "$expected_ref"
    "$REAL_GIT" -C "$WORK" symbolic-ref "$expected_ref" "$helper_ref"
    run_lease workspace
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "symbolic lease authority was not hard: $(<"$OUTPUT")"
    [[ "$("$REAL_GIT" -C "$WORK" rev-parse "$helper_ref")" == "$expected_oid" ]] ||
        fail "symbolic-ref handling mutated its referent"
    [[ "$("$REAL_GIT" -C "$WORK" symbolic-ref "$expected_ref")" == "$helper_ref" ]] ||
        fail "symbolic lease ref was destructively dereferenced"
}

test_normal_branch_movement_is_indeterminate() {
    new_case normal-branch-move false
    printf 'normal update\n' >>"$WORK/feature.txt"
    "$REAL_GIT" -C "$WORK" add feature.txt
    "$REAL_GIT" -C "$WORK" commit -q -m normal-update
    pushed_oid=$(local_feature_oid)
    move_to=$("$REAL_GIT" -C "$WORK" rev-parse refs/remotes/origin/main)
    set +e
    (
        export GIT_MOVE_BRANCH_AFTER_PUSH_TO="$move_to"
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    move_rc=$?
    set -e
    [[ "$move_rc" -eq 75 ]] ||
        fail "normal branch movement after push was accepted: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$pushed_oid" ]] ||
        fail "normal branch movement fixture did not publish the frozen oid"
    [[ "$(local_feature_oid)" == "$move_to" ]] ||
        fail "normal branch movement fixture did not move the local ref"

    new_case already-equal-branch-move false
    move_to=$("$REAL_GIT" -C "$WORK" rev-parse refs/remotes/origin/main)
    set +e
    (
        export GIT_MOVE_BRANCH_AFTER_LS_REMOTE_TO="$move_to"
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    equal_move_rc=$?
    set -e
    [[ "$equal_move_rc" -eq 75 ]] ||
        fail "already-equal branch movement was accepted: $(<"$OUTPUT")"
}

wait_for_barrier_participant() {
    local barrier=$1 loops=0
    while [[ "$(find "$barrier" -type f 2>/dev/null | wc -l)" -lt 1 ]]; do
        loops=$((loops + 1))
        [[ "$loops" -lt 200 ]] ||
            fail "timed out waiting for first command at transaction barrier"
        sleep 0.05
    done
}

test_command_capture_and_publish_races() {
    new_case command-capture-race true
    capture_barrier="$STATE/capture-barrier"
    mkdir -p "$capture_barrier"
    set +e
    (
        export FAIL_ALL_BD_UPDATE_MATCH='polecat_push_lease_ref='
        export GIT_TX_BARRIER_MATCH='/context '
        export GIT_TX_BARRIER_DIR="$capture_barrier"
        invoke_lease workspace
    ) >"$STATE/capture-one.out" 2>&1 &
    capture_one=$!
    wait_for_barrier_participant "$capture_barrier"
    (
        export FAIL_ALL_BD_UPDATE_MATCH='polecat_push_lease_ref='
        export GIT_TX_BARRIER_MATCH='/context '
        export GIT_TX_BARRIER_DIR="$capture_barrier"
        invoke_lease workspace
    ) >"$STATE/capture-two.out" 2>&1 &
    capture_two=$!
    wait "$capture_one"
    capture_one_rc=$?
    wait "$capture_two"
    capture_two_rc=$?
    set -e
    [[ "$capture_one_rc" -eq 75 && "$capture_two_rc" -eq 75 ]] ||
        fail "command capture race did not fail closed after one shared winner"
    [[ "$(namespace_count)" -eq 4 ]] ||
        fail "command capture race exposed partial or refreshed authority"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "identical command capture loser blocked source"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 && "$(namespace_count)" -eq 5 ]] ||
        fail "command capture winner state was not restartable: $(<"$OUTPUT")"

    new_case command-publish-race true
    set +e
    (
        export GIT_REBASE_RESPONSE_LOST=1
        run_lease workspace
        exit "$RUN_RC"
    )
    unpublished_rc=$?
    set -e
    [[ "$unpublished_rc" -eq 75 && "$(namespace_count)" -eq 4 ]] ||
        fail "publish-race fixture did not leave an explicit detached candidate"

    publish_barrier="$STATE/publish-barrier"
    mkdir -p "$publish_barrier"
    set +e
    (
        export FAIL_ALL_BD_UPDATE_MATCH='polecat_push_lease_state=rebased'
        export GIT_TX_BARRIER_MATCH='/rebased '
        export GIT_TX_BARRIER_DIR="$publish_barrier"
        invoke_lease publish-rebase
    ) >"$STATE/publish-one.out" 2>&1 &
    publish_one=$!
    wait_for_barrier_participant "$publish_barrier"
    (
        export FAIL_ALL_BD_UPDATE_MATCH='polecat_push_lease_state=rebased'
        export GIT_TX_BARRIER_MATCH='/rebased '
        export GIT_TX_BARRIER_DIR="$publish_barrier"
        invoke_lease publish-rebase
    ) >"$STATE/publish-two.out" 2>&1 &
    publish_two=$!
    wait "$publish_one"
    publish_one_rc=$?
    wait "$publish_two"
    publish_two_rc=$?
    set -e
    [[ "$publish_one_rc" -eq 75 && "$publish_two_rc" -eq 75 ]] ||
        fail "command publish race did not preserve its shared winner"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "command publish race exposed partial phase refs"
    rebased_ref=$(lease_ref_with_suffix rebased)
    [[ "$(local_feature_oid)" == "$("$REAL_GIT" -C "$WORK" rev-parse "$rebased_ref")" ]] ||
        fail "command publish race left branch and phase ref inconsistent"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "identical command publish loser blocked source"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "command publish winner state was not restartable: $(<"$OUTPUT")"
}

test_multi_commit_local_ahead_rebase() {
    new_case multi-commit-local-ahead true
    printf 'local one\n' >"$WORK/local-one.txt"
    "$REAL_GIT" -C "$WORK" add local-one.txt
    "$REAL_GIT" -C "$WORK" commit -q -m local-one
    printf 'local two\n' >"$WORK/local-two.txt"
    "$REAL_GIT" -C "$WORK" add local-two.txt
    "$REAL_GIT" -C "$WORK" commit -q -m local-two
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "multi-commit local-ahead rebase failed: $(<"$OUTPUT")"
    [[ -f "$WORK/local-one.txt" && -f "$WORK/local-two.txt" ]] ||
        fail "multi-commit local-ahead rebase lost local work"
    commit_count=$("$REAL_GIT" -C "$WORK" rev-list --count \
        refs/remotes/origin/main..refs/heads/polecat/source-1)
    [[ "$commit_count" -eq 3 ]] ||
        fail "multi-commit rebase did not preserve remote feature plus two local commits"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 && "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "multi-commit rebased submit did not publish exactly"
}

test_true_rebase_conflict_resolution() {
    new_case true-rebase-conflict true
    "$REAL_GIT" -C "$SEED" switch -q main
    printf 'base from main\n' >"$SEED/base.txt"
    "$REAL_GIT" -C "$SEED" add base.txt
    "$REAL_GIT" -C "$SEED" commit -q -m main-conflict
    "$REAL_GIT" -C "$SEED" push -q origin main
    printf 'base from feature\n' >"$WORK/base.txt"
    "$REAL_GIT" -C "$WORK" add base.txt
    "$REAL_GIT" -C "$WORK" commit -q -m feature-conflict

    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "true rebase conflict did not stop indeterminate: $(<"$OUTPUT")"
    rebase_merge=$("$REAL_GIT" -C "$WORK" rev-parse --git-path rebase-merge)
    rebase_apply=$("$REAL_GIT" -C "$WORK" rev-parse --git-path rebase-apply)
    [[ "$rebase_merge" == /* ]] || rebase_merge="$WORK/$rebase_merge"
    [[ "$rebase_apply" == /* ]] || rebase_apply="$WORK/$rebase_apply"
    [[ -d "$rebase_merge" || -d "$rebase_apply" ]] ||
        fail "true rebase conflict did not preserve resumable Git state"
    [[ "$(namespace_count)" -eq 4 ]] ||
        fail "true rebase conflict advanced authority before resolution"

    printf 'resolved base\n' >"$WORK/base.txt"
    "$REAL_GIT" -C "$WORK" add base.txt
    GIT_EDITOR=true "$REAL_GIT" -C "$WORK" rebase --continue >/dev/null
    run_lease publish-rebase
    [[ "$RUN_RC" -eq 0 && "$(namespace_count)" -eq 5 ]] ||
        fail "resolved rebase did not publish explicitly: $(<"$OUTPUT")"
    [[ "$(<"$WORK/base.txt")" == "resolved base" ]] ||
        fail "explicit conflict publication lost the reviewed resolution"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 && "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "resolved conflict submit did not publish exactly"
}

test_linked_worktree_ref_races() {
    new_case linked-ref-races false
    linked="$CASE_DIR/linked"
    "$REAL_GIT" -C "$WORK" worktree add -q --detach "$linked" \
        refs/heads/polecat/source-1
    pre=$(local_feature_oid)
    base=$("$REAL_GIT" -C "$WORK" rev-parse refs/remotes/origin/main)
    context=$(printf 'linked-race-context\n' |
        "$REAL_GIT" -C "$WORK" hash-object -w --stdin)
    capture_ns=refs/gascity/test-linked-capture

    capture_tx() {
        local repo=$1
        printf '%s\n' \
            start \
            "option no-deref" \
            "create $capture_ns/context $context" \
            "create $capture_ns/expected $pre" \
            "create $capture_ns/pre $pre" \
            "create $capture_ns/base $base" \
            prepare \
            commit | "$REAL_GIT" -C "$repo" update-ref --stdin \
                >/dev/null 2>&1
    }

    set +e
    capture_tx "$WORK" &
    capture_one=$!
    capture_tx "$linked" &
    capture_two=$!
    wait "$capture_one"
    capture_one_rc=$?
    wait "$capture_two"
    capture_two_rc=$?
    set -e
    [[ $(( (capture_one_rc == 0) + (capture_two_rc == 0) )) -eq 1 ]] ||
        fail "linked-worktree capture race did not produce exactly one winner"
    [[ "$("$REAL_GIT" -C "$WORK" for-each-ref --format='%(refname)' "$capture_ns" | wc -l)" -eq 4 ]] ||
        fail "linked-worktree capture race exposed partial refs"

    tree=$("$REAL_GIT" -C "$WORK" rev-parse "$pre^{tree}")
    candidate_a=$(printf 'candidate-a\n' |
        "$REAL_GIT" -C "$WORK" commit-tree "$tree" -p "$pre")
    candidate_b=$(printf 'candidate-b\n' |
        "$REAL_GIT" -C "$WORK" commit-tree "$tree" -p "$pre")
    [[ "$candidate_a" != "$candidate_b" ]] ||
        fail "linked-worktree branch race candidates are identical"
    branch_ns=refs/gascity/test-linked-branch
    "$REAL_GIT" -C "$WORK" update-ref "$branch_ns/context" "$context"
    "$REAL_GIT" -C "$WORK" update-ref "$branch_ns/expected" "$pre"
    "$REAL_GIT" -C "$WORK" update-ref "$branch_ns/pre" "$pre"
    "$REAL_GIT" -C "$WORK" update-ref "$branch_ns/base" "$base"

    branch_tx() {
        local repo=$1 candidate=$2
        printf '%s\n' \
            start \
            "option no-deref" \
            "verify $branch_ns/context $context" \
            "update refs/heads/polecat/source-1 $candidate $pre" \
            "create $branch_ns/rebased $candidate" \
            prepare \
            commit | "$REAL_GIT" -C "$repo" update-ref --stdin \
                >/dev/null 2>&1
    }

    set +e
    branch_tx "$WORK" "$candidate_a" &
    branch_one=$!
    branch_tx "$linked" "$candidate_b" &
    branch_two=$!
    wait "$branch_one"
    branch_one_rc=$?
    wait "$branch_two"
    branch_two_rc=$?
    set -e
    [[ $(( (branch_one_rc == 0) + (branch_two_rc == 0) )) -eq 1 ]] ||
        fail "linked-worktree branch CAS did not produce exactly one winner"
    winner=$("$REAL_GIT" -C "$WORK" rev-parse refs/heads/polecat/source-1)
    published=$("$REAL_GIT" -C "$WORK" rev-parse "$branch_ns/rebased")
    [[ "$winner" == "$published" ]] ||
        fail "linked-worktree branch and rebased phase disagree"
}

test_normal_push
test_rebased_exact_lease_push
test_rejected_auto_push_false_stops_before_freeze
test_remote_race_terminalizes
test_terminalization_revalidates_graph_authority
test_unreadable_is_indeterminate
test_capture_mirror_crash_recovery
test_rebase_mirror_crash_recovery
test_submit_mirror_crash_recovery
test_push_response_lost_recovery
test_cleanup_transaction_retry
test_metadata_cleanup_restart
test_unpublished_rebase_requires_explicit_publish
test_frozen_push_url
test_mail_failure_retries_before_step_close
test_closed_step_drain_retry
test_mirror_tamper_is_hard
test_auto_push_authority
test_graph_base_authority
test_artifact_dir_authority
test_legacy_work_dir_is_not_lease_authority
test_artifact_dir_containment_matrix
test_runtime_identity_deduplication
test_runtime_identity_query_rows_are_exact
test_live_graph_state_is_active_and_outcome_free
test_alternate_identity_live_and_closed_recovery
test_closed_recovery_root_classification
test_closed_recovery_target_root_state_matrix
test_ambiguous_runtime_identity_steps_fail_closed
test_unreadable_runtime_identity_query_fails_closed
test_witness_authority
test_unchanged_transaction_failures
test_leased_remote_missing_is_hard
test_context_ref_mismatch_is_hard
test_symbolic_lease_ref_is_hard_and_preserved
test_normal_branch_movement_is_indeterminate
test_command_capture_and_publish_races
test_multi_commit_local_ahead_rebase
test_true_rebase_conflict_resolution
test_linked_worktree_ref_races

echo "polecat lease command tests passed"
