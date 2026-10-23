#!/usr/bin/env bash
set -euo pipefail

# Executed coverage for the `dolt-health` step of mol-deacon-patrol.
#
# `gc dolt health` is a command of the Dolt pack, not of gc. A city without a
# gc-managed Dolt data plane answers it with `unknown command "dolt"` (gc's
# --json envelope says error.code json_command_not_found), and a bd-owned
# proxied scope answers with a `skipped` report. The step used to run the
# command and pipe it into a parser that only knew `applicable == false`, a
# field no released gc emits, so both answers were evaluated as a health
# report, and a real failure to run the check was indistinguishable from
# either.
#
# The step's script is LIFTED out of the formula (through tomllib, so TOML
# escapes decode exactly as gc decodes them) and executed against a stub `gc`
# whose `dolt health --json` answers are the literal outputs measured from gc
# v1.5.0 and the 1.5.1 hotfix branch. Point DOLT_HEALTH_FORMULA at another tree
# to run this file byte-unmodified against it (the red control).

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
FORMULA="${DOLT_HEALTH_FORMULA:-$ROOT/gastown/formulas/mol-deacon-patrol.toml}"

command -v jq >/dev/null 2>&1 || {
    echo "FAIL: jq required (the lifted script classifies the report with real jq)" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

BIN="$tmp/bin"
BLOCK="$tmp/dolt-health.sh"
GC_LOG="$tmp/gc.log"
LAST_OUT="/dev/null"
RC=0
export GC_LOG

fail() {
    echo "FAIL: $*" >&2
    if [ -s "$LAST_OUT" ]; then
        echo "--- captured step output ---" >&2
        tail -n 20 "$LAST_OUT" >&2
    fi
    exit 1
}

# Every bash fence of the dolt-health step that runs `gc dolt health`, in
# order, as one script: if the step ever splits the run from its
# classification again, the split is executed exactly as an agent would.
lift_step() {
    python3 - "$FORMULA" "$BLOCK" <<'PY'
import sys
import tomllib

formula, dest = sys.argv[1], sys.argv[2]
with open(formula, "rb") as handle:
    steps = tomllib.load(handle).get("steps", [])
step = next((s for s in steps if s.get("id") == "dolt-health"), None)
if step is None:
    sys.exit(f"{formula}: no dolt-health step")
fences, block, inside = [], [], False
for line in step["description"].split("\n"):
    if line.strip().startswith("```"):
        if inside:
            fences.append("\n".join(block))
            block, inside = [], False
        elif line.strip() == "```bash":
            inside = True
        continue
    if inside:
        block.append(line)
def runs_health(fence):
    # A command position, not a mention: escalation text that quotes the
    # command name is not a second run of it.
    return any(line.strip().startswith("gc dolt health") or "$(gc dolt health" in line
               for line in fence.split("\n"))

runs = [f for f in fences if runs_health(f)]
if not runs:
    sys.exit(f"{formula}: the dolt-health step has no bash fence that runs gc dolt health")
body = "\n".join(runs).replace("{{binding_prefix}}", "") + "\n"
if "{{" in body:
    sys.exit("unsubstituted template hole in the lifted dolt-health script")
open(dest, "w").write(body)
PY
    bash -n "$BLOCK" || fail "the lifted dolt-health script does not parse"
}

write_gc_stub() {
    mkdir -p "$BIN"
    cat >"$BIN/gc" <<'SH'
#!/usr/bin/env bash
printf 'gc %s\n' "$*" >>"$GC_LOG"
if [ "$*" != "dolt health --json" ]; then
    case "$1" in
        dolt) echo "stub: unexpected gc dolt invocation: $*" >&2; exit 64 ;;
        *) exit 0 ;;
    esac
fi
case "$STUB_HEALTH" in
missing-envelope)
    # gc v1.5.0 / 1.5.1 with --json in a city without the Dolt pack.
    printf '%s\n' '{"schema_version":"1","ok":false,"error":{"code":"json_command_not_found","message":"command \"dolt health\" was not found","exit_code":1}}'
    exit 1 ;;
missing-text)
    # The same gc without the JSON envelope (and older gc releases).
    printf 'gc: unknown command "dolt"\n\nRun "gc --help" for usage.\n' >&2
    exit 1 ;;
skipped)
    # bd-owned proxied scope (examples/bd/dolt print_proxied_skip_json).
    printf '%s\n' '{
  "timestamp": "2026-10-22T00:00:00Z",
  "skipped": {
    "reason": "bd-owned-proxied-scope",
    "message": "dolt lifecycle is owned by bd for proxied scopes; nothing to do"
  }
}'
    exit 0 ;;
not-applicable)
    printf '%s\n' '{"applicable":false,"reason":"city beads backend is mysql; no managed Dolt runtime to probe","server":{"running":false,"reachable":false}}'
    exit 0 ;;
port-unresolved)
    # Dolt pack present, runtime port unresolvable: the pack script exits 78.
    printf 'gc dolt: cannot resolve runtime port\n  remediation: run `gc start` to bring up the city\n' >&2
    printf '%s\n' '{"schema_version":"1","ok":false,"error":{"code":"command_failed","message":"exit 78","exit_code":78}}'
    exit 78 ;;
