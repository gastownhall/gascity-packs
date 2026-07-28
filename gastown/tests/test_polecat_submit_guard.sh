#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
FRAGMENT="$ROOT/gastown/template-fragments/approval-fallacy.template.md"
PROMPT="$ROOT/gastown/agents/polecat/prompt.template.md"
TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

extract_guard() {
    python3 - "$1" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
begin = "# BEGIN_GASTOWN_SUBMIT_GUARD"
end = "# END_GASTOWN_SUBMIT_GUARD"
if text.count(begin) != 1 or text.count(end) != 1:
    raise SystemExit(f"{sys.argv[1]} must contain exactly one submit guard")
guard = text.split(begin, 1)[1].split(end, 1)[0]
print(guard.replace("{{ .BindingPrefix }}", "gastown.").strip())
PY
}

extract_guard "$FRAGMENT" >"$TMPDIR_TEST/fragment-guard.sh"
extract_guard "$PROMPT" >"$TMPDIR_TEST/prompt-guard.sh"
cmp -s "$TMPDIR_TEST/fragment-guard.sh" "$TMPDIR_TEST/prompt-guard.sh" ||
    fail "prompt and fragment submit guards differ"

mkdir -p "$TMPDIR_TEST/bin"
cat >"$TMPDIR_TEST/bin/sleep" <<'SH'
#!/usr/bin/env bash
exit 0
SH
cat >"$TMPDIR_TEST/bin/gc" <<'SH'
#!/usr/bin/env bash
set -u

if [[ "${1:-}" == "hook" ]]; then
    touch "$STATE_DIR/called-hook"
    exit 99
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "list" ]]; then
    if [[ " $* " != *" --assignee $EXPECTED_TEST_ASSIGNEE "* ]] ||
       [[ " $* " != *" --status=in_progress "* ]] ||
       [[ " $* " != *" --limit=0 "* ]] ||
       [[ " $* " != *" --json "* ]]; then
        touch "$STATE_DIR/bad-list-filter"
        exit 96
    fi
    case "${LIST_MODE:-one}" in
        list-fail)
            exit 8
            ;;
        none)
            printf '[]\n'
            ;;
        malformed)
            printf '{"not":"an array"}\n'
            ;;
        multiple)
            jq -n --arg assignee "$EXPECTED_TEST_ASSIGNEE" \
                --arg step_ref "${STEP_REF_VALUE:-mol-polecat-work.submit-and-exit}" '[
                {
                    id: "step-1",
                    status: "in_progress",
                    assignee: $assignee,
                    metadata: {
                        "gc.step_ref": $step_ref,
                        "gc.root_bead_id": "root-1"
                    }
                },
                {
                    id: "step-2",
                    status: "in_progress",
                    assignee: $assignee,
                    metadata: {
                        "gc.step_ref": $step_ref,
                        "gc.root_bead_id": "root-2"
                    }
                }
            ]'
            ;;
        rootless)
            jq -n --arg assignee "$EXPECTED_TEST_ASSIGNEE" \
                --arg step_ref "${STEP_REF_VALUE:-mol-polecat-work.submit-and-exit}" '[{
                id: "step-1",
                status: "in_progress",
                assignee: $assignee,
                metadata: {"gc.step_ref": $step_ref}
            }]'
            ;;
        one|step-show-fail|root-show-fail|convoy-fail|source-show-fail)
            jq -n --arg assignee "$EXPECTED_TEST_ASSIGNEE" \
                --arg step_ref "${STEP_REF_VALUE:-mol-polecat-work.submit-and-exit}" '[{
                id: "step-1",
                status: "in_progress",
                assignee: $assignee,
                metadata: {
                    "gc.step_ref": $step_ref,
                    "gc.root_bead_id": "root-1"
                }
            }]'
            ;;
        *)
            exit 2
            ;;
    esac
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "show" ]]; then
    id="${3:-}"
    if [[ -z "$id" ]]; then
        touch "$STATE_DIR/empty-id-read"
        exit 98
    fi
    if [[ "${LIST_MODE:-one}" == "step-show-fail" && "$id" == "step-1" ]] ||
       [[ "${LIST_MODE:-one}" == "root-show-fail" && "$id" == "root-1" ]] ||
       [[ "${LIST_MODE:-one}" == "source-show-fail" && "$id" == "source-1" ]]; then
        exit 9
    fi
    case "$id" in
        step-1)
            if [[ -f "$STATE_DIR/closed-pass" ]]; then
                jq -n --arg step_ref "${STEP_REF_VALUE:-mol-polecat-work.submit-and-exit}" '[{
                    id: "step-1",
                    status: "closed",
                    assignee: env.EXPECTED_TEST_ASSIGNEE,
                    metadata: {
                        "gc.step_ref": $step_ref,
                        "gc.root_bead_id": "root-1",
                        "gc.outcome": "pass"
                    }
                }]'
            elif [[ -f "$STATE_DIR/closed-fail" ]]; then
                jq -n --arg step_ref "${STEP_REF_VALUE:-mol-polecat-work.submit-and-exit}" '[{
                    id: "step-1",
                    status: "closed",
                    assignee: env.EXPECTED_TEST_ASSIGNEE,
                    metadata: {
                        "gc.step_ref": $step_ref,
                        "gc.root_bead_id": "root-1",
                        "gc.outcome": "fail"
                    }
                }]'
            else
                jq -n --arg step_ref "${STEP_REF_VALUE:-mol-polecat-work.submit-and-exit}" '[{
                    id: "step-1",
                    status: "in_progress",
                    assignee: env.EXPECTED_TEST_ASSIGNEE,
                    metadata: {
                        "gc.step_ref": $step_ref,
                        "gc.root_bead_id": "root-1"
                    }
                }]'
            fi
            ;;
        root-1)
            jq -n '[{
                id: "root-1",
                status: "in_progress",
                metadata: {
                    "gc.kind": "workflow",
                    "gc.formula_contract": "graph.v2",
                    "gc.input_convoy_id": "convoy-1"
                }
            }]'
            ;;
        source-1)
            jq -n --arg status "$SOURCE_STATUS" --arg assignee "$SOURCE_ASSIGNEE" '[{
                id: "source-1",
                status: $status,
                assignee: $assignee
            }]'
            ;;
        *)
            exit 3
            ;;
    esac
    exit 0
