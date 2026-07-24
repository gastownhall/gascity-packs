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

test_refinery_find_work_recovers_no_history_rows_and_fails_closed() {
    local formula tmpdir fake_bin selector calls output status
    formula="$GASTOWN/formulas/mol-refinery-patrol.toml"
    tmpdir="$(mktemp -d)"
    fake_bin="$tmpdir/bin"
    selector="$tmpdir/refinery-find-work.sh"
    calls="$tmpdir/calls"
    mkdir -p "$fake_bin"

    python3 - "$formula" >"$selector" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    formula = tomllib.load(handle)
text = next(step["description"] for step in formula["steps"] if step["id"] == "find-work")
anchor = text.index("Search for work beads assigned to you with branch metadata:")
start_marker = "```bash\n"
start = text.index(start_marker, anchor) + len(start_marker)
end = text.index("\n```", start)
print(text[start:end])
print("printf 'WORK=%s\\n' \"$WORK\"")
PY
    bash -n "$selector" ||
        fail "refinery find-work block must be valid Bash"

    cat >"$fake_bin/gc" <<'SH'
#!/usr/bin/env bash
set -u

{
    printf 'gc'
    for arg in "$@"; do
        printf ' <%s>' "$arg"
    done
    printf '\n'
} >>"$GC_TEST_CALLS"

if [ "${1:-}" != "bd" ]; then
    printf 'unexpected gc command: %s\n' "$*" >&2
    exit 97
fi

case "${2:-}" in
    list)
        case "${GC_TEST_SCENARIO:-}" in
            history)
                printf '%s\n' '[{"id":"history-1","status":"open","issue_type":"task","assignee":"kisakcod/gastown.refinery","metadata":{"branch":"polecat/history-1"}}]'
                ;;
            list_error)
                exit 42
                ;;
            list_bad_json)
                printf '%s\n' '{"not":"finished"'
                ;;
            *)
                printf '%s\n' '[]'
                ;;
        esac
        ;;
    query)
        case "${GC_TEST_SCENARIO:-}" in
            no_history)
                printf '%s\n' '[
                  {"id":"epic-1","status":"open","issue_type":"epic","assignee":"kisakcod/gastown.refinery","metadata":{"branch":"polecat/epic-1"}},
                  {"id":"wrong-agent","status":"open","issue_type":"task","assignee":"kisakcod/other","metadata":{"branch":"polecat/wrong-agent"}},
                  {"id":"empty-branch","status":"open","issue_type":"task","assignee":"kisakcod/gastown.refinery","metadata":{"branch":""}},
                  {"id":"durable-1","status":"open","issue_type":"task","assignee":"kisakcod/gastown.refinery","metadata":{"branch":"polecat/durable-1"}}
                ]'
                ;;
            no_branch)
                printf '%s\n' '[
                  {"id":"absent-branch","status":"open","issue_type":"task","assignee":"kisakcod/gastown.refinery","metadata":{}},
                  {"id":"empty-branch","status":"open","issue_type":"task","assignee":"kisakcod/gastown.refinery","metadata":{"branch":""}},
                  {"id":"whitespace-branch","status":"open","issue_type":"task","assignee":"kisakcod/gastown.refinery","metadata":{"branch":" \t "}}
                ]'
                ;;
            query_error)
                exit 43
                ;;
            query_bad_json)
                printf '%s\n' 'not-json'
                ;;
            query_non_object)
                printf '%s\n' '[null]'
                ;;
            query_truncated)
                printf '['
                for i in $(seq 1 21); do
                    [ "$i" -eq 1 ] || printf ','
                    printf '{"id":"branchless-%s","status":"open","issue_type":"task","assignee":"kisakcod/gastown.refinery","metadata":{}}' "$i"
                done
                printf ']\n'
                ;;
            *)
                printf 'unexpected query scenario: %s\n' "${GC_TEST_SCENARIO:-}" >&2
                exit 97
                ;;
        esac
        ;;
    *)
        printf 'unexpected gc bd command: %s\n' "$*" >&2
        exit 97
        ;;
