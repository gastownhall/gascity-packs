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

# Issue #615: a failed default-branch fetch during worktree creation is
# silent, so a new slot is cut from a stale local default with no trace.
# Point origin at a path that no longer exists (simulating a remote outage
# or credential-helper gap) and confirm the start still succeeds -- the
# fetch must stay non-fatal -- but stderr now names the failed fetch and
# the local ref the slot was cut from.
test_create_warns_on_stderr_when_default_branch_fetch_fails() {
    local base="$1"
    local rig="$base/rig" wt="$base/wt-fetchfail"

    # Break origin after the clone so refs/remotes/origin/HEAD is already
    # configured locally (as it would be for an existing rig), but any
    # fetch against it fails exactly like a remote outage or credential
    # gap would.
    git_c -C "$rig" remote set-url origin "$base/missing-upstream.git"

    local stderr_file
    stderr_file="$base/stderr-fetchfail.txt"

    sh "$SCRIPT" "$rig" "$wt" fetchfail 2>"$stderr_file" ||
        fail "worktree-setup should still succeed when the default-branch fetch fails"

    [ -e "$wt/.git" ] ||
        fail "worktree should have been created at $wt despite the failed fetch"

    grep -q "fetch of origin/main failed" "$stderr_file" ||
        fail "stderr should name the failed fetch of origin/main; got: $(cat "$stderr_file")"
    grep -q "refs/remotes/origin/main" "$stderr_file" ||
        fail "stderr should name the local ref the slot was cut from; got: $(cat "$stderr_file")"
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
new_upstream_and_rig "$tmp"

test_create_warns_on_stderr_when_default_branch_fetch_fails "$tmp"

echo "worktree-setup fetch-warning tests passed"
