#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
GASTOWN="$ROOT/gastown"
FORMULA="$GASTOWN/formulas/mol-idea-to-plan.toml"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

extract_wiring_block() {
    local output=$1
    python3 - "$FORMULA" "$output" <<'PY'
import pathlib
import sys
import tomllib

formula_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
with formula_path.open("rb") as handle:
    formula = tomllib.load(handle)
step = next(step for step in formula["steps"] if step["id"] == "create-beads")
description = step["description"]
try:
    begin = description.index("# BEGIN PLAN_DEPENDENCY_WIRING")
    end = description.index("# END PLAN_DEPENDENCY_WIRING", begin)
except ValueError:
    sys.exit("create-beads has no PLAN_DEPENDENCY_WIRING block; dependencies are unwired")
block = description[begin:end].splitlines()[1:]
output_path.write_text("\n".join(block) + "\n", encoding="utf-8")
PY
}

# Minimal bead store: EDGES records `<dependent> <blocker>` pairs written by
# `gc bd dep add`, LABELS records `<bead> <label>` pairs read by `gc bd show`.
# Everything the wiring block observes has to come back through gc, so a step
# that only wrote a label cannot make the store report an edge.
write_gc_stub() {
    gc() {
        printf 'gc %s\n' "$*" >>"$CALLS"
        [[ "${1:-}" == "bd" ]] || return 1
        shift
        case "${1:-} ${2:-}" in
            "dep add")
                [[ "${DEP_ADD_FAILS:-0}" != "1" ]] || return 1
                # DEP_ADD_SILENT models a store that accepts the write and does
                # not persist the edge; the block must not trust its own add.
                [[ "${DEP_ADD_SILENT:-0}" == "1" ]] || printf '%s %s\n' "$3" "$4" >>"$EDGES"
                return 0
                ;;
            "dep list")
                awk -v id="$3" '$1 == id { print $2 }' "$EDGES" |
                    jq -R -s 'split("\n") | map(select(length > 0) | {id: ., dependency_type: "blocks"})'
                return 0
                ;;
            "show "*)
                awk -v id="$2" '$1 == id { print $2 }' "$LABELS" |
                    jq -R -s --arg id "$2" \
                        '[{id: $id, labels: (split("\n") | map(select(length > 0)))}]'
                return 0
                ;;
        esac
        return 1
    }
}

run_wiring() {
    local status=0
    (
        set +e
        write_gc_stub
        # shellcheck source=/dev/null
        source "$BLOCK"
    ) >"$OUT" 2>"$ERR" || status=$?
    return "$status"
}

setup_case() {
    TMP=$(mktemp -d)
    BLOCK="$TMP/wiring.sh"
    CALLS="$TMP/calls"
    EDGES="$TMP/edges"
    LABELS="$TMP/labels"
    OUT="$TMP/out"
    ERR="$TMP/err"
    PLAN_LEDGER="$TMP/plan-ledger.tsv"
    REVIEW_ID="regression"
    export PLAN_LEDGER REVIEW_ID
    unset DEP_ADD_FAILS DEP_ADD_SILENT || true
    : >"$CALLS"
    : >"$EDGES"
    : >"$LABELS"
    extract_wiring_block "$BLOCK"
}

# The headline regression: a plan that says "cache-rewrite waits on
# bounded-asset-reads" must end with a real dep edge in the store. A
# `blocked-on:` label satisfies nothing here, because the assertion reads the
# edge store, not the ledger.
test_blocking_relationship_becomes_a_real_dep_edge() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    cat >"$PLAN_LEDGER" <<'LEDGER'
ki-vxc bounded-asset-reads -
ki-msb cache-rewrite bounded-asset-reads
LEDGER

    run_wiring || fail "wiring block failed on a well-formed single-blocker plan: $(cat "$ERR")"

    grep -Fx 'gc bd dep add ki-msb ki-vxc' "$CALLS" >/dev/null ||
        fail "a blocking relationship did not produce gc bd dep add <dependent> <blocker>"
    grep -Fx 'ki-msb ki-vxc' "$EDGES" >/dev/null ||
        fail "no blocks edge was persisted for the blocked bead"
    grep -F 'PLAN_DEP_WIRING_OK edges=1' "$OUT" >/dev/null ||
        fail "wiring block did not report the edge it wrote"
    ! grep -F 'blocked-on:' "$CALLS" >/dev/null ||
        fail "the wiring step must never emit a blocked-on: label as a dependency"
    # Temporal inversion guard: "X needs Y" is `dep add X Y`, never `dep add Y X`.
    ! grep -Fx 'gc bd dep add ki-vxc ki-msb' "$CALLS" >/dev/null ||
        fail "dependency direction was inverted; the blocker must be the second argument"
}

