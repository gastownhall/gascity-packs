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

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
new_upstream_and_rig "$tmp"

test_sync_pulls_when_branch_lacks_origin_tracking "$tmp"
test_sync_still_works_with_configured_tracking "$tmp"

echo "worktree-setup sync tests passed"
