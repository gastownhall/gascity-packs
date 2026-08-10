#!/usr/bin/env bash
# Guards the wisp-resolver contract for every gastown patrol agent.
#
# Patrol wisps fall in the infrastructure visibility class, which `gc bd list`
# hides by default. A resolver without `--include-infra` returns `[]` for a
# wisp that `gc bd show` proves exists — in_progress and assigned to the very
# agent asking. Worse, it fails inside `$(...)` without tripping `set -e`: the
# resolver reads "no wisp", the guarded "not burning" branch fires as
# designed, and the stale wisp is left assigned and orphaned. One more leaks
# every patrol cycle, silently, until an operator runs the query by hand.
#
# `--type=wisp` is a separate, older bug: not a valid gc bd issue type at all,
# so the command errors and matches nothing.
#
# This test fails if any patrol prompt or formula resolves a wisp without
# `--include-infra`, or regresses to `--type=wisp`.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

FILES=(
    "gastown/formulas/mol-refinery-patrol.toml"
    "gastown/formulas/mol-deacon-patrol.toml"
    "gastown/formulas/mol-witness-patrol.toml"
    "gastown/agents/refinery/prompt.template.md"
    "gastown/agents/deacon/prompt.template.md"
    "gastown/agents/witness/prompt.template.md"
)

failures=0

fail() {
    echo "FAIL: $*" >&2
    failures=$((failures + 1))
}

for rel in "${FILES[@]}"; do
    path="$ROOT/$rel"

    # Only real invocations count, never the prose that warns against these
    # forms: a resolver line always runs `gc bd list` and ends in `--json`.

    # 1. No gc bd list may filter --type=wisp: not a valid issue type, so it
    #    errors and matches nothing.
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        fail "$rel: gc bd list filters --type=wisp, which is not a valid issue type: $line"
    done < <(grep -n 'gc bd list' "$path" | grep -- '--type=wisp' || true)

    # 2. Every wisp resolver (a gc bd list filtering --type=molecule) must pass
    #    --include-infra, or it silently returns [] and the wisp is orphaned.
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        fail "$rel: wisp resolver omits --include-infra (returns [] for wisps that exist): $line"
    done < <(grep -n 'gc bd list' "$path" | grep -- '--type=molecule' | grep -- '--json' | grep -v -- '--include-infra' || true)

    # 3. Each patrol file must still resolve wisps the working way — catches a
    #    wholesale deletion that would make rules 1 and 2 vacuously pass.
    if ! grep -q -- '--type=molecule --include-infra' "$path"; then
        fail "$rel: no '--type=molecule --include-infra' wisp resolver found"
    fi
done

if [ "$failures" -ne 0 ]; then
    echo "$failures wisp-resolver check(s) failed" >&2
    exit 1
fi

echo "PASS: wisp resolvers pass --include-infra in ${#FILES[@]} files"
