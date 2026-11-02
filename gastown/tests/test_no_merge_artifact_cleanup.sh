#!/usr/bin/env bash
# No-merge deliverable cleanup: a closed bead whose deliverable lives off the
# branch (comment|verdict|config|artifact|none) must reach a terminal cleanup
# row on the same evidence the polecat submit gate enforced, with the retired
# checkout provably recoverable from origin. Covers the explicit-id matrix and
# the no-ID sweep selection, including the no-starvation ordering.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CLEANUP="$ROOT/gastown/assets/scripts/task-artifact-cleanup.sh"
REAL_GIT=$(command -v git)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/gascity-no-merge-cleanup-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

BIN="$TMP/bin"
mkdir -p "$BIN"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# The stub gc serves bd list/show/update against a JSON state array and
# re-enters the cleanup script for `gc gastown task-artifact-cleanup`.
cat >"$BIN/gc" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

printf 'gc' >>"$GC_IT_LOG"
for arg in "$@"; do
    printf ' <%s>' "$arg" >>"$GC_IT_LOG"
done
printf '\n' >>"$GC_IT_LOG"

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
        while [ "${1:-}" = "--rig" ]; do
            shift 2
        done
        action=${1:-}
        shift || true
        case "$action" in
            list)
                cat "$GC_IT_STATE"
                ;;
            show)
                id=${1:-}
                shift || true
                jq --arg id "$id" '[.[] | select(.id == $id)]' "$GC_IT_STATE"
                ;;
            update)
                id=${1:-}
                shift
                while [ "$#" -gt 0 ]; do
                    case "$1" in
                        --set-metadata)
                            [ "$#" -ge 2 ] || exit 92
                            pair=$2
                            key=${pair%%=*}
                            value=${pair#*=}
                            replace_state 'map(if .id == $id then .metadata[$key] = $value else . end)' \
                                --arg id "$id" --arg key "$key" --arg value "$value"
                            shift 2
                            ;;
                        --unset-metadata)
                            [ "$#" -ge 2 ] || exit 92
                            key=$2
                            replace_state 'map(if .id == $id then del(.metadata[$key]) else . end)' \
                                --arg id "$id" --arg key "$key"
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
        "$GC_IT_CLEANUP" "${@:3}"
        ;;
    *)
        echo "unexpected gc call: $*" >&2
        exit 90
        ;;
esac
SH

# Real git, except the ancestor probe honors GC_IT_REACHABLE so the
# "fork SHA is not durable" arm is exercisable without rewriting history,
# and a fetch failure can be simulated via GC_IT_FETCH_FAIL.
cat >"$BIN/git" <<'SH'
#!/bin/sh
set -eu

case " $* " in
    *" merge-base --is-ancestor "*)
        if [ "$(cat "$GC_IT_REACHABLE" 2>/dev/null || printf '1')" != "1" ]; then
            exit 1
        fi
        ;;
    *" fetch --no-tags "*)
        if [ "${GC_IT_FETCH_FAIL:-0}" = "1" ]; then
            exit 1
        fi
        ;;
esac

exec "$GC_IT_REAL_GIT" "$@"
SH

chmod +x "$BIN/gc" "$BIN/git"

export PATH="$BIN:$PATH"
export GC_AGENT="demo/gastown.refinery"
export GC_RIG=demo
export GC_IT_CLEANUP="$CLEANUP"
export GC_IT_REAL_GIT="$REAL_GIT"

