#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPT="$ROOT/gastown/assets/scripts/worktree-setup.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

git_c() {
    git -c user.email=a@a.com -c user.name=a "$@"
}

# new_upstream_and_rig — a bare "upstream" repo plus a rig clone of it, with
# one commit on main and origin/HEAD already configured (the common case:
# the rig was cloned from an origin that already existed).
new_upstream_and_rig() {
    local base="$1"
    git_c init -q --bare -b main "$base/upstream.git"
    git_c init -q -b main "$base/seed"
    (cd "$base/seed" && git_c commit -q --allow-empty -m init \
        && git_c remote add origin "$base/upstream.git" \
        && git_c push -q origin main)
    git_c clone -q "$base/upstream.git" "$base/rig"
}

# stable_branch — the branch worktree-setup.sh gives the worktree at <wt> for
# <agent> (its branch_name()). --sync keeps exactly this branch current with
# origin/HEAD, so the tests check it out to exercise the sync of the
# worktree's own branch.
stable_branch() {
    local rig="$1" wt="$2" agent="$3" hash
    hash=$(printf '%s' "$wt" | git_c -C "$rig" hash-object --stdin | cut -c1-12)
    printf 'gc-%s-%s' "$agent" "$hash"
}

test_sync_pulls_when_branch_lacks_origin_tracking() {
    local base="$1"
    local rig="$base/rig" wt="$base/wt-notrack"
    local branch
    branch=$(stable_branch "$rig" "$wt" notrack)

    # Build #299's precondition by hand, not through the script: the branch
    # the no-start-point fallback creates (the path taken when origin/HEAD
    # isn't configured at creation time -- e.g. a rig set up locally and
    # given a remote afterwards) has no branch.<name>.remote/.merge config.
    # --no-track pins that state even when the developer's
    # branch.autoSetupMerge (always, inherit) would track the start point.
    git_c -C "$rig" worktree add -q --no-track "$wt" -b "$branch"
    if git_c -C "$wt" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        fail "test setup bug: $branch must have no upstream tracking configured"
    fi

    # origin's default branch has since moved ahead of the worktree -- the
    # exact "we hit this in production" scenario from the issue, where a
    # frozen worktree fell 31 commits behind main.
    (cd "$base" && git_c clone -q "$base/upstream.git" advance \
        && cd advance \
        && git_c commit -q --allow-empty -m "advanced upstream" \
        && git_c push -q origin main)
    local advanced_sha
    advanced_sha=$(git_c -C "$base/advance" rev-parse main)

    sh "$SCRIPT" "$rig" "$wt" notrack --sync

    local wt_sha
    wt_sha=$(git_c -C "$wt" rev-parse HEAD)
    [ "$wt_sha" = "$advanced_sha" ] ||
        fail "sync should have pulled the advanced commit despite missing tracking config; want $advanced_sha got $wt_sha"
    # Still on its own branch: stable_branch() matched the script's name, so
    # this exercised the fast-forward rather than a fresh branch at origin/HEAD.
    [ "$(git_c -C "$wt" branch --show-current)" = "$branch" ] ||
        fail "sync should have kept the worktree on $branch"
}

test_sync_still_works_with_configured_tracking() {
    local base="$1"
    local rig="$base/rig" wt="$base/wt-tracked"
    local branch
    branch=$(stable_branch "$rig" "$wt" tracked)

    # The already-working case: a branch created from an explicit
    # origin-tracking start point (the DEFAULT_REF path this script's own
    # creation logic normally takes) gets real tracking config under git's
    # default branch.autoSetupMerge; --track pins it even when the
    # developer's setting (false, simple) would not. sync_worktree never
    # reads tracking config, so this guards that configured tracking is
    # harmless to the sync rather than exercising a separate path.
    git_c -C "$rig" worktree add -q --track "$wt" -b "$branch" refs/remotes/origin/main
    if ! git_c -C "$wt" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        fail "test setup bug: $branch must have upstream tracking configured"
    fi

    (cd "$base" && git_c clone -q "$base/upstream.git" advance2 \
        && cd advance2 \
        && git_c commit -q --allow-empty -m "advanced tracked" \
        && git_c push -q origin main)
    local advanced_sha
    advanced_sha=$(git_c -C "$base/advance2" rev-parse main)

    sh "$SCRIPT" "$rig" "$wt" tracked --sync

    local wt_sha
    wt_sha=$(git_c -C "$wt" rev-parse HEAD)
    [ "$wt_sha" = "$advanced_sha" ] ||
        fail "sync should still pull for a normally-tracked branch; want $advanced_sha got $wt_sha"
    [ "$(git_c -C "$wt" branch --show-current)" = "$branch" ] ||
        fail "sync should have kept the worktree on $branch"
}

