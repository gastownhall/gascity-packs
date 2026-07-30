#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/polecat-submit/run.sh"
LEASE_COMMAND="$ROOT/gastown/commands/polecat-lease/run.sh"
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

if [[ "$1" == "gastown" && "$2" == "polecat-lease" ]]; then
    [[ "${FAIL_LEASE:-}" != "1" ]] || exit 97
    printf 'lease-cwd=%s\n' "$PWD" >>"$FAKE_LOG"
    shift 2
    exec bash "$LEASE_COMMAND" "$@"
fi

if [[ "$1" == "runtime" && "$2" == "drain-ack" ]]; then
    [[ "${FAIL_DRAIN:-}" != "1" ]] || exit 98
    : >"$FAKE_DB.drained"
    exit 0
fi

if [[ "$1" == "session" &&
      ("$2" == "wake" || "$2" == "nudge") ]]; then
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
                --assignee)
                    assignee=$2
                    shift 2
                    ;;
                --assignee=*)
                    assignee=${1#*=}
                    shift
                    ;;
                --unset-metadata)
                    unset_key=$2
                    shift 2
                    if [[ "${DROP_UNSET_METADATA:-}" == "$unset_key" ]]; then
                        continue
                    fi
                    metadata=$(jq -cn \
                        --argjson current "$metadata" \
                        --arg key "$unset_key" \
                        '$current + {($key): null}')
                    ;;
                --append-notes)
                    shift 2
                    ;;
                --notes)
                    shift 2
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        [[ "${UPDATE_MODE:-}" != "noop" ]] || exit 0
        jq --arg id "$id" --arg status "$status" \
           --arg assignee "${assignee-__unchanged__}" \
           --argjson metadata "$metadata" '
          if $status != "" then .beads[$id].status = $status else . end |
          if $assignee != "__unchanged__"
          then .beads[$id].assignee = $assignee else . end |
          .beads[$id].metadata += $metadata |
          .beads[$id].metadata |= with_entries(select(.value != null))
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
    CITY="$STATE/city"
    RIG_ROOT="$STATE/rig"
    ORIGIN="$STATE/origin.git"
    ARTIFACT="$CITY/.gc/worktrees/demo/artifacts/worktrees/source-1"
    RUN_CWD="$STATE/provider-cwd"
    mkdir -p "$(dirname -- "$ARTIFACT")" "$RUN_CWD"
    git init -q --bare "$ORIGIN"
    git init -q -b main "$RIG_ROOT"
    git -C "$RIG_ROOT" config user.name "Polecat Submit Test"
    git -C "$RIG_ROOT" config user.email "polecat-submit@example.invalid"
    printf 'base\n' >"$RIG_ROOT/base.txt"
    git -C "$RIG_ROOT" add base.txt
    git -C "$RIG_ROOT" commit -q -m base
    git -C "$RIG_ROOT" remote add origin "$ORIGIN"
    git -C "$RIG_ROOT" push -q -u origin main
    git -C "$RIG_ROOT" branch polecat/source-1
    git -C "$RIG_ROOT" worktree add -q "$ARTIFACT" polecat/source-1
    jq -n --arg artifact "$ARTIFACT" '{
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
            artifact_dir: $artifact,
            auto_push: false,
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
    mkdir -p "$RUN_CWD"
    (
    cd "$RUN_CWD" || exit 99
    BEADS_ACTOR="runtime-name" \
    GC_SESSION_NAME="runtime-name" \
    GC_SESSION_ID="${TEST_SESSION_ID-session-1}" \
    GC_ALIAS="session-1" \
    GC_AGENT="agent-name" \
    GC_RIG="${TEST_RIG-demo}" \
    GC_CITY_PATH="$CITY" \
    GC_RIG_ROOT="$RIG_ROOT" \
    GC_BIN="$FAKE_GC" \
    LEASE_COMMAND="$LEASE_COMMAND" \
    FAKE_DB="$DB" \
    FAKE_LOG="$LOG" \
    FAIL_LIST_IDENTITY="${FAIL_LIST_IDENTITY:-}" \
    FAIL_SHOW_ID="${FAIL_SHOW_ID:-}" \
    FAIL_FIRST_POST_UPDATE_SHOW="${FAIL_FIRST_POST_UPDATE_SHOW:-}" \
    FAIL_CONVOY="${FAIL_CONVOY:-}" \
    FAIL_LEASE="${FAIL_LEASE:-}" \
    FAIL_DRAIN="${FAIL_DRAIN:-}" \
    UPDATE_MODE="${UPDATE_MODE:-}" \
    DROP_UNSET_METADATA="${DROP_UNSET_METADATA:-}" \
    INJECT_LIST_ROW_MODE="${INJECT_LIST_ROW_MODE:-}" \
    CLEAR_TOKEN_ON_REVALIDATE_ROOT="${CLEAR_TOKEN_ON_REVALIDATE_ROOT:-}" \
    TEST_SESSION_ID="${TEST_SESSION_ID:-session-1}" \
        bash "$COMMAND" "$@" >"$OUTPUT" 2>&1
    )
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
    local mode="auto_push_false"
    if [[ "$(jq -r '.beads["source-1"].status' "$DB")" == "closed" ||
          "$(jq -r '.beads["source-1"].assignee' "$DB")" == *refinery ]]; then
        mode="refinery"
    fi
    install_execution_proof "$mode"
    jq --arg convoy "$convoy" \
        '.beads["source-1"].metadata["gc.polecat_submit_convoy"] = $convoy' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
}

