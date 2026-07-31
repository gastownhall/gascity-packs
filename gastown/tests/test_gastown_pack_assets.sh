#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
GASTOWN="$ROOT/gastown"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

parse_toml() {
    python3 - "$@" <<'PY'
import sys
import tomllib

for path in sys.argv[1:]:
    with open(path, "rb") as handle:
        tomllib.load(handle)
PY
}

test_dog_assets_are_pack_local() {
    [[ -f "$GASTOWN/agents/dog/agent.toml" ]] || fail "missing dog agent config"
    [[ -f "$GASTOWN/agents/dog/prompt.template.md" ]] || fail "missing dog prompt"
    [[ -f "$GASTOWN/formulas/mol-shutdown-dance.toml" ]] || fail "missing shutdown dance formula"
    parse_toml "$GASTOWN/agents/dog/agent.toml" "$GASTOWN/formulas/mol-shutdown-dance.toml"
    grep -F 'wake_mode = "fresh"' "$GASTOWN/agents/dog/agent.toml" >/dev/null ||
        fail "dog agent should own wake_mode"
    grep -F 'work_dir = ".gc/agents/dogs/{{.AgentBase}}"' "$GASTOWN/agents/dog/agent.toml" >/dev/null ||
        fail "dog agent should own work_dir"
    ! grep -F 'fallback = true' "$GASTOWN/agents/dog/agent.toml" >/dev/null ||
        fail "gastown dog should be authoritative over fallback dog providers"
    ! grep -A3 -F '[[patches.agent]]' "$GASTOWN/pack.toml" | grep -F 'name = "dog"' >/dev/null ||
        fail "dog should not be split between pack-local agent and same-name patch"
    [[ ! -e "$GASTOWN/agents/dog/overlay/.gitkeep" ]] ||
        fail "dog overlay placeholder should not be present without an overlay contract"
}

test_retired_dog_formulas_are_not_reintroduced() {
    [[ ! -e "$GASTOWN/formulas/mol-dog-jsonl.toml" ]] || fail "mol-dog-jsonl formula should remain retired"
    [[ ! -e "$GASTOWN/formulas/mol-dog-reaper.toml" ]] || fail "mol-dog-reaper formula should remain retired"
    ! grep -R --exclude='test_gastown_pack_assets.sh' "mol-dog-jsonl\\|mol-dog-reaper" "$GASTOWN" >/dev/null ||
        fail "gastown pack should not advertise retired dog formulas"
}

test_shutdown_dance_contracts_are_executable() {
    local formula="$GASTOWN/formulas/mol-shutdown-dance.toml"

    ! grep -F '[vars.warrant_id]' "$formula" >/dev/null ||
        fail "warrant_id should be the claimed work bead, not a required formula var"
    grep -F 'gc bd show "$GC_BEAD_ID"' "$formula" >/dev/null ||
        fail "shutdown dance should inspect the claimed warrant bead"
    grep -F 'gc bd close "$GC_BEAD_ID"' "$formula" >/dev/null ||
        fail "shutdown dance should close the claimed warrant bead"
    ! grep -F '<wisp-id>' "$formula" >/dev/null ||
        fail "shutdown dance should not contain raw wisp placeholders"
    ! grep -F '<work-bead>' "$formula" >/dev/null ||
        fail "shutdown dance should not contain raw work bead placeholders"
    ! grep -F 'gc mail send {{requester}}/' "$formula" >/dev/null ||
        fail "routine dog requester reporting must use nudge, not mail"
    grep -F 'requester_endpoint="${requester%/}/"' "$formula" >/dev/null ||
        fail "shutdown dance should normalize requester endpoints"
    grep -F 'gc session nudge "$requester_endpoint" "DOG_DONE:' "$formula" >/dev/null ||
        fail "shutdown dance should notify requester with DOG_DONE nudges"
    ! grep -F 'gc session peek "{{target}}"' "$formula" >/dev/null ||
        fail "shutdown dance should use quoted target shell variables for peeks"
    ! grep -F 'gc session kill "{{target}}"' "$formula" >/dev/null ||
        fail "shutdown dance should use quoted target shell variables for kills"
    grep -F 'Verify the warrant bead exists and is not closed' "$formula" >/dev/null ||
        fail "receive step should verify the warrant is not closed rather than demanding open"
    grep -F 'Both `open` and `in_progress` are valid warrant states' "$formula" >/dev/null ||
        fail "receive step should explicitly accept open and in_progress warrant states"
    ! grep -F 'exists and is open' "$formula" >/dev/null ||
        fail "receive step must not regress to an open-only warrant instruction; claimed warrants are in_progress"
}

test_shutdown_dance_lifecycle_and_audit_contracts() {
    local formula="$GASTOWN/formulas/mol-shutdown-dance.toml"
    local prompt="$GASTOWN/agents/dog/prompt.template.md"

    ! grep -Fi 'burn' "$formula" >/dev/null ||
        fail "early-exit paths should drain-ack and exit, not burn a wisp that was never poured"
    [[ "$(grep -c 'gc runtime drain-ack' "$formula")" -ge 8 ]] ||
        fail "every early-exit path and the epitaph should end with gc runtime drain-ack"
    local malformed_branches malformed_closes malformed_drains
    malformed_branches="$(grep -c 'is missing target or reason' "$formula" || true)"
    malformed_closes="$(grep -A4 'is missing target or reason' "$formula" | grep -cF 'gc bd close "$GC_BEAD_ID"' || true)"
    malformed_drains="$(grep -A4 'is missing target or reason' "$formula" | grep -cF 'gc runtime drain-ack' || true)"
    [[ "$malformed_branches" -ge 1 ]] ||
        fail "shutdown dance should validate warrant target/reason metadata"
    [[ "$malformed_closes" -eq "$malformed_branches" ]] ||
        fail "every malformed-warrant branch must close the claimed warrant before exiting"
    [[ "$malformed_drains" -eq "$malformed_branches" ]] ||
        fail "every malformed-warrant branch must drain-ack before exiting, not leak the claimed warrant"
    grep -F 'MALFORMED_WARRANT' "$formula" >/dev/null ||
        fail "malformed warrants should close with a malformed-warrant audit reason"
    ! grep -E '^\[vars' "$formula" >/dev/null ||
        fail "warrant values come from bead metadata; the formula should not declare pour vars"
    grep -F 'EXECUTE_FAILED: kill did not take effect' "$formula" >/dev/null ||
        fail "kill failures should close the warrant as EXECUTE_FAILED, not Executed"
    grep -F 'DOG_DONE: $target - EXECUTE_FAILED (escalated)' "$formula" >/dev/null ||
        fail "kill failures should notify the requester with EXECUTE_FAILED, not EXECUTED"
    grep -F 'gone or shows fresh startup output' "$formula" >/dev/null ||
        fail "execute verification should treat gone-or-freshly-restarted as kill success"
    ! grep -F '{{requester}}' "$prompt" >/dev/null ||
        fail "dog prompt should use the normalized requester endpoint, not raw requester templates"
    ! grep -F 'nudge deacon/' "$prompt" >/dev/null ||
        fail "dog prompt should notify the warrant's requester, not a hardcoded deacon endpoint"
    grep -F 'gc session nudge "$requester_endpoint"' "$prompt" >/dev/null ||
        fail "dog prompt DOG_DONE guidance should use the normalized requester endpoint"
}