healthy)
    printf '%s\n' '{"timestamp":"2026-10-22T00:00:00Z","server":{"running":true,"reachable":true,"pid":4242,"port":3307,"latency_ms":3},"databases":[{"name":"hq","commits":120,"open_beads":7}],"backups":{"dolt_freshness":"fresh","dolt_age_seconds":60,"dolt_stale":false},"processes":{"zombie_count":0,"zombie_pids":[]},"orphans":[]}'
    exit 0 ;;
server-down)
    # A real outage is signalled in-band with exit 0, and must reach the table.
    printf '%s\n' '{"timestamp":"2026-10-22T00:00:00Z","server":{"running":true,"reachable":false,"pid":4242,"port":3307,"latency_ms":0},"databases":[],"backups":{"dolt_stale":false},"processes":{"zombie_count":0,"zombie_pids":[]},"orphans":[]}'
    exit 0 ;;
garbage)
    printf 'panic: runtime error\n'
    exit 0 ;;
*)
    echo "stub: unknown STUB_HEALTH=$STUB_HEALTH" >&2
    exit 64 ;;
esac
SH
    chmod +x "$BIN/gc"
}

run_step() {
    RC=0
    LAST_OUT="$tmp/$1.out"
    : >"$GC_LOG"
    (
        cd "$tmp" || exit 99
        PATH="$BIN:$PATH" GC_LOG="$GC_LOG" STUB_HEALTH="$1" \
            bash -c 'set +eu; . "$1"' bash "$BLOCK"
    ) >"$LAST_OUT" 2>&1 || RC=$?
}

# expect <mode> <verdict> <mail: yes|no>
expect() {
    local mode="$1" verdict="$2" mail="$3" got runs
    run_step "$mode"
    got=$(grep -E '^DOLT_HEALTH: ' "$LAST_OUT" || true)
    [ "$(printf '%s\n' "$got" | grep -c .)" -eq 1 ] ||
        fail "$mode: expected exactly one DOLT_HEALTH verdict line, got: ${got:-none}"
    case "$got" in
        "DOLT_HEALTH: $verdict"*) ;;
        *) fail "$mode: expected verdict '$verdict', got: $got" ;;
    esac
    runs=$(grep -c '^gc dolt health' "$GC_LOG" || true)
    [ "$runs" -eq 1 ] || fail "$mode: gc dolt health ran $runs times; run it once and classify that result"
    if grep '^gc dolt' "$GC_LOG" | grep -F -q -- '--help'; then
        fail "$mode: probed with --help, which exits 0 whether or not gc dolt exists"
    fi
    if [ "$mail" = yes ]; then
        grep -F -q 'gc mail send mayor/' "$GC_LOG" || fail "$mode: a check that could not run must be escalated"
        if grep -F 'gc mail send' "$GC_LOG" | grep -F -q 'CRITICAL'; then
            fail "$mode: a check that could not run is not a CRITICAL Dolt outage"
        fi
    elif grep -F -q 'gc mail send' "$GC_LOG"; then
        fail "$mode: escalated although there was nothing to escalate"
    fi
    return 0
}

leg_missing_envelope() { expect missing-envelope not-applicable no; }
leg_missing_text() { expect missing-text not-applicable no; }
leg_skipped() {
    expect skipped not-applicable no
    grep -F -q 'bd-owned-proxied-scope' "$LAST_OUT" || fail "skipped: the skip reason was not reported"
}
leg_not_applicable() { expect not-applicable not-applicable no; }
leg_port_unresolved() {
    expect port-unresolved error yes
    grep -F 'gc mail send' "$GC_LOG" | grep -F -q 'exited 78' ||
        fail "port-unresolved: the escalation does not name the exit status"
}
leg_garbage() { expect garbage error yes; }
leg_healthy() {
    expect healthy evaluate no
    grep -F -q '"reachable":true' "$LAST_OUT" || fail "healthy: the report to evaluate was not printed"
}
leg_server_down() {
    expect server-down evaluate no
    grep -F -q '"reachable":false' "$LAST_OUT" || fail "server-down: the report to evaluate was not printed"
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

write_gc_stub
lift_step

run_leg "missing command, gc --json envelope -> not applicable" leg_missing_envelope
run_leg "missing command, unknown command text -> not applicable" leg_missing_text
run_leg "bd-owned proxied scope (skipped) -> not applicable" leg_skipped
run_leg "applicable=false -> not applicable" leg_not_applicable
run_leg "check could not run (exit 78) -> non-critical escalation" leg_port_unresolved
run_leg "exit 0 without a JSON report -> non-critical escalation" leg_garbage
run_leg "healthy report -> evaluate" leg_healthy
run_leg "in-band outage -> evaluate (never not-applicable)" leg_server_down

echo "--- leg summary (formula: $FORMULA) ---"
failed=0
for i in "${!LEG_NAMES[@]}"; do
    printf '%-4s %s\n' "${LEG_RESULTS[$i]}" "${LEG_NAMES[$i]}"
    [ "${LEG_RESULTS[$i]}" = "PASS" ] || failed=1
done

if [ "$failed" -ne 0 ]; then
    echo "FAIL: mol-deacon-patrol dolt-health guard" >&2
    exit 1
fi
echo "PASS: mol-deacon-patrol dolt-health guard (${#LEG_NAMES[@]} legs)"