install_execution_proof() {
    local mode=$1
    local session=${TEST_SESSION_ID:-session-1}
    local auto_push=false root_rig root_prefix witness common artifact_real
    local fetch_url push_url repo_fp worktree_fp fetch_fp push_fp head key
    local context context_oid
    [[ "$mode" == "auto_push_false" ]] || auto_push=true
    root_rig=$(jq -r '.beads["root-1"].metadata["gc.var.rig_name"] // ""' "$DB")
    root_prefix=$(jq -r '.beads["root-1"].metadata["gc.var.binding_prefix"] // ""' "$DB")
    witness="${root_rig:+$root_rig/}${root_prefix}witness"
    common=$(git -C "$RIG_ROOT" rev-parse --path-format=absolute --git-common-dir)
    common=$(CDPATH= cd -- "$common" && pwd -P)
    artifact_real=$(CDPATH= cd -- "$ARTIFACT" && pwd -P)
    fetch_url=$(git -C "$RIG_ROOT" remote get-url --all origin)
    push_url=$(git -C "$RIG_ROOT" remote get-url --push --all origin)
    repo_fp=$(printf 'git-common-v1\0%s' "$common" |
        git -C "$RIG_ROOT" hash-object --stdin)
    worktree_fp=$(printf 'worktree-v1\0%s' "$artifact_real" |
        git -C "$RIG_ROOT" hash-object --stdin)
    fetch_fp=$(printf 'fetch-url-v1\0%s' "$fetch_url" |
        git -C "$RIG_ROOT" hash-object --stdin)
    push_fp=$(printf 'push-url-v1\0%s' "$push_url" |
        git -C "$RIG_ROOT" hash-object --stdin)
    head=$(git -C "$ARTIFACT" rev-parse --verify HEAD)
    key=$(printf '%s\n' \
        "schema=gascity-polecat-submit-proof-key-v1" \
        "source=source-1" \
        "workflow_root=root-1" \
        "step=submit-1" \
        "input_convoy=convoy-1" \
        "session_id=$session" |
        git -C "$RIG_ROOT" hash-object --stdin)
    context=$(printf '%s\n' \
        "schema=gascity-polecat-submit-proof-v1" \
        "version=1" \
        "key=$key" \
        "source=source-1" \
        "workflow_root=root-1" \
        "step=submit-1" \
        "step_assignee=session-1" \
        "input_convoy=convoy-1" \
        "session_id=$session" \
        "branch=polecat/source-1" \
        "target=main" \
        "auto_push=$auto_push" \
        "head_oid=$head" \
        "rig=$root_rig" \
        "binding_prefix=$root_prefix" \
        "witness=$witness" \
        "repo_common_fingerprint=$repo_fp" \
        "worktree_fingerprint=$worktree_fp" \
        "origin_fetch_fingerprint=$fetch_fp" \
        "origin_push_fingerprint=$push_fp")
    context_oid=$(printf '%s\n' "$context" |
        git -C "$RIG_ROOT" hash-object -w --stdin)
    git -C "$RIG_ROOT" update-ref \
        "refs/gascity/polecat-submit-proofs/v1/$key/context" "$context_oid"
    git -C "$RIG_ROOT" update-ref \
        "refs/gascity/polecat-submit-proofs/v1/$key/head" "$head"
    jq --arg artifact "$artifact_real" --arg session "$session" \
       --arg head "$head" --arg key "$key" --arg context "$context_oid" \
       --argjson auto_push "$auto_push" '
      .beads["source-1"].metadata.auto_push = $auto_push |
      .beads["source-1"].metadata.artifact_dir = $artifact |
      .beads["source-1"].metadata["gc.polecat_submit_execute_version"] = 1 |
      .beads["source-1"].metadata["gc.polecat_submit_lease_version"] = 1 |
      .beads["source-1"].metadata["gc.polecat_submit_execute_session_id"] = $session |
      .beads["source-1"].metadata["gc.polecat_submit_execute_step_id"] = "submit-1" |
      .beads["source-1"].metadata["gc.polecat_submit_execute_head_sha"] = $head |
      .beads["source-1"].metadata["gc.polecat_submit_execute_artifact_dir"] = $artifact |
      .beads["source-1"].metadata["gc.polecat_submit_proof_key"] = $key |
      .beads["source-1"].metadata["gc.polecat_submit_proof_context"] = $context |
      .beads["source-1"].metadata["gc.polecat_submit_proof_head"] = $head
    ' "$DB" >"$DB.tmp"
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

new_case guard-hq-empty-rig-cannot-reuse-rig-proof
jq '.beads["root-1"].metadata["gc.var.rig_name"] = "" |
    .beads["source-1"].assignee = "gastown.refinery" |
    .beads["source-1"].metadata["gc.polecat_submit_convoy"] = "convoy-1"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
TEST_RIG=""
run_submit guard
unset TEST_RIG
[[ "$RUN_RC" -eq 75 ]] ||
    fail "HQ empty-rig proof mismatch returned $RUN_RC instead of 75"
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
[[ "$(jq -r '.beads["submit-1"].metadata["gc.polecat_submit_version"]' "$DB")" == "2" &&
   "$(jq -r '.beads["submit-1"].metadata["gc.polecat_submit_session_id"]' "$DB")" == "session-1" ]] ||
    fail "applied update did not persist versioned replay evidence"
jq -e '.beads["submit-1"].metadata["gc.polecat_submit_version"] |
       type == "number" and . == 2' "$DB" >/dev/null ||
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
TEST_SESSION_ID=session-old
set_generation_token
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

new_case complete-rejects-mutable-terminal-metadata
jq '.beads["source-1"].metadata["gc.polecat_submit_convoy"] = "convoy-1"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "mutable terminal metadata without durable proof returned $RUN_RC instead of 75"
assert_live_unmutated

new_case complete-rejects-missing-proof-context-ref
set_generation_token
proof_key=$(jq -r \
    '.beads["source-1"].metadata["gc.polecat_submit_proof_key"]' "$DB")
git -C "$RIG_ROOT" update-ref -d \
    "refs/gascity/polecat-submit-proofs/v1/$proof_key/context"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "missing proof context ref returned $RUN_RC instead of 75"
assert_live_unmutated

new_case guard-rejects-tampered-proof-head-ref
set_generation_token
proof_key=$(jq -r \
    '.beads["source-1"].metadata["gc.polecat_submit_proof_key"]' "$DB")
tampered_head=$(printf 'not a commit\n' |
    git -C "$RIG_ROOT" hash-object -w --stdin)
git -C "$RIG_ROOT" update-ref \
    "refs/gascity/polecat-submit-proofs/v1/$proof_key/head" \
    "$tampered_head"
run_submit guard
[[ "$RUN_RC" -eq 75 ]] ||
    fail "tampered proof head ref returned $RUN_RC instead of 75: $(<"$OUTPUT"); ref=$(git -C "$RIG_ROOT" rev-parse "refs/gascity/polecat-submit-proofs/v1/$proof_key/head") source=$(jq -r '.beads["source-1"].metadata["gc.polecat_submit_execute_head_sha"]' "$DB")"
assert_live_unmutated

new_case complete-rejects-dirty-auto-push-false-artifact
set_generation_token
printf 'dirty after proof\n' >"$ARTIFACT/after-proof.txt"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "dirty proof-bound auto_push=false artifact returned $RUN_RC instead of 75"
assert_live_unmutated

new_case complete-rejects-moved-auto-push-false-artifact
set_generation_token
mv "$ARTIFACT" "$ARTIFACT.moved"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "missing proof-bound auto_push=false artifact returned $RUN_RC instead of 75"
assert_live_unmutated

new_case execute-auto-push-false-from-wrong-cwd
printf 'captured at submit\n' >"$ARTIFACT/final.txt"
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "auto_push=false execute failed: $(<"$OUTPUT")"
grep -F 'POLECAT_SUBMIT_EXECUTE_COMPLETE' "$OUTPUT" >/dev/null &&
    grep -F 'mode=auto_push_false' "$OUTPUT" >/dev/null ||
    fail "auto_push=false execute did not report exact completion"
grep -F "lease-cwd=$ARTIFACT" "$LOG" >/dev/null ||
    fail "execute did not enter the recorded artifact before lease submit"
[[ -z "$(git -C "$ARTIFACT" status --porcelain --untracked-files=all)" ]] ||
    fail "execute left the task artifact dirty"
[[ "$(git -C "$ARTIFACT" show HEAD:final.txt)" == "captured at submit" ]] ||
    fail "execute did not deterministically capture remaining changes"
[[ "$(git -C "$RIG_ROOT" for-each-ref --format='%(refname)' \
    refs/gascity/polecat-submit-proofs | wc -l)" -eq 2 ]] ||
    fail "execute did not retain exactly one two-ref submit proof"
[[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_submit_proof_head"]' "$DB")" == \
   "$(git -C "$ARTIFACT" rev-parse HEAD)" ]] ||
    fail "source terminal metadata did not bind the exact proof head"
[[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "closed" &&
   -e "$DB.drained" ]] ||
    fail "execute did not close the exact step and drain"
if git -C "$RIG_ROOT" ls-remote --exit-code origin \
    refs/heads/polecat/source-1 >/dev/null 2>&1; then
    fail "auto_push=false execute pushed the feature branch"
fi

new_case execute-refinery
jq '.beads["source-1"].metadata.auto_push = true |
    del(.beads["source-1"].metadata.branch_ready) |
    del(.beads["source-1"].metadata.halt_reason)' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "refinery execute failed: $(<"$OUTPUT")"
[[ "$(jq -r '.beads["source-1"].assignee' "$DB")" == "demo/gastown.refinery" ]] ||
    fail "refinery execute did not make the exact terminal assignment"
remote_head=$(git -C "$RIG_ROOT" ls-remote origin \
    refs/heads/polecat/source-1 | awk '{print $1}')
[[ -n "$remote_head" &&
   "$remote_head" == "$(git -C "$ARTIFACT" rev-parse HEAD)" ]] ||
    fail "refinery execute did not verify the pushed exact head"
grep -F 'gc session wake demo/gastown.refinery' "$LOG" >/dev/null &&
    grep -F 'gc session nudge demo/gastown.refinery' "$LOG" >/dev/null ||
    fail "refinery execute did not wake and nudge the refinery"

new_case execute-lease-failure-is-fail-closed
printf 'capture before rejected lease\n' >"$ARTIFACT/final.txt"
FAIL_LEASE=1
run_submit execute
unset FAIL_LEASE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "lease failure returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" &&
   "$(jq -r '.beads["source-1"].metadata["gc.polecat_submit_convoy"] // ""' "$DB")" == "" ]] ||
    fail "lease failure advanced durable Graph state"
