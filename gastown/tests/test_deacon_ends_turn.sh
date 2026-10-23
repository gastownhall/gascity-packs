#!/usr/bin/env bash
set -euo pipefail

# Coverage for the deacon's between-cycles contract (gastownhall/gascity#5727).
#
# The deacon is an always-on session, and no sleep or idle-timeout policy paces
# it. What paces it is ending the turn: next-iteration pours the successor
# wisp, burns the current one and ends the turn, and Gas City restarts the
# session on the successor on a later pass. The prompt used to say the
# opposite ("No Idle State ... run `gc hook` immediately"), and its
# crash-recovery fallback ended in `gc hook`, so a deacon re-entered its own
# loop from inside the turn and patrolled back to back on an idle town; the
# formula told it a session_sleep policy would restart it, which never engages
# for an always-on session.
#
# The fallback must also never just end the turn. Gas City moves an always-on
# deacon onto its next cycle only when the wisp it was running is gone, and a
# fallback that could not rotate the patrol wisps leaves that wisp open, so it
# ends by draining (`gc runtime drain-ack`): the restarted deacon's startup
# picks the patrol up again.
#
# The fallback is LIFTED out of the prompt and executed against a stub `gc`
# that records every call; the rest is pinned on the shipped text. Point
# DEACON_TURN_ROOT at another tree to run this file byte-unmodified against it
# (the red control).

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
TREE="${DEACON_TURN_ROOT:-$ROOT}"
PROMPT="$TREE/gastown/agents/deacon/prompt.template.md"
FORMULA="$TREE/gastown/formulas/mol-deacon-patrol.toml"

