#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
RECONCILE="$ROOT/gastown/commands/pr-merge-reconcile/run.sh"
CLEANUP="$ROOT/gastown/assets/scripts/task-artifact-cleanup.sh"
REAL_GIT=$(command -v git)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/gascity-pr-artifact-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

BIN="$TMP/bin"
mkdir -p "$BIN"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

cat >"$BIN/gc" <<'SH'
#!/bin/sh
set -eu

printf 'gc' >>"$GC_IT_LOG"
for arg in "$@"; do
    printf ' <%s>' "$arg" >>"$GC_IT_LOG"
done
printf '\n' >>"$GC_IT_LOG"

decrement_if_positive() {
    counter_file=$1
    count=$(cat "$counter_file" 2>/dev/null || printf '0')
    if [ "$count" -gt 0 ]; then
        printf '%s\n' "$((count - 1))" >"$counter_file"
        return 0
    fi
    return 1
}

replace_state() {
    filter=$1
    shift
    state_tmp="${GC_IT_STATE}.tmp.$$"
    jq "$@" "$filter" "$GC_IT_STATE" >"$state_tmp"
    mv "$state_tmp" "$GC_IT_STATE"
}

[ "$#" -gt 0 ] || exit 90
case "$1" in
    bd)
        shift
        case "${1:-}" in
            --rig)
                shift 2
                ;;
            --rig=*)
                shift
                ;;
        esac
        action=${1:-}
        shift || true
        case "${1:-}" in
            --rig)
                shift 2
                ;;
            --rig=*)
                shift
                ;;
        esac
        case "$action" in
            list)
                cat "$GC_IT_STATE"
                ;;
            show)
                cat "$GC_IT_STATE"
                ;;
            close)
                work=${1:-}
                [ "$work" = "$GC_IT_WORK" ] || exit 91
                if decrement_if_positive "$GC_IT_CLOSE_FAIL_COUNT"; then
                    exit 1
                fi
                replace_state '.[0].status = "closed"'
                ;;
            update)
                work=${1:-}
                [ "$work" = "$GC_IT_WORK" ] || exit 91
                shift
                complete_update=false
                for arg in "$@"; do
                    case "$arg" in
                        artifact_cleanup_state=complete) complete_update=true ;;
                    esac
                done
                if [ "$complete_update" = true ] &&
                   decrement_if_positive "$GC_IT_COMPLETE_UPDATE_FAIL_COUNT"; then
                    exit 1
                fi
                while [ "$#" -gt 0 ]; do
                    case "$1" in
                        --status=*)
                            value=${1#--status=}
                            replace_state '.[0].status = $value' --arg value "$value"
                            shift
                            ;;
                        --set-metadata)
                            [ "$#" -ge 2 ] || exit 92
                            pair=$2
                            key=${pair%%=*}
                            value=${pair#*=}
                            replace_state '.[0].metadata[$key] = $value' \
                                --arg key "$key" --arg value "$value"
                            shift 2
                            ;;
                        --unset-metadata)
                            [ "$#" -ge 2 ] || exit 92
                            key=$2
                            replace_state 'del(.[0].metadata[$key])' --arg key "$key"
                            shift 2
                            ;;
                        *)
                            shift
                            ;;
                    esac
                done
                ;;
            *)
                echo "unexpected gc bd action: $action" >&2
                exit 90
                ;;
        esac
        ;;
    gastown)
        [ "${2:-}" = "task-artifact-cleanup" ] || exit 90
        [ "${3:-}" = "$GC_IT_WORK" ] || exit 91
        if decrement_if_positive "$GC_IT_CLEANUP_FAIL_COUNT"; then
            exit 1
        fi
        "$GC_IT_CLEANUP" "$GC_IT_WORK"
        ;;
    mail)
        [ "${2:-}" = "send" ] || exit 90
        ;;
    *)
        echo "unexpected gc call: $*" >&2
        exit 90
        ;;
esac
SH