[[ "$(git -C "$RIG_ROOT" for-each-ref --format='%(refname)' \
    refs/gascity/polecat-submit-proofs | wc -l)" -eq 0 ]] ||
    fail "failed lease left a durable submit proof"

new_case execute-proof-response-loss-replay
UPDATE_MODE=fail
run_submit execute
unset UPDATE_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "post-proof source-update loss returned $RUN_RC instead of 75"
[[ "$(grep -c 'gc gastown polecat-lease submit' "$LOG")" -eq 1 ]] ||
    fail "first execute did not call the stateful lease exactly once"
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "durable-proof response-loss replay failed: $(<"$OUTPUT")"
[[ "$(grep -c 'gc gastown polecat-lease submit' "$LOG")" -eq 1 ]] ||
    fail "durable-proof replay repeated the stateful lease"
: >"$LOG"
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "closed exact execute replay failed: $(<"$OUTPUT")"
grep -F 'POLECAT_SUBMIT_EXECUTE_COMPLETE replay=true' "$OUTPUT" >/dev/null ||
    fail "closed execute replay was not reported"
! grep -F 'gc gastown polecat-lease submit' "$LOG" >/dev/null ||
    fail "closed exact replay called the lease again"

new_case execute-source-update-apply-then-error
UPDATE_MODE=apply-then-error
run_submit execute
unset UPDATE_MODE
[[ "$RUN_RC" -eq 0 ]] ||
    fail "applied source-update response loss did not recover: $(<"$OUTPUT")"
