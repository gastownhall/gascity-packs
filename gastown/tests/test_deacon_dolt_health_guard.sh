#!/usr/bin/env bash
set -euo pipefail

# Executed coverage for the `dolt-health` step of mol-deacon-patrol.
#
# `gc dolt health` is a command of the Dolt pack, not of gc. A city without a
# gc-managed Dolt answers it in one of three ways: `unknown command "dolt"`
# (gc's --json envelope says error.code json_command_not_found) when the Dolt
# pack is not imported, a `skipped` report on a bd-owned proxied scope, and
# exit 78 with `dolt-state.json (missing)` on a city whose server bd owns
# directly (direct transport). A gc-managed server that is down exits 78 with
# its state file present. The step used to run the command and pipe it into a
# parser that only knew `applicable == false`, a field no released gc emits,
# so each of these was evaluated as a health report, and a real failure to run
# the check was indistinguishable from any of them.
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
port-missing|port-down)
    # Dolt pack present, no port to resolve: the pack's port_resolve.sh exits
    # 78. No runtime state file at all means no gc-managed Dolt in this city
    # (bd owns the server); a state file with no running server means the
    # gc-managed server is down. stderr is that script's template, verbatim.
    state="missing"
    [ "$STUB_HEALTH" = port-down ] && state="present but not running"
    {
        printf 'gc dolt: cannot resolve runtime port\n'
        printf '  state_file: /city/.gc/runtime/packs/dolt/dolt-state.json (%s)\n' "$state"
        printf '  city_path:  /city\n'
        printf '  consulted:  GC_DOLT_PORT (unset), GC_DOLT_STATE_FILE, dolt-provider-state.json\n'
        printf '  remediation: run `gc start` to bring up the city, or set\n'
        printf '               GC_DOLT_PORT explicitly to an already-running\n'
        printf '               server.\n'
    } >&2
    printf '%s\n' '{"schema_version":"1","ok":false,"error":{"code":"command_failed","message":"exit 78","exit_code":78}}'
    exit 78 ;;
other-78)
    # Exit 78 alone is not enough: an unrecognised 78 is a check that failed.
    printf 'gc dolt: something else went wrong\n' >&2
    exit 78 ;;
store-error)
    printf 'Error: dolt: connection refused\n' >&2
    printf '%s\n' '{"schema_version":"1","ok":false,"error":{"code":"command_failed","message":"exit 1","exit_code":1}}'
    exit 1 ;;
healthy)
    printf '%s\n' '{"timestamp":"2026-10-22T00:00:00Z","server":{"running":true,"reachable":true,"pid":4242,"port":3307,"latency_ms":3},"databases":[{"name":"hq","commits":120,"open_beads":7}],"backups":{"dolt_freshness":"fresh","dolt_age_sec":60,"dolt_stale":false},"processes":{"zombie_count":0,"zombie_pids":[]},"orphans":[]}'
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
        if grep -F 'gc mail send' "$GC_LOG" | grep -v -F -q -- '--dedup '; then
            fail "$mode: the could-not-run escalation must be sent with --dedup, or it repeats every patrol cycle"
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
leg_port_missing() { expect port-missing not-applicable no; }
leg_port_down() {
    expect port-down outage no
    grep -F -q 'DOLT_HEALTH: outage (the gc-managed Dolt server is not running) -> CRITICAL row' "$LAST_OUT" ||
        fail "port-down: the outage verdict must route to the CRITICAL row"
}
leg_other_78() { expect other-78 error yes; }
leg_store_error() {
    expect store-error error yes
    grep -F 'gc mail send' "$GC_LOG" | grep -F -q 'exited 1' ||
        fail "store-error: the escalation does not name the exit status"
}
# The outage verdict has no report to evaluate, so the step's own text is what
# sends the CRITICAL escalation for it.
leg_outage_routes_to_critical() {
    python3 - "$FORMULA" <<'PY2' || fail "the dolt-health step must route the outage verdict to Step 3's Server down (CRITICAL) escalation"
import sys
import tomllib
with open(sys.argv[1], "rb") as handle:
    steps = tomllib.load(handle)["steps"]
text = next(s for s in steps if s["id"] == "dolt-health")["description"]
bullet = text.split("- `outage (...)`:", 1)
sys.exit(0 if len(bullet) == 2 and "Server down" in bullet[1].split("\n- ", 1)[0] and "CRITICAL" in bullet[1].split("\n- ", 1)[0] else 1)
PY2
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
run_leg "no gc-managed runtime state (exit 78, missing) -> not applicable" leg_port_missing
run_leg "gc-managed server down (exit 78, present but not running) -> outage" leg_port_down
run_leg "outage verdict routes to the CRITICAL escalation" leg_outage_routes_to_critical
run_leg "unrecognised exit 78 -> deduplicated escalation" leg_other_78
run_leg "check could not run (exit 1) -> deduplicated escalation" leg_store_error
run_leg "exit 0 without a JSON report -> deduplicated escalation" leg_garbage
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
