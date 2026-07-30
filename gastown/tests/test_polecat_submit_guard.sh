#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
PROMPT="$ROOT/gastown/agents/polecat/prompt.template.md"
FRAGMENT="$ROOT/gastown/template-fragments/approval-fallacy.template.md"
FORMULA="$ROOT/gastown/formulas/mol-polecat-work.toml"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

extract_block() {
    local source=$1
    local begin=$2
    local end=$3
    local destination=$4
    python3 - "$source" "$begin" "$end" >"$destination" <<'PY'
import sys

path, begin, end = sys.argv[1:]
text = open(path, encoding="utf-8").read()
if text.count(begin) != 1 or text.count(end) != 1:
    raise SystemExit(f"{path} must contain one {begin}/{end} block")
print(text.split(begin, 1)[1].split(end, 1)[0].strip())
PY
}

extract_block \
    "$FRAGMENT" \
    "# BEGIN_GASTOWN_SUBMIT_GUARD" \
    "# END_GASTOWN_SUBMIT_GUARD" \
    "$TMP/fragment-guard.sh"
extract_block \
    "$PROMPT" \
    "# BEGIN_GASTOWN_SUBMIT_GUARD" \
    "# END_GASTOWN_SUBMIT_GUARD" \
    "$TMP/prompt-guard.sh"
cmp -s "$TMP/fragment-guard.sh" "$TMP/prompt-guard.sh" ||
    fail "prompt and fragment submit guards are not byte-identical"

python3 - "$FORMULA" >"$TMP/submit-execute.sh" <<'PY'
import re
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    document = tomllib.load(handle)
submit = next(
    step["description"]
    for step in document.get("steps", [])
    if step.get("id") == "submit-and-exit"
)
blocks = re.findall(r"```bash\n(.*?)\n```", submit, re.DOTALL)
if len(blocks) != 1:
    raise SystemExit(
        "submit-and-exit must contain exactly one deterministic shell fence"
    )
if blocks[0].count("gc gastown polecat-submit execute") != 1:
    raise SystemExit("terminal fence must call polecat-submit execute exactly once")
print(blocks[0])
PY

for block in \
    "$TMP/fragment-guard.sh" \
    "$TMP/prompt-guard.sh" \
    "$TMP/submit-execute.sh"; do
    if grep -Eq 'gc[[:space:]]+hook([[:space:]]|$)' "$block"; then
        fail "$(basename "$block") contains a raw gc hook call"
    fi
done

mkdir -p "$TMP/bin"
cat >"$TMP/bin/gc" <<'FAKE'
#!/usr/bin/env bash
set -euo pipefail

printf 'gc' >>"$CALL_LOG"
printf ' %q' "$@" >>"$CALL_LOG"
printf '\n' >>"$CALL_LOG"

if [[ "${1:-}" == "hook" ]]; then
    touch "$CASE_STATE/raw-hook"
    exit 97
fi
if [[ "${1:-}" == "bd" ]]; then
    touch "$CASE_STATE/raw-bd"
    exit 96
fi
if [[ "${1:-}" == "gastown" &&
      "${2:-}" == "polecat-submit" &&
      "${3:-}" == "guard" &&
      "$#" -eq 3 ]]; then
    case "${GUARD_MODE:-proceed}" in
        proceed)
            echo '{"contract":"polecat-submit.v1","action":"proceed","step":"submit-1","assignee":"session-1","root":"root-1","convoy":"convoy-1","source":"source-1","mode":"","branch":"polecat/source-1","status":"open","source_assignee":"","replay":false}'
            ;;
        terminal)
            echo '{"contract":"polecat-submit.v1","action":"terminal","step":"submit-1","assignee":"session-1","root":"root-1","convoy":"convoy-1","source":"source-1","mode":"refinery","branch":"polecat/source-1","status":"open","source_assignee":"demo/gastown.refinery","replay":false}'
            ;;
        terminal-replay)
            echo '{"contract":"polecat-submit.v1","action":"terminal","step":"submit-1","assignee":"session-1","root":"root-1","convoy":"convoy-1","source":"source-1","mode":"refinery","branch":"polecat/source-1","status":"closed","source_assignee":"","replay":true}'
            ;;
        terminal-after-complete)
            if [[ -e "$CASE_STATE/completed" ]]; then
                echo '{"contract":"polecat-submit.v1","action":"terminal","step":"submit-1","assignee":"session-1","root":"root-1","convoy":"convoy-1","source":"source-1","mode":"refinery","branch":"polecat/source-1","status":"closed","source_assignee":"","replay":true}'
            else
                echo '{"contract":"polecat-submit.v1","action":"terminal","step":"submit-1","assignee":"session-1","root":"root-1","convoy":"convoy-1","source":"source-1","mode":"refinery","branch":"polecat/source-1","status":"open","source_assignee":"demo/gastown.refinery","replay":false}'
            fi
            ;;
        unsupported)
            echo '{"contract":"polecat-submit.v1","action":"unknown","step":"submit-1","assignee":"session-1","root":"root-1","convoy":"convoy-1","source":"source-1","mode":"refinery","branch":"polecat/source-1","status":"open","source_assignee":"demo/gastown.refinery","replay":false}'
            ;;
        malformed)
            echo '{"action":"terminal","source":"source-1"}'
            ;;
        fail)
            echo "POLECAT_SUBMIT_INDETERMINATE: fixture failure" >&2
            exit 75
            ;;
        *)
            exit 95
            ;;
    esac
    exit 0