[[ "$(jq -r '.beads["source-1"].metadata["gc.polecat_submit_convoy"]' "$DB")" == "convoy-1" &&
   "$(jq -r '.beads["submit-1"].status' "$DB")" == "closed" &&
   -e "$DB.drained" ]] ||
    fail "applied source-update response loss did not reach durable terminal state"
[[ "$(grep -c 'gc gastown polecat-lease submit' "$LOG")" -eq 1 ]] ||
    fail "applied source-update response loss repeated the stateful lease"

for stale_key in artifact_source_sha artifact_cleanup_state; do
    new_case "execute-rejects-lost-${stale_key}-unset"
    jq '.beads["source-1"].metadata.artifact_source_sha = "stale-source" |
        .beads["source-1"].metadata.artifact_cleanup_state = "pending"' \
        "$DB" >"$DB.tmp"
    mv "$DB.tmp" "$DB"
    DROP_UNSET_METADATA=$stale_key
    run_submit execute
    unset DROP_UNSET_METADATA
    [[ "$RUN_RC" -eq 75 ]] ||
        fail "lost $stale_key unset returned $RUN_RC instead of 75"
    [[ "$(jq --arg key "$stale_key" \
        '.beads["source-1"].metadata | has($key)' "$DB")" == "true" ]] ||
        fail "lost $stale_key unset fixture did not retain stale metadata"
    [[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "in_progress" &&
       ! -e "$DB.drained" ]] ||
        fail "lost $stale_key unset closed or drained the workflow"
