#!/usr/bin/env bash
set -euo pipefail

# Regression suite for the polecat Blocked Work Contract.
#
# Reproduction: ki-0aq and ki-gu2 were both left `blocked` with no recorded
# reason. Each read as a crashed session — the next agent had to re-derive the
# whole investigation from nothing — and because the beads stayed claimed while
# still routed to the polecat pool, the pool respawned workers on work it then
# refused to hand out. The fix is a fail-closed contract: record the reason,
# read it back, and only then flip status and release the claim.
#
# The contract ships as an executable block inside the polecat prompt, so this
# suite extracts the shipped block and runs it against a hermetic `gc` stub
# rather than asserting on prose.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
GASTOWN="$ROOT/gastown"
PROMPT="$GASTOWN/agents/polecat/prompt.template.md"
FORMULA="$GASTOWN/formulas/mol-polecat-work.toml"

BLOCKED_BEAD_REASON="ki-0aq needs the ki-vxc bounded-asset-read landing before SP int truncation can be removed"
BLOCKED_BEAD_DISPOSITION="upstream-dependency-required"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

extract_blocked_contract() {
    local output=$1
    python3 - "$PROMPT" "$output" <<'PY'
import pathlib
import sys

prompt_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
text = prompt_path.read_text(encoding="utf-8")
if "bash <<'GC_BLOCKED'\n" not in text:
    sys.exit("polecat prompt lost the executable GC_BLOCKED contract block")
try:
    begin = text.index("# BEGIN POLECAT_BLOCKED_CONTRACT")
    end = text.index("# END POLECAT_BLOCKED_CONTRACT", begin)
except ValueError:
    sys.exit("blocked-work contract must stay an extractable, testable block")
block = text[begin:end].splitlines()[1:]
rendered = "\n".join(block).replace("{{ .BindingPrefix }}", "gastown.")
output_path.write_text(rendered + "\n", encoding="utf-8")
PY
}

# Hermetic stand-in for the real CLI. It dispatches on argv positions and never
# spells out a bare "<beads-cli> <subcommand>" string: tests/test_no_bare_bd_commands.py
# rejects that spelling anywhere in tracked assets, fixtures included.
#
# GC_TEST_SCENARIO=reason_lost models a store that accepts the metadata write
# and does not persist it, so the block cannot trust its own update's exit code.
write_gc_stub() {
    cat >"$FAKE_BIN/gc" <<'SH'
#!/bin/sh
printf '%s\n' "$*" >>"$GC_TEST_CALLS"
REASON_JSON='"blocked_reason":"'"$GC_TEST_REASON"'","blocked_disposition":"'"$GC_TEST_DISPOSITION"'"'
if [ "$1" != "bd" ]; then
    case "$1" in
      mail|runtime) exit 0 ;;
      *) printf 'unexpected command: %s\n' "$*" >&2; exit 97 ;;
    esac
fi
case "$2" in
  update) exit 0 ;;
  show)
    if [ "${GC_TEST_SCENARIO:-}" = "reason_lost" ]; then
      printf '%s\n' '[{"id":"'"$GC_TEST_BEAD"'","status":"in_progress","assignee":"kisakcod/gastown.cheedo","metadata":{}}]'
    elif grep -q -- '--status=blocked' "$GC_TEST_CALLS"; then
      printf '%s\n' '[{"id":"'"$GC_TEST_BEAD"'","status":"blocked","assignee":"","metadata":{'"$REASON_JSON"'}}]'
    else
      printf '%s\n' '[{"id":"'"$GC_TEST_BEAD"'","status":"in_progress","assignee":"kisakcod/gastown.cheedo","metadata":{'"$REASON_JSON"'}}]'
    fi
    ;;
  *) printf 'unexpected command: %s\n' "$*" >&2; exit 97 ;;
esac
SH
    chmod +x "$FAKE_BIN/gc"
}

setup_case() {
    TMP=$(mktemp -d)
    FAKE_BIN="$TMP/bin"
    BLOCK="$TMP/block.sh"
    CALLS="$TMP/calls"
    mkdir -p "$FAKE_BIN"
    : >"$CALLS"
    extract_blocked_contract "$BLOCK"
    write_gc_stub
}

