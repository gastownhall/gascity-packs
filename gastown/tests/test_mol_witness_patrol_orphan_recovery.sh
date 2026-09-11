#!/usr/bin/env bash
set -euo pipefail

# Executed coverage for `recover-orphaned-beads` in mol-witness-patrol.
#
# That step force-closes beads, force-reassigns them and deletes worktrees, and
# it decides to do so from a liveness snapshot and a "did this branch land?"
# test.  Both decisions were previously wrong in the destructive direction: an
# unquoted pathspec made an unmerged branch read as merged, and a lookup failure
# read as "the owner is gone".  Contract pins in
# scripts/gascity_pack_inference_gate.py catch deletion of those guards; this
# file catches them being kept but broken.
#
# The blocks are LIFTED out of the formula and executed, not transcribed.  A
# transcription is a second copy that drifts silently from the recipe that
# actually runs, which is the failure mode this whole area already has.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
FORMULA="$ROOT/gastown/formulas/mol-witness-patrol.toml"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

BIN="$tmp/bin"
STEP1="$tmp/step1-liveness-map.sh"
STEP2A="$tmp/step2a-verdict.sh"
STEP3="$tmp/step3-on-main.sh"
ERRLOG="$tmp/stderr.log"
: >"$ERRLOG"

fail() {
    echo "FAIL: $*" >&2
    if [ -s "$ERRLOG" ]; then
        echo "--- captured stderr ---" >&2
        tail -n 20 "$ERRLOG" >&2
    fi
    exit 1
}

# lift_block <sentinel> <dest> -- extract the fenced ```bash block containing
# <sentinel>.  `<bead>` is the formula's placeholder for the bead id; in shell
# it would parse as a redirect, so it is substituted mechanically.
lift_block() {
    local sentinel="$1" dest="$2"
    awk -v want="$sentinel" '
        /^[[:space:]]*```bash[[:space:]]*$/ { inblk = 1; body = ""; next }
        inblk && /^[[:space:]]*```[[:space:]]*$/ {
            inblk = 0
            if (index(body, want)) { printf "%s", body; found = 1 }
            body = ""
            next
        }
        inblk { body = body $0 "\n"; next }
        END { exit(found ? 0 : 1) }
    ' "$FORMULA" | sed 's/<bead>/TESTBEAD/g' >"$dest" ||
        fail "no fenced bash block in $FORMULA contains: $sentinel"
    [ -s "$dest" ] || fail "lifted an empty block for: $sentinel"
    bash -n "$dest" || fail "lifted block does not parse: $sentinel"
}

# Sentinels are chosen to be stable under the mutations these tests are meant
# to catch: `STILL_ORPHANED=` rather than `STILL_ORPHANED=false`, so flipping
# the verdict's initial value still lifts and is caught by an assertion here
# rather than by the extraction failing.
lift_block 'build_liveness_map() {' "$STEP1"
lift_block 'STILL_ORPHANED=' "$STEP2A"
lift_block 'merge-base --is-ancestor' "$STEP3"

write_gc_stub() {
    mkdir -p "$BIN"
    cat >"$BIN/gc" <<'SH'
#!/usr/bin/env sh
# Match on the reconstructed command line: the repo's bare-`bd` lint only
# accepts beads literals that read as `gc bd ...`.
invocation="gc $*"
case "$invocation" in
    *"gc session list"*)
        if [ -n "${GC_STUB_FAIL_SESSION_LIST:-}" ]; then exit 1; fi
        cat "$GC_SESSIONS_JSON"
        ;;
    *"gc bd list"*) cat "$GC_SESSION_BEADS_JSON" ;;
    *"gc bd show"*)
        if [ -n "${GC_STUB_FAIL_BD_SHOW:-}" ]; then exit 1; fi
        cat "$GC_BEAD_JSON"
        ;;
    *"gc mail send"*) : ;;
    *) printf '{}' ;;
esac
SH
    chmod +x "$BIN/gc"
}