done

new_case execute-existing-proof-rejects-later-dirty-work
UPDATE_MODE=fail
run_submit execute
unset UPDATE_MODE
[[ "$RUN_RC" -eq 75 ]] ||
    fail "dirty-proof setup did not stop after durable proof"
proof_head=$(git -C "$ARTIFACT" rev-parse HEAD)
printf 'must not be captured after proof\n' >"$ARTIFACT/late-change.txt"
run_submit execute
[[ "$RUN_RC" -eq 75 ]] ||
    fail "execute accepted dirty work after a retained submit proof"
[[ "$(git -C "$ARTIFACT" rev-parse HEAD)" == "$proof_head" &&
   -f "$ARTIFACT/late-change.txt" ]] ||
    fail "execute mutated proof-bound late work before rejecting it"
[[ "$(grep -c 'gc gastown polecat-lease submit' "$LOG")" -eq 1 ]] ||
    fail "dirty proof-bound recovery repeated the stateful lease"

new_case execute-drain-failure-replays-without-lease
FAIL_DRAIN=1
run_submit execute
unset FAIL_DRAIN
[[ "$RUN_RC" -eq 75 ]] ||
    fail "post-close drain failure returned $RUN_RC instead of 75"
[[ "$(jq -r '.beads["submit-1"].status' "$DB")" == "closed" ]] ||
    fail "drain-failure fixture did not retain durable closed/pass state"
: >"$LOG"
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "drain-failure exact replay failed: $(<"$OUTPUT")"
! grep -F 'gc gastown polecat-lease submit' "$LOG" >/dev/null ||
    fail "drain-failure replay repeated the stateful lease"
[[ -e "$DB.drained" ]] ||
    fail "drain-failure replay did not acknowledge drain"

new_case execute-rejects-current-legacy-v1
jq '.beads["submit-1"].status = "closed" |
    .beads["submit-1"].metadata["gc.outcome"] = "pass" |
    .beads["submit-1"].metadata["gc.polecat_submit_version"] = 1 |
    .beads["submit-1"].metadata["gc.polecat_submit_source_id"] = "source-1" |
    .beads["submit-1"].metadata["gc.polecat_submit_convoy_id"] = "convoy-1" |
    .beads["submit-1"].metadata["gc.polecat_submit_session_id"] = "session-1"' \
    "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit execute
[[ "$RUN_RC" -eq 75 ]] ||
    fail "legacy v1 current-session history returned $RUN_RC instead of 75"
grep -F 'legacy v1' "$OUTPUT" >/dev/null ||
    fail "legacy v1 rejection did not identify the obsolete proof contract"

new_case execute-ignores-irrelevant-legacy-v1
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "v2 replay setup execute failed: $(<"$OUTPUT")"
jq '.beads["legacy-submit"] = {
      id: "legacy-submit",
      status: "closed",
      assignee: "session-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.submit-and-exit",
        "gc.root_bead_id": "old-root",
        "gc.outcome": "pass",
        "gc.polecat_submit_version": 1,
        "gc.polecat_submit_source_id": "old-source",
        "gc.polecat_submit_convoy_id": "old-convoy",
        "gc.polecat_submit_session_id": "session-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