fi

if [[ "${1:-}" == "convoy" && "${2:-}" == "status" ]]; then
    id="${3:-}"
    if [[ -z "$id" ]]; then
        touch "$STATE_DIR/empty-id-read"
        exit 98
    fi
    [[ "$id" == "convoy-1" ]] || exit 4
    [[ "${LIST_MODE:-one}" != "convoy-fail" ]] || exit 10
    printf '{"children":[{"id":"source-1"}]}\n'
    exit 0
fi

if [[ "${1:-}" == "bd" && "${2:-}" == "update" ]]; then
    touch "$STATE_DIR/called-update"
    [[ "${3:-}" == "step-1" ]] || exit 5
    [[ "${UPDATE_MODE:-ok}" != "fail" ]] || exit 6
    outcome=""
    for arg in "$@"; do
        case "$arg" in
            gc.outcome=pass) outcome=pass ;;
            gc.outcome=fail) outcome=fail ;;
        esac
    done
    [[ -n "$outcome" ]] || exit 7
    if [[ "${UPDATE_MODE:-ok}" != "no-readback" ]]; then
        touch "$STATE_DIR/closed-$outcome"
    fi
    exit 0
fi

if [[ "${1:-}" == "runtime" && "${2:-}" == "drain-ack" ]]; then
    touch "$STATE_DIR/called-drain"
    exit 0
fi

exit 97
SH
chmod +x "$TMPDIR_TEST/bin/gc" "$TMPDIR_TEST/bin/sleep"

run_case() {
    local name=$1
    local status=$2
    local assignee=$3
    local list_mode=$4
    local update_mode=$5
    local expected_rc=$6
    local expected_outcome=$7
    local expected_drain=$8
    local state="$TMPDIR_TEST/state-$name"
    local rc

    mkdir -p "$state"
    set +e
    PATH="$TMPDIR_TEST/bin:$PATH" \
        STATE_DIR="$state" \
        LIST_MODE="$list_mode" \
        UPDATE_MODE="$update_mode" \
        SOURCE_STATUS="$status" \
        SOURCE_ASSIGNEE="$assignee" \
        EXPECTED_TEST_ASSIGNEE="tributary/polecats/ac-test" \
        BEADS_ACTOR="tributary/polecats/ac-test" \
        GC_RIG="tributary" \
        bash "$TMPDIR_TEST/fragment-guard.sh" >"$state/output" 2>&1
    rc=$?
    set -e

    [[ "$rc" -eq "$expected_rc" ]] ||
        fail "$name: exit $rc, expected $expected_rc"
    [[ ! -e "$state/called-hook" ]] ||
        fail "$name: guard called stateful gc hook"
    [[ ! -e "$state/bad-list-filter" ]] ||
        fail "$name: guard did not use exact list filters"
    [[ ! -e "$state/empty-id-read" ]] ||
        fail "$name: guard performed an empty-id lookup"

    case "$expected_outcome" in
        none)
            [[ ! -e "$state/closed-pass" && ! -e "$state/closed-fail" ]] ||
                fail "$name: unexpectedly closed the submit step"
            ;;
        pass|fail)
            [[ -e "$state/closed-$expected_outcome" ]] ||
                fail "$name: missing closed/$expected_outcome outcome"
            ;;
        *)
            fail "$name: invalid expected outcome"
            ;;
    esac

    if [[ "$expected_drain" == "yes" ]]; then
        [[ -e "$state/called-drain" ]] || fail "$name: expected drain"
    else
        [[ ! -e "$state/called-drain" ]] || fail "$name: unexpected drain"
    fi
}