write_gc_stub
export PATH="$BIN:$PATH"
export GC_SESSIONS_JSON="$tmp/sessions.json"
export GC_SESSION_BEADS_JSON="$tmp/session-beads.json"
export GC_BEAD_JSON="$tmp/bead.json"
printf '[]' >"$GC_SESSION_BEADS_JSON"

command -v jq >/dev/null || fail "jq is required (the recipe under test uses it)"

# A roster with two live pool sessions.  Anything else resolves to `absent`.
ROSTER_LIVE='{"sessions":[
  {"id":"pool-1","name":"pool-1","state":"active","closed":false},
  {"id":"pool-2","name":"pool-2","state":"active","closed":false}
]}'
# Sessions exist but carry no identifier the map can key on -- the gc-3tn8g
# schema-drift shape, which yields an empty map while sessions are live.
ROSTER_NO_IDENTIFIERS='{"sessions":[{"state":"active","closed":false}]}'

set_roster() { printf '%s' "$1" >"$GC_SESSIONS_JSON"; }

# run_verdict <step1-assignee> <bead-assignee> <updated-at-spec>
#   updated-at-spec: OLD | BOUNDARY | NEWER | MISSING | <literal RFC3339>
# Sources the shipped Step 1 and Step 2a blocks back to back, as the recipe runs
# them, and reports the verdict.  `set +eu` because the recipe is executed by an
# agent in a plain shell, not under strict mode -- testing it stricter than it
# ships would measure the wrong thing.
run_verdict() {
    VERDICT=$(
        set +eu
        ASSIGNEE="$1"
        bead_assignee="$2"
        spec="$3"
        # The recipe narrates its decisions on stdout; send that to the log so
        # only the verdict is captured, and so `fail` can show the reasoning.
        {
            . "$STEP1"
            case "$spec" in
                OLD) u="2020-01-01T00:00:00Z" ;;
                BOUNDARY) u="${CYCLE_MAP_BUILT_AT%Z}.7035126Z" ;;
                NEWER) u="2099-01-01T00:00:00Z" ;;
                MID_CYCLE)
                    # A timestamp inside the cycle but before Step 2a's own
                    # rebuild.  Sleeping first makes the two watermarks differ
                    # by whole seconds, which is what separates "compared
                    # against the cycle's snapshot" from "compared against the
                    # rebuild that just happened".  GNU date, as in the sibling
                    # heartbeat test: the recipe needs BSD portability, this
                    # Linux-only CI test does not.
                    u=$(date -u -d "$CYCLE_MAP_BUILT_AT + 1 second" +%Y-%m-%dT%H:%M:%SZ)
                    sleep 2.1
                    ;;
                MISSING) u="" ;;
                *) u="$spec" ;;
            esac
            if [ -n "$u" ]; then
                printf '[{"id":"TESTBEAD","assignee":"%s","updated_at":"%s"}]' \
                    "$bead_assignee" "$u" >"$GC_BEAD_JSON"
            else
                printf '[{"id":"TESTBEAD","assignee":"%s"}]' "$bead_assignee" >"$GC_BEAD_JSON"
            fi
            . "$STEP2A"
        } >>"$ERRLOG" 2>&1
        printf '%s' "$STILL_ORPHANED"
    )
}

assert_verdict() {
    local expected="$1" label="$2"
    [ "$VERDICT" = "$expected" ] ||
        fail "$label: expected STILL_ORPHANED=$expected, got '$VERDICT'"
}

# --- Step 2a: the pre-destruction liveness verdict -------------------------

test_absent_assignee_is_still_orphaned() {
    # Positive control.  Without it every guard below passes vacuously by
    # never producing `true` at all, and the step would recover nothing.
    set_roster "$ROSTER_LIVE"
    run_verdict "pool-gone" "pool-gone" OLD
    assert_verdict true "a genuinely absent assignee"
}

test_closed_assignee_is_still_orphaned() {
    set_roster '{"sessions":[{"id":"pool-1","name":"pool-1","state":"active","closed":true}]}'
    run_verdict "pool-1" "pool-1" OLD
    assert_verdict true "an assignee whose session is closed"
}