cat >"$BIN/gh" <<'SH'
#!/bin/sh
cat "$GC_IT_PR_INFO"
SH

cat >"$BIN/date" <<'SH'
#!/bin/sh
printf '2026-07-26T21:00:00Z\n'
SH

cat >"$BIN/git" <<'SH'
#!/bin/sh
set -eu

printf 'git' >>"$GC_IT_LOG"
for arg in "$@"; do
    printf ' <%s>' "$arg" >>"$GC_IT_LOG"
done
printf '\n' >>"$GC_IT_LOG"

case " $* " in
    *" remote get-url origin "*)
        printf 'https://github.com/example/repo.git\n'
        exit 0
        ;;
    *" merge-base --is-ancestor "*)
        if [ "$(cat "$GC_IT_REACHABLE" 2>/dev/null || printf '1')" != "1" ]; then
            exit 1
        fi
        ;;
esac

exec "$GC_IT_REAL_GIT" "$@"
SH

chmod +x "$BIN/gc" "$BIN/gh" "$BIN/date" "$BIN/git"

export PATH="$BIN:$PATH"
export GC_AGENT="demo/gastown.refinery"
export GC_RIG=demo
export GC_IT_CLEANUP="$CLEANUP"
export GC_IT_REAL_GIT="$REAL_GIT"
export GC_IT_WORK=it-1

HEAD_B=cccccccccccccccccccccccccccccccccccccccc
PR_URL=https://github.com/example/repo/pull/1

setup_case() {
    local name=$1
    CASE_DIR="$TMP/$name"
    RIG="$CASE_DIR/rig"
    REMOTE="$CASE_DIR/remote.git"
    CITY="$CASE_DIR/city"
    ARTIFACT="$CITY/.gc/worktrees/demo/artifacts/worktrees/$GC_IT_WORK"
    STATE="$CASE_DIR/bead.json"
    PR_INFO="$CASE_DIR/pr.json"
    LOG="$CASE_DIR/calls.log"
    CLOSE_FAIL_COUNT="$CASE_DIR/close-fail-count"
    CLEANUP_FAIL_COUNT="$CASE_DIR/cleanup-fail-count"
    COMPLETE_UPDATE_FAIL_COUNT="$CASE_DIR/complete-update-fail-count"
    REACHABLE="$CASE_DIR/reachable"

    mkdir -p "$RIG" "$(dirname "$ARTIFACT")" \
        "$CITY/.gc/worktrees/demo/polecats"
    "$REAL_GIT" -C "$RIG" init -q
    "$REAL_GIT" -C "$RIG" config user.name "Lifecycle Test"
    "$REAL_GIT" -C "$RIG" config user.email lifecycle@example.invalid
    printf 'base\n' >"$RIG/base.txt"
    "$REAL_GIT" -C "$RIG" add base.txt
    "$REAL_GIT" -C "$RIG" commit -qm base
    "$REAL_GIT" init -q --bare "$REMOTE"
    "$REAL_GIT" -C "$RIG" branch -M main
    "$REAL_GIT" -C "$RIG" remote add origin "$REMOTE"
    "$REAL_GIT" -C "$RIG" push -q -u origin main
    "$REAL_GIT" -C "$RIG" worktree add -qb "polecat/$GC_IT_WORK" "$ARTIFACT" HEAD
    printf 'task\n' >"$ARTIFACT/task.txt"
    "$REAL_GIT" -C "$ARTIFACT" add task.txt
    "$REAL_GIT" -C "$ARTIFACT" commit -qm task
    TASK_SHA=$("$REAL_GIT" -C "$ARTIFACT" rev-parse HEAD)
    MERGE_SHA=$TASK_SHA
    "$REAL_GIT" -C "$ARTIFACT" push -q -u origin "polecat/$GC_IT_WORK"
    "$REAL_GIT" -C "$RIG" merge -q --ff-only "$TASK_SHA"
    "$REAL_GIT" -C "$RIG" push -q origin main

    jq -n \
        --arg work "$GC_IT_WORK" \
        --arg head "$TASK_SHA" \
        --arg url "$PR_URL" \
        --arg artifact "$ARTIFACT" \
        '[{
          id: $work,
          status: "blocked",
          assignee: "demo/gastown.refinery",
          metadata: {
            branch: ("polecat/" + $work),
            target: "main",
            merged_target: "main",
            merge_result: "pull_request_pending",
            pr_url: $url,
            pr_number: "1",
            pr_head_sha: $head,
            pr_repo: "example/repo",
            pr_state: "open",
            pr_reconcile_pending: "true",
            pr_last_checked_at: "2026-07-26T20:00:00Z",
            artifact_source_sha: $head,
            artifact_dir: $artifact
          }
        }]' >"$STATE"

    : >"$LOG"
    printf '0\n' >"$CLOSE_FAIL_COUNT"
    printf '0\n' >"$CLEANUP_FAIL_COUNT"
    printf '0\n' >"$COMPLETE_UPDATE_FAIL_COUNT"
    printf '1\n' >"$REACHABLE"

    export GC_CITY_PATH="$CITY"
    export GC_RIG_ROOT="$RIG"
    export GC_IT_STATE="$STATE"
    export GC_IT_PR_INFO="$PR_INFO"
    export GC_IT_LOG="$LOG"
    export GC_IT_CLOSE_FAIL_COUNT="$CLOSE_FAIL_COUNT"
    export GC_IT_CLEANUP_FAIL_COUNT="$CLEANUP_FAIL_COUNT"
    export GC_IT_COMPLETE_UPDATE_FAIL_COUNT="$COMPLETE_UPDATE_FAIL_COUNT"
    export GC_IT_REACHABLE="$REACHABLE"
}

