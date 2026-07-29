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
    formula="$GASTOWN/formulas/mol-polecat-work.toml"
    prompt="$GASTOWN/agents/polecat/prompt.template.md"
    fragment="$GASTOWN/template-fragments/approval-fallacy.template.md"
    lease_command="$GASTOWN/commands/polecat-lease/run.sh"
    step_command="$GASTOWN/commands/polecat-step/run.sh"
    submit_command="$GASTOWN/commands/polecat-submit/run.sh"

    parse_toml "$formula"
    [[ -x "$lease_command" ]] ||
        fail "deterministic polecat lease command must be executable"
    [[ -x "$step_command" ]] ||
        fail "deterministic polecat step command must be executable"
    [[ -x "$submit_command" ]] ||
        fail "deterministic polecat submit command must be executable"
    ! grep -F 'gc hook' "$step_command" >/dev/null ||
        fail "polecat step completion must never claim unrelated work"
    grep -F 'gc.outcome=pass' "$step_command" >/dev/null &&
        grep -F 'gc.formula_contract' "$step_command" >/dev/null &&
        grep -F 'gc.input_convoy_id' "$step_command" >/dev/null ||
        fail "polecat step command must bind outcome, Graph-v2 root, and input convoy"
    if ! python3 - "$formula" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    document = tomllib.load(handle)