test_live_assignee_is_not_orphaned() {
    set_roster "$ROSTER_LIVE"
    run_verdict "pool-1" "pool-1" OLD
    assert_verdict false "an assignee that is alive at re-check time"
}

test_unusable_liveness_map_skips_instead_of_orphaning() {
    # The core of the fail-open defect: a failed query must mean "cannot
    # verify", never "the owner is gone".
    set_roster "$ROSTER_LIVE"
    GC_STUB_FAIL_SESSION_LIST=1 run_verdict "pool-gone" "pool-gone" OLD
    assert_verdict false "a failed roster query"
}

test_empty_map_with_live_sessions_skips() {
    set_roster "$ROSTER_NO_IDENTIFIERS"
    run_verdict "pool-gone" "pool-gone" OLD
    assert_verdict false "an empty map built while sessions are live"
}

test_missing_assignee_skips() {
    set_roster "$ROSTER_LIVE"
    run_verdict "" "" OLD
    assert_verdict false "a bead with no assignee to re-verify"
}

test_unreadable_bead_skips() {
    set_roster "$ROSTER_LIVE"
    GC_STUB_FAIL_BD_SHOW=1 run_verdict "pool-gone" "pool-gone" OLD
    assert_verdict false "a bead whose record could not be read"
}

test_missing_updated_at_skips() {
    set_roster "$ROSTER_LIVE"
    run_verdict "pool-gone" "pool-gone" MISSING
    assert_verdict false "a bead with no readable updated_at"
}

test_bead_touched_mid_cycle_skips() {
    set_roster "$ROSTER_LIVE"
    run_verdict "pool-gone" "pool-gone" NEWER
    assert_verdict false "a bead touched after the cycle's snapshot"
}

test_boundary_second_fraction_skips() {
    # Sub-second `updated_at` inside the same second as the whole-second
    # watermark.  Compared as raw strings this inverts -- "." sorts before "Z"
    # -- and it inverts toward destroying, so it is pinned as its own case.
    set_roster "$ROSTER_LIVE"
    run_verdict "pool-gone" "pool-gone" BOUNDARY
    assert_verdict false "a sub-second timestamp in the watermark's own second"
}

test_touch_before_the_recheck_rebuild_still_skips() {
    # The staleness compare must use the watermark from the cycle's FIRST
    # snapshot, not the one Step 2a's own rebuild just stamped.  Against the
    # rebuild's watermark almost every bead reads as "older", so the guard
    # would survive as a line of code while catching nothing.
    set_roster "$ROSTER_LIVE"
    run_verdict "pool-gone" "pool-gone" MID_CYCLE
    assert_verdict false "a bead touched between the snapshot and the re-check"
}

test_reassigned_bead_skips() {
    # Someone handed the bead to a live agent after Step 1 read it.
    set_roster "$ROSTER_LIVE"
    run_verdict "pool-gone" "pool-1" OLD
    assert_verdict false "a bead reassigned since the snapshot"
}

# --- Step 3: the "did this branch land?" test -----------------------------

new_repo() {
    REPO="$tmp/repo-$1"
    ORIGIN="$tmp/repo-$1.git"
    git init -q --bare -b main "$ORIGIN"
    git init -q -b main "$REPO"
    git -C "$REPO" config user.name "Witness Patrol Test"
    git -C "$REPO" config user.email "witness@example.invalid"
    git -C "$REPO" remote add origin "$ORIGIN"
    printf 'baseline\n' >"$REPO/README.md"
    git -C "$REPO" add -A
    git -C "$REPO" commit -q -m baseline
    git -C "$REPO" push -q origin main
}

# commit_branch <branch> <file>...
commit_branch() {
    local branch="$1"
    shift
    git -C "$REPO" checkout -q -b "$branch" main
    local f
    for f in "$@"; do
        printf 'branch work\n' >"$REPO/$f"
    done
    git -C "$REPO" add -A
    git -C "$REPO" commit -q -m "work on $branch"
    git -C "$REPO" push -q origin "$branch"
    git -C "$REPO" checkout -q main
}

