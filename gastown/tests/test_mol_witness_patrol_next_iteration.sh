#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
GASTOWN="$ROOT/gastown"
FORMULA="$GASTOWN/formulas/mol-witness-patrol.toml"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# Pull the next-iteration step's reconciliation bash (the fenced ```bash
# block that resolves CURRENT_WISP) straight out of the live formula TOML.
# This harness always exercises whatever is currently on disk: red against
# the PR#189 $GC_BEAD_ID-only version (vg-5kv), green only once the
# ASSIGNED_WISP open-scan reconciliation replaces it.
extract_next_iteration_bash() {
    python3 - "$1" <<'PY'
import re
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    data = tomllib.load(handle)

for step in data.get("steps", []):
    if step.get("id") == "next-iteration":
        desc = step["description"]
        for block in re.findall(r"```bash\n(.*?)\n```", desc, re.S):
            if "CURRENT_WISP" in block:
                sys.stdout.write(block)
                sys.exit(0)
        sys.exit("next-iteration step has no CURRENT_WISP bash block")
sys.exit("no next-iteration step found in formula")
PY
}

# Mock `gc` — logs every invocation and answers just enough to drive the
# reconciliation bash through both the defective and corrected shapes.
# `jq` is left as the real binary; only gc's JSON output is faked.
write_mock_gc() {
    cat > "$1/gc" <<'MOCKGC'
#!/usr/bin/env bash
echo "$*" >> "$MOCK_CALL_LOG"
case "$1" in
  bd)
    case "$2" in
      list)
        if [[ "$*" == *"--status=open"* ]]; then
          echo "${MOCK_OPEN_WISPS_JSON:-[]}"
        else
          echo "${MOCK_INPROGRESS_JSON:-[]}"
        fi
        ;;
      mol)
        case "$3" in
          wisp) echo "{\"new_epic_id\": \"${MOCK_NEW_EPIC_ID:-wisp-new}\"}" ;;
          burn) echo "$4" >> "$MOCK_BURN_LOG" ;;
        esac
        ;;
      update) : ;;
    esac
    ;;
  runtime) : ;;
esac
exit 0
MOCKGC
    chmod +x "$1/gc"
}

# Run the extracted reconciliation bash under a mocked gc (real jq) with
# GC_BEAD_ID unset — the proven live-witness-runtime shape, see bd memory
# vg-5kv-gc-bead-id-empty-confirmed-live-witness — and a scripted
# --status=open wisp set. Leaves RC/CALLS_FILE/BURNS_FILE/STDOUT_FILE/work
# set in the caller's scope for assertions.
run_next_iteration() {
    local open_wisps_json="$1"
    work=$(mktemp -d)
    write_mock_gc "$work"
    extract_next_iteration_bash "$FORMULA" > "$work/script.sh"

    CALLS_FILE="$work/calls.log"
    BURNS_FILE="$work/burns.log"
    STDOUT_FILE="$work/stdout.log"
    : > "$CALLS_FILE"
    : > "$BURNS_FILE"

    RC=0
    (
      export PATH="$work:$PATH"
      export GC_AGENT="voxlingo/gastown.witness"
      export MOCK_CALL_LOG="$CALLS_FILE"
      export MOCK_BURN_LOG="$BURNS_FILE"
      export MOCK_OPEN_WISPS_JSON="$open_wisps_json"
      export MOCK_INPROGRESS_JSON='[]'
      unset GC_BEAD_ID
      bash "$work/script.sh"
    ) >"$STDOUT_FILE" 2>&1 || RC=$?
}

test_next_iteration_empty_gc_bead_id_one_open_wisp_noop() {
    run_next_iteration '[{"id":"wisp-current"}]'

    [[ "$RC" -eq 0 ]] ||
        fail "next-iteration must exit 0 when GC_BEAD_ID is unset and exactly one open self-assigned wisp exists (got rc=$RC); output: $(cat "$STDOUT_FILE")"
    [[ ! -s "$BURNS_FILE" ]] ||
        fail "next-iteration must not burn any wisp in the steady-state noop case; burned: $(cat "$BURNS_FILE")"
    ! grep -q '^bd mol wisp ' "$CALLS_FILE" ||
        fail "next-iteration must not pour a new wisp when one is already open and assigned"

    rm -rf "$work"
}

test_next_iteration_burns_surplus_without_gc_bead_id() {
    run_next_iteration '[{"id":"wisp-current"},{"id":"wisp-surplus"}]'

    [[ "$RC" -eq 0 ]] ||
        fail "next-iteration must exit 0 reconciling a surplus wisp without GC_BEAD_ID (got rc=$RC); output: $(cat "$STDOUT_FILE")"
    [[ "$(cat "$BURNS_FILE")" == "wisp-surplus" ]] ||
        fail "next-iteration must burn exactly the surplus wisp (wisp-surplus) and keep wisp-current; burned: $(cat "$BURNS_FILE")"
    ! grep -q '^bd mol wisp ' "$CALLS_FILE" ||
        fail "next-iteration must not pour a new wisp when the reconciled set already has an assigned wisp"

    rm -rf "$work"
}

test_next_iteration_empty_gc_bead_id_one_open_wisp_noop
test_next_iteration_burns_surplus_without_gc_bead_id

echo "mol-witness-patrol next-iteration tests passed"
