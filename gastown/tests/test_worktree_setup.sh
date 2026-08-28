#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

test_agent_pre_start_quotes_rendered_paths() {
    local expected agent
    expected='pre_start = ["\"{{.ConfigDir}}/assets/scripts/worktree-setup.sh\" \"{{.RigRoot}}\" \"{{.WorkDir}}\" \"{{.AgentBase}}\" --sync"]'

    for agent in polecat refinery; do
        grep -Fx "$expected" "$ROOT/gastown/agents/$agent/agent.toml" >/dev/null ||
            fail "$agent pre_start does not quote rendered paths"
    done
}

test_worktree_setup_supports_paths_with_spaces() {
    local tmp bare rig target branch target_root expected_root
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    bare="$tmp/origin repo.git"
    rig="$tmp/rig repo"
    target="$tmp/city root/.gc/worktrees/Wayfinder/polecats/gastown.nux"

    git init --bare "$bare" >/dev/null
    git -C "$bare" symbolic-ref HEAD refs/heads/main
    git init -b main "$rig" >/dev/null
    git -C "$rig" config user.name "Gas City Test"
    git -C "$rig" config user.email "gas-city-test@example.invalid"
    printf 'test\n' >"$rig/README.md"
    git -C "$rig" add README.md
    git -C "$rig" commit -m init >/dev/null
    git -C "$rig" remote add origin "$bare"
    git -C "$rig" push -u origin main >/dev/null
    git -C "$rig" remote set-head origin main

    "$ROOT/gastown/assets/scripts/worktree-setup.sh" \
        "$rig" "$target" gastown.nux --sync

    [[ -f "$target/.git" ]] || fail "linked worktree was not created at the requested path"
    target_root=$(git -C "$target" rev-parse --show-toplevel)
    expected_root=$(cd "$target" && pwd -P)
    [[ "$target_root" == "$expected_root" ]] || fail "unexpected worktree root: $target_root"
    branch=$(git -C "$target" branch --show-current)
    [[ "$branch" == gc-gastown.nux-* ]] || fail "unexpected worktree branch: $branch"
}

test_agent_pre_start_quotes_rendered_paths
test_worktree_setup_supports_paths_with_spaces

echo "PASS: Gastown worktree setup tests"
