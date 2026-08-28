#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

render_pre_start() {
    local agent_file config_dir rig_root work_dir agent_base line command escaped_quote quote
    agent_file=$1
    config_dir=$2
    rig_root=$3
    work_dir=$4
    agent_base=$5
    line=$(grep '^pre_start = ' "$agent_file")
    [[ "$line" == 'pre_start = ["'*'"]' ]] || fail "unsupported pre_start TOML: $line"
    command=${line:14:${#line}-16}
    escaped_quote='\"'
    quote='"'
    command=${command//"$escaped_quote"/$quote}
    command=${command//'{{.ConfigDir}}'/$config_dir}
    command=${command//'{{.RigRoot}}'/$rig_root}
    command=${command//'{{.WorkDir}}'/$work_dir}
    command=${command//'{{.AgentBase}}'/$agent_base}
    printf '%s\n' "$command"
}

test_agent_pre_start_executes_rendered_paths_with_spaces() {
    local tmp bare rig target command agent
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    bare="$tmp/origin repo.git"
    rig="$tmp/rig repo"

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

    for agent in polecat refinery; do
        target="$tmp/city root/.gc/worktrees/Wayfinder/$agent worktree"
        command=$(render_pre_start \
            "$ROOT/gastown/agents/$agent/agent.toml" \
            "$ROOT/gastown" "$rig" "$target" "gastown.$agent")
        sh -c "$command"
        [[ -f "$target/.git" ]] || fail "$agent rendered pre_start did not create its worktree"
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

test_worktree_setup_falls_back_without_origin_head() {
    local tmp rig target target_root expected_root
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    rig="$tmp/rig repo"
    target="$tmp/city root/.gc/worktrees/Wayfinder/polecats/gastown.nux"

    git init -b main "$rig" >/dev/null
    git -C "$rig" config user.name "Gas City Test"
    git -C "$rig" config user.email "gas-city-test@example.invalid"
    printf 'test\n' >"$rig/README.md"
    git -C "$rig" add README.md
    git -C "$rig" commit -m init >/dev/null

    "$ROOT/gastown/assets/scripts/worktree-setup.sh" "$rig" "$target" gastown.nux

    [[ -f "$target/.git" ]] || fail "no-origin fallback did not create a linked worktree"
    target_root=$(git -C "$target" rev-parse --show-toplevel)
    expected_root=$(cd "$target" && pwd -P)
    [[ "$target_root" == "$expected_root" ]] || fail "unexpected no-origin worktree root: $target_root"
}

test_worktree_setup_restores_staged_files_after_creation_failure() {
    local tmp rig target holder branch hash stage
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    rig="$tmp/rig repo"
    target="$tmp/city root/.gc/worktrees/Wayfinder/polecats/gastown.nux"
    holder="$tmp/existing branch holder"

    git init -b main "$rig" >/dev/null
    git -C "$rig" config user.name "Gas City Test"
    git -C "$rig" config user.email "gas-city-test@example.invalid"
    printf 'test\n' >"$rig/README.md"
    git -C "$rig" add README.md
    git -C "$rig" commit -m init >/dev/null

    hash=$(printf '%s' "$target" | git -C "$rig" hash-object --stdin | cut -c1-12)
    branch="gc-gastown.nux-$hash"
    git -C "$rig" worktree add -b "$branch" "$holder" >/dev/null

    mkdir -p "$target"
    printf 'preserve me\n' >"$target/sentinel.txt"
    printf 'preserve hidden\n' >"$target/.hidden-sentinel"

    if "$ROOT/gastown/assets/scripts/worktree-setup.sh" "$rig" "$target" gastown.nux; then
        fail "worktree creation unexpectedly succeeded with its branch checked out elsewhere"
    fi

    [[ $(cat "$target/sentinel.txt") == 'preserve me' ]] || fail "staged file was not restored"
    [[ $(cat "$target/.hidden-sentinel") == 'preserve hidden' ]] || fail "staged hidden file was not restored"
    [[ ! -e "$target/.git" ]] || fail "failed creation left partial worktree metadata"
    stage=$(find "$(dirname "$target")" -maxdepth 1 -name '.gascity-worktree-stage.*' -print -quit)
    [[ -z "$stage" ]] || fail "failed creation left staging residue: $stage"
}

tests=(
    test_agent_pre_start_executes_rendered_paths_with_spaces
    test_worktree_setup_supports_paths_with_spaces
    test_worktree_setup_falls_back_without_origin_head
    test_worktree_setup_restores_staged_files_after_creation_failure
)
ran=0
for test_name in "${tests[@]}"; do
    [[ -z "${TEST_FILTER:-}" || "$test_name" == "$TEST_FILTER" ]] || continue
    echo "RUN: $test_name"
    "$test_name"
    ran=$((ran + 1))
done
[[ "$ran" -gt 0 ]] || fail "TEST_FILTER did not match a worktree setup test: ${TEST_FILTER:-}"

echo "PASS: Gastown worktree setup tests"