test_composition_is_documented() {
    # The retired maintenance pack is gone: the runtime composes the builtin
    # core pack via explicit city.toml includes, and gastown owns the only
    # mol-shutdown-dance. The docs must describe that model, not the old
    # fallback/ordering workarounds.
    grep -F 'builtin core pack' "$GASTOWN/README.md" >/dev/null ||
        fail "README should attribute mechanical housekeeping to the builtin core pack"
    ! grep -F '[imports.maintenance]' "$GASTOWN/README.md" >/dev/null ||
        fail "README should not reference the retired maintenance pack import"
    ! grep -Fi 'implicit maintenance' "$GASTOWN/README.md" >/dev/null ||
        fail "README should not describe implicit maintenance injection"
    grep -F 'gc formula show mol-shutdown-dance' "$GASTOWN/README.md" >/dev/null ||
        fail "README should document how to verify the effective shutdown-dance formula"
    grep -F 'builtin core' "$GASTOWN/pack.toml" >/dev/null ||
        fail "pack.toml should attribute mechanical housekeeping to the builtin core pack"
    ! grep -F '[imports.maintenance]' "$GASTOWN/pack.toml" >/dev/null ||
        fail "pack.toml should not reference the retired maintenance pack import"
}

test_polecat_startup_uses_scripted_hook_claim() {
    local agent prompt propulsion following restart
    agent="$GASTOWN/agents/polecat/agent.toml"
    prompt="$GASTOWN/agents/polecat/prompt.template.md"
    propulsion="$GASTOWN/template-fragments/propulsion.template.md"
    following="$GASTOWN/template-fragments/following-mol.template.md"
    restart=$(sed -n '/^\*\*Restart \/ resume:\*\*/,/^\*\*Claim ->/p' "$prompt")

    grep -F 'POLECAT_CLAIM_CONTRACT' "$agent" >/dev/null ||
        fail "polecat nudge should enter the complete scripted claim contract"
    grep -F 'first operational action' "$agent" >/dev/null ||
        fail "polecat nudge should make the complete contract the first operational action"
    grep -F 'CLAIMED_BEAD_ID' "$agent" >/dev/null ||
        fail "polecat nudge should gate continuation on a claim receipt"
    ! grep -F 'gc hook --claim' "$agent" >/dev/null ||
        fail "polecat nudge must not bypass the scripted startup contract"
    grep -F 'default_sling_formula = "mol-polecat-work"' "$agent" >/dev/null ||
        fail "plain polecat sling must compile the implementation workflow instead of routing a bare task"
    grep -F 'gc hook --claim --drain-ack --json' "$prompt" >/dev/null ||
        fail "polecat prompt should use the transactional startup claim path"
    grep -F '`{{ cmd }} prime` may reload this prompt only' "$prompt" >/dev/null ||
        fail "prime recovery should be context restoration only"
    grep -F 'Only after `CLAIMED_BEAD_ID` may you re-read formula steps' "$prompt" >/dev/null ||
        fail "polecat restart should gate formula/workspace access on the claim receipt"
    ! grep -F 'FIRST action on restart' "$prompt" >/dev/null ||
        fail "polecat prompt should not retain a competing manual first action"
    [[ "$restart" != *'CONVOY_STATUS=$(gc convoy status'* ]] ||
        fail "polecat prompt should not retain a manual resume bypass"
    grep -F 'complete `POLECAT_CLAIM_CONTRACT` as its first operational action' \
        "$following" >/dev/null ||
        fail "shared restart guidance should preserve the polecat claim-first gate"
    grep -F '`CLAIMED_BEAD_ID`' "$following" >/dev/null ||
        fail "shared restart guidance should wait for the polecat claim receipt"
    ! grep -F 'On crash or restart, re-read your formula steps' "$following" >/dev/null ||
        fail "shared restart guidance should not read formulas before polecat claim"
    grep -F 'rerun the complete `POLECAT_CLAIM_CONTRACT` exactly once' "$propulsion" >/dev/null ||
        fail "polecat propulsion must reuse the validated claim contract after each step"
    grep -F 'rerun the complete' "$prompt" >/dev/null &&
        grep -F '`POLECAT_CLAIM_CONTRACT` block exactly once' "$prompt" >/dev/null ||
        fail "polecat prompt must require one validated continuation claim"
    ! grep -F 'for i in $(seq 1 6); do' "$prompt" >/dev/null &&
        ! grep -F '2>/dev/null || true' "$prompt" >/dev/null ||
        fail "polecat prompt must not retry or suppress uncertain claim results"
    grep -F 'Complete each step through' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment must require hook continuation after each formula step"
    ! grep -F 'bounded 60-second' "$propulsion" >/dev/null ||
        fail "polecat propulsion must not preserve the obsolete raw-hook poll"
    ! grep -F 'run `gc hook` or' "$prompt" >/dev/null ||
        fail "polecat prompt must not regress to an unclaimed hook/work-query choice"
    ! grep -F 'run `gc hook` or' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment must not regress to an unclaimed hook/work-query choice"
}