# Dirty work must be available to the provider after pre_start, including a
# marker-only tree. Never "recover" it by stashing, discarding, or hiding it.
test_dirty_worktree_resumes_unchanged() {
    local base="$1" kind="$2"
    local rig="$base/rig" wt="$base/wt" branch before_head excludes attempt
    new_upstream_and_rig "$base"
    printf 'original\n' > "$rig/tracked.txt"
    git_c -C "$rig" add tracked.txt
    git_c -C "$rig" commit -qm 'tracked fixture'
    git_c -C "$rig" push -q origin main
    sh "$SCRIPT" "$rig" "$wt" recovery
    branch=$(git_c -C "$wt" branch --show-current)

    # A pre-existing stash belongs to the user, not to startup recovery.
    printf 'stashed work\n' > "$wt/tracked.txt"
    git_c -C "$wt" stash push -qm 'preserved user stash'
    case "$kind" in
        tracked)
            printf 'staged work\n' > "$wt/tracked.txt"
            git_c -C "$wt" add tracked.txt
            printf 'unstaged work\n' >> "$wt/tracked.txt"
            ;;
        untracked) printf 'untracked work\n' > "$wt/untracked.txt" ;;
        marker) printf 'active cleanup marker\n' > "$wt/.worktree-stale" ;;
        named-unpushed)
            git_c -C "$wt" checkout -qb preserved-work
            git_c -C "$wt" commit -q --allow-empty -m 'unpushed work'
            printf 'unfinished work\n' > "$wt/tracked.txt"
            ;;
        detached-unreachable)
            git_c -C "$wt" checkout -q --detach
            git_c -C "$wt" commit -q --allow-empty -m 'detached work'
            printf 'unfinished detached work\n' > "$wt/untracked.txt"
            ;;
        *) fail "unknown dirty fixture: $kind" ;;
    esac

    # A newer upstream exists; resuming dirty work must not fetch or move refs.
    git_c -C "$rig" commit -q --allow-empty -m 'new upstream'
    git_c -C "$rig" push -q origin main
    before_head=$(git_c -C "$wt" rev-parse HEAD)
    git_c -C "$wt" symbolic-ref -q HEAD > "$base/branch.before" || :
    git_c -C "$rig" for-each-ref > "$base/refs.before"
    git_c -C "$wt" stash list --format='%gd %H %gs' > "$base/stash.before"
    git_c -C "$wt" status --porcelain=v1 -z > "$base/status.before"
    git_c -C "$wt" diff --binary > "$base/work.before"
    git_c -C "$wt" diff --cached --binary > "$base/index.before"
    cp "$wt/tracked.txt" "$base/tracked.before"
    if [ -f "$wt/untracked.txt" ]; then
        cp "$wt/untracked.txt" "$base/untracked.before"
    fi
    if [ -f "$wt/.worktree-stale" ]; then
        cp "$wt/.worktree-stale" "$base/marker.before"
    fi
    excludes=$(git_c -C "$wt" rev-parse --git-path info/exclude)
    printf '\n# preserved user exclude\nuser-local-only/\n' >> "$excludes"
    cp "$excludes" "$base/exclude.before"

    # A second invocation models the restart loop; both must reach the
    # provider with the same preserved work, not just report exit status zero.
    for attempt in 1 2; do
        if sh "$SCRIPT" "$rig" "$wt" recovery --sync > "$base/sync-$attempt.log" 2>&1; then
            printf 'provider resumed\n' > "$base/provider-$attempt"
        else
            cat "$base/sync-$attempt.log" >&2
            fail "$kind pre_start blocked the provider on attempt $attempt"
        fi
        [ -s "$base/provider-$attempt" ] || fail "$kind provider did not resume"
        grep -q 'left as-is: dirty' "$base/sync-$attempt.log" ||
            fail "$kind startup must explain that sync was skipped"
        [ "$(git_c -C "$wt" rev-parse HEAD)" = "$before_head" ] || fail "$kind HEAD moved"
        git_c -C "$wt" symbolic-ref -q HEAD > "$base/branch.after" || :
        git_c -C "$rig" for-each-ref > "$base/refs.after"
        git_c -C "$wt" stash list --format='%gd %H %gs' > "$base/stash.after"
        git_c -C "$wt" status --porcelain=v1 -z > "$base/status.after"
        git_c -C "$wt" diff --binary > "$base/work.after"
        git_c -C "$wt" diff --cached --binary > "$base/index.after"
        for state in branch refs stash status work index; do
            cmp "$base/$state.before" "$base/$state.after" || fail "$kind changed $state"
        done
        cmp "$base/tracked.before" "$wt/tracked.txt" || fail "$kind changed tracked bytes"
        cmp "$base/exclude.before" "$excludes" || fail "$kind changed shared excludes"
        if [ -f "$base/untracked.before" ]; then
            cmp "$base/untracked.before" "$wt/untracked.txt" || fail "$kind changed untracked bytes"
        fi
        if [ -f "$base/marker.before" ]; then
            cmp "$base/marker.before" "$wt/.worktree-stale" || fail "$kind removed or changed marker"
        fi
    done
}