write_pr() {
    local state=$1
    local head=${2:-$TASK_SHA}
    local merged_at=${3:-}
    local merge_sha=${4:-}
    jq -n \
        --arg url "$PR_URL" \
        --arg state "$state" \
        --arg head "$head" \
        --arg merged_at "$merged_at" \
        --arg merge_sha "$merge_sha" \
        --arg branch "polecat/$GC_IT_WORK" \
        '{
          url: $url,
          number: 1,
          state: $state,
          headRefName: $branch,
          headRefOid: $head,
          baseRefName: "main",
          mergedAt: (if $merged_at == "" then null else $merged_at end),
          mergeCommit: (if $merge_sha == "" then null else {oid: $merge_sha} end)
        }' >"$PR_INFO"
}

assert_marker_present() {
    [ "$(jq -r '.[0].metadata.pr_reconcile_pending // empty' "$STATE")" = true ] ||
        fail "PR reconciliation marker was cleared prematurely"
}

test_publication_arms_without_premature_cleanup_then_converges() {
    setup_case success

    gc gastown task-artifact-cleanup "$GC_IT_WORK"
    [ -d "$ARTIFACT" ] || fail "publication-time cleanup removed the artifact"
    [ "$(jq -r '.[0].metadata.artifact_cleanup_state' "$STATE")" = pending ] ||
        fail "publication-time cleanup did not durably arm pending state"
    assert_marker_present

    : >"$LOG"
    write_pr MERGED "$TASK_SHA" 2026-07-26T20:30:00Z "$MERGE_SHA"
    "$RECONCILE"

    [ ! -e "$ARTIFACT" ] || fail "verified merge did not retire the artifact"
    [ "$(jq -r '.[0].status' "$STATE")" = closed ] ||
        fail "verified merge did not close the bead"
    [ "$(jq -r '.[0].metadata.artifact_cleanup_state' "$STATE")" = complete ] ||
        fail "verified merge did not durably complete cleanup"
    [ "$(jq -r '.[0].metadata.merge_result' "$STATE")" = mr_merged ] ||
        fail "verified MR close did not retain the distinct mr_merged result"
    [ "$(jq -r '.[0].metadata.pr_head_sha' "$STATE")" = "$TASK_SHA" ] ||
        fail "verified MR cleanup did not retain the validated PR head"
    [ "$(jq -r '.[0].metadata.branch' "$STATE")" = "polecat/$GC_IT_WORK" ] ||
        fail "verified MR cleanup did not retain the exact polecat source branch"
    [ "$(jq -r '.[0].metadata.pr_reconcile_pending // empty' "$STATE")" = "" ] ||
        fail "marker remained after terminal cleanup convergence"
    [ "$(jq -r '.[0].metadata.artifact_dir // empty' "$STATE")" = "" ] ||
        fail "artifact path remained after cleanup"

    local close_line cleanup_line clear_line
    close_line=$(grep -nF 'gc <bd> <close>' "$LOG" | head -n1 | cut -d: -f1)
    cleanup_line=$(grep -nF 'gc <gastown> <task-artifact-cleanup>' "$LOG" | head -n1 | cut -d: -f1)
    clear_line=$(grep -nF '<--unset-metadata> <pr_reconcile_pending>' "$LOG" | head -n1 | cut -d: -f1)
    [[ "$close_line" -lt "$cleanup_line" && "$cleanup_line" -lt "$clear_line" ]] ||
        fail "combined success path did not order close, cleanup, marker clear"
}