test_polecat_submit_guard_and_step_completion_contracts() {
    local formula prompt fragment lease_command step_command submit_command
    local workspace_command conflict_command
    formula="$GASTOWN/formulas/mol-polecat-work.toml"
    prompt="$GASTOWN/agents/polecat/prompt.template.md"
    fragment="$GASTOWN/template-fragments/approval-fallacy.template.md"
    lease_command="$GASTOWN/commands/polecat-lease/run.sh"
    step_command="$GASTOWN/commands/polecat-step/run.sh"
    submit_command="$GASTOWN/commands/polecat-submit/run.sh"
    workspace_command="$GASTOWN/commands/polecat-workspace/run.sh"
    conflict_command="$GASTOWN/commands/polecat-conflict/run.sh"

    parse_toml "$formula"
    [[ -x "$lease_command" ]] ||
        fail "deterministic polecat lease command must be executable"
    [[ -x "$step_command" ]] ||
        fail "deterministic polecat step command must be executable"
    [[ -x "$submit_command" ]] ||
        fail "deterministic polecat submit command must be executable"
    [[ -x "$workspace_command" ]] ||
        fail "deterministic polecat workspace command must be executable"
    [[ -x "$conflict_command" ]] ||
        fail "deterministic polecat conflict command must be executable"
    ! grep -F 'gc hook' "$step_command" >/dev/null ||
        fail "polecat step completion must never claim unrelated work"
    grep -F 'gc.outcome=pass' "$step_command" >/dev/null &&
        grep -F 'gc.formula_contract' "$step_command" >/dev/null &&
        grep -F 'gc.input_convoy_id' "$step_command" >/dev/null ||
        fail "polecat step command must bind outcome, Graph-v2 root, and input convoy"
    if ! python3 - "$formula" <<'PY'
import re
import shlex
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    document = tomllib.load(handle)

steps = {step["id"]: step for step in document.get("steps", [])}
expected = [
    "load-context",
    "preflight-tests",
    "implement",
    "self-review",
]
errors = []
for step_id in expected:
    description = steps.get(step_id, {}).get("description", "")
    step_ref = f'mol-polecat-work.{step_id}'
    if description.count("gc gastown polecat-step complete") != 1:
        errors.append(f"{step_id}: must invoke polecat-step complete exactly once")
    if '--convoy "{{convoy_id}}"' not in description:
        errors.append(f"{step_id}: must bind the exact input convoy")
    if f'--step-ref "{step_ref}"' not in description:
        errors.append(f"{step_id}: must bind exact step ref {step_ref}")
    if "Do not run `gc bd close` on this step." not in description:
        errors.append(f"{step_id}: must forbid raw close substitution")
    if "POLECAT_STEP_COMPLETE" not in description:
        errors.append(f"{step_id}: must wait for verified completion output")

exec_counts = {
    "workspace-setup": 1,
    "preflight-tests": 1,
    "implement": 1,
    "self-review": 5,
}
for step_id, count in exec_counts.items():
    description = steps.get(step_id, {}).get("description", "")
    actual = description.count("gc gastown polecat-step exec")
    if actual != count:
        errors.append(f"{step_id}: artifact exec count {actual}, want {count}")
    if f'--step-ref "mol-polecat-work.{step_id}"' not in description:
        errors.append(f"{step_id}: artifact exec does not bind its exact step")

load = steps.get("load-context", {}).get("description", "")
for index, block in enumerate(
    re.findall(r"```bash\n(.*?)\n```", load, re.DOTALL), start=1
):
    if "$WORK_BEAD_ID" in block and "WORK_BEAD_ID=$(" not in block:
        errors.append(
            f"load-context shell fence {index} consumes stale WORK_BEAD_ID"
        )

workspace = steps.get("workspace-setup", {}).get("description", "")
workspace_blocks = re.findall(
    r"```bash\n(.*?)\n```", workspace, re.DOTALL
)
workspace_execute = "gc gastown polecat-workspace execute"
if len(workspace_blocks) != 2:
    errors.append("workspace-setup must contain exactly two shell fences")
else:
    workspace_block, conflict_block = workspace_blocks
    if (
        workspace.count(workspace_execute) != 1
        or workspace_block.count(workspace_execute) != 1
        or f"if ! {workspace_execute}; then" not in workspace_block
        or workspace_block.count("gc ") != 1
    ):
        errors.append("workspace-setup must delegate exactly once and fail closed")
    conflict_command = re.sub(r"\\\s*\n\s*", " ", conflict_block).strip()
    try:
        conflict_argv = shlex.split(conflict_command)
    except ValueError:
        conflict_argv = []
    if conflict_argv != [
        "gc", "gastown", "polecat-step", "exec",
        "--convoy", "{{convoy_id}}",
        "--step-ref", "mol-polecat-work.workspace-setup",
        "--", "gc", "gastown", "polecat-conflict", "stage",
    ]:
        errors.append(
            "workspace-setup conflict fence must use the exact artifact-bound command"
        )
for forbidden in (
    "polecat-step",
    "polecat-lease",
    "gc bd ",
    "gc convoy ",
    "git ",
    "{{setup_command}}",
    "--allow-workspace-transition",
):
    if workspace_blocks and forbidden in workspace_blocks[0]:
        errors.append(
            f"workspace-setup reconstructs deterministic behavior via {forbidden!r}"
        )
if "POLECAT_WORKSPACE_EXECUTE_COMPLETE" not in workspace:
    errors.append("workspace-setup must require the durable execute receipt")
for step_id in expected:
    description = steps.get(step_id, {}).get("description", "")
    if "gc runtime drain-ack" in description:
        errors.append(
            f"{step_id}: raw drain-ack can re-wake an unblocked hard failure"
        )
for step_id in ("preflight-tests", "implement", "self-review"):
    description = steps.get(step_id, {}).get("description", "")
    for index, block in enumerate(
        re.findall(r"```bash\n(.*?)\n```", description, re.DOTALL), start=1
    ):
        cwd_sensitive = (
            "git " in block
            or any(
                marker in block
                for marker in (
                    "{{setup_command}}",
                    "{{typecheck_command}}",
                    "{{lint_command}}",
                    "{{build_command}}",
                    "{{test_command}}",
                    "{{affected_tests_command}}",
                )
            )
        )
        if cwd_sensitive and "gc gastown polecat-step exec" not in block:
            errors.append(
                f"{step_id} shell fence {index} bypasses artifact exec"
            )

if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
PY
    then
        fail "every non-terminal polecat worker stage must use exact validated completion"
    fi
    grep -F 'run_gc gastown polecat-step block' "$workspace_command" >/dev/null &&
        grep -F '"workspace.canonical-artifact-invalid"' "$workspace_command" >/dev/null &&
        grep -F '"workspace.artifact-path-collision"' "$workspace_command" >/dev/null &&
        grep -F '"workspace.unrecorded-branch-work"' "$workspace_command" >/dev/null &&
        grep -F '"workspace.recovered-branch-no-fork"' "$workspace_command" >/dev/null &&
        grep -F 'flock -n "$SETUP_LOCK_FD"' "$workspace_command" >/dev/null &&
        grep -F '"workspace.setup-execution-ambiguous"' "$workspace_command" >/dev/null &&
        grep -F 'run_gc mail send "$WITNESS_TARGET"' "$workspace_command" >/dev/null ||
        fail "workspace command must durably quarantine unsafe artifact and branch state"
    grep -F 'GIT_INDEX_FILE="$INDEX_COPY"' "$conflict_command" >/dev/null &&
        grep -F '"create $CONFLICT_DONE_REF $EXPECTED_TREE"' "$conflict_command" >/dev/null &&
        grep -F 'revalidate_authority' "$conflict_command" >/dev/null ||
        fail "conflict command must bind staging to an immutable authority proof"
    if ! python3 - "$prompt" "$fragment" <<'PY'
import sys

def guard(path):
    text = open(path, encoding="utf-8").read()
    begin = "# BEGIN_GASTOWN_SUBMIT_GUARD"
    end = "# END_GASTOWN_SUBMIT_GUARD"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit(1)
    return text.split(begin, 1)[1].split(end, 1)[0]

if guard(sys.argv[1]) != guard(sys.argv[2]):
    raise SystemExit(1)
PY
    then
        fail "polecat prompt and approval fragment must carry the same submit guard"
    fi

    grep -F 'gc gastown polecat-submit guard' "$prompt" "$fragment" >/dev/null ||
        fail "done-state guards must delegate to the deterministic submit command"
    grep -F 'polecat-submit.v1' "$prompt" "$fragment" >/dev/null &&
        grep -F 'gc gastown polecat-submit complete' "$prompt" "$fragment" >/dev/null &&
        grep -F 'if ! gc runtime drain-ack' "$prompt" "$fragment" >/dev/null ||
        fail "terminal guard callers must strictly validate, complete, and acknowledge drain"
    ! sed -n '/BEGIN_GASTOWN_SUBMIT_GUARD/,/END_GASTOWN_SUBMIT_GUARD/p' "$fragment" |
        grep -E 'gc hook --claim|gc bd (list|show|update)' >/dev/null ||
        fail "done-state guard must not claim or reconstruct submit state"
    [[ "$(grep -cF 'gc gastown polecat-submit execute' "$formula")" -eq 1 ]] ||
        fail "terminal stage must delegate exactly once to deterministic submit execute"
    ! grep -F 'gc gastown polecat-submit complete' "$formula" >/dev/null &&
        ! grep -F 'gc gastown polecat-lease submit' "$formula" >/dev/null ||
        fail "terminal formula must not reconstruct lease or completion behavior"
    ! grep -F 'EXPECTED_ASSIGNEE="${BEADS_ACTOR' "$formula" "$prompt" "$fragment" >/dev/null ||
        fail "submit paths must not retain single-precedence identity logic"
    ! grep -F 'gc hook' "$submit_command" >/dev/null ||
        fail "deterministic submit command must never claim unrelated work"
    grep -F 'RUNTIME_IDENTITIES+=("$value")' "$submit_command" >/dev/null &&
        grep -F 'STEP_ASSIGNEE' "$submit_command" >/dev/null &&
        grep -F 'CURRENT_SESSION_ID=${GC_SESSION_ID:-}' "$submit_command" >/dev/null &&
        grep -F '"polecat-submit.v1"' "$submit_command" >/dev/null &&
        grep -F 'replay_closed_step' "$submit_command" >/dev/null &&
        grep -F 'gc.polecat_submit_convoy' "$submit_command" >/dev/null &&
        grep -F 'gc.polecat_submit_version' "$submit_command" >/dev/null &&
        grep -F 'SOURCE_BRANCH_READY' "$submit_command" >/dev/null &&
        grep -F 'revalidate_context' "$submit_command" >/dev/null &&
        grep -F 'prepare_execute_artifact' "$submit_command" >/dev/null &&
        grep -F 'verify_submit_proof' "$submit_command" >/dev/null &&
        grep -F 'POLECAT_SUBMIT_EXECUTE_COMPLETE' "$submit_command" >/dev/null ||
        fail "submit command must bind identities, source evidence, and mutation readback"
    if ! python3 - "$submit_command" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
start = text.rindex('\nif [[ "$ACTION" == "guard" ]]; then') + 1
guard = text[start:text.index("\nevidence_matches ||", start)]
if "close_step" in guard or "run_gc_bd update" in guard:
    raise SystemExit("guard branch must remain read-only")
PY
    then
        fail "submit guard must never mutate either source or workflow step"
    fi
    if ! python3 - "$step_command" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
start = text.index('if [[ "$ACTION" == "exec" ]]; then')
end = text.index('if ! run_gc_bd update "$STEP_BEAD_ID"', start)
branch = text[start:end]
required = (
    'run_gc_convoy status "$CONVOY_ID" --json',
    ".metadata.artifact_dir",
    "validate_artifact_context()",
    'rig_namespace="$CITY_ROOT/.gc/worktrees/$RUNTIME_RIG"',
    'canonical_artifact="$rig_namespace_real/artifacts/worktrees/$SOURCE_ID"',
    "worktree list --porcelain -z",
    'read_one_line_file "$artifact_real/.git"',
    'read_one_line_file "$admin_real/gitdir"',
    'cd -- "$ARTIFACT_REAL"',
    'validate_artifact_context "."',
    'exec -- "${EXEC_ARGV[@]}"',
)
for fragment in required:
    if fragment not in branch:
        raise SystemExit(f"artifact exec contract missing: {fragment}")
if "run_gc_bd update" in branch or "eval " in branch:
    raise SystemExit("artifact exec must remain mutation-free and no-eval")
if text.index('exec -- "${EXEC_ARGV[@]}"') > end:
    raise SystemExit("artifact exec does not terminate before completion mutation")
PY
    then
        fail "polecat step artifact executor is not read-only or fail-closed"
    fi
    ! grep -F 'gc bd close "$WORK_BEAD_ID"' "$formula" >/dev/null ||
        fail "polecat formula must never close the source work bead"
    grep -F 'Every process generation and every' "$prompt" >/dev/null &&
        grep -F 'gc gastown polecat-step exec --convoy ... --step-ref ... -- <argv>' "$prompt" >/dev/null &&
        grep -F 'A prior `cd`, `$PWD`, or shell variable is never' "$prompt" >/dev/null &&
        grep -F 'For a non-shell file tool' "$prompt" >/dev/null ||
        fail "polecat prompt must not assume workspace-setup cwd survives later stages"
    if ! python3 - "$prompt" <<'PY'
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
start = text.index("For a lighter context handoff")
end = text.index("## Rejection-Aware Resume", start)
handoff = text[start:end]
if "gc runtime request-restart" not in handoff:
    raise SystemExit("lighter handoff must request a controller restart")
if "gc runtime drain-ack" in handoff:
    raise SystemExit("lighter handoff must not raw-drain assigned demand")
if "recipe command fails, drain and" in text:
    raise SystemExit("recipe-read failure must not raw-drain assigned demand")
if (
    "If the exact recipe command fails, escalate" not in text
    or "leave the assigned source and workflow step unchanged" not in text
):
    raise SystemExit("recipe-read failure lacks fail-closed assigned-state guidance")
quick = next(
    line for line in text.splitlines()
    if "| Handoff to next session |" in line
)
if "gc runtime request-restart" not in quick or "drain-ack" in quick:
    raise SystemExit("handoff quick-reference contradicts restart contract")
PY
    then
        fail "polecat prompt retains an unsafe raw-drain handoff"
    fi
    ! grep -F 'done sequence — branch-shape gate' "$prompt" >/dev/null ||
        fail "polecat final reminder must not retain the pre-artifact-entry sequence"

    if ! python3 - "$formula" "$workspace_command" "$submit_command" <<'PY'
import re
import sys
import tomllib

formula_path, workspace_command_path, command_path = sys.argv[1:]
formula_text = open(formula_path, encoding="utf-8").read()
workspace_command_text = open(workspace_command_path, encoding="utf-8").read()
command_text = open(command_path, encoding="utf-8").read()
with open(formula_path, "rb") as handle:
    document = tomllib.load(handle)
submit = next(
    step["description"]
    for step in document.get("steps", [])
    if step.get("id") == "submit-and-exit"
)
shell_blocks = re.findall(r"```bash\n(.*?)\n```", submit, re.DOTALL)
if len(shell_blocks) != 1:
    raise SystemExit("terminal submit must use exactly one shell fence")
block = shell_blocks[0]
execute = "gc gastown polecat-submit execute"
if submit.count(execute) != 1 or block.count(execute) != 1:
    raise SystemExit("terminal submit must invoke deterministic execute exactly once")
if f"if ! {execute}; then" not in block:
    raise SystemExit("terminal submit must fail closed when execute fails")
if block.count("gc ") != 1:
    raise SystemExit("terminal submit shell fence must contain one gc command")
for forbidden in (
    "polecat-lease",
    "polecat-submit guard",
    "polecat-submit complete",
    "gc bd ",
    "gc runtime ",
    "gc session ",
    "git ",
):
    if forbidden in block:
        raise SystemExit(f"terminal submit reconstructs delegated behavior: {forbidden}")
if "POLECAT_SUBMIT_EXECUTE_COMPLETE" not in submit:
    raise SystemExit("terminal submit must require the durable execute receipt")

workspace_execute = formula_text.index("gc gastown polecat-workspace execute")
terminal_execute = formula_text.index(execute)
if not workspace_execute < terminal_execute:
    raise SystemExit("workspace and submit execute order drifted")
for fragment in (
    "run_gc gastown polecat-lease workspace",
    "ROOT_SETUP_COMMAND",
    "gc.polecat_workspace_version",
    "run_gc gastown polecat-step complete",
    "POLECAT_WORKSPACE_EXECUTE_COMPLETE",
):
    if fragment not in workspace_command_text:
        raise SystemExit(f"deterministic workspace command is missing {fragment!r}")

execute_start = command_text.index("execute_submit() {")
execute_end = command_text.index(
    'if [[ "$ACTION" == "execute" ]]; then', execute_start
)
execute_body = command_text[execute_start:execute_end]
ordered = (
    "prepare_execute_artifact",
    "run_gc gastown polecat-lease submit",
    "execute_terminal_update",
    "close_step pass",
    'run_gc runtime drain-ack',
    "POLECAT_SUBMIT_EXECUTE_COMPLETE",
)
positions = [execute_body.index(fragment) for fragment in ordered]
if positions != sorted(positions):
    raise SystemExit("deterministic execute transaction ordering drifted")
for fragment in (
    "prepare_submit_proof_context",
    "verify_submit_proof",
    "execution_evidence_matches",
    'run_gc session wake "$REFINERY_TARGET"',
):
    if fragment not in execute_body:
        raise SystemExit(f"deterministic execute is missing {fragment!r}")
PY
    then
        fail "deterministic submit delegation or transaction ordering drifted"
    fi
    ! grep -F 'git push' "$formula" >/dev/null ||
        fail "formula prose must delegate every push to the deterministic command"
    grep -F 'option no-deref' "$lease_command" >/dev/null &&
        grep -F '"create $EXPECTED_REF $EXPECTED_OID"' "$lease_command" >/dev/null &&
        grep -F '"create $SUBMIT_REF $head_oid"' "$lease_command" >/dev/null &&
        grep -F -- '--force-with-lease="$BRANCH_REF:$EXPECTED_OID"' "$lease_command" >/dev/null &&
        grep -F -- '-- "$PUSH_URL" "$SUBMIT_REF:$BRANCH_REF"' "$lease_command" >/dev/null &&
        grep -F '"delete $SUBMIT_REF $SUBMIT_OID"' "$lease_command" >/dev/null ||
        fail "lease command must retain exact no-deref capture/freeze/push/cleanup primitives"
    ! grep -E 'git push[[:space:]]+(--force|-f)([[:space:]]|$)' "$lease_command" >/dev/null ||
        fail "polecat lease command must never use an unconditional force push"
    grep -F 'auto_push=false is unsupported for a rejection-rebased branch' \
        "$lease_command" >/dev/null ||
        fail "rejected auto_push=false must stop before creating a dead-end frozen submit"
    grep -F '`polecat_push_lease_*`' "$prompt" >/dev/null &&
        grep -F 'authoritative repo-local lease refs' "$prompt" >/dev/null ||
        fail "polecat prompt must distinguish lease refs from the metadata mirror"
}