# One rig with a bare origin and one task worktree sitting untouched at the
# fork point — the exact shape a no-merge completion leaves behind.
setup_case() {
    local name=$1
    CASE_DIR="$TMP/$name"
    RIG="$CASE_DIR/rig"
    REMOTE="$CASE_DIR/remote.git"
    CITY="$CASE_DIR/city"
    STATE="$CASE_DIR/bead.json"
    LOG="$CASE_DIR/calls.log"
    REACHABLE="$CASE_DIR/reachable"
    POLECANS="$CITY/.gc/worktrees/demo/polecats"

    mkdir -p "$RIG" "$POLECANS"
    "$REAL_GIT" -C "$RIG" init -q
    "$REAL_GIT" -C "$RIG" config user.name "No-Merge Cleanup Test"
    "$REAL_GIT" -C "$RIG" config user.email no-merge@example.invalid
    printf 'base\n' >"$RIG/base.txt"
    "$REAL_GIT" -C "$RIG" add base.txt
    "$REAL_GIT" -C "$RIG" commit -qm base
    "$REAL_GIT" -C "$RIG" branch -M main
    "$REAL_GIT" init -q --bare "$REMOTE"
    "$REAL_GIT" -C "$RIG" remote add origin "$REMOTE"
    "$REAL_GIT" -C "$RIG" push -q -u origin main
    FORK_SHA=$("$REAL_GIT" -C "$RIG" rev-parse HEAD)

    : >"$LOG"
    printf '1\n' >"$REACHABLE"
    export GC_CITY_PATH="$CITY"
    export GC_RIG_ROOT="$RIG"
    export GC_IT_STATE="$STATE"
    export GC_IT_LOG="$LOG"
    export GC_IT_REACHABLE="$REACHABLE"
}

# A closed no-merge bead: worktree at the fork point, no commits, no push.
add_no_merge_bead() {
    local id=$1 deliverable=$2 comments=$3 evidence=$4 updated=$5
    local artifact="$CITY/.gc/worktrees/demo/artifacts/worktrees/$id"
    mkdir -p "$(dirname "$artifact")"
    "$REAL_GIT" -C "$RIG" worktree add -qb "polecat/$id" "$artifact" HEAD
    printf '%s' "$FORK_SHA" >"$CASE_DIR/fork-$id"

    local state_tmp="${STATE}.tmp.$$"
    jq -n \
        --arg id "$id" \
        --arg artifact "$artifact" \
        --arg fork "$FORK_SHA" \
        --arg deliverable "$deliverable" \
        --arg evidence "$evidence" \
        --arg updated "$updated" \
        --arg comments "$comments" \
        '[
          {
            id: $id,
            status: "closed",
            comment_count: ($comments | tonumber),
            updated_at: $updated,
            metadata: {
              artifact_cleanup_state: "pending",
              artifact_dir: $artifact,
              fork_sha: $fork,
              base_ref: "refs/remotes/origin/main",
              branch: ("polecat/" + $id),
              deliverable: (if $deliverable == "" then null else $deliverable end),
              deliverable_evidence: (if $evidence == "" then null else $evidence end)
            }
          }
        ]' >"$state_tmp"
    if [ -f "$STATE" ]; then
        jq -s 'add' "$STATE" "$state_tmp" >"${state_tmp}.2" && mv "${state_tmp}.2" "$STATE"
    else
        mv "$state_tmp" "$STATE"
    fi
    ARTIFACT="$artifact"
}

run_cleanup() {
    gc gastown task-artifact-cleanup ${1:+"$1"}
}

cleanup_state() {
    jq -r '.[] | select(.id == $id) | .metadata.artifact_cleanup_state // ""' \
        --arg id "$1" "$STATE"
}

expect_kept() {
    [ -d "$1" ] || fail "worktree for $2 was removed but must be kept"
}

expect_gone() {
    [ ! -d "$1" ] || fail "worktree for $2 still exists but must be retired"
}

# 1. A proven verdict bead converges: worktree retired, record complete,
#    artifact_dir dropped.
setup_case verdict-converges
add_no_merge_bead nm-v verdict 2 "" 2026-01-01
out=$(run_cleanup nm-v)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_COMPLETE' >/dev/null ||
    fail "proven verdict did not complete: $out"
[ "$(cleanup_state nm-v)" = complete ] ||
    fail "proven verdict cleanup state: $(cleanup_state nm-v)"
expect_gone "$ARTIFACT" nm-v
[ "$(jq -r '.[0].metadata.artifact_dir // ""' "$STATE")" = "" ] ||
    fail "complete record still carries artifact_dir"