fi
if [[ "${1:-}" == "gastown" &&
      "${2:-}" == "polecat-submit" &&
      "${3:-}" == "complete" ]]; then
    [[ "${SUBMIT_MODE:-ok}" == "ok" ]] || {
        echo "POLECAT_SUBMIT_INDETERMINATE: fixture failure" >&2
        exit 75
    }
    touch "$CASE_STATE/completed"
    echo "POLECAT_SUBMIT_COMPLETE step=submit-1"
    exit 0
fi
if [[ "${1:-}" == "gastown" &&
      "${2:-}" == "polecat-submit" &&
      "${3:-}" == "execute" &&
      "$#" -eq 3 ]]; then
    [[ "${SUBMIT_MODE:-ok}" == "ok" ]] || {
        echo "POLECAT_SUBMIT_INDETERMINATE: fixture failure" >&2
        exit 75
    }
    touch "$CASE_STATE/completed" "$CASE_STATE/drained"
    echo "POLECAT_SUBMIT_EXECUTE_COMPLETE step=submit-1"
    exit 0
fi
if [[ "${1:-}" == "runtime" &&
      "${2:-}" == "drain-ack" &&
      "$#" -eq 2 ]]; then
    case "${DRAIN_MODE:-ok}" in
        fail)
            exit 1
            ;;
        fail-once)
            if [[ ! -e "$CASE_STATE/drain-failed-once" ]]; then
                touch "$CASE_STATE/drain-failed-once"
                exit 1
            fi
            ;;
    esac
    touch "$CASE_STATE/drained"
    exit 0
fi
exit 94
FAKE
chmod +x "$TMP/bin/gc"

assert_no_raw_state_calls() {
    local state=$1
    [[ ! -e "$state/raw-hook" ]] ||
        fail "$(basename "$state") called raw gc hook"
    [[ ! -e "$state/raw-bd" ]] ||
        fail "$(basename "$state") bypassed the submit helper with gc bd"
}

run_guard_case() {
    local name=$1
    local guard_mode=$2
    local submit_mode=$3
    local drain_mode=$4
    local expected_rc=$5
    local expected_output=$6
    local expected_drain=$7
    local expected_complete=$8
    local state="$TMP/guard-$name"
    local rc

    mkdir -p "$state"
    : >"$state/calls"
    set +e
    PATH="$TMP/bin:$PATH" \
        CALL_LOG="$state/calls" \
        CASE_STATE="$state" \
        GUARD_MODE="$guard_mode" \
        SUBMIT_MODE="$submit_mode" \
        DRAIN_MODE="$drain_mode" \
        bash "$TMP/fragment-guard.sh" >"$state/output" 2>&1
    rc=$?
    set -e

    [[ "$rc" -eq "$expected_rc" ]] ||
        fail "guard $name returned $rc, expected $expected_rc: $(<"$state/output")"
    grep -F "$expected_output" "$state/output" >/dev/null ||
        fail "guard $name did not report $expected_output"
    [[ "$(grep -c '^gc gastown polecat-submit guard$' "$state/calls")" -eq 1 ]] ||
        fail "guard $name did not delegate exactly once"
    [[ "$(grep -c '^gc gastown polecat-submit complete ' "$state/calls" || true)" -eq "$expected_complete" ]] ||
        fail "guard $name made the wrong number of terminal completion calls"
    if [[ "$expected_complete" -gt 0 ]]; then
        grep -Fx 'gc gastown polecat-submit complete --convoy convoy-1 --source source-1 --branch polecat/source-1 --mode refinery' \
            "$state/calls" >/dev/null ||
            fail "guard $name did not pass the exact validated terminal tuple"
    fi
    if [[ "$expected_drain" == "yes" ]]; then
        [[ -e "$state/drained" ]] ||
            fail "guard $name did not drain after terminal evidence"
    else
        [[ ! -e "$state/drained" ]] ||
            fail "guard $name drained without terminal evidence"
    fi
    assert_no_raw_state_calls "$state"
}

