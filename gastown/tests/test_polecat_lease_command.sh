#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/polecat-lease/run.sh"
CONFLICT_COMMAND="$ROOT/gastown/commands/polecat-conflict/run.sh"
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

if [[ "${1:-}" == "gastown" &&
      "${2:-}" == "polecat-lease" &&
      "${3:-}" == "record-replay" ]]; then
    [[ -n "${POLECAT_LEASE_COMMAND:-}" ]] || exit 99
    if "$POLECAT_LEASE_COMMAND" "${@:3}"; then
        if [[ "${GIT_RECORD_REPLAY_RESPONSE_LOST_ONCE:-0}" == "1" &&
              ! -e "$FAKE_STATE/record-replay-response-lost-fired" ]]; then
            touch "$FAKE_STATE/record-replay-response-lost-fired"
            exit 97
        fi
        exit 0
    else
        exit $?
    fi
fi

write_db() {
    mv "$FAKE_DB.tmp" "$FAKE_DB"
}

direct_store_env_is_exact() {
    [[ "${GC_NO_API:-}" == "1" &&
       "${GC_CITY:-}" == "$EXPECTED_CITY_ROOT" &&
       "${GC_CITY_PATH:-}" == "$EXPECTED_CITY_ROOT" &&
       "${GC_RIG:-}" == "$EXPECTED_RUNTIME_RIG" &&
       "${GC_RIG_ROOT:-}" == "$EXPECTED_RIG_ROOT" &&
       "${GC_STORE_ROOT:-}" == "$EXPECTED_RIG_ROOT" &&
       "${GC_STORE_SCOPE:-}" == "rig" ]]
}

if [[ "${1:-}" == "bd" ]]; then
    if [[ "${2:-}" != "--rig" ||
          "${3:-}" != "$EXPECTED_RUNTIME_RIG" ]] ||
       ! direct_store_env_is_exact; then
        touch "$FAKE_STATE/non-direct-store-read"
        exit 98
    fi
    set -- bd "${@:4}"
fi

if [[ "${1:-}" == "convoy" ]] && ! direct_store_env_is_exact; then
    touch "$FAKE_STATE/stale-convoy-cache-read"
    printf '%s\n' \
        '{"schema_version":"1","convoy":{"id":"convoy-1"},"children":[{"id":"stale-source"}]}'
    exit 0
fi

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
    if [[ "${FAIL_SOURCE_BLOCK_READBACK:-0}" == "1" &&
          "$id" == "source-1" &&
          -e "$FAKE_STATE/source-blocked-for-readback" ]]; then
        exit 96
    fi
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
    if [[ "${FAIL_SOURCE_BLOCK_READBACK:-0}" == "1" &&
          "$id" == "source-1" &&
          "$(jq -r '.beads["source-1"].status' "$FAKE_DB")" == "blocked" ]]; then
        touch "$FAKE_STATE/source-blocked-for-readback"
    fi
    exit 0
fi

if [[ "${1:-}" == "convoy" && "${2:-}" == "status" &&
      "${3:-}" == "convoy-1" && "${4:-}" == "--json" ]]; then
    count_file="$FAKE_STATE/convoy-read-count"
    count=0
    if [[ -f "$count_file" ]]; then
        count=$(<"$count_file")
    fi
    count=$((count + 1))
    printf '%s\n' "$count" >"$count_file"
    source_id=${FAKE_CONVOY_SOURCE_ID:-source-1}
    if [[ "${FAKE_CONVOY_DRIFT_AFTER_FIRST:-0}" == "1" &&
          "$count" -gt 1 ]]; then
        source_id=drifted-source
    elif [[ "${FAKE_CONVOY_DRIFT_AFTER_RACE:-0}" == "1" &&
            -e "$FAKE_STATE/race-fired" ]]; then
        source_id=drifted-source
    fi
    jq -cn \
        --arg schema "${FAKE_CONVOY_SCHEMA_VERSION:-1}" \
        --arg convoy "${FAKE_CONVOY_ID:-convoy-1}" \
        --arg source "$source_id" \
        '{
          schema_version: $schema,
          convoy: {id: $convoy},
          children: [{id: $source}]
        }'
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

git_args=("$@")
git_arg_index=0
while [[ "${git_args[git_arg_index]:-}" == "-c" ]]; do
    git_arg_index=$((git_arg_index + 2))
done
GIT_SUBCOMMAND=${git_args[git_arg_index]:-}
GIT_SUBARG1=${git_args[git_arg_index + 1]:-}

if [[ "$GIT_SUBCOMMAND" == "ls-remote" &&
      "${GIT_LS_REMOTE_UNREADABLE:-0}" == "1" ]]; then
    exit 128
fi

if [[ "$GIT_SUBCOMMAND" == "rebase" && "$GIT_SUBARG1" == "-h" &&
      "${GIT_REBASE_HELP_UNSUPPORTED:-0}" == "1" ]]; then
    printf '%s\n' "usage: git rebase [options]"
    exit 129
fi

if [[ "$GIT_SUBCOMMAND" == "rebase" && "$GIT_SUBARG1" == "--continue" &&
      "${GIT_FAIL_REBASE_CONTINUE_BEFORE_ONCE:-0}" == "1" &&
      ! -e "$FAKE_STATE/rebase-continue-prewrite-failure-fired" ]]; then
    touch "$FAKE_STATE/rebase-continue-prewrite-failure-fired"
    exit 1
fi

if [[ "$GIT_SUBCOMMAND" == "commit" && " $* " == *" --allow-empty "* &&
      "${GIT_EMPTY_COMMIT_RESPONSE_LOST_ONCE:-0}" == "1" &&
      ! -e "$FAKE_STATE/empty-commit-response-lost-fired" ]]; then
    "$REAL_GIT" "$@"
    touch "$FAKE_STATE/empty-commit-response-lost-fired"
    exit 1
fi