test_polecat_workflow_is_fail_fast_scoped() {
    local formula="$GASTOWN/formulas/mol-polecat-work.toml"

    if ! python3 - "$formula" <<'PY'
import sys
import tomllib

path = sys.argv[1]
with open(path, "rb") as handle:
    document = tomllib.load(handle)

expected = {
    "load-context": ("setup", []),
    "workspace-setup": ("setup", ["load-context"]),
    "preflight-tests": ("member", ["workspace-setup"]),
    "implement": ("member", ["preflight-tests"]),
    "self-review": ("member", ["implement"]),
    "submit-and-exit": ("member", ["self-review"]),
}
errors = []
steps = {}
for step in document.get("steps", []):
    step_id = step.get("id")
    if step_id in steps:
        errors.append(f"duplicate step id {step_id!r}")
    steps[step_id] = step

body = steps.get("body", {})
body_metadata = body.get("metadata", {})
if body_metadata.get("gc.kind") != "scope":
    errors.append("body must be a scope")
if body_metadata.get("gc.scope_name") != "polecat-work":
    errors.append("body must use the polecat-work scope name")
if body_metadata.get("gc.scope_role") != "body":
    errors.append("body must use the body scope role")
if set(body.get("needs", [])) != set(expected):
    errors.append("body must depend on every worker stage")

for step_id, (role, needs) in expected.items():
    step = steps.get(step_id)
    if not step:
        errors.append(f"{step_id} must be redeclared by the child formula")
        continue
    metadata = step.get("metadata", {})
    if metadata.get("gc.scope_ref") != "body":
        errors.append(f"{step_id} must reference body")
    if metadata.get("gc.scope_role") != role:
        errors.append(f"{step_id} must use scope role {role}")
    if metadata.get("gc.on_fail") != "abort_scope":
        errors.append(f"{step_id} must abort the scope on failure")
    if metadata.get("gc.continuation_group") != "polecat-work":
        errors.append(f"{step_id} must stay in the polecat-work continuation group")
    if metadata.get("gc.session_affinity") != "require":
        errors.append(f"{step_id} must require session affinity")
    if step.get("needs", []) != needs:
        errors.append(f"{step_id} needs {step.get('needs', [])!r}, want {needs!r}")

teardowns = [
    step.get("id")
    for step in document.get("steps", [])
    if step.get("metadata", {}).get("gc.scope_ref") == "body"
    and step.get("metadata", {}).get("gc.scope_role") == "teardown"
]
if teardowns:
    errors.append(f"hard-failure evidence must not be removed by teardown steps: {teardowns!r}")

if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
PY
    then
        fail "polecat worker stages must compile inside one fail-fast body scope"
    fi
}