# A slug can name work that is not a single bead. abi-widening covers three
# beads, so the dependent must wait on all three, not on an arbitrary one.
test_multi_bead_capability_fans_out_to_every_provider() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    cat >"$PLAN_LEDGER" <<'LEDGER'
ki-a01 abi-widening -
ki-a02 abi-widening -
ki-a03 abi-widening -
ki-cw9 production-ci abi-widening
LEDGER

    run_wiring || fail "wiring block failed on a multi-provider capability: $(cat "$ERR")"

    local edge
    for edge in "ki-cw9 ki-a01" "ki-cw9 ki-a02" "ki-cw9 ki-a03"; do
        grep -Fx "$edge" "$EDGES" >/dev/null ||
            fail "capability fan-out missed edge $edge"
    done
    [[ "$(wc -l <"$EDGES")" -eq 3 ]] ||
        fail "expected exactly one edge per delivering bead"
    grep -F 'PLAN_DEP_WIRING_OK edges=3' "$OUT" >/dev/null ||
        fail "wiring block miscounted the fan-out"
}

test_rerun_is_idempotent() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    cat >"$PLAN_LEDGER" <<'LEDGER'
ki-vxc bounded-asset-reads -
ki-7ea cache-rewrite bounded-asset-reads
LEDGER

    run_wiring || fail "first wiring run failed: $(cat "$ERR")"
    : >"$CALLS"
    run_wiring || fail "second wiring run failed: $(cat "$ERR")"

    ! grep -F 'gc bd dep add' "$CALLS" >/dev/null ||
        fail "rerun re-added an edge that already existed"
    [[ "$(wc -l <"$EDGES")" -eq 1 ]] ||
        fail "rerun duplicated the dependency edge"
    grep -F 'PLAN_DEP_WIRING_OK edges=1' "$OUT" >/dev/null ||
        fail "rerun did not confirm the pre-existing edge"
}

# A surviving blocked-on: label is the defect this step exists to prevent, so
# the step must refuse to report success while one is still on a planned bead.
test_surviving_blocked_on_label_fails_the_step() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    cat >"$PLAN_LEDGER" <<'LEDGER'
ki-vxc bounded-asset-reads -
ki-yvj cache-rewrite bounded-asset-reads
LEDGER
    printf 'ki-yvj blocked-on:bounded-asset-reads\n' >"$LABELS"

    ! run_wiring || fail "a bead still carrying a blocked-on: label was reported as wired"
    grep -F 'PLAN_DEP_WIRING_FAILURE' "$ERR" >/dev/null ||
        fail "label leak did not raise PLAN_DEP_WIRING_FAILURE"
    grep -F 'ki-yvj' "$ERR" >/dev/null ||
        fail "label leak did not name the offending bead"
}

test_unresolvable_slug_fails_closed() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    cat >"$PLAN_LEDGER" <<'LEDGER'
ki-msb cache-rewrite production-ci
LEDGER

    ! run_wiring || fail "a blocker slug no bead delivers was silently accepted"
    grep -F "waits on 'production-ci' but no ledger bead delivers it" "$ERR" >/dev/null ||
        fail "unresolvable slug did not fail closed with a usable message"
    ! grep -F 'gc bd dep add' "$CALLS" >/dev/null ||
        fail "an edge was written despite an unresolvable slug"
}