steps = {step["id"]: step for step in document.get("steps", [])}
expected = [
    "load-context",
    "workspace-setup",
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

if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
PY
    then
        fail "every non-terminal polecat worker stage must use exact validated completion"
    fi
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
    [[ "$(grep -cF 'gc gastown polecat-submit complete' "$formula")" -eq 2 ]] ||
        fail "normal and auto_push=false paths must each use deterministic submit completion"
    grep -F -- '--mode auto_push_false' "$formula" >/dev/null &&
        grep -F -- '--mode refinery' "$formula" >/dev/null ||
        fail "submit completion calls must select exact durable evidence modes"
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
        grep -F 'revalidate_context' "$submit_command" >/dev/null ||
        fail "submit command must bind identities, source evidence, and mutation readback"
    if ! python3 - "$submit_command" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
start = text.index('if [[ "$ACTION" == "guard" ]]; then', text.index("close_step()"))
guard = text[start:text.index("evidence_matches() {", start)]
if "close_step" in guard or "run_gc_bd update" in guard:
    raise SystemExit("guard branch must remain read-only")
PY
    then
        fail "submit guard must never mutate either source or workflow step"
    fi
    ! grep -F 'gc bd close "$WORK_BEAD_ID"' "$formula" >/dev/null ||
        fail "polecat formula must never close the source work bead"
    grep -F 'later formula stage may nevertheless resume in controller' "$prompt" >/dev/null &&
        grep -F 'first re-enters the exact source' "$prompt" >/dev/null ||
        fail "polecat prompt must not assume workspace-setup cwd survives later stages"
    ! grep -F 'done sequence — branch-shape gate' "$prompt" >/dev/null ||
        fail "polecat final reminder must not retain the pre-artifact-entry sequence"

    if ! python3 - "$formula" <<'PY'
import re
import sys
import tomllib

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
with open(path, "rb") as handle:
    document = tomllib.load(handle)
submit = next(
    step["description"]
    for step in document.get("steps", [])
    if step.get("id") == "submit-and-exit"
)
required_entry = (
    "expected exactly one source child",
    '(.[0] | type) == "object" and .[0].id == $source and',
    '(.[0].metadata | type) == "object" and',
    '(.[0].metadata.artifact_dir | type) == "string" and',
    'if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_RIG:-}" ] ||',
    'RIG_NAMESPACE="$CITY_ROOT/.gc/worktrees/$GC_RIG"',
    '[ "$RIG_NAMESPACE_REAL" != "$RIG_NAMESPACE" ]',
    'case "$ARTIFACT_DIR" in',
    '[ "$ARTIFACT_REAL" != "$ARTIFACT_DIR" ]',
    '[ "$PROVIDER_ROOT" != "$RIG_NAMESPACE_REAL/polecats" ]',
    "CURRENT_GIT_TOP=$(git rev-parse --show-toplevel 2>/dev/null)",
    '[ "$CURRENT_GIT_TOP" != "$ARTIFACT_DIR" ]',
    "ARTIFACT_COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)",
    'RIG_COMMON=$(git -C "$RIG_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)',
    '[ "$ARTIFACT_COMMON" != "$RIG_COMMON" ]',
)
for marker in (
    "# BEGIN_GASTOWN_POLECAT_SUBMIT_ARTIFACT_ENTRY",
    "# END_GASTOWN_POLECAT_SUBMIT_ARTIFACT_ENTRY",
):
    if submit.count(marker) != 1:
        raise SystemExit(f"submit stage must contain exactly one {marker}")

shell_blocks = re.findall(r"```bash\n(.*?)\n```", submit, re.DOTALL)
entry_blocks = [
    block
    for block in shell_blocks
    if "# BEGIN_GASTOWN_POLECAT_SUBMIT_ARTIFACT_ENTRY" in block
]
if len(entry_blocks) != 1:
    raise SystemExit(
        "artifact entry, branch check, final clean, and lease must share one shell fence"
    )
entry_block = entry_blocks[0]
for fragment in required_entry:
    if fragment not in entry_block:
        raise SystemExit(f"artifact entry contract is missing {fragment!r}")
exact_source_fragment = '(.[0] | type) == "object" and .[0].id == $source and'
if entry_block.count(exact_source_fragment) != 2:
    raise SystemExit("artifact and auto_push reads must each validate the exact source")
lease_auto_push = (
    'AUTO_PUSH=$(printf \'%s\' "$SOURCE_JSON"',
    '.[0].metadata.auto_push == false then "false"',
    '.[0].metadata.auto_push == true then "true"',
    'error("metadata.auto_push must be boolean")',
    'submit_artifact_entry_fail "could not resolve exact boolean source metadata.auto_push"',
    "false) AUTO_PUSH_BOOL=false ;;",
    '""|true) AUTO_PUSH_BOOL=true ;;',
)
for fragment in lease_auto_push:
    if fragment not in entry_block:
        raise SystemExit(f"lease auto_push guard is missing {fragment!r}")
if 'AUTO_PUSH=$(gc bd show "$WORK_BEAD_ID"' in entry_block:
    raise SystemExit("lease auto_push guard must reuse exact SOURCE_JSON")
final_clean = (
    "FINAL_STATUS=$(git status --porcelain)",
    'submit_artifact_entry_fail "could not inspect final task-artifact status"',
    'if [ -n "$FINAL_STATUS" ]; then',
    'submit_artifact_entry_fail "could not verify final task-artifact status"',
    'submit_artifact_entry_fail "task artifact is not clean after final capture"',
)
for fragment in final_clean:
    if fragment not in entry_block:
        raise SystemExit(f"lease final-clean guard is missing {fragment!r}")
if entry_block.count("FINAL_STATUS=$(git status --porcelain)") != 2:
    raise SystemExit("lease must inspect final status before and after capture")

entry_order = (
    "# BEGIN_GASTOWN_POLECAT_SUBMIT_ARTIFACT_ENTRY",
    'SOURCE_JSON=$(gc bd show "$WORK_BEAD_ID" --json 2>/dev/null)',
    'ARTIFACT_DIR=$(printf \'%s\' "$SOURCE_JSON"',
    'CANONICAL_ARTIFACT="$RIG_NAMESPACE_REAL/artifacts/worktrees/$WORK_BEAD_ID"',
    '\ncd -- "$ARTIFACT_DIR" ||',
    "CURRENT_GIT_TOP=$(git rev-parse --show-toplevel 2>/dev/null)",
    '[ "$ARTIFACT_COMMON" != "$RIG_COMMON" ]',
    "# END_GASTOWN_POLECAT_SUBMIT_ARTIFACT_ENTRY",
    "CURRENT_BRANCH=$(git branch --show-current)",
    "FINAL_STATUS=$(git status --porcelain)",
    'AUTO_PUSH=$(printf \'%s\' "$SOURCE_JSON"',
    "# BEGIN_GASTOWN_POLECAT_LEASE_SUBMIT",
    "gc gastown polecat-lease submit",
)
entry_positions = [entry_block.index(fragment) for fragment in entry_order]
if entry_positions != sorted(entry_positions):
    raise SystemExit(
        "submit stage must enter an exact contained same-repo artifact in the "
        "same invocation as branch, final-clean, and lease operations"
    )
for block in shell_blocks:
    if "git " not in block:
        continue
    if "# BEGIN_GASTOWN_POLECAT_SUBMIT_ARTIFACT_ENTRY" not in block:
        raise SystemExit("later submit fence contains cwd-dependent Git")
if submit.count("git branch --show-current") != 1:
    raise SystemExit("only the same-fence branch gate may inspect the current branch")
if 'BRANCH="$EXPECTED_BRANCH"' not in submit:
    raise SystemExit("auto_push=false must use the canonical expected branch")
if "git checkout --detach" in submit or "git branch -D" in submit:
    raise SystemExit("post-handoff cleanup must not mutate an inherited cwd")

handoff_blocks = [
    block
    for block in shell_blocks
    if "# BEGIN_GASTOWN_REFINERY_HANDOFF_CONTEXT" in block
]
completion_blocks = [
    block
    for block in shell_blocks
    if "# BEGIN_GASTOWN_REFINERY_COMPLETION_CONTEXT" in block
]
for marker in (
    "# BEGIN_GASTOWN_REFINERY_HANDOFF_CONTEXT",
    "# END_GASTOWN_REFINERY_HANDOFF_CONTEXT",
    "# BEGIN_GASTOWN_REFINERY_COMPLETION_CONTEXT",
    "# END_GASTOWN_REFINERY_COMPLETION_CONTEXT",
):
    if submit.count(marker) != 1:
        raise SystemExit(f"submit stage must contain exactly one {marker}")
if len(handoff_blocks) != 1:
    raise SystemExit("refinery handoff context and action must share one shell fence")
if len(completion_blocks) != 1:
    raise SystemExit("refinery completion context and action must share one shell fence")
handoff_block = handoff_blocks[0]
completion_block = completion_blocks[0]
handoff_contract = (
    '(.[0] | type) == "object" and .[0].id == $source and',
    '.[0].metadata.branch == $branch;',
    '((.[0].metadata | has("auto_push")) | not) or',
    ".[0].metadata.auto_push == true",
    '((.[0].metadata | has("gc.polecat_submit_convoy")) | not)',
    'then "proceed"',
    '(.[0].status | IN("open", "in_progress"))',
    ".[0].assignee == $refinery",
    '.[0].metadata["gc.polecat_submit_convoy"] == $convoy',
    '(.[0].metadata["gc.routed_to"] // "") == ""',
    '((.[0].metadata | has("branch_ready")) | not)',
    '((.[0].metadata | has("halt_reason")) | not)',
    'then "replay"',
    'elif .[0].status == "closed" and',
    "source is neither proceedable nor exact current-convoy handoff",
    'elif [ "$HANDOFF_ACTION" = "replay" ]; then',
    "Refinery handoff already exists for this exact convoy",
    "HANDOFF_SHAPE_OK=true",
    'elif [ "$HANDOFF_STATUS" = "closed" ]; then',
    "HANDOFF_ASSIGNEE_OK=true",
)
for fragment in handoff_contract:
    if fragment not in handoff_block:
        raise SystemExit(f"refinery handoff context is missing {fragment!r}")
handoff_exact_source = '(.[0] | type) == "object" and .[0].id == $source and'
if handoff_block.count(handoff_exact_source) != 2:
    raise SystemExit(
        "refinery handoff classification and readback must validate the exact source"
    )
for repeated_fragment in (
    '.[0].metadata["gc.polecat_submit_convoy"] == $convoy',
    '((.[0].metadata | has("branch_ready")) | not)',
    '((.[0].metadata | has("halt_reason")) | not)',
):
    if handoff_block.count(repeated_fragment) != 2:
        raise SystemExit(
            f"active and closed handoff replay must retain {repeated_fragment!r}"
        )
handoff_order = (
    "# BEGIN_GASTOWN_REFINERY_HANDOFF_CONTEXT",
    "CONVOY_STATUS=$(gc convoy status {{convoy_id}} --json 2>/dev/null)",
    "WORK_BEAD_ID=$(printf '%s' \"$CONVOY_STATUS\"",
    'EXPECTED_BRANCH="polecat/$WORK_BEAD_ID"',
    'REFINERY_TARGET="${GC_RIG:+$GC_RIG/}{{binding_prefix}}refinery"',
    'SOURCE_JSON=$(gc bd show "$WORK_BEAD_ID" --json 2>/dev/null)',
    'HANDOFF_ACTION=$(printf \'%s\' "$SOURCE_JSON"',
    "# END_GASTOWN_REFINERY_HANDOFF_CONTEXT",
    'if [ "$HANDOFF_ACTION" = "proceed" ]; then',
    'if ! gc bd update "$WORK_BEAD_ID"',
)
completion_order = (
    "# BEGIN_GASTOWN_REFINERY_COMPLETION_CONTEXT",
    "CONVOY_STATUS=$(gc convoy status {{convoy_id}} --json 2>/dev/null)",
    "WORK_BEAD_ID=$(printf '%s' \"$CONVOY_STATUS\"",
    'EXPECTED_BRANCH="polecat/$WORK_BEAD_ID"',
    "# END_GASTOWN_REFINERY_COMPLETION_CONTEXT",
    "# BEGIN_GASTOWN_REFINERY_STEP_COMPLETION",
    "gc gastown polecat-submit complete",
)
for label, block, order in (
    ("refinery handoff", handoff_block, handoff_order),
    ("refinery completion", completion_block, completion_order),
):
    positions = [block.index(fragment) for fragment in order]
    if positions != sorted(positions):
        raise SystemExit(f"{label} must derive exact context before its action")

workspace_lease = text.index('gc gastown polecat-lease workspace')
explicit_publish = text.index('gc gastown polecat-lease publish-rebase')
new_branch = text.index('git checkout -b "$BRANCH" "origin/{{base_branch}}"')
submit_lease = text.index('# BEGIN_GASTOWN_POLECAT_LEASE_SUBMIT')
manual_ready = submit.index('echo "auto_push=false: halting at branch-ready')
handoff_verified = submit.index('Refinery handoff did not verify exact status/assignee')
cleanup = submit.index('Local Git cleanup is deliberately skipped')
step_completion = submit.index('# BEGIN_GASTOWN_REFINERY_STEP_COMPLETION')
if not workspace_lease < explicit_publish < new_branch < submit_lease:
    raise SystemExit(1)
submit_lease_in_stage = submit.index('# BEGIN_GASTOWN_POLECAT_LEASE_SUBMIT')
if not submit_lease_in_stage < manual_ready < handoff_verified < cleanup < step_completion:
    raise SystemExit(1)
PY
    then
        fail "deterministic workspace/submit command and handoff cleanup ordering drifted"
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
    grep -F 'Local Git cleanup is deliberately skipped here' "$formula" >/dev/null ||
        fail "post-handoff cleanup must avoid cwd-dependent Git"
    grep -F 'The `gc bd update` in step 4 generates' "$formula" >/dev/null ||
        fail "refinery wake prose must reference the renumbered handoff step"

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
        "$GASTOWN/agents/witness/prompt.template.md" <<'PY'
from pathlib import Path
import sys

polecat, refinery, witness, refinery_prompt, witness_prompt = (
    Path(name).read_text(encoding="utf-8") for name in sys.argv[1:]
)
token_set = "--set-metadata gc.polecat_submit_convoy={{convoy_id}}"
if polecat.count(token_set) != 2:
    raise SystemExit("both source transitions must bind the exact convoy")

auto = polecat.split('if [ "$AUTO_PUSH" = "false" ]; then', 1)[1].split(
    "# BEGIN_GASTOWN_AUTO_PUSH_FALSE_STEP_COMPLETION", 1
)[0]
for fragment in (
    "--status=open --assignee=",
    '--set-metadata branch="$BRANCH"',
    "--set-metadata target={{base_branch}}",
    token_set,
    "--set-metadata branch_ready=true",
    "--set-metadata halt_reason=auto_push_false",
    "--set-metadata gc.routed_to=",
    "--unset-metadata artifact_source_sha",
    "--unset-metadata artifact_cleanup_state",
    "BRANCH_READY_CONVOY",
    "BRANCH_READY_TARGET",
    "BRANCH_READY_HALT",
    "BRANCH_READY_STALE_ARTIFACT",
):
    if fragment not in auto:
        raise SystemExit(f"auto_push=false transition missing {fragment}")

handoff = polecat.split(
    "**4. Atomically hand the exact source generation to the refinery:", 1
)[1].split("HANDOFF_JSON=", 1)[0]
if handoff.count('gc bd update "$WORK_BEAD_ID"') != 1:
    raise SystemExit("refinery handoff must use one source update")
for fragment in (
    "--status=open",
    '--assignee="$REFINERY_TARGET"',
    '--set-metadata branch="$EXPECTED_BRANCH"',
    "--set-metadata target={{base_branch}}",
    token_set,
    "--set-metadata gc.routed_to=",
    "--unset-metadata artifact_source_sha",
    "--unset-metadata artifact_cleanup_state",
    "--unset-metadata branch_ready",
    "--unset-metadata halt_reason",
):
    if fragment not in handoff:
        raise SystemExit(f"atomic refinery handoff missing {fragment}")
for fragment in (
    "HANDOFF_BRANCH",
    "HANDOFF_TARGET",
    "HANDOFF_CONVOY",
    "HANDOFF_ROUTED",
    "HANDOFF_STALE_GENERATION",
):
    if fragment not in polecat:
        raise SystemExit(f"refinery handoff readback missing {fragment}")
if polecat.count("if ! gc runtime drain-ack; then") < 2:
    raise SystemExit("both completion callers must fail on drain error")

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

echo "gastown pack asset tests passed"