# 2. A verdict bead with no comments keeps waiting: the proof can still
#    arrive, so it defers (pending) and nothing is removed.
setup_case verdict-unproven
add_no_merge_bead nm-u verdict 0 "" 2026-01-01
out=$(run_cleanup nm-u)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_DEFERRED' >/dev/null ||
    fail "unproven verdict did not defer: $out"
printf '%s' "$out" | grep -F 'unproven (no comments)' >/dev/null ||
    fail "deferral did not name the missing proof: $out"
[ "$(cleanup_state nm-u)" = pending ] || fail "unproven verdict state: $(cleanup_state nm-u)"
expect_kept "$ARTIFACT" nm-u

# 3. A config deliverable converges on a non-empty evidence stamp alone.
setup_case config-converges
add_no_merge_bead nm-c config 0 "/etc/gk/config.yaml verified by gate run" 2026-01-01
out=$(run_cleanup nm-c)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_COMPLETE' >/dev/null ||
    fail "proven config did not complete: $out"
expect_gone "$ARTIFACT" nm-c
[ "$(cleanup_state nm-c)" = complete ] || fail "proven config state: $(cleanup_state nm-c)"

# 4. A config deliverable without its evidence stamp defers.
setup_case config-unproven
add_no_merge_bead nm-c2 config 0 "" 2026-01-01
out=$(run_cleanup nm-c2)
printf '%s' "$out" | grep -F 'unproven (no deliverable_evidence)' >/dev/null ||
    fail "unproven config did not name its missing evidence: $out"
[ "$(cleanup_state nm-c2)" = pending ] || fail "unproven config state: $(cleanup_state nm-c2)"
expect_kept "$ARTIFACT" nm-c2

# 5. Out-of-vocabulary and absent deliverables stay non-terminal, exactly as
#    the submit gate keeps its halt armed for them.
setup_case vocab-gap
add_no_merge_bead nm-x code 2 "" 2026-01-01
out=$(run_cleanup nm-x)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_DEFERRED' >/dev/null ||
    fail "code deliverable did not defer: $out"
[ "$(cleanup_state nm-x)" = pending ] || fail "code deliverable state: $(cleanup_state nm-x)"
expect_kept "$ARTIFACT" nm-x

setup_case vocab-absent
add_no_merge_bead nm-a "" 2 "" 2026-01-01
out=$(run_cleanup nm-a)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_DEFERRED' >/dev/null ||
    fail "absent deliverable did not defer: $out"
expect_kept "$ARTIFACT" nm-a

# 6. A stamped deliverable never overrides a live merge handoff: an open
#    merge_result keeps the record deferred on the merge path.
setup_case open-handoff-wins
add_no_merge_bead nm-o verdict 5 "" 2026-01-01
jq '.[0].metadata.merge_result = "pull_request_pending"' "$STATE" >"$STATE.t" && mv "$STATE.t" "$STATE"
out=$(run_cleanup nm-o)
printf '%s' "$out" | grep -F 'result=pull_request_pending' >/dev/null ||
    fail "open handoff did not defer on its merge result: $out"
expect_kept "$ARTIFACT" nm-o

# 7. If the fork SHA is not durably reachable from the recorded base on
#    origin, the checkout is the only copy: blocked, nothing removed.
setup_case fork-not-durable
add_no_merge_bead nm-d verdict 1 "" 2026-01-01
printf '0\n' >"$REACHABLE"
out=$(run_cleanup nm-d 2>&1) || true
printf '%s' "$out" | grep -F 'fork SHA is not durable' >/dev/null ||
    fail "unreachable fork SHA did not block: $out"
[ "$(cleanup_state nm-d)" = blocked ] || fail "fork-not-durable state: $(cleanup_state nm-d)"
expect_kept "$ARTIFACT" nm-d

# 8. Missing fork_sha cannot prove the checkout is the fork point: blocked.
setup_case missing-fork-sha
add_no_merge_bead nm-f verdict 1 "" 2026-01-01
jq 'map(if .id == "nm-f" then del(.metadata.fork_sha) else . end)' "$STATE" >"$STATE.t" && mv "$STATE.t" "$STATE"
out=$(run_cleanup nm-f 2>&1) || true
printf '%s' "$out" | grep -F 'missing fork_sha' >/dev/null ||
    fail "missing fork_sha did not block: $out"