test_review_leg_contract_forbids_synthetic_mutation() {
    local formula prompt
    formula="$GASTOWN/formulas/mol-review-leg.toml"
    prompt="$GASTOWN/agents/polecat/prompt.template.md"

    grep -F 'Do not create synthetic/test beads' "$formula" >/dev/null ||
        fail "review-leg formula must forbid synthetic test beads"
    grep -F 'Do not create test beads' "$formula" >/dev/null ||
        fail "review-leg load-assignment must forbid test bead creation"
    grep -F 'The only allowed bead mutations are the formula-prescribed' "$formula" >/dev/null ||
        fail "review-leg formula must define allowed mutation boundary"
    grep -F 'treat that text as' "$formula" >/dev/null ||
        fail "review-leg formula must treat plans/checklists as review subject matter"
    grep -F 'Do not start cities, spawn sessions, route extra work' "$formula" >/dev/null ||
        fail "review-leg formula must forbid executing reviewed checklist items"
    grep -F 'Formula-specific non-implementation assignments may explicitly tell you' "$prompt" >/dev/null ||
        fail "polecat prompt must allow formula-specific review/control close steps"
    ! grep -F '`gc bd close`, `gc bd close`' "$prompt" >/dev/null ||
        fail "polecat prompt must not duplicate its close prohibition"
    grep -F 'Default implementation formula: `mol-polecat-work`' "$prompt" >/dev/null ||
        fail "polecat prompt must describe mol-polecat-work as the default implementation formula"
    ! grep -F '**You MUST NOT close beads. EVER. No exceptions.**' "$prompt" >/dev/null ||
        fail "polecat prompt must not globally forbid review-leg close steps"
}