test_closed_legacy_pull_request_is_not_terminal() {
    setup_case closed-legacy-pull-request
    jq '
        .[0].status = "closed"
        | .[0].metadata.merge_result = "pull_request"
        | del(.[0].metadata.artifact_cleanup_state)
    ' "$STATE" >"$STATE.next"
    mv "$STATE.next" "$STATE"

    cleanup_output=$(gc gastown task-artifact-cleanup "$GC_IT_WORK")
    printf '%s\n' "$cleanup_output" |
        grep -F 'ARTIFACT_CLEANUP_DEFERRED' >/dev/null ||
        fail "closed legacy pull_request was not treated as nonterminal"
    [ -d "$ARTIFACT" ] ||
        fail "closed legacy pull_request removed an unverified artifact"
    [ "$(jq -r '.[0].metadata.artifact_cleanup_state' "$STATE")" = pending ] ||
        fail "closed legacy pull_request did not retain a pending cleanup marker"
    [ -n "$(jq -r '.[0].metadata.artifact_dir // empty' "$STATE")" ] ||
        fail "closed legacy pull_request cleared artifact metadata"
}

test_cleanup_failure_then_closed_bead_retry() {
    setup_case cleanup-retry
    write_pr MERGED "$TASK_SHA" 2026-07-26T20:30:00Z "$MERGE_SHA"
    printf '1\n' >"$CLEANUP_FAIL_COUNT"

    if "$RECONCILE"; then
        fail "injected cleanup failure should fail reconciliation"
    fi
    [ "$(jq -r '.[0].status' "$STATE")" = closed ] ||
        fail "cleanup failure should occur after close"
    [ -d "$ARTIFACT" ] || fail "failed cleanup removed the artifact"
    assert_marker_present

    : >"$LOG"
    "$RECONCILE"
    [ ! -e "$ARTIFACT" ] || fail "closed-bead retry did not remove artifact"
    [ "$(jq -r '.[0].metadata.pr_reconcile_pending // empty' "$STATE")" = "" ] ||
        fail "closed-bead retry did not clear marker after convergence"
    grep -F 'gc <bd> <list> <--rig=demo> <--all>' "$LOG" >/dev/null ||
        fail "closed-bead retry was not discovered through the all-status scan"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "closed-bead retry attempted to close the bead again"
}