# add_branch_commit <branch> <file>
add_branch_commit() {
    git -C "$REPO" checkout -q "$1"
    printf 'more work\n' >"$REPO/$2"
    git -C "$REPO" add -A
    git -C "$REPO" commit -q -m "more work on $1"
    git -C "$REPO" push -q origin "$1"
    git -C "$REPO" checkout -q main
}

advance_main() {
    printf 'unrelated\n' >>"$REPO/README.md"
    git -C "$REPO" add -A
    git -C "$REPO" commit -q -m "unrelated main commit"
    git -C "$REPO" push -q origin main
}

land_merge() {
    git -C "$REPO" merge -q --no-ff -m "merge $1" "$1"
    git -C "$REPO" push -q origin main
}

land_rebase() {
    # Replays the branch's commits onto a moved main: same content, new SHAs,
    # so ancestry can never see the landing.
    git -C "$REPO" cherry-pick "origin/main..origin/$1" >/dev/null 2>&1 ||
        fail "cherry-pick of $1 onto main failed"
    git -C "$REPO" push -q origin main
}

land_squash() {
    git -C "$REPO" merge --squash "$1" >/dev/null 2>&1
    git -C "$REPO" commit -q -m "squashed $1"
    git -C "$REPO" push -q origin main
}

# run_on_main <branch>
run_on_main() {
    ON_MAIN=$(
        set +eu
        cd "$REPO" || exit 1
        BRANCH="$1"
        ON_MAIN=
        { . "$STEP3"; } >>"$ERRLOG" 2>&1
        printf '%s' "$ON_MAIN"
    )
}

assert_on_main() {
    local expected="$1" label="$2"
    [ "$ON_MAIN" = "$expected" ] ||
        fail "$label: expected ON_MAIN=$expected, got '$ON_MAIN'"
}

test_merge_commit_landing_reads_as_on_main() {
    new_repo ff
    commit_branch feat "feature.txt"
    land_merge feat
    run_on_main feat
    assert_on_main true "a branch merged with a merge commit"
}

test_rebased_landing_reads_as_on_main() {
    new_repo rebased
    commit_branch feat "feature.txt"
    advance_main
    land_rebase feat
    run_on_main feat
    assert_on_main true "a branch replayed onto a moved main"
}

test_squashed_landing_reads_as_on_main() {
    new_repo squashed
    commit_branch feat "one.txt"
    add_branch_commit feat "two.txt"
    advance_main
    land_squash feat
    run_on_main feat
    assert_on_main true "a branch squashed onto main"
}

test_unlanded_branch_reads_as_not_on_main() {
    new_repo unlanded
    commit_branch feat "feature.txt"
    advance_main
    run_on_main feat
    assert_on_main false "a branch that never landed"
}

test_unlanded_branch_with_space_in_path_reads_as_not_on_main() {
    # Unquoted, this filename word-splits into pathspecs matching nothing;
    # `git diff --quiet` over those exits 0 and the branch reads as merged.
    new_repo space-unlanded
    commit_branch feat "has space.txt"
    advance_main
    run_on_main feat
    assert_on_main false "an unlanded branch touching a path with a space"
}

test_unlanded_branch_with_newline_in_path_reads_as_not_on_main() {
    # Without `-z`, `--name-only` C-quotes this path; re-reading the quoted
    # form yields a pathspec matching nothing -- the same destructive verdict
    # by a different route, which a per-file loop over unquoted output does
    # not fix.
    new_repo newline-unlanded
    commit_branch feat "$(printf 'has\nnewline.txt')"
    advance_main
    run_on_main feat
    assert_on_main false "an unlanded branch touching a path with a newline"
}

test_landed_branch_with_space_in_path_reads_as_on_main() {
    # Positive control for the two cases above: the quoting fix must not turn
    # every awkward filename into a permanent "not merged".
    new_repo space-landed
    commit_branch feat "has space.txt"
    advance_main
    land_rebase feat
    run_on_main feat
    assert_on_main true "a landed branch touching a path with a space"
}