test_refinery_direct_merge_is_worktree_safe_and_fail_closed() {
    local formula direct_block
    formula="$GASTOWN/formulas/mol-refinery-patrol.toml"

    direct_block=$(python3 - "$formula" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
start = text.index('**If MERGE_STRATEGY = "direct"')
end = text.index('**If MERGE_STRATEGY = "mr"')
print(text[start:end])
PY
)

    [[ "$direct_block" == *'git worktree add --detach "$MERGE_WT" "origin/$TARGET"'* ]] ||
        fail "direct refinery merge must use a detached target worktree"
    [[ "$direct_block" == *'+refs/heads/${TARGET}:refs/remotes/origin/${TARGET}'* ]] ||
        fail "direct refinery merge refspecs must brace TARGET for zsh-safe expansion"
    [[ "$direct_block" == *'git -C "$MERGE_WT" push origin "HEAD:$TARGET"'* ]] ||
        fail "direct refinery merge must push the verified merge worktree HEAD"
    [[ "$direct_block" == *'[ "$MERGED_SHA" != "$REMOTE" ]'* ]] ||
        fail "direct refinery merge must compare merged SHA to origin target"
    [[ "$direct_block" == *'STOP. Do not mutate bead state.'* ]] ||
        fail "direct refinery merge must fail closed before metadata writes"
    ! printf '%s\n' "$direct_block" | grep -E '^[[:space:]]*git checkout \$TARGET([[:space:]]|$)' >/dev/null ||
        fail "direct refinery merge must not checkout target branch in the active worktree"

    python3 - "$formula" <<'PY' || fail "direct refinery merge must verify origin before setting merged metadata"
import sys
text = open(sys.argv[1], encoding="utf-8").read()
start = text.index('**If MERGE_STRATEGY = "direct"')
end = text.index('**If MERGE_STRATEGY = "mr"')
block = text[start:end]
verify = block.index('[ "$MERGED_SHA" != "$REMOTE" ]')
metadata = block.index('--set-metadata merge_result=merged')
if verify >= metadata:
    raise SystemExit(1)
PY
}