test_close_failure_retries_from_complete_blocked_merge_evidence() {
    setup_case close-failure
    write_pr MERGED "$TASK_SHA" 2026-07-26T20:30:00Z "$MERGE_SHA"
    printf '1\n' >"$CLOSE_FAIL_COUNT"

    if "$RECONCILE"; then
        fail "injected close failure should fail reconciliation"
    fi
    [ "$(jq -r '.[0].status' "$STATE")" = blocked ] ||
        fail "failed close changed bead status"
    [ -d "$ARTIFACT" ] || fail "failed close removed artifact"
    assert_marker_present
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "cleanup started before close succeeded"

    [ "$(jq -r '.[0].metadata.merge_result' "$STATE")" = mr_merged ] &&
        [ "$(jq -r '.[0].metadata.pr_state' "$STATE")" = merged ] &&
        [ "$(jq -r '.[0].metadata.merged_sha' "$STATE")" = "$MERGE_SHA" ] &&
        [ -n "$(jq -r '.[0].metadata.pr_merged_at // empty' "$STATE")" ] ||
        fail "close failure did not retain complete verified merge evidence"

    : >"$LOG"
    export GC_AGENT="demo/gastown.refinery-recycled"
    "$RECONCILE"
    export GC_AGENT="demo/gastown.refinery"

    [ "$(jq -r '.[0].status' "$STATE")" = closed ] ||
        fail "verified blocked merge retry did not close the bead"
    [ ! -e "$ARTIFACT" ] ||
        fail "verified blocked merge retry did not clean the artifact"
    [ "$(jq -r '.[0].metadata.pr_reconcile_pending // empty' "$STATE")" = "" ] ||
        fail "verified blocked merge retry did not clear its marker"
    grep -F 'gc <bd> <close> <--rig=demo> <it-1>' "$LOG" >/dev/null ||
        fail "recycled refinery did not retry the failed close"
}

test_removed_before_metadata_crash_retries_to_completion() {
    setup_case removed-before-metadata
    write_pr MERGED "$TASK_SHA" 2026-07-26T20:30:00Z "$MERGE_SHA"
    printf '1\n' >"$COMPLETE_UPDATE_FAIL_COUNT"

    if "$RECONCILE"; then
        fail "injected post-removal metadata failure should fail reconciliation"
    fi
    [ ! -e "$ARTIFACT" ] ||
        fail "post-removal metadata failure did not reach the intended crash window"
    [ -n "$(jq -r '.[0].metadata.artifact_dir // empty' "$STATE")" ] ||
        fail "injected failure unexpectedly cleared the stale artifact path"
    assert_marker_present

    "$RECONCILE"
    [ "$(jq -r '.[0].metadata.artifact_cleanup_state' "$STATE")" = complete ] ||
        fail "missing-path retry did not complete cleanup metadata"
    [ "$(jq -r '.[0].metadata.artifact_dir // empty' "$STATE")" = "" ] ||
        fail "missing-path retry did not clear stale artifact metadata"
    [ "$(jq -r '.[0].metadata.pr_reconcile_pending // empty' "$STATE")" = "" ] ||
        fail "missing-path retry did not clear reconciliation marker"
}

test_changed_head_and_closed_unmerged_never_cleanup() {
    setup_case changed-head
    write_pr OPEN "$HEAD_B"
    "$RECONCILE"
    [ "$(jq -r '.[0].status' "$STATE")" = open ] ||
        fail "changed head did not requeue work"
    [ -d "$ARTIFACT" ] || fail "changed head removed artifact"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "changed head invoked terminal cleanup"

    setup_case closed-unmerged
    write_pr CLOSED "$TASK_SHA"
    if "$RECONCILE"; then
        fail "closed-unmerged PR should return nonzero"
    fi
    [ "$(jq -r '.[0].status' "$STATE")" = blocked ] ||
        fail "closed-unmerged PR left blocked state"
    [ -d "$ARTIFACT" ] || fail "closed-unmerged PR removed artifact"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "closed-unmerged PR invoked terminal cleanup"
}

test_publication_arms_without_premature_cleanup_then_converges
test_closed_legacy_pull_request_is_not_terminal
test_cleanup_failure_then_closed_bead_retry
test_close_failure_retries_from_complete_blocked_merge_evidence
test_removed_before_metadata_crash_retries_to_completion
test_changed_head_and_closed_unmerged_never_cleanup

echo "PR/artifact lifecycle integration tests passed"