[ "$(cleanup_state nm-f)" = blocked ] || fail "missing-fork_sha state: $(cleanup_state nm-f)"
expect_kept "$ARTIFACT" nm-f

# 9. Missing or non-origin base_ref cannot identify the recovery target.
setup_case missing-base-ref
add_no_merge_bead nm-b verdict 1 "" 2026-01-01
jq 'map(if .id == "nm-b" then del(.metadata.base_ref) else . end)' "$STATE" >"$STATE.t" && mv "$STATE.t" "$STATE"
out=$(run_cleanup nm-b 2>&1) || true
printf '%s' "$out" | grep -F 'incomplete no-merge base evidence' >/dev/null ||
    fail "missing base_ref did not block: $out"
[ "$(cleanup_state nm-b)" = blocked ] || fail "missing-base_ref state: $(cleanup_state nm-b)"
expect_kept "$ARTIFACT" nm-b

setup_case unsafe-base-ref
add_no_merge_bead nm-b2 verdict 1 "" 2026-01-01
jq '.[0].metadata.base_ref = "refs/remotes/origin/../../../etc"' "$STATE" >"$STATE.t" && mv "$STATE.t" "$STATE"
out=$(run_cleanup nm-b2 2>&1) || true
printf '%s' "$out" | grep -F 'unsafe no-merge base ref' >/dev/null ||
    fail "traversal base_ref did not block: $out"
expect_kept "$ARTIFACT" nm-b2

# 10. The generic evidence rails still hold on the no-merge path: a dirty
#     worktree or a moved HEAD blocks instead of removing.
setup_case dirty-worktree
add_no_merge_bead nm-w verdict 1 "" 2026-01-01
printf 'stray\n' >"$ARTIFACT/stray.txt"
out=$(run_cleanup nm-w 2>&1) || true
printf '%s' "$out" | grep -F 'artifact is dirty' >/dev/null ||
    fail "dirty no-merge worktree did not block: $out"
[ "$(cleanup_state nm-w)" = blocked ] || fail "dirty worktree state: $(cleanup_state nm-w)"
expect_kept "$ARTIFACT" nm-w

setup_case moved-head
add_no_merge_bead nm-h verdict 1 "" 2026-01-01
printf 'x\n' >"$ARTIFACT/moved.txt"
"$REAL_GIT" -C "$ARTIFACT" add moved.txt
"$REAL_GIT" -C "$ARTIFACT" -c user.name=t -c user.email=t@example.invalid commit -qm moved
out=$(run_cleanup nm-h 2>&1) || true
printf '%s' "$out" | grep -F 'artifact HEAD mismatch' >/dev/null ||
    fail "moved worktree HEAD did not block: $out"
expect_kept "$ARTIFACT" nm-h

# 11. A proven deliverable with no recorded artifact path completes without
#     one — there is nothing to retire and no removal happens.
setup_case absent-artifact
add_no_merge_bead nm-n verdict 1 "" 2026-01-01
jq 'map(if .id == "nm-n" then del(.metadata.artifact_dir) else . end)' "$STATE" >"$STATE.t" && mv "$STATE.t" "$STATE"
out=$(run_cleanup nm-n)
printf '%s' "$out" | grep -F 'artifact=absent' >/dev/null ||
    fail "absent artifact did not complete cleanly: $out"
[ "$(cleanup_state nm-n)" = complete ] || fail "absent-artifact state: $(cleanup_state nm-n)"

