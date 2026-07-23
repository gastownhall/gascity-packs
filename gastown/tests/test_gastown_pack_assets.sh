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
    grep -F 'gc hook --claim --json' "$prompt" >/dev/null ||
        fail "polecat prompt should call the standard hook claim path"
    grep -F 'gc hook --claim --json' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment should call the standard hook claim path"
    grep -F 'After closing any formula step bead, immediately run' "$prompt" >/dev/null ||
        fail "polecat prompt must require hook continuation after each formula step"
    grep -F 'After closing a step bead,' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment must require hook continuation after each formula step"
    ! grep -F 'run `gc hook` or' "$prompt" >/dev/null ||
        fail "polecat prompt must not regress to an unclaimed hook/work-query choice"
    ! grep -F 'run `gc hook` or' "$propulsion" >/dev/null ||
        fail "polecat propulsion fragment must not regress to an unclaimed hook/work-query choice"
}

test_polecat_claim_infra_failure_escalates_without_drain_ack() {
    local prompt block
    prompt="$GASTOWN/agents/polecat/prompt.template.md"

    grep -F 'CLAIM_INFRA_FAILURE' "$prompt" >/dev/null ||
        fail "polecat claim loop must distinguish hook infrastructure failure from no-work"
    ! grep -F 'CLAIM_REJECTED gc hook --claim returned no workable bead after retries' "$prompt" >/dev/null ||
        fail "exhausted hook retries must not be reported as 'no workable bead'"

    # The terminal infra-failure path must escalate and exit non-zero WITHOUT
    # drain-ack: drain-ack reports idle and sleeps, hiding the outage from
    # town oversight in a wake->drain->sleep loop no health check can see.
    block="$(awk '/CLAIM_INFRA_FAILURE gc hook --claim failed after/{found=1} found{print} found && /^fi$/{exit}' "$prompt")"
    [[ "$block" == *'exit 1'* ]] ||
        fail "hook infrastructure failure must exit non-zero, not exit 0 like genuine no-work"
    [[ "$block" != *'gc runtime drain-ack'* ]] ||
        fail "hook infrastructure failure must NOT drain-ack — that reports idle and hides the outage"
    [[ "$block" == *'ESCALATION: gc hook --claim failing [HIGH]'* ]] ||
        fail "hook infrastructure failure must escalate to the witness"

    grep -F 'If it prints `CLAIM_INFRA_FAILURE`' "$prompt" >/dev/null ||
        fail "claim-block outcome guidance must cover CLAIM_INFRA_FAILURE"
}

test_polecat_claim_trusts_hook_receipt_when_direct_read_lags() {
    local prompt tmpdir fake_bin claim_script output calls claim_code
    prompt="$GASTOWN/agents/polecat/prompt.template.md"
    tmpdir="$(mktemp -d)"
    fake_bin="$tmpdir/bin"
    claim_script="$tmpdir/claim.sh"
    calls="$tmpdir/calls"
    mkdir -p "$fake_bin"

    # Execute the exact startup block from the asset. The hook returns the
    # authoritative successful claim observed in production, while the
    # immediately-following direct read repeatedly returns its stale
    # open/unassigned projection.
    python3 - "$prompt" >"$claim_script" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
start_marker = "bash <<'GC_CLAIM'\n"
start = text.index(start_marker) + len(start_marker)
end = text.index("\nGC_CLAIM", start)
print(text[start:end].replace("{{ .BindingPrefix }}", "gastown."))
PY
    cat >"$fake_bin/gc" <<'SH'
#!/bin/sh
printf '%s\n' "$*" >>"$GC_TEST_CALLS"
case "$*" in
  "hook --claim --json")
    if [ "${GC_TEST_SCENARIO:-}" = "claims_errored" ]; then
      printf '%s\n' '{"schema_version":"1","ok":true,"command":"hook","action":"drain","reason":"claims_errored"}'
      exit 1
    fi
    printf '%s\n' '{"schema_version":"1","ok":true,"command":"hook","action":"work","reason":"claimed","bead_id":"ac-3iv","assignee":"kisakcod/gastown.polecat-1","route":"kisakcod/gastown.polecat"}'
    ;;
  "bd show ac-3iv --json")
    printf '%s\n' '[{"id":"ac-3iv","status":"open","assignee":"","metadata":{"gc.routed_to":"kisakcod/gastown.polecat"}}]'
    ;;
  "mail send "*)
    exit 0
    ;;
  *)
    printf 'unexpected mutation after authoritative claim: %s\n' "$*" >&2
    exit 97
    ;;
esac
SH
    cat >"$fake_bin/sleep" <<'SH'
#!/bin/sh
exit 0
SH
    chmod +x "$fake_bin/gc" "$fake_bin/sleep" "$claim_script"

    output="$(
        PATH="$fake_bin:$PATH" \
        GC_TEST_CALLS="$calls" \
        GC_RIG="kisakcod" \
        GC_SESSION_NAME="kisakcod/gastown.polecat-1" \
        BEADS_ACTOR="kisakcod/gastown.polecat-1" \
        bash "$claim_script"
    )" || fail "schema-valid hook claim must survive a stale direct read"

    [[ "$output" == *'CLAIM_READ_STALE ac-3iv direct_status=open direct_assignee=unavailable'* ]] ||
        fail "stale direct claim projection should be diagnosed without overriding the hook receipt"
    [[ "$output" == *'CLAIMED_BEAD_ID=ac-3iv'* ]] ||
        fail "authoritative hook bead id must remain claimed when the direct read lags"
    [[ "$output" == *'CLAIMED_ASSIGNEE=kisakcod/gastown.polecat-1'* ]] ||
        fail "authoritative hook assignee must be preserved"
    [[ "$output" == *'CLAIMED_ROUTE=kisakcod/gastown.polecat'* ]] ||
        fail "authoritative hook route must be preserved"
    ! grep -F 'bd update' "$calls" >/dev/null ||
        fail "stale post-claim reads must never mutate or release the claimed bead"
    ! grep -F 'runtime drain-ack' "$calls" >/dev/null ||
        fail "stale post-claim reads must never drain-ack the worker"

    # A structured claims_errored result means routed work existed but its
    # claim mutation failed. It must remain an observable infrastructure
    # failure, never be laundered into the same drain path as genuine no_work.
    : >"$calls"
    set +e
    output="$(
        PATH="$fake_bin:$PATH" \
        GC_TEST_CALLS="$calls" \
        GC_TEST_SCENARIO="claims_errored" \
        GC_RIG="kisakcod" \
        GC_SESSION_NAME="kisakcod/gastown.polecat-1" \
        BEADS_ACTOR="kisakcod/gastown.polecat-1" \
        bash "$claim_script" 2>&1
    )"
    claim_code=$?
    set -e
    [[ "$claim_code" -eq 1 ]] ||
        fail "claims_errored must remain a non-zero infrastructure failure"
    [[ "$output" == *'CLAIM_INFRA_FAILURE'* ]] ||
        fail "claims_errored must surface as CLAIM_INFRA_FAILURE"
    ! grep -F 'bd update' "$calls" >/dev/null ||
        fail "claims_errored must never mutate or release a bead"
    ! grep -F 'runtime drain-ack' "$calls" >/dev/null ||
        fail "claims_errored must never acknowledge drain"

    rm -rf "$tmpdir"
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
test_polecat_claim_infra_failure_escalates_without_drain_ack
test_polecat_claim_trusts_hook_receipt_when_direct_read_lags
test_review_leg_contract_forbids_synthetic_mutation
test_refinery_direct_merge_is_worktree_safe_and_fail_closed

echo "gastown pack asset tests passed"