test_missing_ledger_and_malformed_rows_fail_closed() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    ! run_wiring || fail "a missing capability ledger was treated as an empty plan"
    grep -F 'PLAN_DEP_WIRING_FAILURE' "$ERR" >/dev/null ||
        fail "missing ledger did not raise PLAN_DEP_WIRING_FAILURE"

    printf 'ki-msb cache-rewrite\n' >"$PLAN_LEDGER"
    ! run_wiring || fail "a two-column ledger row was accepted"
    grep -F 'every ledger row needs 3 columns' "$ERR" >/dev/null ||
        fail "malformed ledger row did not report the expected shape"

    printf 'ki-msb;reboot cache-rewrite -\n' >"$PLAN_LEDGER"
    ! run_wiring || fail "an unvalidated bead ID reached the shell"
    grep -F 'refusing to shell out unvalidated names' "$ERR" >/dev/null ||
        fail "ledger identifier validation did not fail closed"
}

# The store is the authority, not the exit status of the add.
test_unpersisted_edge_fails_closed() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    cat >"$PLAN_LEDGER" <<'LEDGER'
ki-vxc bounded-asset-reads -
ki-msb cache-rewrite bounded-asset-reads
LEDGER

    DEP_ADD_SILENT=1
    ! run_wiring || fail "an edge that never persisted was reported as wired"
    unset DEP_ADD_SILENT
    grep -F 'did not read back as a blocks dependency' "$ERR" >/dev/null ||
        fail "unpersisted edge did not fail closed"

    : >"$CALLS"
    DEP_ADD_FAILS=1
    ! run_wiring || fail "a failed gc bd dep add was reported as wired"
    unset DEP_ADD_FAILS
    grep -F 'gc bd dep add ki-msb ki-vxc failed' "$ERR" >/dev/null ||
        fail "failed dep add did not fail closed"
}

test_formula_contracts_keep_dependencies_machine_readable() {
    python3 - "$FORMULA" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    tomllib.load(handle)
PY

    grep -F 'gc bd dep add "$bead" "$provider"' "$FORMULA" >/dev/null ||
        fail "the planner must execute gc bd dep add, not merely mention it"
    grep -F '# BEGIN PLAN_DEPENDENCY_WIRING' "$FORMULA" >/dev/null ||
        fail "dependency wiring must stay an extractable, testable block"
    grep -F 'plan-ledger.tsv' "$FORMULA" >/dev/null ||
        fail "the planner needs a slug-to-bead-ID ledger recorded at creation time"
    grep -F 'capability:<slug>' "$FORMULA" >/dev/null ||
        fail "task beads should declare the capability they deliver"
    grep -F 'Never encode a blocking relationship as a label.' "$FORMULA" >/dev/null ||
        fail "the label-instead-of-edge failure mode must stay called out"
    grep -F 'cascade-nudge-on-blocker-close' "$FORMULA" >/dev/null ||
        fail "the formula should explain which reader depends on real edges"
    grep -F 'gc convoy add <convoy-id> <task-id>' "$FORMULA" >/dev/null ||
        fail "convoy membership wiring should be preserved"
    grep -F 'tracks' "$FORMULA" >/dev/null ||
        fail "convoy tracks edges should be distinguished from blocking edges"
    ! grep -E -- '--labels[^\n]*blocked-on:' "$FORMULA" >/dev/null ||
        fail "the formula must never instruct the planner to create blocked-on: labels"
    # gascity_pack_inference_gate.GASTOWN_FORMULA_CONTRACTS pins these strings.
    grep -F 'Convert the refined plan into beads' "$FORMULA" >/dev/null ||
        fail "create-beads step title is pinned by the pack inference gate"
    grep -F 'gc bd dep add' "$FORMULA" >/dev/null ||
        fail "gc bd dep add is pinned by the pack inference gate"
}

test_blocking_relationship_becomes_a_real_dep_edge
test_formula_contracts_keep_dependencies_machine_readable
test_multi_bead_capability_fans_out_to_every_provider
test_rerun_is_idempotent
test_surviving_blocked_on_label_fails_the_step
test_unresolvable_slug_fails_closed
test_missing_ledger_and_malformed_rows_fail_closed
test_unpersisted_edge_fails_closed

echo "idea-to-plan dependency wiring tests passed"
