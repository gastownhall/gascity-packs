#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/pr-merge-reconcile/run.sh"
FORMULA="$ROOT/gastown/formulas/mol-refinery-patrol.toml"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/gascity-pr-reconcile-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

BIN="$TMP/bin"
LOG="$TMP/calls.log"
LIST_JSON="$TMP/list.json"
PR_INFO="$TMP/pr.json"
REST_INFO="$TMP/pr-rest.json"
UPDATE_COUNT="$TMP/update-count"
CLOSED_FILE="$TMP/closed"
CLEANUP_FILE="$TMP/cleanup-complete"
mkdir -p "$BIN"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

cat >"$BIN/gc" <<'SH'
#!/bin/sh
printf 'gc' >>"$GC_TEST_LOG"
for arg in "$@"; do
    printf ' <%s>' "$arg" >>"$GC_TEST_LOG"
done
printf '\n' >>"$GC_TEST_LOG"

case "$1" in
    bd)
        case "$2" in
            list)
                cat "$GC_TEST_LIST_JSON"
                ;;
            show)
                show_status=${GC_TEST_SHOW_STATUS:-closed}
                show_result=${GC_TEST_SHOW_RESULT:-mr_merged}
                jq \
                    --arg merged_sha "$GC_TEST_MERGE_SHA" \
                    --arg show_status "$show_status" \
                    --arg show_result "$show_result" \
                    '.[0]
                     | .status = $show_status
                     | .metadata.merge_result = $show_result
                     | .metadata.merged_sha = $merged_sha
                     | .metadata.artifact_cleanup_state = "complete"
                     | del(.metadata.artifact_dir, .metadata.work_dir)
                     | [.]' "$GC_TEST_LIST_JSON"
                ;;
            update)
                count=$(cat "$GC_TEST_UPDATE_COUNT" 2>/dev/null || printf '0')
                count=$((count + 1))
                printf '%s\n' "$count" >"$GC_TEST_UPDATE_COUNT"
                if [ "${GC_TEST_FAIL_UPDATE_AT:-0}" = "$count" ]; then
                    exit 1
                fi
                exit 0
                ;;
            close)
                if [ "${GC_TEST_CLOSE_FAIL:-0}" != "0" ]; then
                    exit 1
                fi
                : >"$GC_TEST_CLOSED_FILE"
                ;;
            *)
                echo "unexpected gc bead call: $*" >&2
                exit 90
                ;;
        esac
        ;;
    mail)
        [ "$2" = "send" ] || exit 90
        ;;
    gastown)
        [ "$2" = "task-artifact-cleanup" ] || exit 90
        [ -f "$GC_TEST_CLOSED_FILE" ] || {
            echo "cleanup ran before close" >&2
            exit 91
        }
        if [ "${GC_TEST_CLEANUP_FAIL:-0}" != "0" ]; then
            exit 1
        fi
        : >"$GC_TEST_CLEANUP_FILE"
        ;;
    *)
        echo "unexpected gc call: $*" >&2
        exit 90
        ;;
esac
SH

cat >"$BIN/gh" <<'SH'
#!/bin/sh
printf 'gh' >>"$GC_TEST_LOG"
for arg in "$@"; do
    printf ' <%s>' "$arg" >>"$GC_TEST_LOG"
done
printf '\n' >>"$GC_TEST_LOG"
[ "${GC_TEST_GH_FAIL:-0}" = "0" ] || exit 1
cat "$GC_TEST_PR_INFO"
SH

cat >"$BIN/curl" <<'SH'
#!/bin/sh
printf 'curl' >>"$GC_TEST_LOG"
for arg in "$@"; do
    case "$arg" in
        Authorization:*) printf ' <Authorization: REDACTED>' >>"$GC_TEST_LOG" ;;
        *) printf ' <%s>' "$arg" >>"$GC_TEST_LOG" ;;
    esac
done
printf '\n' >>"$GC_TEST_LOG"
cat "$GC_TEST_REST_INFO"
SH

cat >"$BIN/git" <<'SH'
#!/bin/sh
printf 'git' >>"$GC_TEST_LOG"
for arg in "$@"; do
    printf ' <%s>' "$arg" >>"$GC_TEST_LOG"