if [[ "$GIT_SUBCOMMAND" == "ls-remote" &&
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

if [[ "$GIT_SUBCOMMAND" == "rebase" && "$GIT_SUBARG1" != "-h" &&
      "${GIT_REBASE_RESPONSE_LOST:-0}" == "1" &&
      ! -e "$FAKE_STATE/rebase-response-lost-fired" ]]; then
    touch "$FAKE_STATE/rebase-response-lost-fired"
    "$REAL_GIT" "$@"
    exit 1
fi

if [[ "$GIT_SUBCOMMAND" == "push" ]]; then
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

if [[ "$GIT_SUBCOMMAND" == "add" && -z "${GIT_INDEX_FILE:-}" &&
      -n "${GIT_MUTATE_BEFORE_REAL_ADD_PATH:-}" &&
      ! -e "$FAKE_STATE/real-add-race-fired" ]]; then
    touch "$FAKE_STATE/real-add-race-fired"
    printf '%s' "${GIT_MUTATE_BEFORE_REAL_ADD_CONTENT:-raced}" \
        >"$GIT_MUTATE_BEFORE_REAL_ADD_PATH"
fi

if [[ "$GIT_SUBCOMMAND" == "update-ref" && "$GIT_SUBARG1" == "--stdin" ]]; then
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
    if [[ -n "${GIT_TX_RESPONSE_LOST_MATCH:-}" &&
          "$payload" == *"$GIT_TX_RESPONSE_LOST_MATCH"* &&
          ! -e "$FAKE_STATE/transaction-response-lost-fired" ]]; then
        touch "$FAKE_STATE/transaction-response-lost-fired"
        printf '%s\n' "$payload" | "$REAL_GIT" "$@"
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
              "gc.var.binding_prefix": "",
              "gc.graphv2_vars.v1": {
                base_branch: "main",
                rig_name: "rig",
                binding_prefix: "",
                setup_command: ""
              }
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
        GC_SESSION_ID="${LEASE_GC_SESSION_ID-actor-session-1}" \
        GC_ALIAS="${LEASE_GC_ALIAS-}" \
        GC_AGENT="${LEASE_GC_AGENT-}" \
        EXPECTED_CITY_ROOT="$CITY_ROOT" \
        EXPECTED_RIG_ROOT="$RIG_ROOT" \
        EXPECTED_RUNTIME_RIG=rig \
        FAKE_DB="$DB" \
        FAKE_STATE="$STATE" \
        FAKE_GC_LOG="$STATE/gc.log" \
        FAKE_CONVOY_SCHEMA_VERSION="${FAKE_CONVOY_SCHEMA_VERSION:-1}" \
        FAKE_CONVOY_ID="${FAKE_CONVOY_ID:-convoy-1}" \
        FAKE_CONVOY_SOURCE_ID="${FAKE_CONVOY_SOURCE_ID:-source-1}" \
        FAKE_CONVOY_DRIFT_AFTER_FIRST="${FAKE_CONVOY_DRIFT_AFTER_FIRST:-0}" \
        FAKE_CONVOY_DRIFT_AFTER_RACE="${FAKE_CONVOY_DRIFT_AFTER_RACE:-0}" \
        WRONG_BD_LIST_ASSIGNEE="${WRONG_BD_LIST_ASSIGNEE:-}" \
        DUPLICATE_BD_LIST_ASSIGNEE="${DUPLICATE_BD_LIST_ASSIGNEE:-}" \
        TERMINAL_AUTHORITY_DRIFT="${TERMINAL_AUTHORITY_DRIFT:-}" \
        GIT_FAIL_REBASE_CONTINUE_BEFORE_ONCE="${GIT_FAIL_REBASE_CONTINUE_BEFORE_ONCE:-0}" \
        GIT_EMPTY_COMMIT_RESPONSE_LOST_ONCE="${GIT_EMPTY_COMMIT_RESPONSE_LOST_ONCE:-0}" \
        GIT_RECORD_REPLAY_RESPONSE_LOST_ONCE="${GIT_RECORD_REPLAY_RESPONSE_LOST_ONCE:-0}" \
        GIT_PUSH_LOG="$PUSH_LOG" \
        REAL_GIT="$REAL_GIT" \
        POLECAT_LEASE_COMMAND="$COMMAND" \
        "$COMMAND" "$action" \
            --source "${LEASE_SOURCE:-source-1}" \
            --convoy "${LEASE_CONVOY:-convoy-1}" \
            --base "${LEASE_BASE:-main}" \
            --branch "${LEASE_BRANCH:-polecat/source-1}" \
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

invoke_conflict_stage() {
    (
        cd "$WORK"
        PATH="$TEST_TMP/bin:$PATH" \
        GC_BIN="$TEST_TMP/bin/gc" \
        GC_CITY_PATH="$CITY_ROOT" \
        GC_RIG=rig \
        GC_RIG_ROOT="$RIG_ROOT" \
        BEADS_ACTOR=actor-1 \
        GC_SESSION_NAME="" \
        GC_SESSION_ID=actor-session-1 \
        GC_ALIAS="" \
        GC_AGENT="" \
        GC_POLECAT_CONVOY_ID=convoy-1 \
        GC_POLECAT_SOURCE_ID=source-1 \
        GC_POLECAT_SOURCE_BRANCH=polecat/source-1 \
        GC_POLECAT_ARTIFACT_DIR="$WORK" \
        EXPECTED_CITY_ROOT="$CITY_ROOT" \
        EXPECTED_RIG_ROOT="$RIG_ROOT" \
        EXPECTED_RUNTIME_RIG=rig \
        FAKE_DB="$DB" \
        FAKE_STATE="$STATE" \
        FAKE_GC_LOG="$STATE/gc.log" \
        FAKE_CONVOY_SCHEMA_VERSION="${FAKE_CONVOY_SCHEMA_VERSION:-1}" \
        FAKE_CONVOY_ID="${FAKE_CONVOY_ID:-convoy-1}" \
        FAKE_CONVOY_SOURCE_ID="${FAKE_CONVOY_SOURCE_ID:-source-1}" \
        GIT_FAIL_TX_MATCH="${GIT_FAIL_TX_MATCH:-}" \
        GIT_TX_RESPONSE_LOST_MATCH="${GIT_TX_RESPONSE_LOST_MATCH:-}" \
        GIT_MUTATE_BEFORE_REAL_ADD_PATH="${GIT_MUTATE_BEFORE_REAL_ADD_PATH:-}" \
        GIT_MUTATE_BEFORE_REAL_ADD_CONTENT="${GIT_MUTATE_BEFORE_REAL_ADD_CONTENT:-}" \
        REAL_GIT="$REAL_GIT" \
            "$CONFLICT_COMMAND" stage
    )
}

run_conflict_stage() {
    set +e
    invoke_conflict_stage >"$OUTPUT" 2>&1
    RUN_RC=$?
    set -e
}

namespace_count() {
    "$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-push-leases | wc -l
}

submit_proof_count() {
    "$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-submit-proofs | wc -l
}

conflict_proof_count() {
    "$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-conflicts | wc -l
}

replay_proof_count() {
    "$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-rebase-proofs | wc -l
}

replay_proof_ref() {
    local suffix=$1
    "$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-rebase-proofs |
        sed -n "\\|/$suffix$|p"
}

replay_mapping_count() {
    local kind=$1
    "$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-rebase-proofs |
        sed -n "\\|/$kind/[0-9][0-9]*$|p" | wc -l
}

proof_receipt_field() {
    local field=$1 line token
    line=$(grep -E '^POLECAT_SUBMIT_PROOF ' "$OUTPUT") || return 1
    [[ "$(grep -Ec '^POLECAT_SUBMIT_PROOF ' "$OUTPUT")" -eq 1 ]] || return 1
    for token in $line; do
        case "$token" in
            "$field="*)
                printf '%s' "${token#*=}"
                return 0
                ;;
        esac
    done
    return 1
}

assert_submit_proof() {
    local expected_auto_push=$1 expected_head=$2
    local version key context head mode namespace context_body
    version=$(proof_receipt_field version) ||
        fail "submit proof has no exact version receipt: $(<"$OUTPUT")"
    key=$(proof_receipt_field key) ||
        fail "submit proof has no exact key receipt: $(<"$OUTPUT")"
    context=$(proof_receipt_field context) ||
        fail "submit proof has no exact context receipt: $(<"$OUTPUT")"
    head=$(proof_receipt_field head) ||
        fail "submit proof has no exact head receipt: $(<"$OUTPUT")"
    mode=$(proof_receipt_field auto_push) ||
        fail "submit proof has no exact auto_push receipt: $(<"$OUTPUT")"
    [[ "$version" == "1" && "$mode" == "$expected_auto_push" &&
       "$head" == "$expected_head" ]] ||
        fail "submit proof receipt has the wrong version/mode/head: $(<"$OUTPUT")"
    for oid in "$key" "$context" "$head"; do
        [[ "$oid" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] ||
            fail "submit proof receipt contains an invalid object id: $oid"
    done
    namespace="refs/gascity/polecat-submit-proofs/v1/$key"
    [[ "$(submit_proof_count)" -eq 2 ]] ||
        fail "submit proof is not exactly one two-ref record"
    [[ "$("$REAL_GIT" -C "$WORK" rev-parse "$namespace/context")" == "$context" &&
       "$("$REAL_GIT" -C "$WORK" rev-parse "$namespace/head")" == "$head" ]] ||
        fail "submit proof receipt disagrees with its authoritative refs"
    [[ "$("$REAL_GIT" -C "$WORK" cat-file -t "$context")" == "blob" &&
       "$("$REAL_GIT" -C "$WORK" cat-file -t "$head")" == "commit" ]] ||
        fail "submit proof refs do not target blob/commit objects"
    context_body=$("$REAL_GIT" -C "$WORK" cat-file blob "$context")
    for exact in \
        "schema=gascity-polecat-submit-proof-v1" \
        "version=1" \
        "key=$key" \
        "source=source-1" \
        "workflow_root=root-1" \
        "step=submit-1" \
        "step_assignee=actor-1" \
        "input_convoy=convoy-1" \
        "session_id=${LEASE_GC_SESSION_ID-actor-session-1}" \
        "branch=polecat/source-1" \
        "target=main" \
        "auto_push=$expected_auto_push" \
        "head_oid=$head" \
        "rig=rig" \
        "binding_prefix=" \
        "witness=rig/witness"; do
        printf '%s\n' "$context_body" | grep -Fx "$exact" >/dev/null ||
            fail "submit proof context is missing $exact"
    done
}

remote_feature_oid() {
    "$REAL_GIT" --git-dir="$ORIGIN" rev-parse refs/heads/polecat/source-1
}

test_direct_store_convoy_authority() {
    new_case direct-store-convoy-authority false
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "direct-store convoy authority failed: $(<"$OUTPUT")"
    [[ ! -e "$STATE/non-direct-store-read" &&
       ! -e "$STATE/stale-convoy-cache-read" ]] ||
        fail "lease consulted a non-authoritative store or stale convoy cache"
    rg -q '^gc bd --rig rig list ' "$STATE/gc.log" ||
        fail "bead reads were not explicitly scoped to the runtime rig"
    rg -q '^gc convoy status convoy-1 --json ' "$STATE/gc.log" ||
        fail "authoritative convoy status was not consulted"
}

test_convoy_schema_and_identity_fail_closed() {
    new_case convoy-schema-mismatch false
    FAKE_CONVOY_SCHEMA_VERSION=2
    run_lease workspace
    unset FAKE_CONVOY_SCHEMA_VERSION
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "wrong convoy schema returned $RUN_RC instead of 75"
    [[ "$(namespace_count)" -eq 0 &&
       "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "wrong convoy schema mutated protected state"

    new_case convoy-identity-mismatch false
    FAKE_CONVOY_ID=other-convoy
    run_lease workspace
    unset FAKE_CONVOY_ID
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "wrong convoy identity returned $RUN_RC instead of 75"
    [[ "$(namespace_count)" -eq 0 &&
       "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "wrong convoy identity mutated protected state"
}

test_convoy_source_revalidated_before_protected_mutation() {
    new_case convoy-source-drift true
    FAKE_CONVOY_DRIFT_AFTER_FIRST=1
    run_lease workspace
    unset FAKE_CONVOY_DRIFT_AFTER_FIRST
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "convoy source drift returned $RUN_RC instead of 75: $(<"$OUTPUT")"
    [[ "$(<"$STATE/convoy-read-count")" -eq 2 ]] ||
        fail "convoy source was not re-read at the protected mutation seam"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "convoy source drift created lease authority"
    [[ "$(jq -r '.beads["source-1"].metadata.rejection_reason' "$DB")" == "rejected" ]] ||
        fail "convoy source drift mutated source metadata"
    ! rg -q '^gc bd --rig rig update source-1 ' "$STATE/gc.log" ||
        fail "convoy source drift attempted a protected bead mutation"
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

test_invalid_arguments_stop_before_provenance() {
    local label
    for label in wrong-branch invalid-base invalid-source; do
        new_case "pre-provenance-$label" true
        case "$label" in
            wrong-branch) LEASE_BRANCH=polecat/other ;;
            invalid-base) LEASE_BASE='bad branch' ;;
            invalid-source) LEASE_SOURCE='bad/source' ;;
        esac
        run_lease workspace
        unset LEASE_BRANCH LEASE_BASE LEASE_SOURCE
        [[ "$RUN_RC" -eq 2 ]] ||
            fail "$label returned $RUN_RC instead of usage exit 2: $(<"$OUTPUT")"
        [[ ! -s "$STATE/gc.log" && "$(namespace_count)" -eq 0 ]] ||
            fail "$label read Graph provenance or created lease refs"
        [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
            fail "$label notified or drained before provenance"
    done
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
    assert_submit_proof true "$(local_feature_oid)"
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
    assert_submit_proof true "$SUBMIT"
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
    jq '.beads["source-1"].metadata.auto_push = false' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    BEFORE=$(remote_feature_oid)
    run_lease submit --auto-push false
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "rejected auto_push=false did not stop safely: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$BEFORE" ]] ||
        fail "rejected auto_push=false changed the remote"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "rejected auto_push=false froze submit or lost recovery refs"
    [[ "$(submit_proof_count)" -eq 0 ]] ||
        fail "rejected auto_push=false created submit proof without success"
    [[ "$(jq -r '.beads["source-1"].metadata.polecat_push_lease_state' "$DB")" == "rebased" ]] ||
        fail "rejected auto_push=false changed the rebased mirror phase"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "rejected auto_push=false closed the only authorized Graph step"
    [[ ! -e "$STATE/drained" ]] ||
        fail "rejected auto_push=false drained the live recovery step"
}

test_auto_push_false_proof_is_local_and_idempotent() {
    local before head first_receipt
    new_case auto-push-false-proof false
    jq '.beads["source-1"].metadata.auto_push = false' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    before=$(remote_feature_oid)
    printf 'local only\n' >>"$WORK/feature.txt"
    "$REAL_GIT" -C "$WORK" add feature.txt
    "$REAL_GIT" -C "$WORK" commit -q -m local-only
    head=$(local_feature_oid)

    run_lease submit --auto-push false
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "auto_push=false proof failed: $(<"$OUTPUT")"
    [[ "$(remote_feature_oid)" == "$before" ]] ||
        fail "auto_push=false changed the remote"
    [[ "$head" != "$before" ]] ||
        fail "auto_push=false fixture did not create a local-only head"
    assert_submit_proof false "$head"
    first_receipt=$(grep -E '^POLECAT_SUBMIT_PROOF ' "$OUTPUT")

    run_lease submit --auto-push false
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "auto_push=false exact retry failed: $(<"$OUTPUT")"
    assert_submit_proof false "$head"
    [[ "$(grep -E '^POLECAT_SUBMIT_PROOF ' "$OUTPUT")" == "$first_receipt" ]] ||
        fail "auto_push=false retry returned a different proof receipt"
}

test_submit_proof_ref_tamper_is_hard() {
    local key context_ref tampered original_head
    new_case submit-proof-tamper false
    jq '.beads["source-1"].metadata.auto_push = false' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease submit --auto-push false
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "submit-proof tamper setup failed: $(<"$OUTPUT")"
    key=$(proof_receipt_field key)
    original_head=$(proof_receipt_field head)
    context_ref="refs/gascity/polecat-submit-proofs/v1/$key/context"
    tampered=$(printf 'tampered submit proof\n' |
        "$REAL_GIT" -C "$WORK" hash-object -w --stdin)
    "$REAL_GIT" -C "$WORK" update-ref "$context_ref" "$tampered"

    run_lease submit --auto-push false
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "submit-proof ref tamper returned $RUN_RC instead of hard failure: $(<"$OUTPUT")"
    [[ "$("$REAL_GIT" -C "$WORK" rev-parse "$context_ref")" == "$tampered" ]] ||
        fail "submit-proof tamper was overwritten"
    [[ "$("$REAL_GIT" -C "$WORK" rev-parse \
        "refs/gascity/polecat-submit-proofs/v1/$key/head")" == "$original_head" ]] ||
        fail "submit-proof tamper changed the retained head"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "submit-proof tamper did not block the source"
}

test_submit_proof_create_race_is_idempotent() {
    local first_pid second_pid first_rc second_rc first_receipt second_receipt
    new_case submit-proof-create-race false
    jq '.beads["source-1"].metadata.auto_push = false' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    mkdir -p "$STATE/proof-barrier"

    set +e
    (
        export GIT_TX_BARRIER_MATCH="create refs/gascity/polecat-submit-proofs/v1/"
        export GIT_TX_BARRIER_DIR="$STATE/proof-barrier"
        invoke_lease submit --auto-push false
    ) >"$STATE/proof-race-one.out" 2>&1 &
    first_pid=$!
    (
        export GIT_TX_BARRIER_MATCH="create refs/gascity/polecat-submit-proofs/v1/"
        export GIT_TX_BARRIER_DIR="$STATE/proof-barrier"
        invoke_lease submit --auto-push false
    ) >"$STATE/proof-race-two.out" 2>&1 &
    second_pid=$!
    wait "$first_pid"
    first_rc=$?
    wait "$second_pid"
    second_rc=$?
    set -e

    [[ "$first_rc" -eq 0 && "$second_rc" -eq 0 ]] ||
        fail "same-context submit-proof race was not idempotent: rc=$first_rc/$second_rc"
    [[ "$(submit_proof_count)" -eq 2 ]] ||
        fail "same-context submit-proof race exposed partial or duplicate refs"
    first_receipt=$(grep -E '^POLECAT_SUBMIT_PROOF ' "$STATE/proof-race-one.out")
    second_receipt=$(grep -E '^POLECAT_SUBMIT_PROOF ' "$STATE/proof-race-two.out")
    [[ "$first_receipt" == "$second_receipt" ]] ||
        fail "same-context submit-proof race returned different receipts"
}

test_dirty_artifact_cannot_create_submit_proof() {
    new_case dirty-submit-proof false
    jq '.beads["source-1"].metadata.auto_push = false' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    printf 'untracked\n' >"$WORK/untracked.txt"
    run_lease submit --auto-push false
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "dirty artifact returned $RUN_RC instead of indeterminate"
    [[ "$(submit_proof_count)" -eq 0 ]] ||
        fail "dirty artifact created a submit proof"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "dirty artifact terminalized the Graph step"
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
    source_line=$(rg -n '^gc bd --rig rig update source-1 .*--status=blocked' \
        "$STATE/gc.log" | cut -d: -f1) ||
        fail "remote race did not log source terminalization"
    mail_line=$(rg -n '^gc mail send rig/witness .*--notify' \
        "$STATE/gc.log" | cut -d: -f1) ||
        fail "remote race did not log durable Witness notification"
    step_line=$(rg -n '^gc bd --rig rig update submit-1 .*gc\.outcome=fail' \
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

        [[ "$race_rc" -eq 75 ]] ||
            fail "$drift drift conflict returned $race_rc instead of 75: $(<"$OUTPUT")"
        [[ -e "$STATE/terminal-authority-drift-fired" ]] ||
            fail "$drift drift fixture did not fire before terminalization"
        [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" &&
           "$(jq -r '.beads["source-1"].assignee' "$DB")" == "" ]] ||
            fail "$drift drift mutated source state from stale Graph authority"
        ! rg -q '^gc bd --rig rig update source-1 .*--status=blocked' "$STATE/gc.log" ||
            fail "$drift drift attempted to block the source"
        [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
            fail "$drift drift notified or drained without current Graph authority"
        rg -q 'Graph authority changed before hard terminalization' "$OUTPUT" ||
            fail "$drift drift did not report the authority failure"
    done
}

test_terminalization_revalidates_convoy_authority() {
    prepare_rebased terminal-convoy-drift
    make_racer
    : >"$PUSH_LOG"
    set +e
    (
        export GIT_RACER_WORK="$RACER"
        export FAKE_CONVOY_DRIFT_AFTER_RACE=1
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    race_rc=$?
    set -e

    [[ "$race_rc" -eq 75 ]] ||
        fail "convoy-drift conflict returned $race_rc instead of 75: $(<"$OUTPUT")"
    [[ -e "$STATE/race-fired" ]] ||
        fail "convoy-drift fixture did not fire before terminalization"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" &&
       "$(jq -r '.beads["source-1"].assignee' "$DB")" == "" ]] ||
        fail "terminalization mutated source after convoy authority changed"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "terminalization closed the Graph step after convoy authority changed"
    [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
        fail "terminalization notified or drained after convoy authority changed"
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
    [[ "$(replay_proof_count)" -eq 0 ]] ||
        fail "lost-response recovery retained completed replay-proof refs"
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
    [[ "$(replay_proof_count)" -gt 0 ]] ||
        fail "failed cleanup transaction partially removed replay-proof refs"
    [[ "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "cleanup failure fixture did not occur after verified push"

    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "cleanup transaction retry did not recover: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "cleanup transaction retry left refs"
    [[ "$(replay_proof_count)" -eq 0 ]] ||
        fail "cleanup transaction retry retained replay-proof refs"
}

test_metadata_cleanup_restart() {
    prepare_rebased metadata-cleanup
    printf '%s' '--unset-metadata polecat_push_lease_ref' >"$STATE/fail-update-once"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "metadata cleanup failure was not indeterminate: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "metadata cleanup failure did not occur after atomic ref cleanup"
    [[ "$(replay_proof_count)" -eq 0 ]] ||
        fail "metadata cleanup failure retained replay-proof refs"
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

test_completed_rebase_work_ref_recovers_after_lost_response() {
    new_case unpublished-rebase true
    pre_oid=$(local_feature_oid)
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
        fail "nonzero rebase exit invented lease-owned candidate evidence"
    [[ "$(local_feature_oid)" == "$pre_oid" ]] ||
        fail "completed rebase response loss moved the canonical branch before publication"
    ! "$REAL_GIT" -C "$WORK" show-ref --verify --quiet \
        "$(lease_ref_with_suffix candidate)" ||
        fail "completed rebase response loss created candidate evidence"
    work_ref=$("$REAL_GIT" -C "$WORK" for-each-ref --format='%(refname)' \
        refs/heads/gascity-polecat-rebase)
    [[ -n "$work_ref" &&
       "$("$REAL_GIT" -C "$WORK" branch --show-current)" == \
         "${work_ref#refs/heads/}" ]] ||
        fail "completed rebase was not retained on its lease-owned work branch"
    final_ref=$(replay_proof_ref final)
    [[ "$(replay_proof_count)" -eq 4 && -n "$final_ref" &&
       "$("$REAL_GIT" -C "$WORK" rev-parse "$final_ref")" == \
         "$("$REAL_GIT" -C "$WORK" rev-parse "$work_ref")" ]] ||
        fail "completed rebase did not durably seal its one-entry replay proof"

    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "workspace restart did not adopt its lease-owned completed rebase: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 5 ]] ||
        fail "workspace restart did not publish the recovered rebased phase"
    [[ "$(local_feature_oid)" != "$pre_oid" ]] ||
        fail "workspace restart did not move the canonical branch to the rebase result"
    [[ "$("$REAL_GIT" -C "$WORK" rev-parse "$final_ref")" == \
       "$(local_feature_oid)" ]] ||
        fail "workspace restart published a tip other than the sealed replay proof"
    ! "$REAL_GIT" -C "$WORK" show-ref --verify --quiet "$work_ref" ||
        fail "workspace restart retained the temporary rebase work ref"
}

test_sealed_replay_exec_response_loss_recovers() {
    local canonical_pre rebase_dir final_ref
    new_case sealed-replay-exec-response-loss true
    printf 'local one\n' >"$WORK/local-one.txt"
    "$REAL_GIT" -C "$WORK" add local-one.txt
    "$REAL_GIT" -C "$WORK" commit -q -m local-one
    printf 'local two\n' >"$WORK/local-two.txt"
    "$REAL_GIT" -C "$WORK" add local-two.txt
    "$REAL_GIT" -C "$WORK" commit -q -m local-two
    canonical_pre=$(local_feature_oid)

    GIT_RECORD_REPLAY_RESPONSE_LOST_ONCE=1 run_lease workspace
    [[ "$RUN_RC" -eq 75 &&
       -e "$STATE/record-replay-response-lost-fired" ]] ||
        fail "sealed replay exec response loss was not restartable: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 4 &&
       "$(local_feature_oid)" == "$canonical_pre" ]] ||
        fail "sealed replay exec response loss advanced canonical authority"
    [[ "$(replay_proof_count)" -eq 3 &&
       "$(replay_mapping_count source)" -eq 1 &&
       "$(replay_mapping_count replay)" -eq 1 &&
       -z "$(replay_proof_ref final)" ]] ||
        fail "lost first exec response did not retain one exact sealed prefix"
    rebase_dir=$("$REAL_GIT" -C "$WORK" rev-parse --git-path rebase-merge)
    [[ "$rebase_dir" == /* ]] || rebase_dir="$WORK/$rebase_dir"
    [[ -d "$rebase_dir" && ! -e "$rebase_dir/stopped-sha" ]] ||
        fail "lost replay exec response did not retain the expected non-conflict rebase state"
    ! "$REAL_GIT" -C "$WORK" rev-parse --verify REBASE_HEAD \
        >/dev/null 2>&1 ||
        fail "lost replay exec response unexpectedly retained conflict authority"

    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "sealed replay exec restart did not continue: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 5 &&
       "$(replay_proof_count)" -eq 8 &&
       "$(replay_mapping_count source)" -eq 3 &&
       "$(replay_mapping_count replay)" -eq 3 ]] ||
        fail "sealed replay exec restart did not complete the exact three-entry proof"
    [[ "$(local_feature_oid)" != "$canonical_pre" &&
       -f "$WORK/feature.txt" &&
       -f "$WORK/local-one.txt" &&
       -f "$WORK/local-two.txt" ]] ||
        fail "sealed replay exec restart lost or failed to publish captured work"

    new_case sealed-final-exec-response-loss true
    canonical_pre=$(local_feature_oid)
    GIT_RECORD_REPLAY_RESPONSE_LOST_ONCE=1 run_lease workspace
    [[ "$RUN_RC" -eq 75 &&
       -e "$STATE/record-replay-response-lost-fired" &&
       "$(namespace_count)" -eq 4 &&
       "$(local_feature_oid)" == "$canonical_pre" ]] ||
        fail "sealed final exec response loss advanced authority or was not restartable: $(<"$OUTPUT")"
    final_ref=$(replay_proof_ref final)
    [[ "$(replay_proof_count)" -eq 4 &&
       -n "$final_ref" &&
       "$(replay_mapping_count source)" -eq 1 &&
       "$(replay_mapping_count replay)" -eq 1 ]] ||
        fail "lost final exec response did not atomically retain its completed proof"
    rebase_dir=$("$REAL_GIT" -C "$WORK" rev-parse --git-path rebase-merge)
    [[ "$rebase_dir" == /* ]] || rebase_dir="$WORK/$rebase_dir"
    [[ -d "$rebase_dir" && ! -e "$rebase_dir/stopped-sha" ]] ||
        fail "lost final exec response did not retain the expected non-conflict rebase state"
    ! "$REAL_GIT" -C "$WORK" rev-parse --verify REBASE_HEAD \
        >/dev/null 2>&1 ||
        fail "lost final exec response unexpectedly retained conflict authority"

    run_lease workspace
    [[ "$RUN_RC" -eq 0 &&
       "$(namespace_count)" -eq 5 &&
       "$(local_feature_oid)" == \
         "$("$REAL_GIT" -C "$WORK" rev-parse "$final_ref")" &&
       -f "$WORK/feature.txt" ]] ||
        fail "sealed final exec restart did not publish its exact final proof: $(<"$OUTPUT")"
}

test_hostile_same_count_work_ref_cannot_publish_captured_lease() {
    local source_count replacement tree ordinal
    new_case hostile-same-count-work-ref true
    set +e
    (
        export GIT_REBASE_HELP_UNSUPPORTED=1
        run_lease workspace
        exit "$RUN_RC"
    )
    unsupported_rc=$?
    set -e
    [[ "$unsupported_rc" -eq 75 && "$(namespace_count)" -eq 4 ]] ||
        fail "hostile work-ref fixture did not preserve captured refs: $(<"$OUTPUT")"
    [[ "$(replay_proof_count)" -eq 0 ]] ||
        fail "unsupported rebase created replay proof evidence"

    pre_ref=$(lease_ref_with_suffix pre-rebase)
    base_ref=$(lease_ref_with_suffix base)
    pre_oid=$("$REAL_GIT" -C "$WORK" rev-parse "$pre_ref")
    base_oid=$("$REAL_GIT" -C "$WORK" rev-parse "$base_ref")
    work_ref=$("$REAL_GIT" -C "$WORK" for-each-ref --format='%(refname)' \
        refs/heads/gascity-polecat-rebase)
    [[ -n "$work_ref" ]] || fail "hostile work-ref fixture has no temporary ref"
    original_base=$("$REAL_GIT" -C "$WORK" merge-base "$pre_oid" "$base_oid")
    source_count=$("$REAL_GIT" -C "$WORK" rev-list --count \
        "$original_base..$pre_oid")
    [[ "$source_count" -gt 0 ]] ||
        fail "hostile work-ref fixture has no captured source commits"
    tree=$("$REAL_GIT" -C "$WORK" rev-parse "$base_oid^{tree}")
    replacement=$base_oid
    for ((ordinal = 1; ordinal <= source_count; ordinal++)); do
        replacement=$(printf 'hostile replacement %d\n' "$ordinal" |
            "$REAL_GIT" -C "$WORK" commit-tree "$tree" -p "$replacement")
    done
    [[ "$("$REAL_GIT" -C "$WORK" rev-list --count \
            "$base_oid..$replacement")" -eq "$source_count" ]] ||
        fail "hostile replacement did not match the captured commit count"
    ! "$REAL_GIT" -C "$WORK" cat-file -e "$replacement:feature.txt" \
        2>/dev/null ||
        fail "hostile replacement unexpectedly retained the feature tree"
    "$REAL_GIT" -C "$WORK" switch -q --detach "$replacement"
    "$REAL_GIT" -C "$WORK" update-ref "$work_ref" "$replacement"

    run_lease workspace
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "same-count work ref returned $RUN_RC instead of 64: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 4 ]] ||
        fail "same-count work ref published a lease phase"
    [[ "$(local_feature_oid)" == "$pre_oid" ]] ||
        fail "same-count work ref moved the canonical branch"
    [[ "$("$REAL_GIT" -C "$WORK" show "$pre_oid:feature.txt")" == "feature" ]] ||
        fail "same-count work ref erased the canonical feature content"
    [[ "$(replay_proof_count)" -eq 0 ]] ||
        fail "same-count work ref forged replay proof evidence"
    ! "$REAL_GIT" -C "$WORK" show-ref --verify --quiet \
        "$(lease_ref_with_suffix candidate)" ||
        fail "same-count work ref created candidate evidence"
    ! "$REAL_GIT" -C "$WORK" show-ref --verify --quiet \
        "$(lease_ref_with_suffix rebased)" ||
        fail "same-count work ref created a rebased ref"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "same-count work ref was not durably quarantined"
}

test_direct_lease_rejects_symlink_git_pointer() {
    new_case symlink-dotgit false
    mv "$WORK/.git" "$WORK/.git.pointer"
    ln -s .git.pointer "$WORK/.git"

    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "symlink .git pointer returned $RUN_RC instead of 75: $(<"$OUTPUT")"
    [[ "$(namespace_count)" -eq 0 ]] ||
        fail "symlink .git pointer created lease refs"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "symlink .git pointer terminalized the source"
    [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
        fail "symlink .git pointer notified or drained"
    rg -q 'invalid or redirected .git pointer' "$OUTPUT" ||
        fail "symlink .git pointer did not produce the exact rejection diagnostic"
}

test_workspace_rejects_absent_branch_metadata_without_quarantine() {
    new_case absent-branch-metadata false
    jq '.beads["source-1"].metadata.branch = ""' "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"

    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "absent branch metadata returned $RUN_RC instead of indeterminate"
    rg -n 'metadata.branch is absent; run gc gastown polecat-workspace execute' \
        "$OUTPUT" >/dev/null ||
        fail "absent branch metadata did not direct callers to the workspace wrapper"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "direct lease quarantined a source whose branch metadata was merely absent"
    [[ "$(jq -r '.beads["workspace-1"].status' "$DB")" == "in_progress" ]] ||
        fail "direct lease terminalized the workspace step for absent branch metadata"
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
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "mail failure conflict did not request an indeterminate retry: $(<"$OUTPUT")"
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

test_terminalization_failure_never_reports_durable_quarantine() {
    prepare_rebased terminal-update-failure
    advance_remote
    set +e
    (
        export FAIL_ALL_BD_UPDATE_MATCH='--status=blocked'
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    update_rc=$?
    set -e
    [[ "$update_rc" -eq 75 ]] ||
        fail "failed source quarantine returned $update_rc instead of 75: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "open" ]] ||
        fail "failed source quarantine mutated the source"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "failed source quarantine closed the Graph step"
    [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
        fail "failed source quarantine notified or drained"

    prepare_rebased terminal-readback-failure
    advance_remote
    set +e
    (
        export FAIL_SOURCE_BLOCK_READBACK=1
        run_lease submit --auto-push true
        exit "$RUN_RC"
    )
    readback_rc=$?
    set -e
    [[ "$readback_rc" -eq 75 ]] ||
        fail "unreadable quarantine returned $readback_rc instead of 75: $(<"$OUTPUT")"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "readback fixture did not durably write the source quarantine"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" ]] ||
        fail "unreadable quarantine closed the Graph step"
    [[ ! -e "$STATE/mail-sent" && ! -e "$STATE/drained" ]] ||
        fail "unreadable quarantine notified or drained"
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
        'gc bd --rig rig list --assignee actor-1 --status=in_progress ' \
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
    [[ "$publish_rc" -eq 75 && "$(namespace_count)" -eq 5 ]] ||
        fail "failed publish transaction did not preserve candidate state: $(<"$OUTPUT")"
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
        export GIT_FAIL_TX_MATCH='/rebased '
        run_lease workspace
        exit "$RUN_RC"
    )
    unpublished_rc=$?
    set -e
    [[ "$unpublished_rc" -eq 75 && "$(namespace_count)" -eq 5 ]] ||
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
    [[ "$(replay_proof_count)" -eq 8 &&
       "$(replay_mapping_count source)" -eq 3 &&
       "$(replay_mapping_count replay)" -eq 3 ]] ||
        fail "multi-commit rebase did not map every frozen source commit exactly once"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 && "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "multi-commit rebased submit did not publish exactly"
}

test_count_preserving_rebase_policy() {
    local feature_oid count base_tree head_tree empty_count commit parent

    new_case already-based-rejected false
    jq '.beads["source-1"].metadata.rejection_reason = "stale rejection"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 &&
       "$(replay_proof_count)" -eq 4 &&
       "$(replay_mapping_count source)" -eq 1 &&
       "$(replay_mapping_count replay)" -eq 1 ]] ||
        fail "already-based rejected branch did not execute one trusted replay: $(<"$OUTPUT")"
    [[ -f "$WORK/feature.txt" ]] ||
        fail "already-based trusted replay lost the feature content"

    new_case hostile-instruction-format true
    instruction_marker="$STATE/instruction-format-exec-fired"
    "$REAL_GIT" -C "$WORK" config rebase.instructionFormat \
        "%s%nexec touch '$instruction_marker'"
    set +e
    (
        export GIT_CONFIG_PARAMETERS="'rebase.instructionFormat=%s%nexec touch $instruction_marker'"
        run_lease workspace
        exit "$RUN_RC"
    )
    instruction_rc=$?
    set -e
    [[ "$instruction_rc" -eq 0 ]] ||
        fail "pinned rebase instruction format failed: $(<"$OUTPUT")"
    [[ ! -e "$instruction_marker" ]] ||
        fail "repository rebase.instructionFormat injected arbitrary shell"
    [[ "$(replay_proof_count)" -eq 4 &&
       "$(replay_mapping_count source)" -eq 1 &&
       "$(replay_mapping_count replay)" -eq 1 ]] ||
        fail "pinned instruction format did not retain the exact replay mapping"

    new_case already-upstream-commit true
    feature_oid=$("$REAL_GIT" --git-dir="$ORIGIN" rev-parse \
        refs/heads/polecat/source-1)
    "$REAL_GIT" -C "$SEED" cherry-pick "$feature_oid" >/dev/null
    "$REAL_GIT" -C "$SEED" push -q origin main
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "already-upstream commit rebase failed: $(<"$OUTPUT")"
    count=$("$REAL_GIT" -C "$WORK" rev-list --count \
        refs/remotes/origin/main..refs/heads/polecat/source-1)
    [[ "$count" -eq 1 ]] ||
        fail "already-upstream commit was dropped instead of kept empty"
    base_tree=$("$REAL_GIT" -C "$WORK" rev-parse refs/remotes/origin/main^{tree})
    head_tree=$("$REAL_GIT" -C "$WORK" rev-parse \
        refs/heads/polecat/source-1^{tree})
    [[ "$head_tree" == "$base_tree" ]] ||
        fail "already-upstream kept commit did not preserve the base tree"

    new_case multi-commit-one-empty true
    printf 'upstream-equivalent\n' >"$WORK/upstream.txt"
    "$REAL_GIT" -C "$WORK" add upstream.txt
    "$REAL_GIT" -C "$WORK" commit -qm upstream-equivalent
    printf 'unique local\n' >"$WORK/unique-local.txt"
    "$REAL_GIT" -C "$WORK" add unique-local.txt
    "$REAL_GIT" -C "$WORK" commit -qm unique-local
    printf 'upstream-equivalent\n' >"$SEED/upstream.txt"
    "$REAL_GIT" -C "$SEED" add upstream.txt
    "$REAL_GIT" -C "$SEED" commit -qm main-equivalent
    "$REAL_GIT" -C "$SEED" push -q origin main
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "multi-commit empty-preserving rebase failed: $(<"$OUTPUT")"
    count=$("$REAL_GIT" -C "$WORK" rev-list --count \
        refs/remotes/origin/main..refs/heads/polecat/source-1)
    [[ "$count" -eq 3 ]] ||
        fail "multi-commit rebase did not preserve all three source commits"
    empty_count=0
    while IFS= read -r commit; do
        parent=$("$REAL_GIT" -C "$WORK" rev-parse "$commit^")
        if [[ "$("$REAL_GIT" -C "$WORK" rev-parse "$commit^{tree}")" == \
              "$("$REAL_GIT" -C "$WORK" rev-parse "$parent^{tree}")" ]]; then
            empty_count=$((empty_count + 1))
        fi
    done < <("$REAL_GIT" -C "$WORK" rev-list \
        refs/remotes/origin/main..refs/heads/polecat/source-1)
    [[ "$empty_count" -ge 1 ]] ||
        fail "multi-commit rebase did not retain the upstream-equivalent empty commit"
    [[ "$(replay_proof_count)" -eq 8 &&
       "$(replay_mapping_count source)" -eq 3 &&
       "$(replay_mapping_count replay)" -eq 3 ]] ||
        fail "empty-preserving rebase did not map all three source commits exactly once"

    new_case unsupported-count-policy true
    set +e
    (
        export GIT_REBASE_HELP_UNSUPPORTED=1
        invoke_lease workspace
    ) >"$OUTPUT" 2>&1
    unsupported_rc=$?
    set -e
    [[ "$unsupported_rc" -eq 75 && "$(namespace_count)" -eq 4 ]] ||
        fail "unsupported rebase policy did not stop with captured recovery refs"
    rg -q 'Git lacks the count-preserving rebase policy' "$OUTPUT" ||
        fail "unsupported rebase policy lacked its exact diagnostic"
    [[ "$("$REAL_GIT" -C "$WORK" branch --show-current)" == \
       gascity-polecat-rebase/* ]] ||
        fail "unsupported policy did not remain on the lease-owned work branch"
}

test_trusted_replay_disables_hostile_post_commit_hooks() {
    local scope hooks_dir marker global_config scope_rc

    for scope in repo global environment; do
        new_case "hostile-post-commit-$scope" true
        hooks_dir="$STATE/hostile-hooks"
        marker="$STATE/hostile-post-commit-fired"
        mkdir -p "$hooks_dir"
        cat >"$hooks_dir/post-commit" <<SH
#!/usr/bin/env bash
set -euo pipefail
touch '$marker'
git rm -q --ignore-unmatch feature.txt
git -c core.hooksPath=/dev/null commit --amend --no-edit --no-verify >/dev/null
SH
        chmod +x "$hooks_dir/post-commit"

        case "$scope" in
            repo)
                "$REAL_GIT" -C "$WORK" config core.hooksPath "$hooks_dir"
                run_lease workspace
                scope_rc=$RUN_RC
                ;;
            global)
                global_config="$STATE/hostile-global.config"
                "$REAL_GIT" config --file "$global_config" \
                    core.hooksPath "$hooks_dir"
                set +e
                (
                    export GIT_CONFIG_GLOBAL="$global_config"
                    run_lease workspace
                    exit "$RUN_RC"
                )
                scope_rc=$?
                set -e
                ;;
            environment)
                set +e
                (
                    export GIT_CONFIG_COUNT=1
                    export GIT_CONFIG_KEY_0=core.hooksPath
                    export GIT_CONFIG_VALUE_0="$hooks_dir"
                    run_lease workspace
                    exit "$RUN_RC"
                )
                scope_rc=$?
                set -e
                ;;
        esac

        [[ "$scope_rc" -eq 0 ]] ||
            fail "$scope hostile post-commit config broke trusted replay: $(<"$OUTPUT")"
        [[ ! -e "$marker" ]] ||
            fail "$scope hostile post-commit hook executed during trusted replay"
        [[ -f "$WORK/feature.txt" &&
           "$(replay_proof_count)" -eq 4 &&
           "$(replay_mapping_count source)" -eq 1 &&
           "$(replay_mapping_count replay)" -eq 1 ]] ||
            fail "$scope hostile post-commit config altered or bypassed the trusted replay"
    done
}

test_trusted_replay_excludes_custom_content_drivers() {
    local scope marker driver global_config source_oid scope_rc filter_driver
    local key value common_dir git_dir attributes_file

    for scope in global environment repo worktree; do
        new_case "hostile-merge-driver-$scope" true
        marker="$STATE/hostile-merge-driver-fired"
        driver="$STATE/drop-source-driver"
        cat >"$driver" <<SH
#!/usr/bin/env bash
set -euo pipefail
touch '$marker'
# A successful custom driver may leave %A unchanged, silently dropping the
# source side of the conflict.
exit 0
SH
        chmod +x "$driver"

        "$REAL_GIT" -C "$SEED" switch -q main
        printf 'driver.txt merge=drop-source\n' >"$SEED/.gitattributes"
        printf 'main side\n' >"$SEED/driver.txt"
        "$REAL_GIT" -C "$SEED" add .gitattributes driver.txt
        "$REAL_GIT" -C "$SEED" commit -qm main-driver-conflict
        "$REAL_GIT" -C "$SEED" push -q origin main
        printf 'source side\n' >"$WORK/driver.txt"
        "$REAL_GIT" -C "$WORK" add driver.txt
        "$REAL_GIT" -C "$WORK" commit -qm source-driver-conflict
        source_oid=$(local_feature_oid)

        case "$scope" in
            global)
                global_config="$STATE/hostile-global.config"
                "$REAL_GIT" config --file "$global_config" \
                    merge.drop-source.driver "$driver %O %A %B %L %P"
                set +e
                (
                    export GIT_CONFIG_GLOBAL="$global_config"
                    run_lease workspace
                    exit "$RUN_RC"
                )
                scope_rc=$?
                set -e
                ;;
            environment)
                set +e
                (
                    export GIT_CONFIG_COUNT=1
                    export GIT_CONFIG_KEY_0=merge.drop-source.driver
                    export GIT_CONFIG_VALUE_0="$driver %O %A %B %L %P"
                    run_lease workspace
                    exit "$RUN_RC"
                )
                scope_rc=$?
                set -e
                ;;
            repo)
                "$REAL_GIT" -C "$WORK" config merge.drop-source.driver \
                    "$driver %O %A %B %L %P"
                run_lease workspace
                scope_rc=$RUN_RC
                ;;
            worktree)
                "$REAL_GIT" -C "$RIG_ROOT" config \
                    extensions.worktreeConfig true
                "$REAL_GIT" -C "$WORK" config --worktree \
                    merge.drop-source.driver \
                    "$driver %O %A %B %L %P"
                run_lease workspace
                scope_rc=$RUN_RC
                ;;
        esac

        [[ "$scope_rc" -eq 75 ]] ||
            fail "$scope custom merge driver did not fail closed: $(<"$OUTPUT")"
        [[ ! -e "$marker" ]] ||
            fail "$scope custom merge driver executed during trusted replay"
        [[ "$(local_feature_oid)" == "$source_oid" ]] ||
            fail "$scope custom merge driver changed the canonical source branch"
        if [[ "$scope" == "repo" || "$scope" == "worktree" ]]; then
            rg -q 'unsafe trusted-replay extension point' "$OUTPUT" ||
                fail "$scope custom merge driver lacked its fail-closed diagnostic"
        fi
    done

    new_case hostile-local-filter-driver true
    marker="$STATE/hostile-filter-driver-fired"
    filter_driver="$STATE/filter-driver"
    cat >"$filter_driver" <<SH
#!/usr/bin/env bash
set -euo pipefail
touch '$marker'
cat
SH
    chmod +x "$filter_driver"
    "$REAL_GIT" -C "$WORK" config filter.hostile.clean "$filter_driver"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 && ! -e "$marker" ]] ||
        fail "repository filter driver did not fail closed: $(<"$OUTPUT")"
    rg -q 'unsafe trusted-replay extension point' "$OUTPUT" ||
        fail "repository filter driver lacked its fail-closed diagnostic"

    new_case hostile-local-config-include true
    global_config="$STATE/included-hostile.config"
    "$REAL_GIT" config --file "$global_config" \
        merge.drop-source.driver /bin/false
    "$REAL_GIT" -C "$WORK" config include.path "$global_config"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "repository config include did not fail closed: $(<"$OUTPUT")"
    rg -q 'unsafe trusted-replay extension point' "$OUTPUT" ||
        fail "repository config include lacked its fail-closed diagnostic"

    for key in merge.default merge.drop-source.recursive diff.external \
        hook.hostile.command gc.recentObjectsHook; do
        new_case "hostile-local-${key//./-}" true
        marker="$STATE/hostile-$key-fired"
        driver="$STATE/hostile-$key-driver"
        cat >"$driver" <<SH
#!/usr/bin/env bash
set -euo pipefail
touch '$marker'
exit 0
SH
        chmod +x "$driver"
        value=$driver
        if [[ "$key" == "merge.default" ||
              "$key" == "merge.drop-source.recursive" ]]; then
            value=union
        fi
        source_oid=$(local_feature_oid)
        "$REAL_GIT" -C "$WORK" config "$key" "$value"
        if [[ "$key" == "hook.hostile.command" ]]; then
            "$REAL_GIT" -C "$WORK" config --add \
                hook.hostile.event post-commit
        fi
        run_lease workspace
        [[ "$RUN_RC" -eq 75 && ! -e "$marker" ]] ||
            fail "$key did not fail closed: $(<"$OUTPUT")"
        [[ "$(local_feature_oid)" == "$source_oid" ]] ||
            fail "$key changed the canonical source branch"
        rg -q 'unsafe trusted-replay extension point' "$OUTPUT" ||
            fail "$key lacked its fail-closed diagnostic"
    done

    for scope in common worktree; do
        new_case "hostile-$scope-info-attributes" true
        common_dir=$("$REAL_GIT" -C "$WORK" rev-parse \
            --path-format=absolute --git-common-dir)
        git_dir=$("$REAL_GIT" -C "$WORK" rev-parse \
            --path-format=absolute --absolute-git-dir)
        case "$scope" in
            common) attributes_file="$common_dir/info/attributes" ;;
            worktree) attributes_file="$git_dir/info/attributes" ;;
        esac
        mkdir -p "$(dirname "$attributes_file")"
        printf '*.txt merge=union\n' >"$attributes_file"
        source_oid=$(local_feature_oid)
        run_lease workspace
        [[ "$RUN_RC" -eq 75 ]] ||
            fail "$scope info attributes did not fail closed: $(<"$OUTPUT")"
        [[ "$(local_feature_oid)" == "$source_oid" ]] ||
            fail "$scope info attributes changed the canonical source branch"
        rg -q 'unsafe trusted-replay extension point' "$OUTPUT" ||
            fail "$scope info attributes lacked its fail-closed diagnostic"
    done

    for scope in common worktree; do
        new_case "hostile-$scope-info-grafts" true
        common_dir=$("$REAL_GIT" -C "$WORK" rev-parse \
            --path-format=absolute --git-common-dir)
        git_dir=$("$REAL_GIT" -C "$WORK" rev-parse \
            --path-format=absolute --absolute-git-dir)
        case "$scope" in
            common) attributes_file="$common_dir/info/grafts" ;;
            worktree) attributes_file="$git_dir/info/grafts" ;;
        esac
        mkdir -p "$(dirname "$attributes_file")"
        printf '%s %s\n' "$(local_feature_oid)" \
            "$("$REAL_GIT" -C "$WORK" rev-parse refs/remotes/origin/main)" \
            >"$attributes_file"
        source_oid=$(local_feature_oid)
        run_lease workspace
        [[ "$RUN_RC" -eq 75 ]] ||
            fail "$scope info grafts did not fail closed: $(<"$OUTPUT")"
        [[ "$(local_feature_oid)" == "$source_oid" ]] ||
            fail "$scope info grafts changed the canonical source branch"
        rg -q 'unsafe trusted-replay extension point' "$OUTPUT" ||
            fail "$scope info grafts lacked its fail-closed diagnostic"
    done

    new_case hostile-repository-routing-environment true
    source_oid=$(local_feature_oid)
    set +e
    (
        export GIT_DIR="$ORIGIN"
        export GIT_WORK_TREE="$WORK"
        export GIT_COMMON_DIR="$ORIGIN"
        export GIT_INDEX_FILE="$STATE/hostile-index"
        export GIT_OBJECT_DIRECTORY="$ORIGIN/objects"
        export GIT_ALTERNATE_OBJECT_DIRECTORIES="$RIG_ROOT/.git/objects"
        export GIT_NAMESPACE=hostile
        run_lease workspace
        exit "$RUN_RC"
    )
    scope_rc=$?
    set -e
    [[ "$scope_rc" -eq 0 ]] ||
        fail "repository-routing environment was not sanitized: $(<"$OUTPUT")"
    [[ "$(local_feature_oid)" != "$source_oid" &&
       "$(replay_proof_count)" -eq 4 ]] ||
        fail "sanitized repository-routing environment did not publish the exact replay"

    new_case hostile-local-core-worktree true
    source_oid=$(local_feature_oid)
    "$REAL_GIT" -C "$WORK" config core.worktree "$SEED"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "repository core.worktree did not fail closed: $(<"$OUTPUT")"
    [[ "$(local_feature_oid)" == "$source_oid" ]] ||
        fail "repository core.worktree changed the canonical source branch"
}

test_conflict_resolved_to_base_keeps_empty_commit() {
    local count canonical_pre materialized_empty
    new_case conflict-resolved-to-base true
    "$REAL_GIT" -C "$SEED" switch -q main
    printf 'base from main\n' >"$SEED/base.txt"
    "$REAL_GIT" -C "$SEED" add base.txt
    "$REAL_GIT" -C "$SEED" commit -qm main-conflict
    "$REAL_GIT" -C "$SEED" push -q origin main
    printf 'base from feature\n' >"$WORK/base.txt"
    "$REAL_GIT" -C "$WORK" add base.txt
    "$REAL_GIT" -C "$WORK" commit -qm feature-conflict

    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "base-resolution conflict did not stop: $(<"$OUTPUT")"
    printf 'base from main\n' >"$WORK/base.txt"
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "base-resolution staging failed: $(<"$OUTPUT")"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "base-resolution continuation failed: $(<"$OUTPUT")"
    count=$("$REAL_GIT" -C "$WORK" rev-list --count \
        refs/remotes/origin/main..refs/heads/polecat/source-1)
    [[ "$count" -eq 2 ]] ||
        fail "conflict resolved to base dropped the now-empty source commit"
    [[ "$("$REAL_GIT" -C "$WORK" rev-parse HEAD^{tree})" == \
       "$("$REAL_GIT" -C "$WORK" rev-parse HEAD^^{tree})" ]] ||
        fail "conflict resolved to base did not retain an empty top commit"

    prepare_simple_conflict empty-conflict-continue-crash
    canonical_pre=$("$REAL_GIT" -C "$WORK" rev-parse \
        refs/heads/polecat/source-1)
    printf 'base from main\n' >"$WORK/base.txt"
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "empty continuation crash fixture could not stage: $(<"$OUTPUT")"
    GIT_EMPTY_COMMIT_RESPONSE_LOST_ONCE=1 \
    GIT_FAIL_REBASE_CONTINUE_BEFORE_ONCE=1 \
        run_lease workspace
    [[ "$RUN_RC" -eq 75 &&
       -e "$STATE/empty-commit-response-lost-fired" &&
       -e "$STATE/rebase-continue-prewrite-failure-fired" ]] ||
        fail "empty commit response loss/pre-continue crash was not preserved: $(<"$OUTPUT")"
    materialized_empty=$("$REAL_GIT" -C "$WORK" rev-parse HEAD)
    [[ "$materialized_empty" != "$canonical_pre" &&
       "$("$REAL_GIT" -C "$WORK" rev-parse HEAD^{tree})" == \
         "$("$REAL_GIT" -C "$WORK" rev-parse HEAD^^{tree})" &&
       "$("$REAL_GIT" -C "$WORK" rev-parse refs/heads/polecat/source-1)" == \
         "$canonical_pre" ]] ||
        fail "empty response-loss state did not retain one detached empty commit while freezing the canonical branch"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "empty commit pre-continue retry did not recover: $(<"$OUTPUT")"
    count=$("$REAL_GIT" -C "$WORK" rev-list --count \
        refs/remotes/origin/main..refs/heads/polecat/source-1)
    [[ "$count" -eq 2 ]] ||
        fail "pre-continue crash retry duplicated or dropped the empty commit"
    [[ "$("$REAL_GIT" -C "$WORK" rev-list --count \
            "$materialized_empty..refs/heads/polecat/source-1")" -eq 0 &&
       "$("$REAL_GIT" -C "$WORK" rev-parse refs/heads/polecat/source-1)" != \
         "$canonical_pre" ]] ||
        fail "empty response-loss retry replaced the proved commit or skipped atomic publication"
    mapping_hits=$("$REAL_GIT" -C "$WORK" for-each-ref \
        --points-at "$materialized_empty" --format='%(refname)' \
        refs/gascity/polecat-rebase-proofs |
        sed -n '\|/replay/[0-9][0-9]*$|p')
    [[ "$(replay_proof_count)" -eq 6 &&
       "$(printf '%s\n' "$mapping_hits" | sed '/^$/d' | wc -l)" -eq 1 ]] ||
        fail "empty response-loss retry duplicated or omitted its replay mapping"
}

test_multiple_conflict_generations_and_hostile_paths() {
    local first_path second_path count
    first_path=$'hostile\tpath\nname.txt'
    second_path='second-conflict.txt'
    new_case multiple-conflict-generations true
    "$REAL_GIT" -C "$SEED" switch -q main
    printf 'main one\n' >"$SEED/$first_path"
    printf 'main two\n' >"$SEED/$second_path"
    "$REAL_GIT" -C "$SEED" add -- "$first_path" "$second_path"
    "$REAL_GIT" -C "$SEED" commit -qm main-two-conflicts
    "$REAL_GIT" -C "$SEED" push -q origin main
    printf 'feature one\n' >"$WORK/$first_path"
    "$REAL_GIT" -C "$WORK" add -- "$first_path"
    "$REAL_GIT" -C "$WORK" commit -qm feature-conflict-one
    printf 'feature two\n' >"$WORK/$second_path"
    "$REAL_GIT" -C "$WORK" add -- "$second_path"
    "$REAL_GIT" -C "$WORK" commit -qm feature-conflict-two

    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "first hostile conflict did not stop: $(<"$OUTPUT")"
    printf 'resolved one\n' >"$WORK/$first_path"
    printf 'untracked\n' >"$WORK/untracked-during-conflict"
    run_conflict_stage
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "untracked conflict state was accepted"
    rm -f -- "$WORK/untracked-during-conflict"
    printf 'outside change\n' >"$WORK/new-base.txt"
    run_conflict_stage
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "unstaged path outside U was accepted"
    "$REAL_GIT" -C "$WORK" checkout -- new-base.txt
    printf 'preserved staged change\n' >"$WORK/feature.txt"
    "$REAL_GIT" -C "$WORK" add feature.txt
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "hostile NUL-safe conflict staging failed: $(<"$OUTPUT")"
    "$REAL_GIT" -C "$WORK" diff --cached --quiet -- feature.txt &&
        fail "conflict staging lost the already-staged nonconflict path"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "second conflict generation did not stop: $(<"$OUTPUT")"
    printf 'resolved two\n' >"$WORK/$second_path"
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "second conflict generation staging failed: $(<"$OUTPUT")"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "multiple conflict continuation failed: $(<"$OUTPUT")"
    [[ "$(conflict_proof_count)" -eq 6 ]] ||
        fail "multiple conflicts did not retain two immutable three-ref proofs"
    count=$("$REAL_GIT" -C "$WORK" rev-list --count \
        refs/remotes/origin/main..refs/heads/polecat/source-1)
    [[ "$count" -eq 3 ]] ||
        fail "multiple conflict rebase changed the source commit count"
}

prepare_simple_conflict() {
    local name=$1
    new_case "$name" true
    "$REAL_GIT" -C "$SEED" switch -q main
    printf 'base from main\n' >"$SEED/base.txt"
    "$REAL_GIT" -C "$SEED" add base.txt
    "$REAL_GIT" -C "$SEED" commit -qm main-conflict
    "$REAL_GIT" -C "$SEED" push -q origin main
    printf 'base from feature\n' >"$WORK/base.txt"
    "$REAL_GIT" -C "$WORK" add base.txt
    "$REAL_GIT" -C "$WORK" commit -qm feature-conflict
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "$name did not establish a lease-owned conflict: $(<"$OUTPUT")"
}

test_conflict_proof_response_loss_and_races() {
    local done_ref tree_ref

    prepare_simple_conflict conflict-intent-response-loss
    printf 'resolved intent loss\n' >"$WORK/base.txt"
    GIT_TX_RESPONSE_LOST_MATCH='/context ' run_conflict_stage
    [[ "$RUN_RC" -eq 0 && -e "$STATE/transaction-response-lost-fired" &&
       "$(conflict_proof_count)" -eq 3 ]] ||
        fail "intent transaction response loss was not recovered exactly: $(<"$OUTPUT")"

    prepare_simple_conflict conflict-done-prewrite-failure
    printf 'resolved done retry\n' >"$WORK/base.txt"
    GIT_FAIL_TX_MATCH='/done ' run_conflict_stage
    [[ "$RUN_RC" -eq 75 && "$(conflict_proof_count)" -eq 2 &&
       -z "$("$REAL_GIT" -C "$WORK" ls-files -u)" ]] ||
        fail "post-add/pre-done failure did not preserve recoverable intent"
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 && "$(conflict_proof_count)" -eq 3 ]] ||
        fail "post-add/pre-done retry did not publish exact done proof: $(<"$OUTPUT")"
    rg -q 'replay=true' "$OUTPUT" ||
        fail "post-add/pre-done retry did not report proof replay"

    prepare_simple_conflict conflict-done-response-loss
    printf 'resolved done loss\n' >"$WORK/base.txt"
    GIT_TX_RESPONSE_LOST_MATCH='/done ' run_conflict_stage
    [[ "$RUN_RC" -eq 0 && -e "$STATE/transaction-response-lost-fired" &&
       "$(conflict_proof_count)" -eq 3 ]] ||
        fail "done transaction response loss was not accepted by exact readback"

    prepare_simple_conflict conflict-symbolic-proof
    printf 'resolved symbolic\n' >"$WORK/base.txt"
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "symbolic proof fixture could not stage: $(<"$OUTPUT")"
    done_ref=$("$REAL_GIT" -C "$WORK" for-each-ref \
        --format='%(refname)' refs/gascity/polecat-conflicts | grep '/done$')
    [[ -n "$done_ref" ]] || fail "symbolic proof fixture has no done ref"
    tree_ref="${done_ref%/done}/tree"
    "$REAL_GIT" -C "$WORK" symbolic-ref "$done_ref" "$tree_ref"
    run_lease workspace
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "symbolic conflict proof was accepted by lease continuation"
    jq -e '
      .beads["source-1"].status == "open" and
      .beads["workspace-1"].status == "in_progress"
    ' "$DB" >/dev/null ||
        fail "symbolic conflict proof caused a false hard quarantine"

    prepare_simple_conflict conflict-resolution-content-race
    printf 'reviewed resolution\n' >"$WORK/base.txt"
    GIT_MUTATE_BEFORE_REAL_ADD_PATH="$WORK/base.txt" \
    GIT_MUTATE_BEFORE_REAL_ADD_CONTENT='raced resolution' \
        run_conflict_stage
    [[ "$RUN_RC" -eq 75 && -e "$STATE/real-add-race-fired" &&
       "$(conflict_proof_count)" -eq 2 ]] ||
        fail "U-resolution content race was not caught before done publication"

    prepare_simple_conflict conflict-outside-path-race
    printf 'reviewed resolution\n' >"$WORK/base.txt"
    GIT_MUTATE_BEFORE_REAL_ADD_PATH="$WORK/new-base.txt" \
    GIT_MUTATE_BEFORE_REAL_ADD_CONTENT='outside race' \
        run_conflict_stage
    [[ "$RUN_RC" -eq 75 && -e "$STATE/real-add-race-fired" &&
       "$(conflict_proof_count)" -eq 2 ]] ||
        fail "outside-U race was not caught before done publication"

    prepare_simple_conflict conflict-marker-rejection
    printf '%s\n' '<<<<<<< ours' 'bad' '=======' 'worse' '>>>>>>> theirs' \
        >"$WORK/base.txt"
    run_conflict_stage
    [[ "$RUN_RC" -eq 75 && "$(conflict_proof_count)" -eq 0 ]] ||
        fail "conflict-marker resolution was accepted"
    printf 'clean resolution\n' >"$WORK/base.txt"
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "clean resolution after marker rejection failed: $(<"$OUTPUT")"
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
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "exact conflict staging command failed: $(<"$OUTPUT")"
    [[ -z "$("$REAL_GIT" -C "$WORK" ls-files -u)" ]] ||
        fail "conflict staging command left unmerged entries"
    run_lease workspace
    [[ "$RUN_RC" -eq 0 && "$(namespace_count)" -eq 5 ]] ||
        fail "same workspace action did not continue and publish the resolved rebase: $(<"$OUTPUT")"
    [[ "$(<"$WORK/base.txt")" == "resolved base" ]] ||
        fail "workspace conflict continuation lost the reviewed resolution"
    run_lease submit --auto-push true
    [[ "$RUN_RC" -eq 0 && "$(remote_feature_oid)" == "$(local_feature_oid)" ]] ||
        fail "resolved conflict submit did not publish exactly"
}

test_conflict_todo_injection_stops_before_execution() {
    local todo marker canonical_pre
    prepare_simple_conflict conflict-todo-injection
    canonical_pre=$(local_feature_oid)
    printf 'reviewed resolution\n' >"$WORK/base.txt"
    run_conflict_stage
    [[ "$RUN_RC" -eq 0 ]] ||
        fail "todo-injection fixture could not stage its conflict: $(<"$OUTPUT")"
    todo=$("$REAL_GIT" -C "$WORK" rev-parse --git-path \
        rebase-merge/git-rebase-todo)
    [[ "$todo" == /* ]] || todo="$WORK/$todo"
    marker="$STATE/arbitrary-todo-exec-fired"
    {
        printf 'exec touch %q\n' "$marker"
        sed -n '1,$p' "$todo"
    } >"$todo.tmp"
    mv "$todo.tmp" "$todo"

    run_lease workspace
    [[ "$RUN_RC" -eq 64 ]] ||
        fail "tampered conflict todo returned $RUN_RC instead of hard failure: $(<"$OUTPUT")"
    [[ ! -e "$marker" ]] ||
        fail "tampered conflict todo executed arbitrary shell before validation"
    [[ "$(local_feature_oid)" == "$canonical_pre" ]] ||
        fail "tampered conflict todo moved the canonical branch"
    [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "blocked" ]] ||
        fail "tampered conflict todo was not durably quarantined"
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

test_invalid_arguments_stop_before_provenance
test_normal_push
test_direct_store_convoy_authority
test_convoy_schema_and_identity_fail_closed
test_convoy_source_revalidated_before_protected_mutation
test_rebased_exact_lease_push
test_rejected_auto_push_false_stops_before_freeze
test_auto_push_false_proof_is_local_and_idempotent
test_submit_proof_ref_tamper_is_hard
test_submit_proof_create_race_is_idempotent
test_dirty_artifact_cannot_create_submit_proof
test_remote_race_terminalizes
test_terminalization_revalidates_graph_authority
test_terminalization_revalidates_convoy_authority
test_unreadable_is_indeterminate
test_capture_mirror_crash_recovery
test_rebase_mirror_crash_recovery
test_submit_mirror_crash_recovery
test_push_response_lost_recovery
test_cleanup_transaction_retry
test_metadata_cleanup_restart
test_completed_rebase_work_ref_recovers_after_lost_response
test_sealed_replay_exec_response_loss_recovers
test_hostile_same_count_work_ref_cannot_publish_captured_lease
test_direct_lease_rejects_symlink_git_pointer
test_workspace_rejects_absent_branch_metadata_without_quarantine
test_frozen_push_url
test_mail_failure_retries_before_step_close
test_terminalization_failure_never_reports_durable_quarantine
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
test_count_preserving_rebase_policy
test_trusted_replay_disables_hostile_post_commit_hooks
test_trusted_replay_excludes_custom_content_drivers
test_conflict_resolved_to_base_keeps_empty_commit
test_multiple_conflict_generations_and_hostile_paths
test_conflict_proof_response_loss_and_races
test_true_rebase_conflict_resolution
test_conflict_todo_injection_stops_before_execution
test_linked_worktree_ref_races

echo "polecat lease command tests passed"
