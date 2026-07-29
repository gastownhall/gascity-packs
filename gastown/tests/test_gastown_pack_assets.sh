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

test_polecat_startup_uses_standard_hook_claim() {
    local agent prompt propulsion
    agent="$GASTOWN/agents/polecat/agent.toml"
    prompt="$GASTOWN/agents/polecat/prompt.template.md"
    propulsion="$GASTOWN/template-fragments/propulsion.template.md"

    grep -F 'gc hook --claim --json' "$agent" >/dev/null ||
        fail "polecat nudge should call the standard hook claim path"
    grep -F 'default_sling_formula = "mol-polecat-work"' "$agent" >/dev/null ||
        fail "plain polecat sling must compile the implementation workflow instead of routing a bare task"
    grep -F 'gc hook --claim --json' "$prompt" >/dev/null ||
        fail "polecat prompt should call the standard hook claim path"
    grep -F 'gc hook --claim --json' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment should call the standard hook claim path"
    grep -F 'After closing any formula step bead, immediately run' "$prompt" >/dev/null ||
        fail "polecat prompt must require hook continuation after each formula step"
    grep -F 'Poll up to 60 seconds (6 attempts, 10 seconds apart)' "$prompt" >/dev/null &&
        grep -F 'for i in $(seq 1 6); do' "$prompt" >/dev/null &&
        grep -F 'sleep 10' "$prompt" >/dev/null &&
        grep -F 'gc hook --claim --drain-ack --json' "$prompt" >/dev/null ||
        fail "polecat prompt must wait through bounded control gaps before draining"
    grep -F 'After closing a step bead,' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment must require hook continuation after each formula step"
    grep -F 'bounded 60-second' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment must preserve the poll-before-drain contract"
    ! grep -F 'run `gc hook` or' "$prompt" >/dev/null ||
        fail "polecat prompt must not regress to an unclaimed hook/work-query choice"
    ! grep -F 'run `gc hook` or' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment must not regress to an unclaimed hook/work-query choice"
}