esac
SH
    chmod +x "$fake_bin/gc" "$selector"

    run_selector() {
        local scenario="$1"
        local agent="$2"
        local rig="$3"
        : >"$calls"
        set +e
        output="$(
            PATH="$fake_bin:$PATH" \
            GC_TEST_CALLS="$calls" \
            GC_TEST_SCENARIO="$scenario" \
            GC_AGENT="$agent" \
            GC_RIG="$rig" \
            bash "$selector" 2>&1
        )"
        status=$?
        set -e
    }

    # Normal history-backed rows stay on the indexed list path. An empty rig
    # must add no accidental --rig argument.
    run_selector history "kisakcod/gastown.refinery" ""
    [[ "$status" -eq 0 && "$output" == *'WORK=history-1'* ]] ||
        fail "refinery list fast path must select a valid history-backed row"
    grep -F 'gc <bd> <list>' "$calls" >/dev/null ||
        fail "refinery history path must call gc bd list"
    grep -F '<--assignee=kisakcod/gastown.refinery>' "$calls" >/dev/null ||
        fail "refinery list must pass GC_AGENT as one quoted assignee argument"
    ! grep -F 'gc <bd> <query>' "$calls" >/dev/null ||
        fail "refinery history path must not pay for the durable fallback query"
    ! grep -F '<--rig=' "$calls" >/dev/null ||
        fail "HQ refinery read must not synthesize an empty rig scope"

    # A valid empty list falls back to full-row query output, rejects decoys,
    # and finds the durable no-history handoff with branch metadata.
    run_selector no_history "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 0 && "$output" == *'WORK=durable-1'* ]] ||
        fail "refinery fallback must recover a durable no-history row"
    [[ "$(grep -c '<--rig=kisakcod>' "$calls")" -eq 2 ]] ||
        fail "both refinery reads must carry the exact rig scope"
    grep -F 'gc <bd> <query>' "$calls" >/dev/null ||
        fail "an empty refinery list must trigger the durable query fallback"
    grep -F '<status=open AND assignee="kisakcod/gastown.refinery" AND type!=epic>' "$calls" >/dev/null ||
        fail "TOML-decoded refinery fallback must preserve quotes around the exact assignee"
    grep -F '<--limit=21>' "$calls" >/dev/null ||
        fail "refinery fallback query must stay bounded"

    # metadata.branch must contain a non-whitespace string on either read path.
    # Valid objects with absent branch metadata may be skipped.
    run_selector no_branch "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 0 && "$output" == *'WORK='* && "$output" != *'WORK=empty-branch'* && "$output" != *'WORK=whitespace-branch'* ]] ||
        fail "refinery fallback must not select an empty or whitespace-only metadata.branch"

    # A full bounded page with no usable branch is potentially truncated.
    # It must be observable as ambiguity, never laundered into genuine idle.
    run_selector query_truncated "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 1 && "$output" == *'reached its safety bound'* ]] ||
        fail "a full branchless refinery query page must fail as truncation-ambiguous"

    # Command and JSON failures are infrastructure failures, never an idle
    # queue. A failed fast-path read must not be hidden by the fallback.
    run_selector list_error "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 1 && "$output" == *'Could not list refinery work'* ]] ||
        fail "refinery list command errors must fail closed"
    ! grep -F 'gc <bd> <query>' "$calls" >/dev/null ||
        fail "refinery list command errors must not fall through to query"

    run_selector list_bad_json "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 1 && "$output" == *'Could not parse refinery work list'* ]] ||
        fail "malformed refinery list JSON must fail closed"
    ! grep -F 'gc <bd> <query>' "$calls" >/dev/null ||
        fail "malformed refinery list JSON must not fall through to query"

    run_selector query_error "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 1 && "$output" == *'Could not query durable refinery work'* ]] ||
        fail "refinery fallback command errors must fail closed"

    run_selector query_bad_json "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 1 && "$output" == *'Could not parse durable refinery work'* ]] ||
        fail "malformed durable refinery JSON must fail closed"

    run_selector query_non_object "kisakcod/gastown.refinery" "kisakcod"
    [[ "$status" -eq 1 && "$output" == *'Could not parse durable refinery work'* ]] ||
        fail "non-object durable refinery rows must fail schema validation"

    # The dynamic query value is allowed only after the canonical identity
    # grammar rejects quotes, whitespace, and query-language operators.
    run_selector no_history 'kisakcod/gastown.refinery" OR status=closed' "kisakcod"
    [[ "$status" -eq 1 && "$output" == *'not a canonical agent identity'* ]] ||
        fail "noncanonical GC_AGENT must fail before query construction"
    [[ ! -s "$calls" ]] ||
        fail "an injectable GC_AGENT must be rejected before any gc command"

    rm -rf "$tmpdir"
}

test_polecat_refinery_handoff_uses_configured_template_identity() {
    local formula
    formula="$GASTOWN/formulas/mol-polecat-work.toml"

    python3 - "$formula" <<'PY' || fail "polecat refinery handoff must derive and validate the configured template identity"
import sys

text = open(sys.argv[1], encoding="utf-8").read()
start = text.index("**6. Reassign to refinery:**")
end = text.index("**7. Signal refinery", start)
block = text[start:end]

required = [
    "POOL_TEMPLATE=${GC_TEMPLATE:-}",
    'SCOPE_PREFIX="${POOL_TEMPLATE%/*}/"',
    'REFINERY_LOCAL="${TEMPLATE_LOCAL%.polecat}.refinery"',
    'REFINERY_TARGET="${SCOPE_PREFIX}${REFINERY_LOCAL}"',
    "gc status --json",
    ".qualified_name == $target",
    "length == 1",
    'gc bd update "$WORK_BEAD_ID" --status=open --assignee="$REFINERY_TARGET"',
]
for needle in required:
    if needle not in block:
        raise SystemExit(f"missing refinery handoff contract: {needle}")

legacy = '${GC_RIG:+$GC_RIG/}{{binding_prefix}}refinery'
if legacy in block:
    raise SystemExit("refinery handoff still trusts a render-time binding_prefix")

validation = block.index("gc status --json")
mutation = block.index('gc bd update "$WORK_BEAD_ID"')
if validation > mutation:
    raise SystemExit("refinery identity validation occurs after bead mutation")
PY
}

test_dog_assets_are_pack_local
test_retired_dog_formulas_are_not_reintroduced
test_shutdown_dance_contracts_are_executable
test_shutdown_dance_lifecycle_and_audit_contracts
test_composition_is_documented
test_polecat_startup_uses_standard_hook_claim
test_review_leg_contract_forbids_synthetic_mutation
test_refinery_direct_merge_is_worktree_safe_and_fail_closed
test_refinery_find_work_recovers_no_history_rows_and_fails_closed
test_polecat_refinery_handoff_uses_configured_template_identity

echo "gastown pack asset tests passed"