test_submit_generation_lifecycle_contract() {
    if ! python3 - \
        "$GASTOWN/formulas/mol-polecat-work.toml" \
        "$GASTOWN/formulas/mol-refinery-patrol.toml" \
        "$GASTOWN/formulas/mol-witness-patrol.toml" \
        "$GASTOWN/agents/refinery/prompt.template.md" \
        "$GASTOWN/agents/witness/prompt.template.md" \
        "$GASTOWN/commands/polecat-submit/run.sh" <<'PY'
from pathlib import Path
import sys

polecat, refinery, witness, refinery_prompt, witness_prompt, submit = (
    Path(name).read_text(encoding="utf-8") for name in sys.argv[1:]
)
if polecat.count("gc gastown polecat-submit execute") != 1:
    raise SystemExit("formula must delegate its terminal transaction exactly once")
if "gc.polecat_submit_convoy" in polecat:
    raise SystemExit("formula must not reconstruct submit-generation mutation")

terminal_update = submit.split("execute_terminal_update() {", 1)[1].split(
    "\nexecute_submit() {", 1
)[0]
token_set = '--set-metadata "gc.polecat_submit_convoy=$CONVOY_ID"'
if terminal_update.count(token_set) != 2:
    raise SystemExit("both deterministic source transitions must bind the exact convoy")
for fragment in (
    '--set-metadata "branch=$CANONICAL_SOURCE_BRANCH"',
    '--set-metadata "target=$ROOT_BASE_BRANCH"',
    '--set-metadata "gc.polecat_submit_execute_version=$EXECUTE_VERSION"',
    '--set-metadata "gc.polecat_submit_lease_version=$LEASE_EVIDENCE_VERSION"',
    '--set-metadata "gc.polecat_submit_proof_key=$EXECUTE_PROOF_KEY"',
    "--unset-metadata artifact_source_sha",
    "--unset-metadata artifact_cleanup_state",
):
    if terminal_update.count(fragment) != 2:
        raise SystemExit(f"both deterministic source transitions must retain {fragment}")
for fragment in (
    '--status=open --assignee=""',
    "--set-metadata branch_ready=true",
    "--set-metadata halt_reason=auto_push_false",
):
    if fragment not in terminal_update:
        raise SystemExit(f"auto_push=false transition missing {fragment}")
for fragment in (
    '--status=open --assignee="$REFINERY_TARGET"',
    "--unset-metadata branch_ready",
    "--unset-metadata halt_reason",
):
    if fragment not in terminal_update:
        raise SystemExit(f"refinery transition missing {fragment}")

execute = submit.split("execute_submit() {", 1)[1].split(
    '\nif [[ "$ACTION" == "execute" ]]', 1
)[0]
proof = execute.index("verify_submit_proof")
transition = execute.index("execute_terminal_update")
completion = execute.index("close_step pass")
drain = execute.index("run_gc runtime drain-ack")
if not proof < transition < completion < drain:
    raise SystemExit("proof, terminal mutation, close, and drain order drifted")

delete = 'gc workflow delete-source "$WORK" --apply'
delete_positions = []
start = 0
while True:
    position = refinery.find(delete, start)
    if position < 0:
        break
    delete_positions.append(position)
    start = position + 1
if len(delete_positions) != 2:
    raise SystemExit("expected two refinery rejection reopen paths")
for position in delete_positions:
    before = refinery[max(0, position - 2600):position]
    after = refinery[position:position + 1800]
    clear = before.rfind("--unset-metadata gc.polecat_submit_convoy")
    rejection = before.rfind("--set-metadata rejection_reason=")
    readback = before.rfind("PRE_REOPEN_JSON")
    ownership = before.rfind('.assignee == $owner')
    rejection_readback = before.rfind(
        ".metadata.rejection_reason == $rejection"
    )
    if min(clear, rejection, readback, ownership, rejection_readback) < 0:
        raise SystemExit("refinery pre-reopen generation/rejection proof is incomplete")
    if not max(clear, rejection) < readback < min(ownership, rejection_readback):
        raise SystemExit("refinery must stage rejection then read back ownership before reopen")
    reopen = after.find('gc workflow reopen-source "$WORK"')
    route = after.find("--set-metadata gc.routed_to=")
    defensive = after.find("--unset-metadata gc.polecat_submit_convoy", reopen)
    final_readback = after.find("REQUEUE_JSON", reopen)
    if min(reopen, route, defensive, final_readback) < 0 or not (
        reopen < route <= defensive < final_readback
    ):
        raise SystemExit("refinery must defensively clear while routing after reopen")

witness_delete = witness.index("gc workflow delete-source <bead> --apply")
witness_before = witness[max(0, witness_delete - 3600):witness_delete]
witness_after = witness[witness_delete:witness_delete + 2200]
for fragment in (
    "confirm_orphan_still_unowned",
    "--unset-metadata gc.polecat_submit_convoy",
    "TOKEN_CLEAR_JSON",
    '.assignee == $owner',
    "Orphan ownership or liveness changed after generation clear",
):
    if fragment not in witness_before:
        raise SystemExit(f"witness pre-reopen gate missing {fragment}")
for fragment in (
    "gc workflow reopen-source <bead>",
    "--set-metadata gc.routed_to=",
    "--unset-metadata gc.polecat_submit_convoy",
    "RESET_JSON",
):
    if fragment not in witness_after:
        raise SystemExit(f"witness post-reopen proof missing {fragment}")

for text, role in ((refinery_prompt, "refinery"), (witness_prompt, "witness")):
    if "gc.polecat_submit_convoy" not in text:
        raise SystemExit(f"{role} prompt lacks generation lifecycle guidance")
if "read back" not in refinery_prompt:
    raise SystemExit("refinery prompt lacks pre-reopen readback guidance")
prompt_reopen = refinery_prompt.index('gc workflow reopen-source "$WORK"')
prompt_before = refinery_prompt[:prompt_reopen]
prompt_after = refinery_prompt[prompt_reopen:]
for fragment in (
    "REJECTION_REASON=",
    "--unset-metadata gc.polecat_submit_convoy",
    '--set-metadata rejection_reason="$REJECTION_REASON"',
    "PRE_REOPEN_JSON",
    ".metadata.rejection_reason == $rejection",
):
    if fragment not in prompt_before:
        raise SystemExit(f"refinery prompt pre-reopen contract missing {fragment}")
for fragment in (
    "REQUEUE_JSON",
    "--unset-metadata gc.polecat_submit_convoy",
    ".metadata.rejection_reason == $rejection",
    '.metadata["gc.routed_to"] == $route',
):
    if fragment not in prompt_after:
        raise SystemExit(f"refinery prompt post-reopen contract missing {fragment}")
if "exact liveness check" not in witness_prompt:
    raise SystemExit("witness prompt lacks post-clear liveness guidance")
PY
    then
        fail "submit-generation handoff/reset ordering contract drifted"
    fi
}

