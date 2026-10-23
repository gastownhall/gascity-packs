#!/usr/bin/env bash
set -euo pipefail

# Coverage for the mayor's dispatch-failure rule.
#
# The mayor prompt tells the mayor to "fix directly when it makes sense". A
# mayor whose `gc rig add` was refused read that as permission and implemented
# the work itself in its own session: the rig never existed, no polecat ever
# saw the bead, and the human was never told the dispatch had failed. The rule
# below is what stops that, so its contract is pinned on the prompt text the
# mayor actually reads: the section is LIFTED out of the template, and every
# clause an agent acts on is asserted on the lifted text, not on the whole
# file, so moving a clause out of the rule fails here. Point MAYOR_PROMPT at
# another tree's template to run this file byte-unmodified against it (the red
# control).

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PROMPT="${MAYOR_PROMPT:-$ROOT/gastown/agents/mayor/prompt.template.md}"
HEADING='### When routing fails, report it — do not do the work yourself instead'

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
RULE="$tmp/rule.md"

# The section runs from its heading to the next heading or horizontal rule.
awk -v h="$HEADING" '
    $0 == h { on = 1; print; next }
    on && (/^#/ || /^---[[:space:]]*$/) { exit }
    on { print }
' "$PROMPT" >"$RULE"

LEG_NAMES=()
LEG_RESULTS=()

run_leg() {
    local name="$1" fn="$2"
    LEG_NAMES+=("$name")
    if ( "$fn" ); then
        LEG_RESULTS+=("PASS")
        echo "ok   $name"
    else
        LEG_RESULTS+=("FAIL")
        echo "FAIL $name" >&2
    fi
}

leg_rule_exists() {
    [ -s "$RULE" ] || fail "mayor prompt has no dispatch-failure rule ($HEADING)"
}

leg_rule_names_every_dispatch_command() {
    local cmd
    for cmd in '{{ cmd }} rig add' 'gc sling' 'gc bd create' 'formula pour'; do
        grep -F -q -- "$cmd" "$RULE" || fail "the dispatch-failure rule does not name: $cmd"
    done
}

leg_rule_forbids_doing_the_work() {
    grep -F -q 'do not route around the failure by implementing the' "$RULE" ||
        fail "the rule must forbid implementing failed-dispatch work in the mayor's own session"
    grep -F -q 'not a reason to write the code' "$RULE" ||
        fail "the rule must say a failed dispatch is not a reason to write the code"
}

leg_rule_reports_and_leaves_the_bead_open() {
    grep -F -q 'Report the exact command you ran and its full error output' "$RULE" ||
        fail "the rule must report the exact command and its error"
    grep -F -q 'Leave the bead open' "$RULE" ||
        fail "the rule must leave the bead open"
    grep -F -q 'Do not close it, assign it' "$RULE" ||
        fail "the rule must forbid closing or self-assigning the bead"
    grep -F -q 'Stop that piece of work until the failure is fixed' "$RULE" ||
        fail "the rule must hold the work until the failure is fixed"
}

leg_rule_outranks_fix_directly() {
    local fix rule
    grep -F -q 'This rule takes precedence over "Fix directly when it makes sense"' "$RULE" ||
        fail "the rule must state that it takes precedence over Fix directly"
    # Read as the exception it is: it sits right after the permission it limits.
    fix=$(grep -n -F '### Fix directly when it makes sense' "$PROMPT" | cut -d: -f1 || true)
    rule=$(grep -n -F -- "$HEADING" "$PROMPT" | cut -d: -f1 || true)
    [ -n "$fix" ] && [ -n "$rule" ] || fail "could not locate Fix directly and the rule in $PROMPT"
    [ "$fix" -lt "$rule" ] || fail "the rule must follow the Fix directly section it limits"
    [ -z "$(sed -n "$((fix + 1)),$((rule - 1))p" "$PROMPT" | grep -E '^(#|---)' || true)" ] ||
        fail "the rule must be the section immediately after Fix directly"
}

run_leg "rule exists" leg_rule_exists
run_leg "rule names gc rig add, gc sling, gc bd create and pours" leg_rule_names_every_dispatch_command
run_leg "rule forbids doing the work yourself" leg_rule_forbids_doing_the_work
run_leg "rule reports the error and leaves the bead open" leg_rule_reports_and_leaves_the_bead_open
run_leg "rule outranks Fix directly and follows it" leg_rule_outranks_fix_directly

echo "--- leg summary (prompt: $PROMPT) ---"
failed=0
for i in "${!LEG_NAMES[@]}"; do
    printf '%-4s %s\n' "${LEG_RESULTS[$i]}" "${LEG_NAMES[$i]}"
    [ "${LEG_RESULTS[$i]}" = "PASS" ] || failed=1
done

if [ "$failed" -ne 0 ]; then
    echo "FAIL: mayor dispatch-failure rule" >&2
    exit 1
fi
echo "PASS: mayor dispatch-failure rule (${#LEG_NAMES[@]} legs)"