# Runs the shipped block exactly as a polecat would: as its own bash process,
# with only the documented BLOCKED_* environment. Sets CODE and OUTPUT.
run_block() {
    local bead=$1 reason=$2 disposition=$3 scenario=${4:-}
    CODE=0
    set +e
    OUTPUT="$(
        PATH="$FAKE_BIN:$PATH" \
        GC_TEST_CALLS="$CALLS" \
        GC_TEST_SCENARIO="$scenario" \
        GC_TEST_BEAD="$bead" \
        GC_TEST_REASON="$reason" \
        GC_TEST_DISPOSITION="$disposition" \
        GC_RIG="kisakcod" BEADS_ACTOR="kisakcod/gastown.cheedo" \
        BLOCKED_BEAD="$bead" \
        BLOCKED_REASON="$reason" \
        BLOCKED_DISPOSITION="$disposition" \
        bash "$BLOCK" 2>&1
    )"
    CODE=$?
    set -e
}

# The contract must exist and must be the only sanctioned stop path.
test_blocked_work_contract_is_documented() {
    grep -F 'Blocked Work Contract' "$PROMPT" >/dev/null ||
        fail "polecat prompt must document a Blocked Work Contract"
    grep -F 'blocked_reason' "$PROMPT" >/dev/null ||
        fail "polecat prompt must require blocked_reason metadata when blocking"
    grep -F 'blocked_disposition' "$PROMPT" >/dev/null ||
        fail "polecat prompt must require a blocked_disposition token when blocking"
    grep -F 'Blocked Work Contract' "$FORMULA" >/dev/null ||
        fail "mol-polecat-work must carry the Blocked Work Contract"
    grep -F 'blocked_reason' "$FORMULA" >/dev/null ||
        fail "mol-polecat-work must require blocked_reason metadata when blocking"
    ! grep -F 'mark yourself stuck' "$FORMULA" >/dev/null ||
        fail "mol-polecat-work must not tell a polecat to 'mark yourself stuck' with no reason contract"

    python3 - "$FORMULA" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    tomllib.load(handle)
PY
}

# Every runnable blocked/escalated status flip must live inside the contract
# block, after the reason has been written and read back.
test_bare_status_flip_is_not_copyable_from_any_shipped_snippet() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    python3 - "$PROMPT" "$FORMULA" "$BLOCK" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
formula = open(sys.argv[2], encoding="utf-8").read()
block = open(sys.argv[3], encoding="utf-8").read()

# Any other fenced shell snippet an agent could copy verbatim must not offer a
# bare status flip. Prose that forbids the bare flip is exactly the point.
for source, label in ((text, "polecat prompt"), (formula, "mol-polecat-work")):
    fenced = source.split("```")[1::2]
    for snippet in fenced:
        if "GC_BLOCKED" in snippet:
            continue
        if "--status=blocked" in snippet or "--status=escalated" in snippet:
            raise SystemExit(
                f"{label} offers a copyable bare blocked/escalated status flip outside GC_BLOCKED"
            )

for source, label in ((text, "polecat prompt"), (formula, "mol-polecat-work")):
    if "--status=blocked" not in source:
        raise SystemExit(f"{label} must name the bare status flip it forbids")

reason_write = block.index("--set-metadata blocked_reason=")
readback = block.index(".[0].metadata.blocked_reason")
status_flip = block.index('--status="$STATUS"')
if not reason_write < readback < status_flip:
    raise SystemExit("GC_BLOCKED must write the reason, read it back, and only then flip status")
for needle in ('--assignee=""', "--set-metadata gc.routed_to=human", "gc runtime drain-ack"):
    if needle not in block:
        raise SystemExit(f"GC_BLOCKED must release the claim and leave the pool: missing {needle}")
PY
}

# The live defect: block with no reason at all. Must refuse, and must not touch
# the bead, so no bead can end up blocked-and-silent.
test_reasonless_block_is_refused_and_touches_nothing() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    run_block "ki-0aq" "" ""
    [[ "$CODE" -eq 2 ]] || fail "a blocked transition with no reason must be refused"
    [[ "$OUTPUT" == *'BLOCK_REFUSED ki-0aq'* ]] ||
        fail "a reasonless block must report BLOCK_REFUSED"
    [[ ! -s "$CALLS" ]] ||
        fail "a refused block must not issue any gc command: $(cat "$CALLS")"
}