test_clean_unsafe_sync_fails_without_moving_work() {
    local base="$1" kind="$2"
    local rig="$base/rig" wt="$base/wt" before_head excludes
    new_upstream_and_rig "$base"
    sh "$SCRIPT" "$rig" "$wt" unsafe
    case "$kind" in
        stable-unpushed) git_c -C "$wt" commit -q --allow-empty -m 'unique stable work' ;;
        detached-unreachable)
            git_c -C "$wt" checkout -q --detach
            git_c -C "$wt" commit -q --allow-empty -m 'unique detached work'
            ;;
        no-origin) git_c -C "$rig" remote remove origin ;;
        failed-fetch) git_c -C "$rig" remote set-url origin "$base/missing-origin.git" ;;
        *) fail "unknown unsafe fixture: $kind" ;;
    esac
    before_head=$(git_c -C "$wt" rev-parse HEAD)
    git_c -C "$rig" for-each-ref > "$base/refs.before"
    git_c -C "$wt" symbolic-ref -q HEAD > "$base/branch.before" || :
    excludes=$(git_c -C "$wt" rev-parse --git-path info/exclude)
    cp "$excludes" "$base/exclude.before"
    if sh "$SCRIPT" "$rig" "$wt" unsafe --sync > "$base/sync.log" 2>&1; then
        fail "$kind clean worktree must retain its fail-closed sync contract"
    fi
    [ "$(git_c -C "$wt" rev-parse HEAD)" = "$before_head" ] || fail "$kind HEAD moved"
    git_c -C "$rig" for-each-ref > "$base/refs.after"
    git_c -C "$wt" symbolic-ref -q HEAD > "$base/branch.after" || :
    cmp "$base/refs.before" "$base/refs.after" || fail "$kind moved refs"
    cmp "$base/branch.before" "$base/branch.after" || fail "$kind switched branch"
    cmp "$base/exclude.before" "$excludes" || fail "$kind changed excludes"
    [ -z "$(git_c -C "$wt" status --porcelain)" ] || fail "$kind tree changed"
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
new_upstream_and_rig "$tmp"

test_sync_pulls_when_branch_lacks_origin_tracking "$tmp"
test_sync_still_works_with_configured_tracking "$tmp"

failures=0
for kind in tracked untracked marker named-unpushed detached-unreachable; do
    mkdir "$tmp/dirty-$kind"
    set +e
    (set -e; test_dirty_worktree_resumes_unchanged "$tmp/dirty-$kind" "$kind")
    result=$?
    set -e
    if [ "$result" -eq 0 ]; then
        echo "PASS: dirty $kind recovery preserves work"
    else
        failures=$((failures + 1))
    fi
done
for kind in stable-unpushed detached-unreachable no-origin failed-fetch; do
    mkdir "$tmp/unsafe-$kind"
    set +e
    (set -e; test_clean_unsafe_sync_fails_without_moving_work "$tmp/unsafe-$kind" "$kind")
    result=$?
    set -e
    if [ "$result" -eq 0 ]; then
        echo "PASS: clean $kind sync fails safely"
    else
        failures=$((failures + 1))
    fi
done
[ "$failures" -eq 0 ] || fail "$failures worktree sync cases failed"
echo "worktree-setup sync tests passed"