# 12. Sweep: the oldest actionable bead is picked; an older unproven record
#     does not starve it, and neither does an older record whose poisoned
#     comment_count passes jq's numeric compare but not the shell gate's
#     digits-and-int64 form — such a record must never be selected, or the
#     bounded sweep would re-pick it every fire and starve every other
#     cleanup. After the actionable ones drain, the sweep reports idle rather
#     than touching the still-unproven or tampered records.
setup_case sweep-order
add_no_merge_bead sw-old verdict 1 "" 2026-01-01
add_no_merge_bead sw-poison verdict 1.5 "" 2026-01-02
add_no_merge_bead sw-unproven verdict 0 "" 2026-01-02
add_no_merge_bead sw-new config 0 "criteria already satisfied" 2026-01-03
old_artifact="$CITY/.gc/worktrees/demo/artifacts/worktrees/sw-old"
new_artifact="$CITY/.gc/worktrees/demo/artifacts/worktrees/sw-new"
unproven_artifact="$CITY/.gc/worktrees/demo/artifacts/worktrees/sw-unproven"
poison_artifact="$CITY/.gc/worktrees/demo/artifacts/worktrees/sw-poison"
out=$(run_cleanup)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_COMPLETE' >/dev/null ||
    fail "sweep did not complete the oldest actionable bead: $out"
expect_gone "$old_artifact" sw-old
[ "$(cleanup_state sw-old)" = complete ] || fail "sweep state for sw-old: $(cleanup_state sw-old)"
[ "$(cleanup_state sw-new)" = pending ] || fail "sweep touched sw-new early: $(cleanup_state sw-new)"
[ "$(cleanup_state sw-unproven)" = pending ] ||
    fail "sweep touched the unproven record: $(cleanup_state sw-unproven)"
[ "$(cleanup_state sw-poison)" = pending ] ||
    fail "sweep selected the poisoned record: $(cleanup_state sw-poison)"
expect_kept "$poison_artifact" sw-poison

out=$(run_cleanup)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_COMPLETE' >/dev/null ||
    fail "second sweep did not complete the next actionable bead: $out"
expect_gone "$new_artifact" sw-new

out=$(run_cleanup)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_IDLE' >/dev/null ||
    fail "sweep did not report idle once only unactionable records remain: $out"
expect_kept "$unproven_artifact" sw-unproven
expect_kept "$poison_artifact" sw-poison
[ "$(cleanup_state sw-unproven)" = pending ] &&
    [ "$(cleanup_state sw-poison)" = pending ] ||
    fail "idle sweep mutated an unactionable record"

# 13. Case-variant deliverable stamps take the same row (both the sweep
#     filter and the gate normalize case, mirroring the submit gate).
setup_case case-variant
add_no_merge_bead nm-v2 VERDICT 2 "" 2026-01-01
out=$(run_cleanup nm-v2)
printf '%s' "$out" | grep -F 'ARTIFACT_CLEANUP_COMPLETE' >/dev/null ||
    fail "case-variant deliverable did not complete: $out"
expect_gone "$ARTIFACT" nm-v2

# 14. A garbage fork_sha cannot prove the checkout is the fork point: the
#     HEAD-equality gate blocks it.
setup_case garbage-fork-sha
add_no_merge_bead nm-g verdict 1 "" 2026-01-01
jq '.[0].metadata.fork_sha = "not-a-commit"' "$STATE" >"$STATE.t" && mv "$STATE.t" "$STATE"
out=$(run_cleanup nm-g 2>&1) || true
printf '%s' "$out" | grep -F 'artifact HEAD mismatch' >/dev/null ||
    fail "garbage fork_sha did not block: $out"
[ "$(cleanup_state nm-g)" = blocked ] || fail "garbage fork_sha state: $(cleanup_state nm-g)"
expect_kept "$ARTIFACT" nm-g

# 15. An unreadable origin defers rather than blocking: the reachability
#     check stays retryable while origin is down.
setup_case fetch-failure
add_no_merge_bead nm-r verdict 1 "" 2026-01-01
export GC_IT_FETCH_FAIL=1
out=$(run_cleanup nm-r 2>&1) || true
unset GC_IT_FETCH_FAIL
printf '%s' "$out" | grep -F 'could not refresh origin/main' >/dev/null ||
    fail "origin fetch failure did not defer: $out"
[ "$(cleanup_state nm-r)" = pending ] || fail "fetch-failure state: $(cleanup_state nm-r)"
expect_kept "$ARTIFACT" nm-r

echo "no-merge artifact cleanup tests passed"
