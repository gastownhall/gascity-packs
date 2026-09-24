#!/usr/bin/env bash
set -euo pipefail

# Executed coverage for the guarded ancestry decision in the `rebase` step of
# mol-refinery-patrol (issue 374).
#
# The step used to run `git checkout -b temp origin/$BRANCH` followed by an
# unconditional `git rebase origin/$TARGET`.  When the source branch is already
# based on the target, that rebase is not a no-op: it flattens merge commits and
# drops the conflict resolutions recorded in them.  The two observed outcomes
# are an artificial conflict on an unchanged SHA (the rejection treadmill) and a
# silent flattening that merge-push then force-pushes over the source branch.
# The guard probes ancestry first, fails closed on every error, and skips the
# rebase when the source is already based.
#
# The block is LIFTED out of the formula and executed, not transcribed.  A
# transcription is a second copy that drifts silently from the recipe that
# actually runs, which is the failure mode this whole area already has.
#
# The lift sentinel (`git checkout -b temp origin/$BRANCH`) is present on both
# the unguarded and the guarded tree, so running this file against an unguarded
# formula produces behavioral and static reds rather than an extraction error.
# That is the permanent red-control capability: point REBASE_GUARD_FORMULA at
# another tree and run this same file byte-unmodified.
#
# Every leg runs even if an earlier one fails, and the per-leg verdicts are
# summarised at the end.  The red control has to enumerate outcomes per leg
# (never a count), which a first-failure abort could not produce in one run.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
FORMULA="${REBASE_GUARD_FORMULA:-$ROOT/gastown/formulas/mol-refinery-patrol.toml}"

# The halt leg pipes the wisp-pour answer through real `jq`, so jq is a hard
# test dependency.  Declare it rather than shadowing jq in the stub PATH: the
# halt's pour-id extraction must genuinely parse the stub's JSON.
command -v jq >/dev/null 2>&1 || {
    echo "FAIL: jq required (halt leg)" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

BIN="$tmp/bin"
GITSHIM="$tmp/gitshim"
BLOCK="$tmp/rebase-step.sh"
GC_LOG="$tmp/gc.log"
LAST_OUT="/dev/null"
export GC_LOG

# Hermetic git identity.  git 2.43 (local) and 2.52 (CI) disagree about whether
# a missing committer identity is fatal, and a host /etc/gitconfig (e.g.
# core.hooksPath) must not leak into the fixtures either.
export HOME="$tmp/home"
export GIT_CONFIG_GLOBAL="$tmp/home/.gitconfig"
export GIT_CONFIG_NOSYSTEM=1
mkdir -p "$HOME"
: >"$GIT_CONFIG_GLOBAL"

# The environment the real step derives in an earlier fence.  Exporting
# GC_BEAD_ID keeps the halt's empty-GC_BEAD_ID `gc bd list` fallback unreached.
T_BRANCH=source
T_TARGET=main
T_WORK=TESTBEAD
T_AGENT=testrig/refinery
T_WISP=wisp-current

FENCE_RC=0

fail() {
    echo "FAIL: $*" >&2
    if [ -s "$LAST_OUT" ]; then
        echo "--- captured fence output ---" >&2
        tail -n 30 "$LAST_OUT" >&2
    fi
    exit 1
}

# lift_block <sentinel> <dest> -- extract the fenced ```bash block containing
# <sentinel>.  Mechanical substitutions only: the formula's `{{...}}` template
# holes and its `<bead>` placeholder would not survive `bash -n` as written.
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
    ' "$FORMULA" \
        | sed -e 's/{{target_branch}}/main/g' \
              -e 's/{{rig_name}}/testrig/g' \
              -e 's/{{binding_prefix}}//g' \
              -e 's/<bead>/TESTBEAD/g' >"$dest" ||
        fail "no fenced bash block in $FORMULA contains: $sentinel"
    [ -s "$dest" ] || fail "lifted an empty block for: $sentinel"
    bash -n "$dest" || fail "lifted block does not parse: $sentinel"
}

# PATH-shim `gc`.  Every invocation is appended to $GC_LOG; that log is the
# bead-mutation oracle the legs assert against.  Patterns are written so they
# read as `gc bd ...`, which is what the repo's bare-`bd` lint accepts.
write_gc_stub() {
    mkdir -p "$BIN"
    cat >"$BIN/gc" <<'SH'
#!/usr/bin/env sh
invocation="gc $*"
printf '%s\n' "$invocation" >>"$GC_LOG"
case "$invocation" in
    *"gc bd mol wisp"*)       printf '{"new_epic_id":"wisp-next"}\n' ;;
    *"gc bd mol burn"*)       : ;;
    *"gc bd update"*)         : ;;
    *"gc bd list"*)           printf '[{"id":"wisp-current"}]\n' ;;
    *"gc bd show"*)           printf '{"id":"TESTBEAD"}\n' ;;
    *"gc mail send"*)         : ;;
    *"gc runtime drain-ack"*) : ;;
    *)                        printf '{}\n' ;;
esac
SH
    chmod +x "$BIN/gc"
}

# Passthrough `git` shim for leg 6: everything delegates to the real git except
# the ancestry probe, which exits 128.  A poisoned ref would not survive the
# in-fence fetch that runs immediately before the probe, so a stub is the only
# way to reach the probe-error arm.  Real git is resolved to an absolute path
# here, before the shim is ever on PATH.
write_git_shim() {
    local real_git
    real_git=$(command -v git)
    mkdir -p "$GITSHIM"
    cat >"$GITSHIM/git" <<SH
#!/usr/bin/env bash
if [ "\${1:-}" = "merge-base" ]; then
    exit 128
fi
exec "$real_git" "\$@"
SH
    chmod +x "$GITSHIM/git"
}