command -v jq >/dev/null 2>&1 || {
    echo "FAIL: jq required (the lifted fallback parses the stub's JSON with real jq)" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
BIN="$tmp/bin"
GC_LOG="$tmp/gc.log"
export GC_LOG

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# fences <file> <out-dir>: every ```bash fence, one file each, in order. A
# formula is read through tomllib, so its fences are the text an agent reads.
fences() {
    python3 - "$1" "$2" <<'PY'
import pathlib
import sys
import tomllib

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
if src.suffix == ".toml":
    doc = tomllib.loads(src.read_text())
    text = "\n".join([doc.get("description", "")] +
                     [f"<<step {s.get('id')}>>\n" + s.get("description", "") for s in doc.get("steps", [])])
else:
    text = src.read_text()
n, block, inside, step = 0, [], False, ""
for line in text.split("\n"):
    if line.startswith("<<step "):
        step = line[len("<<step "):-2]
        continue
    if line.strip().startswith("```"):
        if inside:
            n += 1
            (out / f"{n:02d}-{step or 'prompt'}.sh").write_text("\n".join(block) + "\n")
            block, inside = [], False
        elif line.strip() == "```bash":
            inside = True
        continue
    if inside:
        block.append(line)
print(n)
PY
}

# runs_gc_hook <file>: does a code line invoke `gc hook` (not merely mention it)?
runs_gc_hook() {
    grep -E -q '^[[:space:]]*(.*(;|&&|\|\||then|do)[[:space:]]*)?gc hook([[:space:]]|$)' "$1"
}

leg_no_fence_reenters_the_loop() {
    local dir f
    for asset in "$PROMPT" "$FORMULA"; do
        dir="$tmp/fences-$(basename "$asset")"
        fences "$asset" "$dir" >/dev/null || fail "could not read fences from $asset"
        for f in "$dir"/*.sh; do
            [ -e "$f" ] || continue
            if runs_gc_hook "$f"; then
                fail "$(basename "$asset") $(basename "$f"): a deacon script runs gc hook, which re-enters the patrol loop inside the turn"
            fi
        done
    done
    return 0
}

leg_prompt_ends_the_turn() {
    # The instructions that re-entered the loop, as they were written. A
    # sentence that forbids running gc hook is the fix, not a regression.
    local instruction
    for instruction in 'run `gc hook` immediately' 'do not pour again; run `gc hook`' \
        '-> pour next iteration -> run `gc hook`'; do
        if grep -n -F -- "$instruction" "$PROMPT"; then
            fail "deacon prompt still tells the deacon to re-enter its loop: $instruction"
        fi
    done
    if grep -n -F 'No Idle State' "$PROMPT"; then
        fail "deacon prompt still forbids the idle state that is the deacon's correct resting state between cycles"
    fi
    grep -F -q -- '-> pour next iteration -> end your turn.' "$PROMPT" ||
        fail "deacon prompt's loop summary must end the turn after pouring the next iteration"
    grep -F -q 'The fallback ends by draining the session' "$PROMPT" ||
        fail "deacon prompt's crash-recovery fallback must say it ends by draining the session"
}

leg_formula_ends_the_turn_truthfully() {
    local step
    step=$(python3 - "$FORMULA" <<'PY'
import sys
import tomllib
with open(sys.argv[1], "rb") as handle:
    steps = tomllib.load(handle)["steps"]
print(next(s for s in steps if s["id"] == "next-iteration")["description"])
PY
)
    printf '%s\n' "$step" | grep -F -q 'IDLE: no work, exiting turn.' ||
        fail "next-iteration must end the turn with the IDLE signal"
    if printf '%s\n' "$step" | grep -n -i 'session_sleep policy will restart'; then
        fail "next-iteration still promises a session_sleep restart; no sleep policy applies to an always-on deacon"
    fi
    printf '%s\n' "$step" | grep -F -q 'run `gc hook` to start the next cycle yourself' ||
        fail "next-iteration must say not to re-enter the loop with gc hook"
    printf '%s\n' "$step" | grep -F -q 'the restarted session resumes from it' ||
        fail "next-iteration must hand the successor to the restarted session"
}

lift_fallback() {
    python3 - "$PROMPT" "$1" <<'PY'
import sys
text = open(sys.argv[1]).read()
marker = "Use this fallback only if"
if marker not in text:
    sys.exit("deacon prompt has no crash-recovery fallback")
rest = text.split(marker, 1)[1]
body = rest.split("```bash", 1)[1].split("```", 1)[0]
body = body.replace("{{ .BindingPrefix }}", "")
if "{{" in body:
    sys.exit("unsubstituted template hole in the deacon fallback")
open(sys.argv[2], "w").write(body)
PY
}

# run_fallback <state>: execute the lifted fallback against a recording stub.
#   empty    the deacon holds no patrol wisp
#   current  the wisp it was running is open and assigned to it, the state the
#            fallback actually meets (a patrol wisp never becomes in_progress)
run_fallback() {
    local fallback="$tmp/fallback.sh"
    lift_fallback "$fallback" || fail "could not lift the deacon fallback"
    bash -n "$fallback" || fail "the lifted deacon fallback does not parse"
    mkdir -p "$BIN"
    cat >"$BIN/gc" <<'SH'
#!/usr/bin/env bash
# Patterns read as `gc bd ...`, which tests/test_no_bare_bd_commands.py accepts.
invocation="gc $*"
printf '%s\n' "$invocation" >>"$GC_LOG"
case "$invocation" in
    "gc bd list "*--status=in_progress*) printf '[]\n' ;;
    "gc bd list "*)
        if [ "$FALLBACK_STATE" = current ]; then
            printf '[{"id":"wisp-1","title":"mol-deacon-patrol","status":"open","issue_type":"molecule","ephemeral":true,"assignee":"deacon","created_at":"2026-10-22T00:00:00Z"}]\n'
        else
            printf '[]\n'
        fi ;;
    "gc bd mol wisp "*) printf '{"new_epic_id":"wisp-2"}\n' ;;
    *) : ;;
esac
SH
    chmod +x "$BIN/gc"
    : >"$GC_LOG"
    (
        cd "$tmp" || exit 99
        env -u GC_BEAD_ID PATH="$BIN:$PATH" GC_LOG="$GC_LOG" GC_AGENT=deacon FALLBACK_STATE="$1" \
            bash -c 'set +eu; . "$1"' bash "$fallback"
    ) >"$tmp/fallback.out" 2>&1 || true
}

leg_fallback_executes_without_reentering() {
    run_fallback empty
    if grep -E -q '^gc hook( |$)' "$GC_LOG"; then
        fail "the crash-recovery fallback ran gc hook and re-entered the patrol loop inside the turn"
    fi
    grep -F -q 'gc bd mol wisp mol-deacon-patrol' "$GC_LOG" ||
        fail "the fallback did not run as far as pouring the next wisp; the leg measured nothing"
}

# Whatever the fallback managed to do, it must end with a drain, or a deacon
# whose current wisp is still open never gets another cycle.
leg_fallback_ends_with_drain() {
    local state
    for state in empty current; do
        run_fallback "$state"
        [ "$(tail -n 1 "$GC_LOG")" = "gc runtime drain-ack" ] ||
            fail "with the deacon's patrol wisp state '$state', the fallback must end with gc runtime drain-ack (last gc call: $(tail -n 1 "$GC_LOG"))"
    done
}

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

run_leg "no deacon script runs gc hook" leg_no_fence_reenters_the_loop
run_leg "prompt ends the turn between cycles" leg_prompt_ends_the_turn
run_leg "next-iteration ends the turn, no sleep-policy promise" leg_formula_ends_the_turn_truthfully
run_leg "fallback executes without re-entering the loop" leg_fallback_executes_without_reentering
run_leg "fallback ends with a drain, whatever state it meets" leg_fallback_ends_with_drain

echo "--- leg summary (tree: $TREE) ---"
failed=0
for i in "${!LEG_NAMES[@]}"; do
    printf '%-4s %s\n' "${LEG_RESULTS[$i]}" "${LEG_NAMES[$i]}"
    [ "${LEG_RESULTS[$i]}" = "PASS" ] || failed=1
done

if [ "$failed" -ne 0 ]; then
    echo "FAIL: deacon ends its turn between cycles" >&2
    exit 1
fi
echo "PASS: deacon ends its turn between cycles (${#LEG_NAMES[@]} legs)"