test_witness_surfaces_durable_polecat_blocks() {
    local formula prompt command help
    formula="$GASTOWN/formulas/mol-witness-patrol.toml"
    prompt="$GASTOWN/agents/witness/prompt.template.md"
    command="$GASTOWN/commands/polecat-blocks/run.sh"
    help="$GASTOWN/commands/polecat-blocks/help.md"

    [[ -x "$command" ]] ||
        fail "polecat-blocks surfacing command should exist and be executable"
    [[ -f "$help" ]] ||
        fail "polecat-blocks surfacing help should be packaged"
    parse_toml "$formula"

    if ! python3 - "$formula" "$prompt" "$command" "$help" <<'PY'
import pathlib
import sys
import tomllib

formula_path, prompt_path, command_path, help_path = map(pathlib.Path, sys.argv[1:])
with formula_path.open("rb") as handle:
    formula = tomllib.load(handle)
prompt = prompt_path.read_text()
command = command_path.read_text()
help_text = help_path.read_text()

steps = formula.get("steps", [])
by_id = {step.get("id"): step for step in steps}
required = {
    "check-inbox",
    "surface-polecat-blocks",
    "recover-orphaned-beads",
    "check-polecat-health",
}
if not required.issubset(by_id):
    raise SystemExit("witness patrol lacks the durable-block surfacing chain")
surface = by_id["surface-polecat-blocks"]
if surface.get("needs") != ["check-inbox"]:
    raise SystemExit("durable-block surfacing must immediately follow inbox")
if by_id["recover-orphaned-beads"].get("needs") != ["surface-polecat-blocks"]:
    raise SystemExit("orphan recovery must wait for durable-block surfacing")
surface_text = surface.get("description", "")
surface_words = " ".join(surface_text.split())
if surface_text.count("gc gastown polecat-blocks surface") != 1:
    raise SystemExit("witness patrol must invoke the surfacer exactly once")
for fragment in (
    "all statuses",
    "gc.polecat_block_version=1",
    "valid, partial, or malformed",
    "at least once",
    "signature receipt",
    "Quarantined",
    "surfacing only",
    "Do not change source/step status",
    "Do not attempt an in-place unblock",
):
    if fragment not in surface_words:
        raise SystemExit(f"witness surface step lacks {fragment!r}")

for step_id in ("recover-orphaned-beads", "check-polecat-health"):
    text = by_id[step_id].get("description", "")
    if "gc.polecat_block_version=1" not in text:
        raise SystemExit(f"{step_id} does not exclude durable block rows")
    if "surface-polecat-blocks" not in text:
        raise SystemExit(f"{step_id} does not defer to the block surfacer")

for fragment in (
    "gc gastown polecat-blocks surface",
    "direct rig store",
    "gc.polecat_block_version=1",
    "partial/malformed",
    "Mayor at least once",
    "signature receipt",
    "Quarantine",
    "Exclude every v1-marked row",
    "never attempt an in-place unblock",
):
    if fragment not in prompt:
        raise SystemExit(f"witness prompt lacks {fragment!r}")

for text, label in ((command, "command"), (help_text, "help")):
    for fragment in (
        "gc.polecat_block_version",
        "gc.polecat_block_alert_version",
        "gc.polecat_block_alert_signature",
    ):
        if fragment not in text:
            raise SystemExit(f"polecat-blocks {label} lacks {fragment!r}")
for fragment in (
    "GC_NO_API=1",
    "GC_STORE_SCOPE=rig",
    "list --all",
    "sha256_stream",
    "bounded_text",
    "row_count=$GROUP_COUNT row_ids=$ROW_IDS_LABEL",
    "mail send mayor/",
    "run_gc_bd update",
):
    if fragment not in command:
        raise SystemExit(f"polecat-blocks command lacks {fragment!r}")
if "rows=$GROUP_COMPACT" in command:
    raise SystemExit("polecat-blocks mail must not embed unbounded full rows")
if "${" + "digest,," + "}" in command:
    raise SystemExit("polecat-blocks must remain compatible with Bash 3.2")

mail = command.index("mail send mayor/")
update = command.index('run_gc_bd update "$ANCHOR_ID"')
verify = command.index("VERIFY_JSON=", update)
if not mail < update < verify:
    raise SystemExit("block receipt must be written only after Mayor mail")
update_body = command[update:verify]
if update_body.count("--set-metadata") != 2:
    raise SystemExit("block receipt update must write exactly two fields")
for forbidden in ("--status", "--assignee", "--unset-metadata"):
    if forbidden in update_body:
        raise SystemExit(f"block receipt update may not use {forbidden}")
PY
    then
        fail "witness durable polecat-block surfacing contract drifted"
    fi
}

test_dog_assets_are_pack_local
test_retired_dog_formulas_are_not_reintroduced
test_shutdown_dance_contracts_are_executable
test_shutdown_dance_lifecycle_and_audit_contracts
test_composition_is_documented
test_polecat_startup_uses_scripted_hook_claim
test_polecat_submit_guard_and_step_completion_contracts
test_polecat_workflow_is_fail_fast_scoped
test_review_leg_contract_forbids_synthetic_mutation
test_refinery_direct_merge_is_worktree_safe_and_fail_closed
test_submit_generation_lifecycle_contract
test_witness_surfaces_durable_polecat_blocks

echo "gastown pack asset tests passed"