# Normal pre-handoff state: continue into submit-and-exit without mutation.
run_case open-unassigned open "" one ok 0 none no

# Exact terminal evidence: close/pass the workflow step, verify, then drain.
run_case open-refinery open "tributary/gastown.refinery" one ok 0 pass yes
run_case active-refinery in_progress "tributary/gastown.refinery" one ok 0 pass yes
run_case closed-source closed "someone/else" one ok 0 pass yes

# Deterministic ownership conflicts terminalize fail, preventing relaunch churn.
run_case third-party-owner open "tributary/polecats/ac-other" one ok 1 fail yes
run_case invalid-active-source in_progress "" one ok 1 fail yes

# Transient or ambiguous reads do not claim, close, or drain.
run_case no-current-step open "" none ok 0 none no
run_case list-failure open "" list-fail ok 0 none no
run_case malformed-list open "" malformed ok 0 none no
run_case multiple-submit-steps open "" multiple ok 0 none no
run_case rootless-step open "" rootless ok 0 none no
run_case step-show-failure open "" step-show-fail ok 0 none no
run_case root-show-failure open "" root-show-fail ok 0 none no
run_case convoy-failure open "" convoy-fail ok 0 none no
run_case source-show-failure open "" source-show-fail ok 0 none no

# Mutation or readback failure is fail-closed and never drains.
run_case close-failure open "tributary/gastown.refinery" one fail 1 none no
run_case readback-failure open "tributary/gastown.refinery" one no-readback 1 none no

extract_formula_completion() {
    local marker=$1
    local destination=$2
    python3 - "$ROOT/gastown/formulas/mol-polecat-work.toml" "$marker" >"$destination" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
marker = sys.argv[2]
begin = f"# BEGIN_GASTOWN_{marker}_STEP_COMPLETION"
end = f"# END_GASTOWN_{marker}_STEP_COMPLETION"
if text.count(begin) != 1 or text.count(end) != 1:
    raise SystemExit(f"missing unique formula completion block {marker}")
block = text.split(begin, 1)[1].split(end, 1)[0]
print(block.replace("{{convoy_id}}", "convoy-1").strip())
PY
}

run_formula_completion_case() {
    local marker=$1
    local update_mode=$2
    local expected_rc=$3
    local expected_closed=$4
    local expected_drain=$5
    local state="$TMPDIR_TEST/formula-state-$marker-$update_mode"
    local script="$TMPDIR_TEST/formula-$marker.sh"
    local rc

    extract_formula_completion "$marker" "$script"
    mkdir -p "$state"
    set +e
    PATH="$TMPDIR_TEST/bin:$PATH" \
        STATE_DIR="$state" \
        LIST_MODE=one \
        UPDATE_MODE="$update_mode" \
        SOURCE_STATUS=open \
        SOURCE_ASSIGNEE="" \
        EXPECTED_TEST_ASSIGNEE="tributary/polecats/ac-test" \
        BEADS_ACTOR="tributary/polecats/ac-test" \
        GC_RIG="tributary" \
        WORK_BEAD_ID="source-1" \
        REFINERY_TARGET="tributary/gastown.refinery" \
        bash "$script" >"$state/output" 2>&1
    rc=$?
    set -e

    [[ "$rc" -eq "$expected_rc" ]] ||
        fail "formula $marker/$update_mode: exit $rc, expected $expected_rc"
    [[ ! -e "$state/called-hook" ]] ||
        fail "formula $marker/$update_mode: called stateful gc hook"
    [[ ! -e "$state/bad-list-filter" ]] ||
        fail "formula $marker/$update_mode: did not use exact list filters"
    [[ ! -e "$state/empty-id-read" ]] ||
        fail "formula $marker/$update_mode: performed an empty-id lookup"

    if [[ "$expected_closed" == "yes" ]]; then
        [[ -e "$state/closed-pass" ]] ||
            fail "formula $marker/$update_mode: submit step was not closed/pass"
    else
        [[ ! -e "$state/closed-pass" ]] ||
            fail "formula $marker/$update_mode: unexpectedly closed submit step"
    fi
    if [[ "$expected_drain" == "yes" ]]; then
        [[ -e "$state/called-drain" ]] ||
            fail "formula $marker/$update_mode: expected drain"
    else
        [[ ! -e "$state/called-drain" ]] ||
            fail "formula $marker/$update_mode: unexpected drain"
    fi
}