test_main_touching_the_files_after_landing_reads_as_not_on_main() {
    # The content test's stated bound.  It answers not-merged, which
    # re-dispatches -- wasteful, never destructive.
    new_repo touched-after
    commit_branch feat "feature.txt"
    advance_main
    land_rebase feat
    printf 'main edited this later\n' >"$REPO/feature.txt"
    git -C "$REPO" add -A
    git -C "$REPO" commit -q -m "main edits the landed file"
    git -C "$REPO" push -q origin main
    run_on_main feat
    assert_on_main false "main having edited the landed files afterwards"
}

test_branch_with_no_changes_reads_as_not_on_main() {
    new_repo empty-branch
    git -C "$REPO" checkout -q -b feat main
    git -C "$REPO" commit -q --allow-empty -m "empty"
    git -C "$REPO" push -q origin feat
    git -C "$REPO" checkout -q main
    advance_main
    run_on_main feat
    assert_on_main false "a branch introducing no file changes"
}

test_unreachable_remote_reads_as_not_on_main() {
    new_repo no-remote
    commit_branch feat "feature.txt"
    land_merge feat
    git -C "$REPO" remote set-url origin "$tmp/does-not-exist.git"
    run_on_main feat
    assert_on_main false "a failed fetch"
}

# --- The lift itself -------------------------------------------------------

test_lifted_step3_block_is_the_hardened_one() {
    # If the extraction ever grabs the wrong block, or the guard is replaced by
    # a form that only looks right, the cases above could pass for the wrong
    # reason.  Assert the two jointly load-bearing halves are what ran.
    grep -qF -- 'git diff --name-only -z "$MERGE_BASE" "origin/$BRANCH"' "$STEP3" ||
        fail "lifted Step 3 block does not collect changed paths NUL-delimited"
    grep -qF -- '-- "${CHANGED[@]}"' "$STEP3" ||
        fail "lifted Step 3 block does not pass changed paths as a quoted array"
}

test_lifted_blocks_use_no_bash4_only_constructs() {
    # Same bar as gastown/tests/test_witness_heartbeat_check.sh: the fleet
    # includes macOS on bash 3.2.  Comment lines are stripped first -- the
    # recipe names `mapfile` in a comment explaining why it is not used.
    local block
    for block in "$STEP1" "$STEP2A" "$STEP3"; do
        ! grep -v '^[[:space:]]*#' "$block" |
            grep -nE 'declare -A|local -A|mapfile|readarray|\$\{[A-Za-z_]+\^|\$\{[A-Za-z_]+,,|&>>|\[\[ -v ' >/dev/null ||
            fail "$(basename "$block") must stay bash 3.2 compatible"
    done
}

test_absent_assignee_is_still_orphaned
test_closed_assignee_is_still_orphaned
test_live_assignee_is_not_orphaned
test_unusable_liveness_map_skips_instead_of_orphaning
test_empty_map_with_live_sessions_skips
test_missing_assignee_skips
test_unreadable_bead_skips
test_missing_updated_at_skips
test_bead_touched_mid_cycle_skips
test_boundary_second_fraction_skips
test_touch_before_the_recheck_rebuild_still_skips
test_reassigned_bead_skips
test_merge_commit_landing_reads_as_on_main
test_rebased_landing_reads_as_on_main
test_squashed_landing_reads_as_on_main
test_unlanded_branch_reads_as_not_on_main
test_unlanded_branch_with_space_in_path_reads_as_not_on_main
test_unlanded_branch_with_newline_in_path_reads_as_not_on_main
test_landed_branch_with_space_in_path_reads_as_on_main
test_main_touching_the_files_after_landing_reads_as_not_on_main
test_branch_with_no_changes_reads_as_not_on_main
test_unreachable_remote_reads_as_not_on_main
test_lifted_step3_block_is_the_hardened_one
test_lifted_blocks_use_no_bash4_only_constructs

echo "mol-witness-patrol orphan recovery tests passed"