test_polecat_submit_guard_and_step_completion_contracts() {
    local formula prompt fragment lease_command
    formula="$GASTOWN/formulas/mol-polecat-work.toml"
    prompt="$GASTOWN/agents/polecat/prompt.template.md"
    fragment="$GASTOWN/template-fragments/approval-fallacy.template.md"
    lease_command="$GASTOWN/commands/polecat-lease/run.sh"

    parse_toml "$formula"
    [[ -x "$lease_command" ]] ||
        fail "deterministic polecat lease command must be executable"
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

    ! grep -F '[ "$WORK_STATUS" != "in_progress" ] || [ "$WORK_ASSIGNEE" != "$EXPECTED_ASSIGNEE" ]' "$prompt" "$fragment" >/dev/null ||
        fail "polecat guard must not treat every non-current source state as submitted"
    grep -F 'gc bd list --assignee "$EXPECTED_ASSIGNEE" --status=in_progress --limit=0 --json' "$fragment" >/dev/null ||
        fail "polecat guard must find its claimed step through an exact read-only session query"
    ! sed -n '/BEGIN_GASTOWN_SUBMIT_GUARD/,/END_GASTOWN_SUBMIT_GUARD/p' "$fragment" | grep -F 'gc hook --claim' >/dev/null ||
        fail "done-state guard must not claim unrelated routed work"
    grep -F '[ "$WORK_STATUS" = "closed" ] || [ "$WORK_ASSIGNEE" = "$REFINERY_TARGET" ]' "$fragment" >/dev/null ||
        fail "polecat guard must require closed or exact-refinery terminal evidence"
    grep -F -- '--set-metadata gc.outcome=fail --status=closed' "$fragment" >/dev/null ||
        fail "deterministic source ownership conflicts must terminalize the workflow step"
    [[ "$(grep -cF -- '--set-metadata gc.outcome=pass --status=closed' "$formula")" -eq 2 ]] ||
        fail "normal and auto_push=false submission paths must close the Graph-v2 step"
    [[ "$(grep -cF 'did not verify closed/pass; refusing to drain' "$formula")" -eq 2 ]] ||
        fail "both successful submission paths must verify step completion before drain"
    ! grep -F 'gc bd close "$WORK_BEAD_ID"' "$formula" >/dev/null ||
        fail "polecat formula must never close the source work bead"

    if ! python3 - "$formula" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
workspace_lease = text.index('gc gastown polecat-lease workspace')
explicit_publish = text.index('gc gastown polecat-lease publish-rebase')
new_branch = text.index('git checkout -B "$BRANCH" "origin/{{base_branch}}"')
submit_lease = text.index('# BEGIN_GASTOWN_POLECAT_LEASE_SUBMIT')
manual_ready = text.index('echo "auto_push=false: halting at branch-ready')
handoff_verified = text.index('Refinery handoff did not verify exact status/assignee')
cleanup = text.index('git checkout --detach')
step_completion = text.index('# BEGIN_GASTOWN_REFINERY_STEP_COMPLETION')
if not workspace_lease < explicit_publish < new_branch < submit_lease:
    raise SystemExit(1)
if not submit_lease < manual_ready < handoff_verified < cleanup < step_completion:
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
    grep -F 'Cleanup is best-effort after the verified durable handoff' "$formula" >/dev/null ||
        fail "post-handoff local cleanup must be explicitly best-effort"
    grep -F 'The `gc bd update` in step 5 generates' "$formula" >/dev/null ||
        fail "refinery wake prose must reference the renumbered handoff step"

    local resume_block
    resume_block=$(sed -n '/BEGIN_GASTOWN_RESUME_VERIFY/,/END_GASTOWN_RESUME_VERIFY/p' "$prompt")
    [[ "$resume_block" == *'startswith("mol-polecat-work.")'* ]] ||
        fail "restart verification must accept every mol-polecat-work Graph-v2 step"
    [[ "$resume_block" == *'.metadata["gc.root_bead_id"]'* ]] &&
        [[ "$resume_block" == *'.metadata["gc.input_convoy_id"]'* ]] ||
        fail "restart verification must prove workflow root/input convoy provenance"
    [[ "$resume_block" == *'.metadata["gc.kind"]'* ]] &&
        [[ "$resume_block" == *'.metadata["gc.formula_contract"]'* ]] &&
        [[ "$resume_block" == *'[ "$ROOT_KIND" != "workflow" ]'* ]] &&
        [[ "$resume_block" == *'[ "$ROOT_CONTRACT" != "graph.v2" ]'* ]] ||
        fail "restart verification must prove the root is a Graph-v2 workflow"
    [[ "$resume_block" == *'expected-open-unassigned'* ]] ||
        fail "restart verification must accept normal Graph-v2 source state"
    [[ "$resume_block" == *'RESUME_TERMINAL'* ]] &&
        [[ "$resume_block" == *'[ "$WORK_ASSIGNEE" = "$REFINERY_TARGET" ]'* ]] ||
        fail "post-handoff restart must recognize exact terminal refinery evidence"
    [[ "$resume_block" != *'$GC_BEAD_ID'* ]] ||
        fail "restart verification must not reinterpret GC_BEAD_ID as the source convoy"
    [[ "$resume_block" != *'OWNERSHIP_LOST'* ]] ||
        fail "restart verification must not derive workflow ownership from source state"
    [[ "$resume_block" != *'gc hook --claim'* ]] ||
        fail "read-only restart verification must not claim unrelated work"
    [[ "$resume_block" != *'gc runtime drain-ack'* ]] ||
        fail "indeterminate restart verification must preserve work for reclaim"
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

test_dog_assets_are_pack_local
test_retired_dog_formulas_are_not_reintroduced
test_shutdown_dance_contracts_are_executable
test_shutdown_dance_lifecycle_and_audit_contracts
test_composition_is_documented
test_polecat_startup_uses_standard_hook_claim
test_polecat_submit_guard_and_step_completion_contracts
test_polecat_workflow_is_fail_fast_scoped
test_review_leg_contract_forbids_synthetic_mutation
test_refinery_direct_merge_is_worktree_safe_and_fail_closed

echo "gastown pack asset tests passed"