# Execute the lifted fence as one unit.  Plain `bash` with `set +eu`: the recipe
# runs in a plain agent shell, and testing it stricter than it ships would
# measure the wrong thing.  The git shim, when supplied, is prepended to PATH
# only here -- fixture setup and assertions always run with real git.
#
# The 4th argument selects which lifted script runs; it defaults to the rebase
# fence, so leg 10 can drive the `mr` recovery fence through the identical
# environment the step itself gets rather than a second harness.
run_fence() {
    local dir="$1" out="$2" pathpre="${3:-}" script="${4:-$BLOCK}"
    FENCE_RC=0
    LAST_OUT="$out"
    : >"$GC_LOG"
    (
        cd "$dir" || exit 99
        PATH="${pathpre:+$pathpre:}$BIN:$PATH" \
        BRANCH="$T_BRANCH" TARGET="$T_TARGET" WORK="$T_WORK" \
        GC_AGENT="$T_AGENT" GC_BEAD_ID="$T_WISP" GC_LOG="$GC_LOG" \
            bash -c 'set +eu; . "$1"' bash "$script"
    ) >"$out" 2>&1 || FENCE_RC=$?
}

gitconf() {
    git -C "$1" config user.name "Rebase Guard Test"
    git -C "$1" config user.email "rebase-guard@example.invalid"
}

assert_rc_zero() {
    [ "$FENCE_RC" -eq 0 ] || fail "$1 (rc=$FENCE_RC)"
}

assert_rc_nonzero() {
    [ "$FENCE_RC" -ne 0 ] || fail "$1 (rc=$FENCE_RC)"
}

assert_contains() {
    grep -Fq -- "$2" "$LAST_OUT" || fail "$1: expected output to contain: $2"
}

assert_not_contains() {
    if grep -Fq -- "$2" "$LAST_OUT"; then
        fail "$1: output unexpectedly contains: $2"
    fi
    return 0
}

assert_log_has() {
    grep -Fq -- "$2" "$GC_LOG" || fail "$1: expected gc log to contain: $2"
}

# The decision arms are retry-later routes: they must not touch bead state.
assert_no_bead_mutation() {
    if grep -Fq -- 'gc bd update' "$GC_LOG"; then
        fail "$1: the block mutated bead state (gc bd update)"
    fi
    if grep -Fq -- 'gc workflow' "$GC_LOG"; then
        fail "$1: the block mutated workflow state"
    fi
    return 0
}