done
printf '\n' >>"$GC_TEST_LOG"

no_replace=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --no-replace-objects)
            no_replace=1
            shift
            ;;
        -C)
            [ "$#" -ge 2 ] || exit 93
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

case "$1" in
    check-ref-format)
        case "$2" in
            refs/heads/*) exit 0 ;;
            *) exit 1 ;;
        esac
        ;;
    remote)
        [ "$2" = "get-url" ] && [ "$3" = "origin" ] || exit 93
        printf '%s\n' "${GC_TEST_ORIGIN_URL:-https://github.com/example/repo.git}"
        ;;
    fetch)
        [ "${GC_TEST_FETCH_FAIL:-0}" = "0" ]
        ;;
    merge-base)
        [ "$no_replace" = 1 ] || exit 93
        [ "${GIT_GRAFT_FILE:-}" = "/dev/null" ] || exit 93
        [ "${GC_TEST_MERGE_REACHABLE:-1}" = "1" ]
        ;;
    rev-parse)
        if [ "$2" = "--short" ]; then
            printf 'bbbbbbbb\n'
            exit 0
        fi
        exit 91
        ;;
    *)
        echo "unexpected git call: $*" >&2
        exit 92
        ;;
esac
SH

cat >"$BIN/date" <<'SH'
#!/bin/sh
printf '2026-07-26T20:00:00Z\n'
SH

chmod +x "$BIN/gc" "$BIN/gh" "$BIN/curl" "$BIN/git" "$BIN/date"

export PATH="$BIN:$PATH"
export GC_TEST_LOG="$LOG"
export GC_TEST_LIST_JSON="$LIST_JSON"
export GC_TEST_PR_INFO="$PR_INFO"
export GC_TEST_REST_INFO="$REST_INFO"
export GC_TEST_UPDATE_COUNT="$UPDATE_COUNT"
export GC_TEST_CLOSED_FILE="$CLOSED_FILE"
export GC_TEST_CLEANUP_FILE="$CLEANUP_FILE"
export GC_AGENT="tributary/gastown.refinery"
export GC_RIG="tributary"
export GC_RIG_ROOT="/srv/tributary"

HEAD_A=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
HEAD_B=cccccccccccccccccccccccccccccccccccccccc
MERGE_SHA=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
export GC_TEST_MERGE_SHA="$MERGE_SHA"
PR_URL=https://github.com/example/repo/pull/181

reset_case() {
    : >"$LOG"
    printf '0\n' >"$UPDATE_COUNT"
    rm -f "$CLOSED_FILE" "$CLEANUP_FILE"
    unset GC_TEST_CLOSE_FAIL GC_TEST_GH_FAIL GC_TEST_FETCH_FAIL GC_TEST_FAIL_UPDATE_AT
    unset GC_TEST_CLEANUP_FAIL
    unset GC_TEST_SHOW_STATUS GC_TEST_SHOW_RESULT
    unset GC_TEST_ORIGIN_URL
    unset GASTOWN_PR_RECONCILE_FORCE_REST GH_TOKEN
    export GC_TEST_MERGE_REACHABLE=1
}

write_pending_list() {
    local head=${1:-$HEAD_A}
    local checked=${2:-2026-07-26T19:00:00Z}
    jq -n \
        --arg head "$head" \
        --arg checked "$checked" \
        --arg url "$PR_URL" \
        '[{
          id: "tr-92a",
          status: "blocked",
          assignee: "gastown__refinery-ac-old",
          metadata: {
            branch: "polecat/tr-92a",
            target: "main",
            merged_target: "main",
            pr_url: $url,
            pr_number: "181",
            pr_head_sha: $head,
            pr_repo: "example/repo",
            pr_reconcile_pending: "true",
            pr_last_checked_at: $checked
          }
        }]' >"$LIST_JSON"
}

write_pr_info() {
    local state=$1
    local head=${2:-$HEAD_A}
    local merged_at=${3:-}
    local merge_sha=${4:-}
    jq -n \
        --arg url "$PR_URL" \
        --arg state "$state" \
        --arg head "$head" \
        --arg merged_at "$merged_at" \
        --arg merge_sha "$merge_sha" \
        '{
          url: $url,
          number: 181,
          state: $state,
          headRefName: "polecat/tr-92a",
          headRefOid: $head,
          baseRefName: "main",
          mergedAt: (if $merged_at == "" then null else $merged_at end),
          mergeCommit: (if $merge_sha == "" then null else {oid: $merge_sha} end)
        }' >"$PR_INFO"
}

write_rest_pr_info() {
    jq -n \
        --arg url "$PR_URL" \
        --arg head "$HEAD_A" \
        '{
          html_url: $url,
          number: 181,
          state: "open",
          merged_at: null,
          merge_commit_sha: null,
          head: {ref: "polecat/tr-92a", sha: $head},
          base: {ref: "main"}
        }' >"$REST_INFO"
}

test_record_blocks_without_closing() {
    reset_case
    "$COMMAND" record tr-92a "$PR_URL" 181 main "$HEAD_A"

    grep -F 'gc <bd> <update> <--rig=tributary> <tr-92a>' "$LOG" >/dev/null ||
        fail "record must update the rig-scoped work bead"
    grep -F '<--status=blocked>' "$LOG" >/dev/null ||
        fail "record must leave the source bead blocked"
    grep -F '<--set-metadata> <merge_result=pull_request_pending>' "$LOG" >/dev/null ||
        fail "record must mark a pending pull request"
    grep -F "<--set-metadata> <pr_head_sha=$HEAD_A>" "$LOG" >/dev/null ||
        fail "record must bind the validated PR head"
    grep -F '<--set-metadata> <pr_repo=example/repo>' "$LOG" >/dev/null ||
        fail "record must bind the pull request to the origin repository"
    local arm_line block_line
    arm_line=$(grep -nF '<--set-metadata> <pr_reconcile_pending=true>' "$LOG" | head -n1 | cut -d: -f1)
    block_line=$(grep -nF '<--status=blocked>' "$LOG" | head -n1 | cut -d: -f1)
    [[ "$arm_line" -lt "$block_line" ]] ||
        fail "record must arm retry before its final transition to blocked"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "record must not close at PR publication"
}

test_record_rejects_origin_repo_mismatch_before_mutation() {
    reset_case
    export GC_TEST_ORIGIN_URL=https://github.com/example/other.git
    if "$COMMAND" record tr-92a "$PR_URL" 181 main "$HEAD_A"; then
        fail "record should reject a pull request from a different origin repository"
    fi

    ! grep -F 'gc <bd> <update>' "$LOG" >/dev/null ||
        fail "origin mismatch must fail before arming or mutating the work bead"
}

test_open_unchanged_stays_blocked() {
    reset_case
    write_pending_list
    write_pr_info OPEN
    "$COMMAND"

    grep -F 'gh <pr> <view>' "$LOG" >/dev/null ||
        fail "reconcile must inspect the pending PR"
    grep -F '<--set-metadata> <pr_state=open>' "$LOG" >/dev/null ||
        fail "unchanged open PR should remain tracked as open"
    grep -F "<--assignee=$GC_AGENT>" "$LOG" >/dev/null ||
        fail "current refinery must adopt pending handoffs from recycled sessions"
    ! grep -F 'gc <bd> <list>' "$LOG" | grep -F '<--assignee=' >/dev/null ||
        fail "pending scan must not be limited to an obsolete refinery assignee"
    ! grep -F '<--status=open>' "$LOG" >/dev/null ||
        fail "unchanged open PR must not re-enter the refinery queue"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "unchanged open PR must not close its bead"
}

test_reconcile_origin_mismatch_retries_without_github_or_close() {
    reset_case
    write_pending_list
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    export GC_TEST_ORIGIN_URL=git@github.com:example/other.git
    if "$COMMAND"; then
        fail "origin mismatch should return nonzero"
    fi

    grep -F '<--set-metadata> <pr_state=origin_mismatch>' "$LOG" >/dev/null ||
        fail "origin mismatch must be recorded as retryable"
    ! grep -F 'gh <pr> <view>' "$LOG" >/dev/null ||
        fail "origin mismatch must fail before trusting GitHub state"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "origin mismatch must not close the source bead"
    ! grep -F '<--unset-metadata> <pr_reconcile_pending>' "$LOG" >/dev/null ||
        fail "origin mismatch must retain the pending marker"
}

test_partial_record_never_blocks_without_complete_metadata() {
    reset_case
    export GC_TEST_FAIL_UPDATE_AT=2
    if "$COMMAND" record tr-92a "$PR_URL" 181 main "$HEAD_A"; then
        fail "partial pending-PR metadata write should return nonzero"
    fi

    grep -F '<--set-metadata> <pr_reconcile_pending=true>' "$LOG" >/dev/null ||
        fail "partial record must first leave a durable retry marker"
    ! grep -F '<--status=blocked>' "$LOG" >/dev/null ||
        fail "partial record must leave bead open for normal refinery retry"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "partial record must never close"
}

test_rest_fallback_preserves_open_pending_state() {
    reset_case
    write_pending_list
    write_rest_pr_info
    export GASTOWN_PR_RECONCILE_FORCE_REST=1
    export GH_TOKEN=test-token
    "$COMMAND"

    grep -F 'curl ' "$LOG" >/dev/null ||
        fail "reconcile must retain the existing GitHub REST fallback when gh is unavailable"
    ! grep -F 'test-token' "$LOG" >/dev/null ||
        fail "REST fallback test log must not expose the GitHub token"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "REST-reported open PR must remain pending"
}

test_open_changed_head_requeues_for_validation() {
    reset_case
    write_pending_list
    write_pr_info OPEN "$HEAD_B"
    "$COMMAND"

    grep -F '<--status=open>' "$LOG" >/dev/null ||
        fail "changed open PR must re-enter refinery work"
    grep -F "<--set-metadata> <existing_pr=$PR_URL>" "$LOG" >/dev/null ||
        fail "changed open PR must preserve the canonical PR for reuse"
    grep -F '<--set-metadata> <merge_result=pull_request_head_changed>' "$LOG" >/dev/null ||
        fail "changed open PR must record why revalidation is required"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "changed open PR must not close its bead"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "changed open PR must not clean its task artifact"
}

test_closed_unmerged_stays_blocked_and_escalates() {
    reset_case
    write_pending_list
    write_pr_info CLOSED
    if "$COMMAND"; then
        fail "closed-unmerged PR should return nonzero"
    fi

    grep -F '<--status=blocked>' "$LOG" >/dev/null ||
        fail "closed-unmerged PR must remain blocked"
    grep -F '<--set-metadata> <merge_result=pull_request_closed_unmerged>' "$LOG" >/dev/null ||
        fail "closed-unmerged PR must record terminal state"
    grep -F 'gc <mail> <send> <mayor/>' "$LOG" >/dev/null ||
        fail "closed-unmerged PR must escalate"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "closed-unmerged PR must not close its bead"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "closed-unmerged PR must not clean its task artifact"
}

test_merged_validated_head_and_target_closes() {
    reset_case
    write_pending_list
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    "$COMMAND"

    grep -F '<fetch> <origin> <+refs/heads/main:refs/remotes/origin/main>' "$LOG" >/dev/null ||
        fail "merged PR must fetch the recorded target"
    grep -F "<--no-replace-objects> <-C> <$GC_RIG_ROOT> <merge-base> <--is-ancestor> <$MERGE_SHA> <origin/main>" "$LOG" >/dev/null ||
        fail "merged PR must prove merge commit reachability"
    grep -F "<--set-metadata> <merged_sha=$MERGE_SHA>" "$LOG" >/dev/null ||
        fail "merged PR must record merge evidence before close"
    grep -F '<--set-metadata> <merge_result=mr_merged>' "$LOG" >/dev/null ||
        fail "verified MR close must use the distinct mr_merged result"
    grep -F 'gc <bd> <close> <--rig=tributary> <tr-92a>' "$LOG" >/dev/null ||
        fail "verified merged PR must close the source bead"
    grep -F 'gc <gastown> <task-artifact-cleanup> <tr-92a>' "$LOG" >/dev/null ||
        fail "verified merged PR must retire its task artifact after close"
    grep -F '<--unset-metadata> <pr_reconcile_pending>' "$LOG" >/dev/null ||
        fail "verified merge must clear its marker after cleanup convergence"
    local close_line cleanup_line clear_line
    close_line=$(grep -nF 'gc <bd> <close>' "$LOG" | head -n1 | cut -d: -f1)
    cleanup_line=$(grep -nF 'gc <gastown> <task-artifact-cleanup>' "$LOG" | head -n1 | cut -d: -f1)
    clear_line=$(grep -nF '<--unset-metadata> <pr_reconcile_pending>' "$LOG" | tail -n1 | cut -d: -f1)
    [[ "$close_line" -lt "$cleanup_line" && "$cleanup_line" -lt "$clear_line" ]] ||
        fail "close, cleanup, and marker-clear order is not crash safe"
}

test_merged_changed_head_stays_blocked() {
    reset_case
    write_pending_list
    write_pr_info MERGED "$HEAD_B" 2026-07-26T19:30:00Z "$MERGE_SHA"
    if "$COMMAND"; then
        fail "merged PR with unvalidated head should return nonzero"
    fi

    grep -F '<--set-metadata> <merge_result=pull_request_merged_unvalidated_head>' "$LOG" >/dev/null ||
        fail "merged unvalidated head must record its quarantine reason"
    grep -F 'gc <mail> <send> <mayor/>' "$LOG" >/dev/null ||
        fail "merged unvalidated head must escalate"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "merged unvalidated head must not close its bead"
}

test_verified_merge_close_failure_remains_retryable() {
    reset_case
    write_pending_list
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    export GC_TEST_CLOSE_FAIL=1
    if "$COMMAND"; then
        fail "failed bead close should return nonzero"
    fi

    grep -F 'gc <bd> <close> <--rig=tributary> <tr-92a>' "$LOG" >/dev/null ||
        fail "verified merge must attempt the close"
    ! grep -F '<--unset-metadata> <pr_reconcile_pending>' "$LOG" >/dev/null ||
        fail "failed close must retain the pending marker for restart-safe retry"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "failed close must not start terminal artifact cleanup"
}

test_cleanup_failure_on_closed_bead_retries() {
    reset_case
    write_pending_list
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    export GC_TEST_CLEANUP_FAIL=1
    if "$COMMAND"; then
        fail "failed artifact cleanup should return nonzero"
    fi

    grep -F 'gc <bd> <close> <--rig=tributary> <tr-92a>' "$LOG" >/dev/null ||
        fail "cleanup failure test must first close the verified bead"
    ! grep -F '<--unset-metadata> <pr_reconcile_pending>' "$LOG" >/dev/null ||
        fail "cleanup failure must retain the PR reconciliation marker"

    jq --arg merged_sha "$MERGE_SHA" '
        .[0].status = "closed"
        | .[0].metadata.merge_result = "mr_merged"
        | .[0].metadata.merged_sha = $merged_sha
        | .[0].metadata.pr_state = "merged"
    ' "$LIST_JSON" >"$LIST_JSON.next"
    mv "$LIST_JSON.next" "$LIST_JSON"
    : >"$LOG"
    unset GC_TEST_CLEANUP_FAIL
    "$COMMAND"

    grep -F 'gc <bd> <list> <--rig=tributary> <--all>' "$LOG" >/dev/null ||
        fail "reconcile must scan closed beads for pending cleanup retries"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "closed-bead cleanup retry must not close the bead again"
    grep -F 'gc <gastown> <task-artifact-cleanup> <tr-92a>' "$LOG" >/dev/null ||
        fail "closed-bead retry did not rerun artifact cleanup"
    grep -F '<--unset-metadata> <pr_reconcile_pending>' "$LOG" >/dev/null ||
        fail "successful cleanup retry did not clear the marker"
}

test_unreachable_merge_commit_retries_without_close() {
    reset_case
    write_pending_list
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    export GC_TEST_MERGE_REACHABLE=0
    if "$COMMAND"; then
        fail "unreachable merge commit should return nonzero"
    fi

    grep -F '<--set-metadata> <pr_state=merged_unverified>' "$LOG" >/dev/null ||
        fail "unreachable merge commit must record retryable verification state"
    ! grep -F '<--unset-metadata> <pr_reconcile_pending>' "$LOG" >/dev/null ||
        fail "retryable verification failure must retain the pending marker"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "unreachable merge commit must not close its bead"
}

test_cleanup_waits_for_durable_closed_record() {
    reset_case
    write_pending_list
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    export GC_TEST_SHOW_STATUS=blocked
    if "$COMMAND"; then
        fail "unconfirmed closed state should fail reconciliation"
    fi

    grep -F 'gc <bd> <close> <--rig=tributary> <tr-92a>' "$LOG" >/dev/null ||
        fail "close verification test must attempt the verified close"
    grep -F '<--set-metadata> <pr_state=merged_close_unverified>' "$LOG" >/dev/null ||
        fail "unconfirmed close must retain an explicit retryable state"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "cleanup must not run until a fresh read proves the bead closed"
    ! grep -F '<--unset-metadata> <pr_reconcile_pending>' "$LOG" >/dev/null ||
        fail "unconfirmed close must retain the pending marker"
}

test_closed_ambiguous_legacy_record_is_reblocked() {
    reset_case
    write_pending_list
    jq '
        .[0].status = "closed"
        | .[0].metadata.merge_result = "pull_request"
    ' "$LIST_JSON" >"$LIST_JSON.next"
    mv "$LIST_JSON.next" "$LIST_JSON"
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    if "$COMMAND"; then
        fail "ambiguous legacy closed record should fail reconciliation"
    fi

    grep -F '<--status=blocked>' "$LOG" >/dev/null ||
        fail "ambiguous legacy closed record must be restored to a dependency-blocking state"
    grep -F '<--set-metadata> <merge_result=pull_request_legacy_closed_unverified>' "$LOG" >/dev/null ||
        fail "ambiguous legacy closed record must record its quarantine reason"
    ! grep -F 'gh <pr> <view>' "$LOG" >/dev/null ||
        fail "ambiguous legacy close must be quarantined before trusting remote PR state"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "ambiguous legacy close must never invoke cleanup"
}

test_noncanonical_source_branch_is_quarantined() {
    reset_case
    write_pending_list
    jq '.[0].metadata.branch = "topic/not-the-polecat-source"' \
        "$LIST_JSON" >"$LIST_JSON.next"
    mv "$LIST_JSON.next" "$LIST_JSON"
    write_pr_info MERGED "$HEAD_A" 2026-07-26T19:30:00Z "$MERGE_SHA"
    if "$COMMAND"; then
        fail "noncanonical MR source branch should fail reconciliation"
    fi

    grep -F '<--status=blocked>' "$LOG" >/dev/null ||
        fail "noncanonical source branch must remain dependency-blocking"
    ! grep -F 'gh <pr> <view>' "$LOG" >/dev/null ||
        fail "noncanonical source branch must fail before remote PR verification"
    ! grep -F 'gc <bd> <close>' "$LOG" >/dev/null ||
        fail "noncanonical source branch must never close the source bead"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "noncanonical source branch must never invoke cleanup"
}

test_closed_mr_with_open_remote_is_reblocked() {
    reset_case
    write_pending_list
    jq --arg merged_sha "$MERGE_SHA" '
        .[0].status = "closed"
        | .[0].metadata.merge_result = "mr_merged"
        | .[0].metadata.merged_sha = $merged_sha
        | .[0].metadata.pr_state = "merged"
    ' "$LIST_JSON" >"$LIST_JSON.next"
    mv "$LIST_JSON.next" "$LIST_JSON"
    write_pr_info OPEN "$HEAD_A"
    if "$COMMAND"; then
        fail "closed MR with contradictory open remote state should fail reconciliation"
    fi

    grep -F '<--status=blocked>' "$LOG" >/dev/null ||
        fail "contradictory closed/open MR must be restored to a dependency-blocking state"
    grep -F '<--set-metadata> <merge_result=pull_request_closed_state_contradiction>' "$LOG" >/dev/null ||
        fail "contradictory closed/open MR must record its quarantine reason"
    ! grep -F 'gc <gastown> <task-artifact-cleanup>' "$LOG" >/dev/null ||
        fail "contradictory closed/open MR must never invoke cleanup"
}

test_oldest_pending_pr_is_selected() {
    reset_case
    jq -n \
        --arg url "$PR_URL" \
        --arg head "$HEAD_A" \
        '[{
          id: "newer",
          status: "blocked",
          metadata: {
            branch: "polecat/newer", merged_target: "main",
            pr_url: $url, pr_number: "181", pr_head_sha: $head,
            pr_repo: "example/repo",
            pr_reconcile_pending: "true",
            pr_last_checked_at: "2026-07-26T19:59:00Z"
          }
        }, {
          id: "tr-92a",
          status: "blocked",
          metadata: {
            branch: "polecat/tr-92a", merged_target: "main",
            pr_url: $url, pr_number: "181", pr_head_sha: $head,
            pr_repo: "example/repo",
            pr_reconcile_pending: "true",
            pr_last_checked_at: "2026-07-26T18:00:00Z"
          }
        }]' >"$LIST_JSON"
    write_pr_info OPEN
    "$COMMAND"

    grep -F 'gc <bd> <update> <--rig=tributary> <tr-92a>' "$LOG" >/dev/null ||
        fail "reconcile must rotate by least-recently-checked pending PR"
    ! grep -F 'gc <bd> <update> <--rig=tributary> <newer>' "$LOG" >/dev/null ||
        fail "one patrol must perform at most one pending PR transition"
}

test_formula_uses_pending_merge_gate() {
    grep -F 'gc gastown pr-merge-reconcile record' "$FORMULA" >/dev/null ||
        fail "refinery formula must record PR handoffs through the reconciler"
    grep -F 'Every time this open step is entered or re-entered after an idle wake' "$FORMULA" >/dev/null ||
        fail "open refinery work scan must repeat pending-merge reconciliation after idle wakes"
    [ "$(grep -c '^id = "find-work"$' "$FORMULA")" -eq 1 ] ||
        fail "refinery formula must contain exactly one repeating find-work step"
    local reconcile_line cleanup_line search_line
    reconcile_line=$(grep -nF 'if ! gc gastown pr-merge-reconcile; then' "$FORMULA" | head -n1 | cut -d: -f1)
    cleanup_line=$(grep -nF 'if ! gc gastown task-artifact-cleanup; then' "$FORMULA" | head -n1 | cut -d: -f1)
    search_line=$(grep -nF 'Search for work beads assigned to you with branch metadata:' "$FORMULA" | head -n1 | cut -d: -f1)
    [[ "$reconcile_line" -lt "$cleanup_line" && "$cleanup_line" -lt "$search_line" ]] ||
        fail "find-work must order reconciliation, bounded cleanup, then normal work search"
    grep -F 'Do not invoke task-artifact cleanup on this publication path.' "$FORMULA" >/dev/null ||
        fail "MR publication path must defer cleanup until verified close"
    ! grep -F 'gc bd close $WORK --reason "Pull request ready:' "$FORMULA" >/dev/null ||
        fail "refinery formula must not close source beads at PR publication"
}

test_record_blocks_without_closing
test_record_rejects_origin_repo_mismatch_before_mutation
test_open_unchanged_stays_blocked
test_reconcile_origin_mismatch_retries_without_github_or_close
test_partial_record_never_blocks_without_complete_metadata
test_rest_fallback_preserves_open_pending_state
test_open_changed_head_requeues_for_validation
test_closed_unmerged_stays_blocked_and_escalates
test_merged_validated_head_and_target_closes
test_merged_changed_head_stays_blocked
test_verified_merge_close_failure_remains_retryable
test_cleanup_failure_on_closed_bead_retries
test_unreachable_merge_commit_retries_without_close
test_cleanup_waits_for_durable_closed_record
test_closed_ambiguous_legacy_record_is_reblocked
test_noncanonical_source_branch_is_quarantined
test_closed_mr_with_open_remote_is_reblocked
test_oldest_pending_pr_is_selected
test_formula_uses_pending_merge_gate

echo "PR merge reconciliation tests passed"