# Execute both formula terminal paths, plus a fail-closed mutation fixture.
run_formula_completion_case AUTO_PUSH_FALSE ok 0 yes yes
run_formula_completion_case REFINERY ok 0 yes yes
run_formula_completion_case REFINERY fail 1 no no

extract_resume_verify() {
    python3 - "$PROMPT" >"$TMPDIR_TEST/resume-verify.sh" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
begin = "# BEGIN_GASTOWN_RESUME_VERIFY"
end = "# END_GASTOWN_RESUME_VERIFY"
if text.count(begin) != 1 or text.count(end) != 1:
    raise SystemExit("missing unique resume verification block")
block = text.split(begin, 1)[1].split(end, 1)[0]
print(block.replace("{{ .BindingPrefix }}", "gastown.").strip())
PY
}

run_resume_case() {
    local name=$1
    local step_ref=$2
    local status=$3
    local assignee=$4
    local list_mode=$5
    local expected_rc=$6
    local expected_output=$7
    local state="$TMPDIR_TEST/resume-state-$name"
    local rc

    mkdir -p "$state"
    set +e
    PATH="$TMPDIR_TEST/bin:$PATH" \
        STATE_DIR="$state" \
        LIST_MODE="$list_mode" \
        UPDATE_MODE=ok \
        STEP_REF_VALUE="$step_ref" \
        SOURCE_STATUS="$status" \
        SOURCE_ASSIGNEE="$assignee" \
        EXPECTED_TEST_ASSIGNEE="tributary/polecats/ac-restarted" \
        BEADS_ACTOR="tributary/polecats/ac-restarted" \
        GC_RIG="tributary" \
        bash "$TMPDIR_TEST/resume-verify.sh" >"$state/output" 2>&1
    rc=$?
    set -e

    [[ "$rc" -eq "$expected_rc" ]] ||
        fail "resume $name: exit $rc, expected $expected_rc"
    grep -F "$expected_output" "$state/output" >/dev/null ||
        fail "resume $name: missing output $expected_output"
    [[ ! -e "$state/called-hook" ]] ||
        fail "resume $name: called stateful gc hook"
    [[ ! -e "$state/called-update" ]] ||
        fail "resume $name: mutated bead state"
    [[ ! -e "$state/called-drain" ]] ||
        fail "resume $name: drained instead of preserving/re-establishing step ownership"
    [[ ! -e "$state/bad-list-filter" ]] ||
        fail "resume $name: did not use exact session list filters"
    [[ ! -e "$state/empty-id-read" ]] ||
        fail "resume $name: performed an empty-id lookup"
    ! grep -F 'OWNERSHIP_LOST' "$state/output" >/dev/null ||
        fail "resume $name: interpreted source state as workflow ownership"
}

extract_resume_verify

# A new provider session resumes any exact mol-polecat-work step. The source
# remains observational: normal open/unassigned and later refinery assignment
# do not invalidate ownership of the current Graph-v2 step.
run_resume_case long-running-implement \
    mol-polecat-work.implement open "" one 0 \
    "RESUME_CONFIRMED step=step-1 ref=mol-polecat-work.implement"
run_resume_case source-already-advanced \
    mol-polecat-work.submit-and-exit open "tributary/gastown.refinery" one 0 \
    "RESUME_TERMINAL step=step-1 source=source-1"

# Missing ownership must go through the standard claim path; unreadable state
# remains fail-closed without draining or guessing.
run_resume_case needs-reclaim \
    mol-polecat-work.implement open "" none 0 RESUME_CLAIM_REQUIRED
run_resume_case list-unreadable \
    mol-polecat-work.implement open "" list-fail 1 RESUME_INDETERMINATE
run_resume_case wrong-formula \
    mol-review-leg.review open "" one 0 RESUME_CLAIM_REQUIRED

echo "polecat submit guard tests passed"