: >"$LOG"
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "irrelevant legacy v1 history poisoned exact v2 replay: $(<"$OUTPUT")"
! grep -F 'gc gastown polecat-lease submit' "$LOG" >/dev/null ||
    fail "v2 replay with irrelevant legacy history repeated the lease"

new_case execute-ignores-irrelevant-partial-v2
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "partial-v2 execute replay setup failed: $(<"$OUTPUT")"
jq '.beads["partial-other-submit"] = {
      id: "partial-other-submit",
      status: "closed",
      assignee: "session-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.submit-and-exit",
        "gc.root_bead_id": "other-root",
        "gc.outcome": "pass",
        "gc.polecat_submit_version": 2,
        "gc.polecat_submit_source_id": "other-source",
        "gc.polecat_submit_convoy_id": "other-convoy",
        "gc.polecat_submit_branch": "polecat/other-source",
        "gc.polecat_submit_mode": "refinery",
        "gc.polecat_submit_session_id": "session-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
: >"$LOG"
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "irrelevant partial v2 history poisoned execute replay: $(<"$OUTPUT")"
! grep -F 'gc gastown polecat-lease submit' "$LOG" >/dev/null ||
    fail "execute replay with irrelevant partial history repeated the lease"

new_case execute-rejects-relevant-partial-v2
run_submit execute
[[ "$RUN_RC" -eq 0 ]] ||
    fail "relevant partial-v2 execute setup failed: $(<"$OUTPUT")"
jq '.beads["partial-current-submit"] = {
      id: "partial-current-submit",
      status: "closed",
      assignee: "session-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.submit-and-exit",
        "gc.root_bead_id": "root-1",
        "gc.outcome": "pass",
        "gc.polecat_submit_version": 2,
        "gc.polecat_submit_source_id": "source-1",
        "gc.polecat_submit_convoy_id": "convoy-1",
        "gc.polecat_submit_branch": "polecat/source-1",
        "gc.polecat_submit_mode": "auto_push_false",
        "gc.polecat_submit_session_id": "session-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit execute
[[ "$RUN_RC" -eq 75 ]] ||
    fail "canonically relevant partial v2 execute history returned $RUN_RC instead of 75"

new_case complete-ignores-irrelevant-partial-v2
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "partial-v2 replay setup did not complete: $(<"$OUTPUT")"
jq '.beads["partial-other-submit"] = {
      id: "partial-other-submit",
      status: "closed",
      assignee: "session-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.submit-and-exit",
        "gc.root_bead_id": "other-root",
        "gc.outcome": "pass",
        "gc.polecat_submit_version": 2,
        "gc.polecat_submit_source_id": "other-source",
        "gc.polecat_submit_convoy_id": "other-convoy",
        "gc.polecat_submit_branch": "polecat/other-source",
        "gc.polecat_submit_mode": "refinery",
        "gc.polecat_submit_session_id": "session-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "irrelevant partial v2 history poisoned requested replay: $(<"$OUTPUT")"

new_case complete-rejects-relevant-partial-v2
set_generation_token
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 0 ]] ||
    fail "relevant partial-v2 setup did not complete: $(<"$OUTPUT")"
jq '.beads["partial-current-submit"] = {
      id: "partial-current-submit",
      status: "closed",
      assignee: "session-1",
      metadata: {
        "gc.step_ref": "mol-polecat-work.submit-and-exit",
        "gc.root_bead_id": "root-1",
        "gc.outcome": "pass",
        "gc.polecat_submit_version": 2,
        "gc.polecat_submit_source_id": "source-1",
        "gc.polecat_submit_convoy_id": "convoy-1",
        "gc.polecat_submit_branch": "polecat/source-1",
        "gc.polecat_submit_mode": "auto_push_false",
        "gc.polecat_submit_session_id": "session-1"
      }
    }' "$DB" >"$DB.tmp"
mv "$DB.tmp" "$DB"
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch polecat/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 75 ]] ||
    fail "canonically relevant partial v2 history returned $RUN_RC instead of 75"

new_case invalid-branch-api
run_submit complete \
    --convoy convoy-1 --source source-1 \
    --branch other/source-1 --mode auto_push_false
[[ "$RUN_RC" -eq 2 ]] ||
    fail "invalid branch API returned $RUN_RC instead of 2"
assert_live_unmutated

echo "polecat submit command tests passed"