# A placeholder reason is the same defect wearing a hat.
test_placeholder_reason_is_refused_and_touches_nothing() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    local placeholder
    for placeholder in blocked stuck unknown n/a tbd; do
        : >"$CALLS"
        run_block "ki-gu2" "$placeholder" "unknown"
        [[ "$CODE" -eq 2 ]] ||
            fail "placeholder blocked_reason '$placeholder' must be refused"
        [[ "$OUTPUT" == *'BLOCK_REFUSED ki-gu2'* ]] ||
            fail "placeholder blocked_reason '$placeholder' must report BLOCK_REFUSED"
        # Named as a placeholder, not merely short: a longer placeholder must
        # not slip past a length check alone.
        [[ "$OUTPUT" == *'is empty or a placeholder'* ]] ||
            fail "blocked_reason '$placeholder' must be rejected as a placeholder, not incidentally"
        [[ ! -s "$CALLS" ]] ||
            fail "a refused block must not issue any gc command: $(cat "$CALLS")"
    done

    # A real reason paired with a placeholder disposition is refused too, and
    # just as silently as far as the bead is concerned.
    : >"$CALLS"
    run_block "ki-gu2" "$BLOCKED_BEAD_REASON" "unknown"
    [[ "$CODE" -eq 2 ]] || fail "a placeholder blocked_disposition must be refused"
    [[ "$OUTPUT" == *'BLOCK_REFUSED ki-gu2'* ]] ||
        fail "a placeholder blocked_disposition must report BLOCK_REFUSED"
    [[ "$OUTPUT" == *'blocked_disposition must be a kebab-case token'* ]] ||
        fail "a placeholder blocked_disposition must be named as the refusal cause"
    [[ ! -s "$CALLS" ]] ||
        fail "a refused block must not issue any gc command: $(cat "$CALLS")"
}

# Reason write silently does not persist: fail closed. Never flip status, never
# release the claim, never drain-ack — escalate instead.
test_unpersisted_reason_fails_closed_and_escalates_once() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    run_block "ki-0aq" "$BLOCKED_BEAD_REASON" "$BLOCKED_BEAD_DISPOSITION" reason_lost
    [[ "$CODE" -eq 1 ]] || fail "an unpersisted blocked_reason must fail closed with exit 1"
    [[ "$OUTPUT" == *'BLOCK_ABORTED ki-0aq'* ]] ||
        fail "an unpersisted blocked_reason must report BLOCK_ABORTED"
    ! grep -F -- '--status=blocked' "$CALLS" >/dev/null ||
        fail "status must never flip to blocked when the reason did not persist"
    ! grep -F -- '--assignee=' "$CALLS" >/dev/null ||
        fail "the claim must not be released when the reason did not persist"
    ! grep -F 'runtime drain-ack' "$CALLS" >/dev/null ||
        fail "a failed block must not drain-ack; that reports idle and hides it"
    [[ "$(grep -c '^mail send ' "$CALLS")" -eq 1 ]] ||
        fail "a failed block must send exactly one witness escalation"
}

# Happy path: reason recorded first, then the status flip and claim release in
# one update.
test_recorded_block_writes_the_reason_before_the_status_flip() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    run_block "ki-0aq" "$BLOCKED_BEAD_REASON" "$BLOCKED_BEAD_DISPOSITION"
    [[ "$CODE" -eq 1 ]] ||
        fail "a recorded block mirrors the refinery: drain-ack then non-zero exit"
    [[ "$OUTPUT" == *'BLOCKED_RECORDED ki-0aq'* ]] ||
        fail "a recorded block must report BLOCKED_RECORDED"
    grep -F -- '--set-metadata blocked_reason=' "$CALLS" >/dev/null ||
        fail "a recorded block must write blocked_reason metadata"
    grep -F -- '--set-metadata gc.routed_to=human' "$CALLS" >/dev/null ||
        fail "a blocked bead must leave the polecat pool (gc.routed_to=human)"
    grep -F 'runtime drain-ack' "$CALLS" >/dev/null ||
        fail "a recorded block must drain-ack so the session is reaped"

    python3 - "$CALLS" <<'PY'
import sys

calls = open(sys.argv[1], encoding="utf-8").read().splitlines()
reason = next(i for i, c in enumerate(calls) if "--set-metadata blocked_reason=" in c)
status = next(i for i, c in enumerate(calls) if "--status=blocked" in c)
release = next(i for i, c in enumerate(calls) if "--assignee=" in c)
if not reason < status:
    raise SystemExit("blocked_reason must be written before the status flip")
if status != release:
    raise SystemExit("the status flip must release the claim in the same update")
PY
}

test_blocked_work_contract_is_documented
test_bare_status_flip_is_not_copyable_from_any_shipped_snippet
test_reasonless_block_is_refused_and_touches_nothing
test_placeholder_reason_is_refused_and_touches_nothing
test_unpersisted_reason_fails_closed_and_escalates_once
test_recorded_block_writes_the_reason_before_the_status_flip

echo "polecat blocked-reason contract tests passed"