assert_no_temp() {
    if git -C "$1" rev-parse --verify --quiet temp >/dev/null 2>&1; then
        fail "$2"
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Fixtures.  Bare origin.git plus a consumer clone, fresh per leg.
# ---------------------------------------------------------------------------

init_pair() {
    local d="$1"
    mkdir -p "$d"
    git init --quiet --bare --initial-branch=main "$d/origin.git"
    git init --quiet --initial-branch=main "$d/build"
    gitconf "$d/build"
    git -C "$d/build" remote add origin "$d/origin.git"
}

finish_pair() {
    local d="$1"
    git clone --quiet "$d/origin.git" "$d/clone"
    gitconf "$d/clone"
}

seed_main() {
    local b="$1"
    printf 'base\n' >"$b/f"
    printf 'base\n' >"$b/g"
    git -C "$b" add f g
    git -C "$b" commit --quiet -m "T: base"
    git -C "$b" push --quiet origin main
}

assert_already_based() {
    local d="$1" label="$2"
    [ "$(git -C "$d/clone" merge-base origin/main origin/source)" = \
      "$(git -C "$d/clone" rev-parse origin/main)" ] ||
        fail "$label fixture is not already-based"
}

# EX-1: already-based, conflicting.  Two --no-ff merges, the second resolving a
# two-sided same-line edit differently from both raw sides, plus a plain commit.
# A flattening rebase drops that recorded resolution and conflicts.
fixture_ex1() {
    local d="$1" b
    init_pair "$d"
    b="$d/build"
    seed_main "$b"
    git -C "$b" checkout --quiet -b source main
    git -C "$b" checkout --quiet -b sideA main
    printf 'A\n' >"$b/f"
    git -C "$b" commit --quiet -am "sideA: f -> A"
    git -C "$b" checkout --quiet source
    git -C "$b" merge --quiet --no-ff -m "merge A" sideA
    git -C "$b" checkout --quiet -b sideB main
    printf 'B\n' >"$b/f"
    git -C "$b" commit --quiet -am "sideB: f -> B"
    git -C "$b" checkout --quiet source
    if git -C "$b" merge --no-ff -m "merge B" sideB >/dev/null 2>&1; then
        fail "EX-1 fixture: merge B was expected to conflict"
    fi
    printf 'C\n' >"$b/f"
    git -C "$b" add f
    git -C "$b" commit --quiet --no-edit
    printf 'extra\n' >"$b/h"
    git -C "$b" add h
    git -C "$b" commit --quiet -m "plain commit"
    git -C "$b" push --quiet origin source
    finish_pair "$d"
    assert_already_based "$d" "EX-1"
}

# EX-2: already-based, clean.  The merges touch disjoint files, so the rebase
# succeeds and the damage is silent flattening rather than a conflict.
fixture_ex2() {
    local d="$1" b
    init_pair "$d"
    b="$d/build"
    seed_main "$b"
    git -C "$b" checkout --quiet -b source main
    git -C "$b" checkout --quiet -b sideA main
    printf 'A\n' >"$b/f"
    git -C "$b" commit --quiet -am "sideA: f -> A"
    git -C "$b" checkout --quiet source
    git -C "$b" merge --quiet --no-ff -m "merge A" sideA
    git -C "$b" checkout --quiet -b sideB main
    printf 'B\n' >"$b/g"
    git -C "$b" commit --quiet -am "sideB: g -> B"
    git -C "$b" checkout --quiet source
    git -C "$b" merge --quiet --no-ff -m "merge B" sideB
    printf 'extra\n' >"$b/h"
    git -C "$b" add h
    git -C "$b" commit --quiet -m "plain commit"
    git -C "$b" push --quiet origin source
    finish_pair "$d"
    assert_already_based "$d" "EX-2"
}

# EX-3a: genuinely diverged, clean (the two sides touch disjoint files).
fixture_ex3a() {
    local d="$1" b
    init_pair "$d"
    b="$d/build"
    seed_main "$b"
    git -C "$b" checkout --quiet -b source main
    printf 'source side\n' >"$b/s"
    git -C "$b" add s
    git -C "$b" commit --quiet -m "source: add s"
    git -C "$b" push --quiet origin source
    git -C "$b" checkout --quiet main
    printf 'main side\n' >"$b/m"
    git -C "$b" add m
    git -C "$b" commit --quiet -m "main: add m"
    git -C "$b" push --quiet origin main
    finish_pair "$d"
}

# EX-3b: genuinely diverged, conflicting (both sides edit the same line).
fixture_ex3b() {
    local d="$1" b
    init_pair "$d"
    b="$d/build"
    seed_main "$b"
    git -C "$b" checkout --quiet -b source main
    printf 'S\n' >"$b/f"
    git -C "$b" commit --quiet -am "source: f -> S"
    git -C "$b" push --quiet origin source
    git -C "$b" checkout --quiet main
    printf 'M\n' >"$b/f"
    git -C "$b" commit --quiet -am "main: f -> M"
    git -C "$b" push --quiet origin main
    finish_pair "$d"
}

# ---------------------------------------------------------------------------
# Legs
# ---------------------------------------------------------------------------

# Leg 1 -- skip preserves topology (EX-1 and EX-2; AC-374-02/04).
# SHA identity plus an intact merge count prove the rebase line was never
# reached.  Red on base: artificial conflict (EX-1), or flattening breaking SHA
# equality and taking merges 2 -> 0 (EX-2).
leg1() {
    local ex d src_before
    for ex in ex1 ex2; do
        d="$tmp/leg1-$ex"
        "fixture_$ex" "$d"
        src_before=$(git -C "$d/clone" rev-parse origin/source)
        [ "$(git -C "$d/clone" rev-list --count --merges origin/source)" -eq 2 ] ||
            fail "leg 1/$ex fixture: expected 2 merge commits"
        run_fence "$d/clone" "$tmp/leg1-$ex.out"
        assert_rc_zero "leg 1/$ex: the skip path must succeed"
        assert_contains "leg 1/$ex" "SKIP-REBASE:"
        [ "$(git -C "$d/clone" rev-parse temp)" = "$src_before" ] ||
            fail "leg 1/$ex: temp is not SHA-identical to origin/source"
        [ "$(git -C "$d/clone" rev-list --count --merges temp)" -eq 2 ] ||
            fail "leg 1/$ex: merge topology was flattened"
        # AC-374-02 names downstream `git merge --ff-only` accepting the source
        # as its verification.  Leg 2 runs this assertion for the diverged path;
        # run it here too so the AC's clause is executable on the skip path it is
        # actually about, rather than only entailed by the SHA identity above.
        git -C "$d/clone" merge-base --is-ancestor origin/main temp ||
            fail "leg 1/$ex: origin/main is not an ancestor of the skipped temp, so merge-push's --ff-only would refuse it"
        [ ! -e "$d/clone/.git/rebase-merge" ] && [ ! -e "$d/clone/.git/rebase-apply" ] ||
            fail "leg 1/$ex: a rebase was started"
        [ "$(git -C "$d/clone" rev-parse origin/source)" = "$src_before" ] ||
            fail "leg 1/$ex: origin/source was rewritten"
        assert_no_bead_mutation "leg 1/$ex"
    done
}

# Leg 1b -- stranded temp fails closed at the skip-arm checkout.
# Executable witness of the exit-checked skip-arm materialization: nothing is
# created, nothing is deleted, and the stale branch is left exactly as found.
# Red on base: the bare checkout fails silently, the unguarded rebase then runs
# against the quiescent detached HEAD and exits 0 with no STOP wording.
leg1b() {
    local d="$tmp/leg1b" stale head_before
    fixture_ex1 "$d"
    stale=$(git -C "$d/clone" rev-parse origin/main)
    git -C "$d/clone" branch temp "$stale"
    git -C "$d/clone" checkout --quiet --detach origin/main
    head_before=$(git -C "$d/clone" rev-parse HEAD)
    run_fence "$d/clone" "$tmp/leg1b.out"
    assert_rc_nonzero "leg 1b: a stranded temp must fail closed"
    assert_contains "leg 1b" "cannot materialize temp at origin/"
    assert_not_contains "leg 1b" "SKIP-REBASE"
    assert_log_has "leg 1b" "gc runtime drain-ack"
    assert_no_bead_mutation "leg 1b"
    [ "$(git -C "$d/clone" rev-parse temp)" = "$stale" ] ||
        fail "leg 1b: the stranded temp branch was moved"
    if git -C "$d/clone" rev-parse --verify --quiet temp2 >/dev/null 2>&1; then
        fail "leg 1b: a temp2 branch was created"
    fi
    [ "$(git -C "$d/clone" rev-parse HEAD)" = "$head_before" ] ||
        fail "leg 1b: HEAD moved"
    [ "$(git -C "$d/clone" rev-parse --abbrev-ref HEAD)" = "HEAD" ] ||
        fail "leg 1b: HEAD is no longer detached (branch switch)"
    return 0
}

# Leg 1c -- stranded temp fails closed at the DIVERGED-arm checkout.
# Leg 1b's twin on the other case arm, and the more dangerous one: here the
# unchecked failure is followed by a rebase, so the block rewrites a branch it
# never materialized.  The fixture is the measured lease-failure state, not a
# synthetic one -- `temp` exists at the sha `mr` pushed and is still CHECKED OUT
# (`mr` step 1 does `git checkout temp`), and another actor has since moved
# origin/source, which is what made the lease fail in the first place.
# Red on base: the bare checkout fails, HEAD is still the stale `temp`, so
# `git rebase origin/$TARGET` rewrites that branch and the fence exits 0 with no
# STOP -- merge-push then force-pushes the rewritten stale branch over source.
leg1c() {
    local d="$tmp/leg1c" stale moved
    fixture_ex3a "$d"
    stale=$(git -C "$d/clone" rev-parse origin/source)
    git -C "$d/clone" branch temp "$stale"
    git -C "$d/clone" checkout --quiet temp
    # The lease-failure trigger: origin/source moves after temp was materialized.
    git -C "$d/build" checkout --quiet source
    printf 'another actor\n' >"$d/build/other"
    git -C "$d/build" add other
    git -C "$d/build" commit --quiet -m "another actor advances source"
    git -C "$d/build" push --quiet origin source
    moved=$(git -C "$d/build" rev-parse source)
    [ "$moved" != "$stale" ] || fail "leg 1c fixture: origin/source did not move"
    run_fence "$d/clone" "$tmp/leg1c.out"
    assert_rc_nonzero "leg 1c: a stranded temp must fail closed on the diverged arm"
    assert_contains "leg 1c" "cannot materialize temp at origin/"
    assert_contains "leg 1c" "for the rebase path"
    assert_not_contains "leg 1c" "SKIP-REBASE"
    assert_log_has "leg 1c" "gc runtime drain-ack"
    assert_no_bead_mutation "leg 1c"
    # The whole point: the stale branch is not rebased, and the commit the other
    # actor pushed is still reachable from origin/source.
    [ "$(git -C "$d/clone" rev-parse temp)" = "$stale" ] ||
        fail "leg 1c: the stranded temp branch was rebased (it must be left exactly as found)"
    [ "$(git -C "$d/clone" rev-parse --abbrev-ref HEAD)" = "temp" ] ||
        fail "leg 1c: HEAD left the stranded temp branch"
    [ ! -e "$d/clone/.git/rebase-merge" ] && [ ! -e "$d/clone/.git/rebase-apply" ] ||
        fail "leg 1c: a rebase was started on the stranded temp"
    [ "$(git -C "$d/clone" rev-parse origin/source)" = "$moved" ] ||
        fail "leg 1c: origin/source no longer carries the other actor's commit"
    return 0
}

# Leg 2 -- diverged clean rebases as today (EX-3a; AC-374-05).  Green control on
# both trees.  Merge count is deliberately not asserted: today's diverged
# flattening semantics are preserved here, not re-litigated.
leg2() {
    local d="$tmp/leg2"
    fixture_ex3a "$d"
    run_fence "$d/clone" "$tmp/leg2.out"
    assert_rc_zero "leg 2: a clean divergence must rebase as today"
    assert_not_contains "leg 2" "SKIP-REBASE"
    [ "$(git -C "$d/clone" rev-parse temp)" != "$(git -C "$d/clone" rev-parse origin/source)" ] ||
        fail "leg 2: temp was not rebased"
    git -C "$d/clone" merge-base --is-ancestor origin/main temp ||
        fail "leg 2: origin/main is not an ancestor of the rebased temp"
    assert_no_bead_mutation "leg 2"
}

# Leg 3 -- diverged conflicting keeps the conflict path (EX-3b; AC-374-05).
# Green control on both trees.  Rejection belongs to the prose tail, so the
# block itself must not mutate anything.
leg3() {
    local d="$tmp/leg3"
    fixture_ex3b "$d"
    run_fence "$d/clone" "$tmp/leg3.out"
    # Scoped rc carve-out: git promises only "non-zero" on a rebase conflict.
    # The 1 is measured (git 2.43; re-confirm on the CI git at fix time) and is
    # the very discriminator the production step's prose keys on.
    [ "$FENCE_RC" -eq 1 ] ||
        fail "leg 3: expected the rebase-conflict rc 1, got $FENCE_RC"
    assert_not_contains "leg 3" "SKIP-REBASE"
    [ -e "$d/clone/.git/rebase-merge" ] || [ -e "$d/clone/.git/rebase-apply" ] ||
        fail "leg 3: no rebase is in progress"
    assert_no_bead_mutation "leg 3"
    git -C "$d/clone" rebase --abort
}

# Leg 4 -- fetch failure stops before the probe (AC-374-01, stale-ref trap).
# The clone's tracking refs are left stale at the fork point while the true
# origin/main has moved past it, so a probe read off stale refs would wrongly
# skip.  Red on base: the block proceeds on those stale refs.
leg4() {
    local d="$tmp/leg4"
    fixture_ex1 "$d"
    git -C "$d/build" checkout --quiet main
    printf 'advanced\n' >"$d/build/m"
    git -C "$d/build" add m
    git -C "$d/build" commit --quiet -m "advance main past the fork"
    git -C "$d/build" push --quiet origin main
    git -C "$d/clone" remote set-url origin "$d/does-not-exist.git"
    run_fence "$d/clone" "$tmp/leg4.out"
    assert_rc_nonzero "leg 4: a failed tracking fetch must stop before the probe"
    assert_contains "leg 4" "tracking refs failed"
    assert_not_contains "leg 4" "SKIP-REBASE"
    assert_no_temp "$d/clone" "leg 4: the stop must precede the checkout"
    assert_log_has "leg 4" "gc runtime drain-ack"
    assert_no_bead_mutation "leg 4"
    # Restore the origin: the decision must now come from fresh refs, which
    # means the rc=1 rebase path and never a skip.
    git -C "$d/clone" remote set-url origin "$d/origin.git"
    run_fence "$d/clone" "$tmp/leg4-restored.out"
    assert_not_contains "leg 4 (restored)" "SKIP-REBASE"
    git -C "$d/clone" rev-parse --verify --quiet temp >/dev/null 2>&1 ||
        fail "leg 4 (restored): the rebase path did not materialize temp"
    if [ -e "$d/clone/.git/rebase-merge" ] || [ -e "$d/clone/.git/rebase-apply" ]; then
        git -C "$d/clone" rebase --abort
    fi
    return 0
}

# Leg 5 -- missing source branch (AC-374-01).  The explicit refspec fetch is
# what fails, before any probe.  Red on base: the failure surfaces later at the
# checkout with no STOP routing.
leg5() {
    local d="$tmp/leg5"
    fixture_ex1 "$d"
    git -C "$d/origin.git" update-ref -d refs/heads/source
    # Prune the local tracking ref too, so a stale origin/source cannot mask
    # the deletion.
    git -C "$d/clone" fetch --prune origin >/dev/null 2>&1 || true
    run_fence "$d/clone" "$tmp/leg5.out"
    # rc discipline: assert only non-zero.  (git 2.43 exits 128 here; that is an
    # observation, and it must never harden into a third exact-code carve-out.)
    assert_rc_nonzero "leg 5: a missing source branch must fail at the fetch"
    assert_contains "leg 5" "tracking refs failed"
    assert_not_contains "leg 5" "SKIP-REBASE"
    assert_no_temp "$d/clone" "leg 5: no temp may be created after a failed fetch"
    assert_no_bead_mutation "leg 5"
}

# Leg 6 -- probe error fails closed (AC-374-03).  Probe-first means there is
# nothing to clean up.  Red on base: no probe exists, so the STOP never fires.
leg6() {
    local d="$tmp/leg6"
    fixture_ex1 "$d"
    write_git_shim
    run_fence "$d/clone" "$tmp/leg6.out" "$GITSHIM"
    assert_rc_nonzero "leg 6: a probe error must fail closed"
    # Scoped carve-out: 128 is the shim's own deterministic exit, not a
    # version-variable git code.
    assert_contains "leg 6" "errored (status 128)"
    assert_not_contains "leg 6" "SKIP-REBASE"
    assert_not_contains "leg 6" "Successfully rebased"
    assert_no_temp "$d/clone" "leg 6: probe-first means no temp is created"
    assert_log_has "leg 6" "gc runtime drain-ack"
    assert_no_bead_mutation "leg 6"
}

count_lit() {
    local lit="$1" want="$2" what="$3" got
    got=$(grep -F -o -- "$lit" "$BLOCK" | wc -l | tr -d '[:space:]') || true
    [ "${got:-0}" -eq "$want" ] ||
        fail "leg 7: expected $what exactly $want time(s) in the lifted block, found ${got:-0}"
}

line_of() {
    local n
    n=$(grep -n -F -m1 -- "$1" "$BLOCK" | cut -d: -f1) || true
    [ -n "$n" ] || fail "leg 7: literal absent from the lifted block: $1"
    printf '%s' "$n"
}

order_lt() {
    [ "$1" -lt "$2" ] || fail "leg 7: ordering violated -- $3"
}

# Leg 7 -- structural backstop and ordering (static, on the lifted text).
# Catches silent mangling on shapes the fixtures do not reach, and pins the
# composition order textually.
leg7() {
    local probe sentinel collective
    local l_prune l_showref l_gfetch l_probe l_capture l_case l_rebase
    probe='git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"'
    sentinel='git checkout -b temp origin/$BRANCH'
    collective='cannot evaluate rebase ancestry'

    # Each count has a distinct duty.  The probe count guards lift_block's
    # concatenate-all-matching-fences semantics against a future second fence
    # that itself contains the probe.  The sentinel count closes the remaining
    # gap: a probe-less sentinel-bearing fence would concatenate silently past
    # the probe check, and necessarily adds a third sentinel occurrence.  The
    # collective-sentence count is the executable witness of the anti-fix rule
    # -- rewording the checkout STOP to append that sentence gains a third site
    # and reds here, while every per-arm literal would stay green.
    count_lit "$probe" 1 "the ancestry probe"
    count_lit "$sentinel" 2 "the lift sentinel"
    count_lit "$collective" 2 "the collective STOP sentence"

    # Both materializing arms are exit-checked, and the count is what makes that
    # measurable: a per-arm presence grep alone stays green when one arm's check
    # is dropped, because the other arm still carries the shared literal.  The
    # two arm-naming suffixes below then say WHICH arm regressed -- and they are
    # why the count cannot be satisfied by wording both STOPs identically.
    count_lit 'cannot materialize temp at origin/' 2 "the exit-checked materialization STOP"
    grep -Fq -- 'for the skip path' "$BLOCK" ||
        fail "leg 7: the skip arm's checkout STOP no longer names its arm"
    grep -Fq -- 'for the rebase path' "$BLOCK" ||
        fail "leg 7: the diverged (rc=1) arm's checkout STOP is missing; an unchecked checkout there rebases a stranded temp"

    # Both explicit refspecs, the capture, and every per-arm STOP literal, so
    # that deleting any single fail-closed arm goes red statically here and not
    # only behaviorally in legs 1b/4/6.
    grep -Fq -- '"+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"' "$BLOCK" ||
        fail "leg 7: the explicit \$BRANCH refspec is missing"
    grep -Fq -- '"+refs/heads/$TARGET:refs/remotes/origin/$TARGET"' "$BLOCK" ||
        fail "leg 7: the explicit \$TARGET refspec is missing"
    grep -Fq -- 'ANCESTOR_RC=$?' "$BLOCK" ||
        fail "leg 7: the probe capture ANCESTOR_RC=\$? is missing"
    grep -Fq -- 'tracking refs failed' "$BLOCK" ||
        fail "leg 7: the fetch-failure STOP literal is missing"
    grep -Fq -- 'errored (status ' "$BLOCK" ||
        fail "leg 7: the probe-error STOP literal is missing"
    # Retained beside the count above for its message: this one says the shared
    # wording vanished outright, the count says one of the two arms lost it.
    grep -Fq -- 'cannot materialize temp at origin/' "$BLOCK" ||
        fail "leg 7: the checkout STOP literal is missing from both materializing arms"

    l_prune=$(line_of 'git fetch --prune origin')
    l_showref=$(line_of 'git show-ref --verify --quiet "refs/remotes/origin/$TARGET"')
    l_gfetch=$(line_of 'git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"')
    l_probe=$(line_of "$probe")
    l_capture=$(line_of 'ANCESTOR_RC=$?')
    l_case=$(line_of 'case "$ANCESTOR_RC" in')
    l_rebase=$(line_of 'git rebase origin/$TARGET')

    [ "$l_prune" -eq 1 ] ||
        fail "leg 7: the prune fetch must be line 1 of the lifted text (found line $l_prune)"
    order_lt "$l_prune" "$l_showref" "the prune fetch must precede the halt's show-ref"
    order_lt "$l_showref" "$l_gfetch" "the halt must precede the guard fetch"
    order_lt "$l_gfetch" "$l_probe" "the guard fetch must precede the probe"
    [ "$l_capture" -eq $((l_probe + 1)) ] ||
        fail "leg 7: the capture must immediately follow the probe (probe $l_probe, capture $l_capture)"
    order_lt "$l_capture" "$l_case" "the capture must precede the case"
    order_lt "$l_probe" "$l_rebase" "git rebase must occur only after the probe"

    bash -n "$BLOCK" || fail "leg 7: the lifted block does not parse"
}

# Leg 8 -- halt composition (AC-374-06).  Green on base and fix: this leg pins
# that the guard neither replaced nor reordered the pre-existing halt.
leg8() {
    local d="$tmp/leg8"
    fixture_ex1 "$d"
    git -C "$d/origin.git" update-ref -d refs/heads/main
    run_fence "$d/clone" "$tmp/leg8.out"
    assert_rc_nonzero "leg 8: the halt exits non-zero"
    # The halt's own `STOP: <reason>` echo is expected.  What must not appear is
    # any of the guard's three STOP arms, or a probe result.
    assert_contains "leg 8" "STOP: Target branch"
    assert_not_contains "leg 8" "tracking refs failed"
    assert_not_contains "leg 8" "errored (status "
    assert_not_contains "leg 8" "cannot materialize temp at origin/"
    assert_not_contains "leg 8" "SKIP-REBASE"
    # The park shape, read off the bead-mutation oracle.
    assert_log_has "leg 8" "gc bd update TESTBEAD"
    assert_log_has "leg 8" "--assignee="
    assert_log_has "leg 8" "merge_result=blocked"
    assert_log_has "leg 8" "gc.routed_to=human"
    assert_log_has "leg 8" "halt_reason=target_branch_missing"
    assert_log_has "leg 8" "gc mail send mayor/"
    assert_log_has "leg 8" "gc bd mol wisp mol-refinery-patrol"
    assert_log_has "leg 8" "gc bd update wisp-next"
    assert_log_has "leg 8" "gc bd mol burn wisp-current"
    assert_log_has "leg 8" "gc runtime drain-ack"
    assert_no_temp "$d/clone" "leg 8: the halt must not create temp"
}

# Leg 9 -- the `mr` lease-failure carve-out (static, on the formula text).
# The skip arm makes `temp` a non-rebase product: it is `origin/$BRANCH` with its
# merges intact.  `mr` is the only downstream path that rewrites `$BRANCH`, and
# its lease-failure recovery used to say "rebase your temp branch again, and
# retry with --force-with-lease" -- on a skipped `temp` that is exactly the
# flattening this guard exists to prevent, force-pushed over the source branch.
# The fix is prose in a different step from the decision it has to agree with,
# so pin it the way leg 7 pins the fence: the two halves drifted apart once
# already.  This leg is the executable counterpart of that contract.
leg9() {
    local mr="$tmp/mr-section.md" off_clear off_probe off_rematerialize

    # Prefix marker, matching the slice in gastown/tests/test_gastown_pack_assets.sh:
    # the heading closes its bold run after the colon, so anchoring on `"mr"**`
    # would match nothing.
    awk 'index($0, "**If MERGE_STRATEGY = \"mr\"") { on = 1 } on' "$FORMULA" >"$mr"
    [ -s "$mr" ] || fail "leg 9: could not slice the mr strategy section out of $FORMULA"

    # The retired instruction must be gone, not merely supplemented: left in
    # place it is still the literal thing an agent follows on lease failure.
    ! grep -Fq -- 'rebase your temp branch again' "$mr" ||
        fail "leg 9: the mr lease-failure recovery still instructs an in-place rebase of temp; on the skip path that flattens the source branch and force-pushes the result"

    # The heading is part of the contract: on the skip path `temp` was never
    # rebased, so a heading promising a rebased branch is false.
    grep -Fq -- '**1. Push the branch back to origin:**' "$mr" ||
        fail "leg 9: the mr push heading must not claim the branch is rebased -- the skip path pushes an unrebased temp"

    # The recovery has to route back through the ancestry decision rather than
    # describe a push-level fixup.
    grep -Fq -- 're-enter the `rebase` step' "$mr" ||
        fail "leg 9: the mr lease-failure recovery must re-enter the rebase step's ancestry decision"
    grep -Fq -- 'git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"' "$mr" ||
        fail "leg 9: the mr lease-failure recovery must re-probe ancestry, direction-locked like the decision itself"
    # Single-line literals throughout: `grep -F` treats an embedded newline as a
    # pattern separator, so a two-line pattern would quietly become an OR.
    grep -Fq -- 'rc=0 re-materializes `temp` at the freshly fetched `origin/$BRANCH`, unrebased' "$mr" ||
        fail "leg 9: the mr recovery must keep an already-based temp unrebased (probe rc=0)"
    grep -Fq -- 'any other status STOPs without mutating bead state' "$mr" ||
        fail "leg 9: the mr recovery must fail closed on a probe error, like the decision's third arm"

    # "Re-materialize" is a verb, not a command.  Bind it: the recovery names the
    # exact pair an agent runs, and leg 10 executes that pair out of the formula.
    grep -Fq -- 'git checkout --detach "origin/$TARGET" && git branch -D temp' "$mr" ||
        fail "leg 9: the mr lease-failure recovery must name the concrete command that clears temp, not an unbound \"re-materialize\""
    grep -Fq -- 'git checkout -B temp' "$mr" ||
        fail "leg 9: the mr recovery must warn off re-materializing in place with git checkout -B temp, which keeps the branch alive across the probe"

    # The provenance line is published to human reviewers.  On the skip path temp
    # was never rebased, so it may not claim it was; both paths do leave
    # origin/$TARGET an ancestor of temp, which is what "Based on" asserts.
    grep -Fq -- "printf -- '- Based on \`%s\` via Gastown Refinery." "$mr" ||
        fail "leg 9: the mr PR body must not advertise a rebase that the skip path never ran"
    ! grep -Fq -- "printf -- '- Rebased on \`%s\` via Gastown Refinery." "$mr" ||
        fail "leg 9: the mr PR body still publishes '- Rebased on ...' provenance, false on the skip path"
    grep -Fq -- 'a step re-entry' "$mr" ||
        fail "leg 9: the mr recovery re-materializes temp, so it must say the retry re-enters the step and re-runs run-tests rather than reading as a push-level fixup"
    grep -Fq -- 'run-tests` runs again' "$mr" ||
        fail "leg 9: the mr recovery must state that run-tests re-runs on the re-materialized temp"

    # Ordering is the load-bearing half, and it is the DECISION's order that wins:
    # the rebase step probes before any branch exists ("so every STOP leaves the
    # worktree clean"), and legs 4/6 assert it.  An earlier revision of this
    # recovery mandated the inverse -- re-materialize, then probe -- which left a
    # mutated temp behind a probe error and put the two halves of one contract in
    # contradiction.  So: clear temp FIRST, then the probe, and only then the
    # re-materialization the arms perform.  Byte offsets, so a reflow of the
    # paragraph cannot break the check.
    off_clear=$(grep -Fob -m1 -- 'git checkout --detach "origin/$TARGET" && git branch -D temp' "$mr" | cut -d: -f1) || true
    [ -n "$off_clear" ] ||
        fail "leg 9: the mr recovery must clear temp with a concrete command before re-entering the step"
    off_probe=$(grep -Fob -m1 -- 'git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"' "$mr" | cut -d: -f1) || true
    [ -n "$off_probe" ] || fail "leg 9: the re-probe literal vanished between checks"
    off_rematerialize=$(grep -Fob -m1 -- 'rc=0 re-materializes `temp` at the freshly fetched `origin/$BRANCH`, unrebased' "$mr" | cut -d: -f1) || true
    [ -n "$off_rematerialize" ] || fail "leg 9: the rc=0 re-materialization literal vanished between checks"
    [ "$off_clear" -lt "$off_probe" ] ||
        fail "leg 9: the mr recovery must clear temp before re-probing (clear at byte $off_clear, probe at byte $off_probe)"
    [ "$off_probe" -lt "$off_rematerialize" ] ||
        fail "leg 9: the mr recovery must probe before re-materializing temp, matching the rebase step's probe-first rationale (probe at byte $off_probe, re-materialize at byte $off_rematerialize)"
}

# Leg 10 -- the `mr` lease-failure recovery, EXECUTED rather than pinned.
# Leg 9 proves the recovery says the right thing; this leg proves it works.  The
# commands are LIFTED out of the formula for the same reason the rebase fence is:
# a transcribed copy drifts from the recipe that actually runs, and "re-materialize
# `temp`" already shipped once as a verb no command in the step could perform.
#
# The lift happens HERE rather than at the top level on purpose: the recovery
# fence does not exist on an unguarded tree, and a top-level lift would abort the
# whole run with an extraction error instead of producing the per-leg red
# enumeration this file's red control depends on.
#
# Both topologies, because the recovery is reached from either: the skip path is
# where an in-place rebase would flatten the merges (the damage the paragraph
# exists to prevent), the diverged path is where it would rewrite a stale branch.
leg10() {
    local ex d recovery first_temp moved
    recovery="$tmp/mr-recovery.sh"
    lift_block 'git checkout --detach "origin/$TARGET" && git branch -D temp' "$recovery"

    for ex in ex1 ex3a; do
        d="$tmp/leg10-$ex"
        "fixture_$ex" "$d"

        # Pass 1 is the state `mr` pushes from: the step materialized temp and
        # left HEAD on it, and `mr` step 1 re-checks it out.
        run_fence "$d/clone" "$tmp/leg10-$ex-pass1.out"
        assert_rc_zero "leg 10/$ex: the first pass must succeed"
        first_temp=$(git -C "$d/clone" rev-parse temp)
        [ "$(git -C "$d/clone" rev-parse --abbrev-ref HEAD)" = "temp" ] ||
            fail "leg 10/$ex: the step did not leave HEAD on temp, so the fixture is not the mr push state"

        # The lease failure: origin/source moves under the tree that was tested.
        git -C "$d/build" checkout --quiet source
        printf 'another actor\n' >"$d/build/other"
        git -C "$d/build" add other
        git -C "$d/build" commit --quiet -m "another actor advances source"
        git -C "$d/build" push --quiet origin source
        moved=$(git -C "$d/build" rev-parse source)

        # The recovery, exactly as the formula states it.
        run_fence "$d/clone" "$tmp/leg10-$ex-recovery.out" "" "$recovery"
        assert_rc_zero "leg 10/$ex: the recovery commands must succeed as written"
        assert_no_temp "$d/clone" "leg 10/$ex: the recovery must delete the tested temp"
        [ "$(git -C "$d/clone" rev-parse --abbrev-ref HEAD)" = "HEAD" ] ||
            fail "leg 10/$ex: the recovery must leave HEAD detached rather than on a branch"

        # Re-entry.  This is what the unbound prose could not do: with temp still
        # alive, the exit-checked checkout STOPs on both arms, so a recovery that
        # only says "re-materialize" dead-ends here instead of deciding.
        run_fence "$d/clone" "$tmp/leg10-$ex-pass2.out"
        assert_rc_zero "leg 10/$ex: the re-entry must reach a decision, not a STOP"
        assert_not_contains "leg 10/$ex (re-entry)" "cannot materialize temp at origin/"
        assert_no_bead_mutation "leg 10/$ex"
        [ "$(git -C "$d/clone" rev-parse origin/source)" = "$moved" ] ||
            fail "leg 10/$ex: the re-entry did not pick up the moved source branch"
        [ "$(git -C "$d/clone" rev-parse temp)" != "$first_temp" ] ||
            fail "leg 10/$ex: temp is still the tree that was already pushed, so the re-entry decided on stale refs"
        git -C "$d/clone" merge-base --is-ancestor origin/main temp ||
            fail "leg 10/$ex: origin/main is not an ancestor of the re-materialized temp, so merge-push's --ff-only would refuse it"

        case "$ex" in
            ex1)
                # Already-based across the move: the recovery must land back on
                # the skip arm, with the merges the in-place rebase would drop.
                assert_contains "leg 10/$ex (re-entry)" "SKIP-REBASE:"
                [ "$(git -C "$d/clone" rev-parse temp)" = "$moved" ] ||
                    fail "leg 10/$ex: the skip arm must re-materialize temp at the moved origin/source"
                [ "$(git -C "$d/clone" rev-list --count --merges temp)" -eq 2 ] ||
                    fail "leg 10/$ex: the recovered temp lost its merge topology"
                ;;
            ex3a)
                # Still diverged: the recovery must land back on the rebase arm.
                assert_not_contains "leg 10/$ex (re-entry)" "SKIP-REBASE"
                [ "$(git -C "$d/clone" rev-parse temp)" != "$moved" ] ||
                    fail "leg 10/$ex: the diverged arm did not rebase the re-materialized temp"
                ;;
        esac
    done
    return 0
}

# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

LEG_NAMES=()
LEG_RESULTS=()

run_leg() {
    local name="$1" fn="$2"
    LEG_NAMES+=("$name")
    if ( "$fn" ); then
        LEG_RESULTS+=("PASS")
        echo "ok   leg $name"
    else
        LEG_RESULTS+=("FAIL")
        echo "FAIL leg $name" >&2
    fi
}

write_gc_stub
lift_block 'git checkout -b temp origin/$BRANCH' "$BLOCK"

run_leg "1"  leg1
run_leg "1b" leg1b
run_leg "1c" leg1c
run_leg "2"  leg2
run_leg "3"  leg3
run_leg "4"  leg4
run_leg "5"  leg5
run_leg "6"  leg6
run_leg "7"  leg7
run_leg "8"  leg8
run_leg "9"  leg9
run_leg "10" leg10

echo "--- leg summary (formula: $FORMULA) ---"
failed=0
for i in "${!LEG_NAMES[@]}"; do
    printf '%-4s leg %s\n' "${LEG_RESULTS[$i]}" "${LEG_NAMES[$i]}"
    [ "${LEG_RESULTS[$i]}" = "PASS" ] || failed=1
done

if [ "$failed" -ne 0 ]; then
    echo "FAIL: mol-refinery-patrol rebase guard" >&2
    exit 1
fi

echo "PASS: mol-refinery-patrol rebase guard (${#LEG_NAMES[@]} legs)"