run_guard_case proceed proceed ok ok 0 '"action":"proceed"' no 0
run_guard_case terminal-live terminal ok ok 0 '"action":"terminal"' yes 1
run_guard_case terminal-replay terminal-replay ok ok 0 '"replay":true' yes 1
run_guard_case helper-failure fail ok ok 1 \
    "Deterministic submit-state guard failed closed" no 0
run_guard_case malformed-result malformed ok ok 1 \
    "Unsupported deterministic submit-state result" no 0
run_guard_case unsupported-result unsupported ok ok 1 \
    "Unsupported deterministic submit-state result" no 0
run_guard_case completion-failure terminal fail ok 1 \
    "Deterministic terminal submit completion failed" no 1
run_guard_case drain-failure terminal ok fail 1 \
    "drain acknowledgement failed" no 1

retry_state="$TMP/guard-drain-retry"
mkdir -p "$retry_state"
: >"$retry_state/calls"
set +e
PATH="$TMP/bin:$PATH" \
    CALL_LOG="$retry_state/calls" \
    CASE_STATE="$retry_state" \
    GUARD_MODE=terminal-after-complete \
    SUBMIT_MODE=ok \
    DRAIN_MODE=fail-once \
    bash "$TMP/fragment-guard.sh" >"$retry_state/first-output" 2>&1
first_rc=$?
PATH="$TMP/bin:$PATH" \
    CALL_LOG="$retry_state/calls" \
    CASE_STATE="$retry_state" \
    GUARD_MODE=terminal-after-complete \
    SUBMIT_MODE=ok \
    DRAIN_MODE=fail-once \
    bash "$TMP/fragment-guard.sh" >"$retry_state/second-output" 2>&1
second_rc=$?
set -e
[[ "$first_rc" -eq 1 && "$second_rc" -eq 0 ]] ||
    fail "drain retry did not fail then replay successfully"
grep -F '"replay":true' "$retry_state/second-output" >/dev/null ||
    fail "drain retry did not consume already-closed replay evidence"
[[ "$(grep -c '^gc gastown polecat-submit complete ' "$retry_state/calls")" -eq 2 ]] ||
    fail "drain retry did not idempotently complete on both attempts"
[[ -e "$retry_state/drained" ]] ||
    fail "drain retry never acknowledged drain"
assert_no_raw_state_calls "$retry_state"

run_formula_case() {
    local name=$1
    local submit_mode=$2
    local expected_rc=$3
    local expected_drain=$4
    local state="$TMP/formula-$name"
    local rc

    mkdir -p "$state"
    : >"$state/calls"
    set +e
    PATH="$TMP/bin:$PATH" \
        CALL_LOG="$state/calls" \
        CASE_STATE="$state" \
        SUBMIT_MODE="$submit_mode" \
        bash "$TMP/submit-execute.sh" >"$state/output" 2>&1
    rc=$?
    set -e

    [[ "$rc" -eq "$expected_rc" ]] ||
        fail "formula $name returned $rc, expected $expected_rc: $(<"$state/output")"
    [[ "$(grep -cFx 'gc gastown polecat-submit execute' "$state/calls")" -eq 1 ]] ||
        fail "formula $name did not call deterministic execute exactly once"
    ! grep -E '^gc (bd|hook|runtime|session)|^gc gastown polecat-submit (guard|complete)|^gc gastown polecat-lease' \
        "$state/calls" >/dev/null ||
        fail "formula $name split deterministic execute into raw stateful calls"
    if [[ "$expected_drain" == "yes" ]]; then
        [[ -e "$state/drained" ]] ||
            fail "formula $name did not drain after verified completion"
    else
        [[ ! -e "$state/drained" ]] ||
            fail "formula $name drained after failed completion"
    fi
    assert_no_raw_state_calls "$state"
}

run_formula_case execute-success ok 0 yes
run_formula_case execute-failure fail 1 no

echo "polecat submit guard integration tests passed"
