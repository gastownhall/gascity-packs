#!/usr/bin/env bash
set -euo pipefail

# Regression suite for the refinery's hosted-CI regression gate.
#
# Reproduction: on a live rig the refinery merged every bead whose LOCAL checks
# passed, and nothing anywhere in its assets read the hosted verdict. The target
# branch went success:9 (07-22) -> failure:3 (07-23) -> failure:11 (07-24), every
# failure a cross-platform target a Linux worker cannot build.
#
# The counter-reproduction matters just as much, and it is the reason the gate
# is scoped the way it is: on the same operator's rig the target branch then
# STAYED red, every branch cut from it inherited those failures, and an absolute
# "red head = reject" gate would have blocked every fix -- including the fixes
# for the failures causing the red. That branch sat frozen for roughly 16 hours
# and only moved when a human authorised a deliberate override.
# test_a_red_base_does_not_freeze_the_repository is that case, and it must pass
# for this gate to be shippable at all.
#
# The gate ships as an executable block inside mol-refinery-patrol, so this
# suite extracts the SHIPPED block and the SHIPPED call chains and runs them
# against a hermetic `gh`/`gc` and a real throwaway git repository, rather than
# asserting on prose. Timing knobs are overridden in the driver so the bounded
# waits resolve immediately; their shipped defaults are asserted separately.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
GASTOWN="$ROOT/gastown"
FORMULA="$GASTOWN/formulas/mol-refinery-patrol.toml"
PROMPT="$GASTOWN/agents/refinery/prompt.template.md"

WORK_ID="ki-hu3"
BRANCH_NAME="fix/sp-int-truncation"
ORIGIN_REPO_NAME="gastownhall/kisakcod"

# The real failing checks from the incident, verbatim.
RED_CHECK_ONE="Windows x86 / Release"
RED_CHECK_TWO="Portable tests / macOS arm64"
# The two jobs a bead ADDED to the board, which failed on their first run and
# took the target from 9 failures to 11 while the bead's own acceptance criteria
# claimed a hosted validation it never performed. They are on no earlier commit,
# so they are the "absent on the base" row of the table.
NEW_CHECK_ONE="Windows x86 SP / Debug"
NEW_CHECK_TWO="Windows x86 SP / Release"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# Extracts a shipped fragment from the formula: the gate block itself, one of
# the two call chains that drive it, or the direct-mode close command. Formula
# vars are substituted with their SHIPPED defaults, so the suite exercises what
# a poured wisp actually runs.
extract_shipped() {
    local what=$1 output=$2
    python3 - "$FORMULA" "$what" "$output" <<'PY'
import pathlib
import sys
import tomllib

formula_path, what, output_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(formula_path, "rb") as handle:
    data = tomllib.load(handle)
steps = {step["id"]: step for step in data["steps"]}
description = steps["merge-push"]["description"]


def fenced(section_marker):
    section = description[description.index(section_marker):]
    return section.split("```bash", 1)[1].split("```", 1)[0]


if what == "gate-block":
    begin = description.index("# BEGIN REFINERY_CI_GATE")
    end = description.index("# END REFINERY_CI_GATE", begin)
    fragment = description[begin:end]
elif what == "direct-chain":
    fragment = fenced("**0b. Hosted-CI regression gate")
elif what == "mr-chain":
    fragment = fenced("**3b. Hosted-CI regression gate")
elif what == "direct-close":
    start = description.index('gc bd update "$WORK" --set-metadata merge_result=merged')
    end = description.index("\n", description.index('gc bd close "$WORK"', start))
    fragment = description[start:end]
else:
    sys.exit(f"unknown fragment {what}")

for name, spec in data["vars"].items():
    fragment = fragment.replace("{{%s}}" % name, spec.get("default", ""))
fragment = fragment.replace("{{rig_name}}", "kisakcod")
if "{{" in fragment:
    sys.exit("shipped fragment still carries an unsubstituted formula var")
pathlib.Path(output_path).write_text(fragment + "\n", encoding="utf-8")
PY
}

# Hermetic GitHub. Serves per-request fixtures out of a directory; a missing
# fixture models an API failure, which the gate must never read as a pass.
# Boards are per-COMMIT because the gate reads two of them -- the head's and the
# base's -- so a fixture named for a SHA wins over the generic one. Sequenced
# fixtures (<name>.<sha>.1.json, <name>.<sha>.2.json) model checks that finish
# between polls.
write_gh_stub() {
    cat >"$BIN/gh" <<'SH'
#!/usr/bin/env bash
printf 'GH %s\n' "$*" >>"$GC_TEST_CALLS"
serve() {
    name="$1"
    if [ ! -f "$GH_FIXTURES/$name.json" ] && [ ! -f "$GH_FIXTURES/$name.1.json" ]; then
        return 1
    fi
    count=$(( $(cat "$GH_FIXTURES/$name.count" 2>/dev/null || echo 0) + 1 ))
    printf '%s' "$count" >"$GH_FIXTURES/$name.count"
    if [ -f "$GH_FIXTURES/$name.$count.json" ]; then
        cat "$GH_FIXTURES/$name.$count.json"
        return 0
    fi
    if [ -f "$GH_FIXTURES/$name.json" ]; then
        cat "$GH_FIXTURES/$name.json"
        return 0
    fi
    return 1
}
serve_commit() {
    kind="$1"
    shift
    all="$*"
    rest="${all#*/commits/}"
    sha="${rest%%/*}"
    serve "$kind.$sha" && return 0
    serve "$kind" && return 0
    printf 'HTTP 502: upstream unavailable (%s for %s)\n' "$kind" "$sha" >&2
    return 1
}
case "$*" in
    */commits/*/check-runs*) serve_commit check-runs "$@" ;;
    */commits/*/status*) serve_commit status "$@" ;;
    */pulls/*) serve pull || { printf 'HTTP 502: upstream unavailable (pull)\n' >&2; exit 1; } ;;
    *) printf 'unexpected gh call: %s\n' "$*" >&2; exit 97 ;;
esac
SH
    chmod +x "$BIN/gh"
}

# Hermetic stand-in for the real CLI. It dispatches on argv positions and never
# spells out a bare "<beads-cli> <subcommand>" string: tests/test_no_bare_bd_commands.py
# rejects that spelling anywhere in tracked assets, fixtures included. Mutating
# calls are logged under distinct markers so assertions never have to match on
# that spelling either.
write_gc_stub() {
    cat >"$BIN/gc" <<'SH'
#!/usr/bin/env bash
case "$1" in
    bd)
        case "$2" in
            update) printf 'UPDATE %s\n' "$*" >>"$GC_TEST_CALLS" ;;
            close) printf 'CLOSE %s\n' "$*" >>"$GC_TEST_CALLS" ;;
            list) printf 'LIST %s\n' "$*" >>"$GC_TEST_CALLS"; printf '[{"id": "wisp-current"}]\n' ;;
            mol)
                case "$3" in
                    wisp) printf 'POUR %s\n' "$*" >>"$GC_TEST_CALLS"; printf '{"new_epic_id": "wisp-next"}\n' ;;
                    burn) printf 'BURN %s\n' "$*" >>"$GC_TEST_CALLS" ;;
                    *) printf 'unexpected: %s\n' "$*" >&2; exit 97 ;;
                esac
                ;;
            *) printf 'unexpected: %s\n' "$*" >&2; exit 97 ;;
        esac
        ;;
    workflow) printf 'WORKFLOW %s\n' "$*" >>"$GC_TEST_CALLS" ;;
    runtime) printf 'RUNTIME %s\n' "$*" >>"$GC_TEST_CALLS" ;;
    session|mail) printf 'NOTIFY %s\n' "$*" >>"$GC_TEST_CALLS" ;;
    *) printf 'unexpected: %s\n' "$*" >&2; exit 97 ;;
esac
exit 0
SH
    chmod +x "$BIN/gc"
}

write_driver() {
    cat >"$DRIVER" <<'SH'
#!/usr/bin/env bash
# Stands in for the refinery session: the same variables the earlier merge-push
# script sets, then the shipped gate block, then the shipped call chain.
cd "$GATE_TEST_REPO_DIR" || exit 90
WORK="$GATE_TEST_WORK"
BRANCH="$GATE_TEST_BRANCH"
TARGET="$GATE_TEST_TARGET"
ORIGIN_REPO="$GATE_TEST_ORIGIN_REPO"
ORIGIN_REPO_ERROR=""
PR_NUMBER="${GATE_TEST_PR_NUMBER:-}"
GC_RIG="kisakcod"
GC_AGENT="kisakcod/refinery"
GC_BEAD_ID="wisp-current"
. "$GATE_BLOCK"
CI_POLL_SECONDS=0
CI_TIMEOUT_SECONDS="$GATE_TEST_CI_TIMEOUT"
CI_ZERO_CHECK_GRACE_SECONDS="$GATE_TEST_CI_GRACE"
CI_GATE="$GATE_TEST_CI_GATE"
CI_GATE_PUBLISH_HEAD="$GATE_TEST_PUBLISH_HEAD"
. "$GATE_CHAIN"
echo "CHAIN_COMPLETED"
SH
}

# A real repository, because the direct chain really inspects refs and, when
# opted in, really pushes, and because the gate resolves its base out of
# refs/remotes/origin/$TARGET rather than out of a fixture. `origin` is a local
# bare repo, so --force-with-lease behaves exactly as it does against GitHub.
setup_case() {
    TMP=$(mktemp -d)
    BIN="$TMP/bin"
    FIX="$TMP/fixtures"
    CALLS="$TMP/calls"
    BLOCK="$TMP/gate-block.sh"
    DRIVER="$TMP/driver.sh"
    REPO="$TMP/work"
    ORIGIN="$TMP/origin.git"
    mkdir -p "$BIN" "$FIX"
    : >"$CALLS"
    extract_shipped gate-block "$BLOCK"
    bash -n "$BLOCK" || fail "the shipped gate block is not valid shell"
    write_gh_stub
    write_gc_stub
    write_driver

    git init --quiet --bare "$ORIGIN"
    git init --quiet "$REPO"
    git -C "$REPO" symbolic-ref HEAD refs/heads/main
    git -C "$REPO" config user.email "refinery@test.invalid"
    git -C "$REPO" config user.name "Refinery Test"
    git -C "$REPO" remote add origin "$ORIGIN"
    mkdir -p "$REPO/src"
    printf 'int route_legacy(void) { return 0; }\n' >"$REPO/src/route.c"
    git -C "$REPO" add -A
    git -C "$REPO" commit --quiet -m "base"
    git -C "$REPO" push --quiet origin main
    git -C "$REPO" checkout --quiet -b temp
    printf 'int route_legacy(void) { return 0; }\nint route_candidate(void) { return 1; }\n' >"$REPO/src/route.c"
    git -C "$REPO" commit --quiet -am "candidate route"
    git -C "$REPO" push --quiet origin "temp:$BRANCH_NAME"
    git -C "$REPO" fetch --quiet origin
    HEAD_SHA=$(git -C "$REPO" rev-parse temp)
    PUBLISHED_SHA=$(git -C "$REPO" rev-parse "origin/$BRANCH_NAME")
    BASE_SHA=$(git -C "$REPO" rev-parse "origin/main")
}

# The steady state of a busy merge queue: the target moved since the polecat
# pushed, so the rebase rewrites the branch and the commit that would land is
# one no forge has seen. `temp` and `origin/$BRANCH` now differ, and the base
# the gate measures against is the MOVED target tip.
setup_rebased_case() {
    setup_case
    git -C "$REPO" checkout --quiet main
    printf 'unrelated target-side change\n' >"$REPO/src/other.c"
    git -C "$REPO" add -A
    git -C "$REPO" commit --quiet -m "target moved"
    git -C "$REPO" push --quiet origin main
    git -C "$REPO" fetch --quiet origin
    git -C "$REPO" checkout --quiet temp
    git -C "$REPO" rebase --quiet origin/main
    HEAD_SHA=$(git -C "$REPO" rev-parse temp)
    PUBLISHED_SHA=$(git -C "$REPO" rev-parse "origin/$BRANCH_NAME")
    BASE_SHA=$(git -C "$REPO" rev-parse "origin/main")
    [[ "$HEAD_SHA" != "$PUBLISHED_SHA" ]] ||
        fail "the rebased fixture must produce a head the forge has never seen"
}

fixture() {
    cat >"$FIX/$1"
}

# board_for <sha>: check-run JSON on stdin, plus an empty legacy status board so
# a test only has to think about check-runs unless it is about statuses.
board_for() {
    cat >"$FIX/check-runs.$1.json"
    cat >"$FIX/status.$1.json" <<'JSON'
{"state": "success", "total_count": 0, "statuses": []}
JSON
}

statuses_for() {
    cat >"$FIX/status.$1.json"
}

empty_board() {
    board_for "$1" <<'JSON'
{"total_count": 0, "check_runs": []}
JSON
}

green_board() {
    board_for "$1" <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"},
  {"name": "Lint", "status": "completed", "conclusion": "skipped"}
]}
JSON
}

# The same names as green_board, plus the two that fail. A base carrying this
# board and a head carrying red_board is the green -> red row.
base_board_for_red_head() {
    board_for "$1" <<JSON
{"total_count": 3, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "success"},
  {"name": "$RED_CHECK_TWO", "status": "completed", "conclusion": "success"},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
}

red_board() {
    board_for "$1" <<JSON
{"total_count": 3, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "failure"},
  {"name": "$RED_CHECK_TWO", "status": "completed", "conclusion": "timed_out"},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
}

# The eleven checks that were failing on the operator's target branch on 07-24,
# after it had been red for a day. Used as BOTH boards in the deadlock case.
incident_red_board() {
    jq -n '["Windows x86 / Release", "Windows x86 / Debug",
            "Portable tests / Linux amd64", "Portable tests / Linux arm64",
            "Portable tests / macOS amd64", "Portable tests / macOS arm64",
            "Portable tests / Windows amd64", "Portable tests / Windows arm64",
            "Windows x86 SP / Release", "Windows x86 SP / Debug",
            "Sanitizers / asan"]
           | {total_count: length,
              check_runs: map({name: ., status: "completed", conclusion: "failure"})}' \
        | board_for "$1"
}

run_chain() {
    local chain=$1
    CODE=0
    set +e
    OUTPUT=$(
        PATH="$BIN:$PATH" \
        GC_TEST_CALLS="$CALLS" \
        GH_FIXTURES="$FIX" \
        GATE_TEST_REPO_DIR="$REPO" \
        GATE_TEST_WORK="$WORK_ID" \
        GATE_TEST_BRANCH="$BRANCH_NAME" \
        GATE_TEST_TARGET="main" \
        GATE_TEST_ORIGIN_REPO="$ORIGIN_REPO_NAME" \
        GATE_TEST_PR_NUMBER="${PR_NUMBER_OVERRIDE:-}" \
        GATE_TEST_CI_TIMEOUT="${CI_TIMEOUT_OVERRIDE:-0}" \
        GATE_TEST_CI_GRACE="${CI_GRACE_OVERRIDE:-0}" \
        GATE_TEST_CI_GATE="${CI_GATE_OVERRIDE:-true}" \
        GATE_TEST_PUBLISH_HEAD="${PUBLISH_HEAD_OVERRIDE:-false}" \
        GATE_BLOCK="$BLOCK" \
        GATE_CHAIN="$chain" \
        bash "$DRIVER" 2>&1
    )
    CODE=$?
    set -e
}

run_direct_chain() {
    local chain="$TMP/direct-chain.sh"
    extract_shipped direct-chain "$chain"
    bash -n "$chain" || fail "the shipped direct-mode chain is not valid shell"
    run_chain "$chain"
}

run_mr_chain() {
    local chain="$TMP/mr-chain.sh"
    extract_shipped mr-chain "$chain"
    bash -n "$chain" || fail "the shipped mr-mode chain is not valid shell"
    run_chain "$chain"
}

assert_not_closed() {
    ! grep -q '^CLOSE ' "$CALLS" ||
        fail "$1: the bead was closed anyway: $(grep '^CLOSE ' "$CALLS")"
}

# A rejection is the recoverable disposition: the bead goes back to the pool
# with a reason a polecat can act on, the branch survives for fix-forward, and
# the patrol loop keeps turning. Anything less strands the queue.
assert_rejected() {
    local needle=$1
    [[ "$CODE" -eq 1 ]] || fail "the CI gate must reject with exit 1 (got $CODE): $OUTPUT"
    [[ "$OUTPUT" == *"CI_GATE_REJECTED $WORK_ID"* ]] ||
        fail "a rejection must announce CI_GATE_REJECTED: $OUTPUT"
    grep -F -- '--status=open' "$CALLS" >/dev/null ||
        fail "a rejection must put the bead back in the pool"
    grep -F -- '--assignee=' "$CALLS" >/dev/null ||
        fail "a rejection must release the refinery claim"
    grep -F -- '--set-metadata rejection_reason=CI gate:' "$CALLS" >/dev/null ||
        fail "a rejection must write a rejection_reason naming the gate: $(cat "$CALLS")"
    grep -F -- "$needle" "$CALLS" >/dev/null ||
        fail "the rejection_reason must be specific enough to act on (want '$needle'): $(cat "$CALLS")"
    grep -F -- "--set-metadata ci_gate_base_sha=$BASE_SHA" "$CALLS" >/dev/null ||
        fail "a rejection must record the base SHA it measured against; a reviewer must never have to guess what 'worse' was worse than: $(cat "$CALLS")"
    grep -F -- 'gc.routed_to' "$CALLS" >/dev/null ||
        fail "a rejection must route the bead back to the polecat pool"
    grep -q '^POUR ' "$CALLS" ||
        fail "a rejection must pour the next patrol wisp; a stalled loop is worse than a red merge"
    grep -q '^BURN ' "$CALLS" ||
        fail "a rejection must burn the current wisp after pouring the next"
    assert_not_closed "a rejection"
    [[ "$OUTPUT" == *"left intact for fix-forward"* ]] ||
        fail "a CI rejection must leave the branch intact for fix-forward: $OUTPUT"
}

assert_undetermined() {
    local label=$1 needle=$2
    [[ "$CODE" -ne 0 ]] || fail "$label must not pass: $OUTPUT"
    [[ "$OUTPUT" == *"CI_GATE_UNDETERMINED"* ]] ||
        fail "$label must report CI_GATE_UNDETERMINED: $OUTPUT"
    [[ "$OUTPUT" == *"$needle"* ]] ||
        fail "$label must say why it could not be determined (want '$needle'): $OUTPUT"
    ! grep -F -- '--status=open' "$CALLS" >/dev/null ||
        fail "$label is our fault, not the branch's: it must not reject the bead"
    assert_not_closed "$label"
}

# The other half of the contract, and the one an absolute gate gets wrong: work
# that did not degrade anything has to get through.
assert_allowed() {
    local label=$1
    [[ "$CODE" -eq 0 ]] || fail "$label must be allowed through (exit $CODE): $OUTPUT"
    [[ "$OUTPUT" != *"CI_GATE_REJECTED"* ]] || fail "$label must not be rejected: $OUTPUT"
    [[ "$OUTPUT" != *"CI_GATE_UNDETERMINED"* ]] ||
        fail "$label must reach a verdict, not stall: $OUTPUT"
    ! grep -F -- '--status=open' "$CALLS" >/dev/null ||
        fail "$label must not put the bead back in the pool: $(cat "$CALLS")"
}

assert_branch_not_republished() {
    [[ "$(git -C "$REPO" rev-parse "refs/remotes/origin/$BRANCH_NAME")" == "$PUBLISHED_SHA" ]] ||
        fail "$1: the gate moved the remote branch"
    git -C "$REPO" fetch --quiet origin
    [[ "$(git -C "$REPO" rev-parse "refs/remotes/origin/$BRANCH_NAME")" == "$PUBLISHED_SHA" ]] ||
        fail "$1: the gate published the branch to origin"
}

# ---------------------------------------------------------------------------

# The shipped defaults decide what a city gets without configuration, so they
# are part of the contract.
test_shipped_defaults_are_fail_closed() {
    python3 - "$FORMULA" "$PROMPT" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    data = tomllib.load(handle)
variables = data["vars"]
if variables["ci_gate"]["default"] != "true":
    raise SystemExit("ci_gate must default to on; a gate off by default is not a gate")
for name in ("ci_timeout_seconds", "ci_zero_check_grace_seconds", "ci_poll_seconds"):
    if int(variables[name]["default"]) < 0:
        raise SystemExit(f"{name} must not be negative")
for name in ("ci_timeout_seconds", "ci_zero_check_grace_seconds"):
    if int(variables[name]["default"]) <= 0:
        raise SystemExit(f"{name} must leave a real window; 0 would rule on every honest branch too early")
if variables["ci_gate_publish_head"]["default"] != "false":
    raise SystemExit(
        "ci_gate_publish_head must default to off: publishing the source branch is a change "
        "to what a direct-mode rig pushes, and an upgrade must not start pushing refs on its own"
    )

steps = {step["id"]: step for step in data["steps"]}
if steps["merge-push"]["needs"] != ["handle-failures"]:
    raise SystemExit("the CI gate must not reshape the step graph; merge-push still follows handle-failures")
if any(step["id"] == "review-diff" for step in data["steps"]):
    raise SystemExit("this change ships the CI gate only; there is no diff-review step")

prompt = open(sys.argv[2], encoding="utf-8").read()
for needle in ("Hosted-CI Regression Gate", "ci_gate=false", "fix-forward",
               "REGRESSION", "inherited", "ci_gate_inherited"):
    if needle not in prompt:
        raise SystemExit(f"refinery prompt must document {needle}")
if 'FORBIDDEN: Reading polecat code to "understand what they were trying to do."' not in prompt:
    raise SystemExit("the CARDINAL RULE is upstream's decision and this change does not touch it")
PY
}

# The gate has to rule before the merge script touches the target, in both
# modes, and before the close in either -- and it has to read TWO boards.
test_the_gate_rules_before_anything_lands() {
    python3 - "$FORMULA" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    data = tomllib.load(handle)
description = {step["id"]: step for step in data["steps"]}["merge-push"]["description"]
direct = description[description.index('**If MERGE_STRATEGY = "direct"'):description.index('**If MERGE_STRATEGY = "mr"')]
if "ci_gate_run" not in direct:
    raise SystemExit("direct mode must run the CI gate")
if direct.index("ci_gate_run") > direct.index("git worktree add --detach"):
    raise SystemExit("the CI gate must rule before direct mode touches the target branch")

mr = description[description.index('**If MERGE_STRATEGY = "mr"'):]
if mr.index("ci_gate_run") > mr.index("--set-metadata merge_result=pull_request"):
    raise SystemExit("mr mode must run the CI gate before it closes the bead")

gate = description[description.index("# BEGIN REFINERY_CI_GATE"):description.index("# END REFINERY_CI_GATE")]
# Without a base board there is nothing to compare against, and the gate
# silently becomes the absolute gate that freezes any repo with a red target.
if "ci_gate_resolve_base" not in gate or 'ci_gate_board "$CI_GATE_BASE_SHA" base' not in gate:
    raise SystemExit(
        "the gate must resolve and read a BASE board; without one every red check on the head "
        "looks like a regression and a repository with a red target can never land its own fix"
    )
if "ci_gate_base_sha" not in gate:
    raise SystemExit("the gate must stamp the base SHA it measured against")

# Publishing a branch is the behaviour change this pack refuses to make by
# default, so the only push in direct mode must sit behind the opt-in.
if direct.count('git push origin "HEAD:$BRANCH"') != 1:
    raise SystemExit("direct mode must have exactly one branch-publishing push, inside the opt-in")
if '"$CI_GATE_PUBLISH_HEAD" = "true"' not in direct:
    raise SystemExit(
        "direct mode publishes the source branch without the ci_gate_publish_head opt-in guard; "
        "an upgrade must not start pushing refs a rig never pushed"
    )
publish = direct.index('git push origin "HEAD:$BRANCH"')
opt_in = direct.index('"$CI_GATE_PUBLISH_HEAD" = "true"')
if not opt_in < publish < direct.index("ci_gate_run"):
    raise SystemExit("direct mode may only publish the branch inside the ci_gate_publish_head opt-in")
PY
}

# The incident itself, correctly scoped: checks that PASS on the target and fail
# on the branch. This branch broke them, so this branch answers for them.
test_green_to_red_is_a_regression_and_rejects() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    base_board_for_red_head "$BASE_SHA"
    red_board "$HEAD_SHA"

    run_direct_chain
    assert_rejected "$RED_CHECK_ONE"
    grep -F -- "$RED_CHECK_TWO" "$CALLS" >/dev/null ||
        fail "a timed_out check is red too and must be named"
    grep -F -- "on the base: green" "$CALLS" >/dev/null ||
        fail "a regression must say what the check was doing on the base, or nobody can tell a regression from an inherited failure: $(cat "$CALLS")"
    grep -F -- "Portable tests / Linux amd64" "$CALLS" >/dev/null &&
        fail "a check that is green on the head must never appear in the rejection reason: $(cat "$CALLS")"
    [[ "$OUTPUT" != *"CI_GATE_GREEN"* ]] || fail "a degraded board must never be reported green: $OUTPUT"
}

# The row an absolute gate gets wrong. The branch did not touch these checks;
# they were already failing on the target it lands on.
test_red_to_red_is_inherited_and_allows() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    red_board "$BASE_SHA"
    red_board "$HEAD_SHA"

    run_direct_chain
    assert_allowed "a head that is red in exactly the ways its base is already red"
    [[ "$OUTPUT" == *"CI_GATE_PREEXISTING_RED"* ]] ||
        fail "an inherited failure must be reported loudly, not swallowed: $OUTPUT"
    [[ "$OUTPUT" == *"$RED_CHECK_ONE"* ]] ||
        fail "the report must name the inherited failures: $OUTPUT"
    grep -F -- '--set-metadata ci_gate_inherited=' "$CALLS" >/dev/null ||
        fail "the bead must record which failures were let through as inherited: $(cat "$CALLS")"
    grep -F -- "ci_gate_inherited=" "$CALLS" | grep -F -- "$RED_CHECK_ONE" >/dev/null ||
        fail "ci_gate_inherited must name the inherited failures: $(cat "$CALLS")"
    grep -F -- "ci_gate_inherited=" "$CALLS" | grep -F -- "$RED_CHECK_TWO" >/dev/null ||
        fail "ci_gate_inherited must name every inherited failure, not just the first: $(cat "$CALLS")"
    grep -F -- "--set-metadata ci_gate_base_sha=$BASE_SHA" "$CALLS" >/dev/null ||
        fail "the bead must record the base those failures were inherited from"
    [[ "$OUTPUT" == *"NOT because hosted CI is well"* ]] ||
        fail "allowing an inherited failure must not read as an all-clear: $OUTPUT"

    # ... but only failures PROVEN inherited are excused. A base check that has
    # not finished has not proven anything, and excusing on "it might fail too"
    # is the direction that lets a real regression through.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    board_for "$BASE_SHA" <<JSON
{"total_count": 1, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "in_progress", "conclusion": null}
]}
JSON
    board_for "$HEAD_SHA" <<JSON
{"total_count": 1, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "failure"}
]}
JSON
    run_direct_chain
    assert_rejected "$RED_CHECK_ONE"
    grep -F -- "on the base: still running" "$CALLS" >/dev/null ||
        fail "an unfinished base check must be named as unproven, not reported as inherited: $(cat "$CALLS")"
}

# THE case this rework exists for. On the operator's rig the target branch went
# red on 07-23 and stayed red; every branch cut from it inherited all eleven
# failures. Under an absolute gate no fix could land -- including the fixes for
# the failures causing the red -- and the branch sat frozen for ~16 hours until
# a human authorised an override. Same failures on both sides must ALLOW, or
# this gate is a freeze with better manners.
test_a_red_base_does_not_freeze_the_repository() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    incident_red_board "$BASE_SHA"
    incident_red_board "$HEAD_SHA"

    run_direct_chain
    assert_allowed "a branch inheriting all eleven of its base's failures"
    [[ "$OUTPUT" == *"CI_GATE_PREEXISTING_RED"* ]] ||
        fail "eleven inherited failures must still be reported: $OUTPUT"
    [[ "$OUTPUT" == *"11 of them are already red on the base"* ]] ||
        fail "the report must account for every inherited failure: $OUTPUT"
    grep -F -- "--set-metadata ci_gate_sha=$HEAD_SHA" "$CALLS" >/dev/null ||
        fail "a bead allowed through onto a red base must still record what was gated"
    for check in "Windows x86 / Release" "Sanitizers / asan" "Portable tests / Windows arm64"; do
        grep -F -- "$check" "$CALLS" >/dev/null ||
            fail "ci_gate_inherited must name every failure let through, missing '$check': $(cat "$CALLS")"
    done
}

# A branch that ADDS a failing job has made things worse even though nothing
# that was passing broke. Observed: a bead added two Windows SP jobs that failed
# on their first run, taking the target from 9 failures to 11.
test_absent_on_base_and_red_on_head_is_a_regression() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    # The base is ALREADY RED -- so this also proves the absent -> red rule is
    # not just the absolute gate reappearing on a green base.
    board_for "$BASE_SHA" <<JSON
{"total_count": 2, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "failure"},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    board_for "$HEAD_SHA" <<JSON
{"total_count": 4, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "failure"},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"},
  {"name": "$NEW_CHECK_ONE", "status": "completed", "conclusion": "failure"},
  {"name": "$NEW_CHECK_TWO", "status": "completed", "conclusion": "failure"}
]}
JSON

    run_direct_chain
    assert_rejected "$NEW_CHECK_ONE"
    grep -F -- "$NEW_CHECK_TWO" "$CALLS" >/dev/null ||
        fail "both added failing jobs must be named"
    grep -F -- "on the base: no such check" "$CALLS" >/dev/null ||
        fail "the rejection must say the job did not exist on the base: $(cat "$CALLS")"
    grep -F -- "2 of 4 checks are red" "$CALLS" >/dev/null ||
        fail "the pre-existing failure must not be counted as a regression: $(cat "$CALLS")"
}

# The happy path, end to end: the gate finds no degradation, stamps its
# forensics, and the shipped terminal update closes the bead with the merged SHA.
test_green_to_green_passes_and_the_bead_closes() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    green_board "$HEAD_SHA"

    run_direct_chain
    assert_allowed "a green head on a green base"
    [[ "$OUTPUT" == *"CHAIN_COMPLETED"* ]] || fail "the gate chain did not complete: $OUTPUT"
    [[ "$OUTPUT" == *"CI_GATE_EXACT"* ]] ||
        fail "an un-rebased branch is landed at its published tip and the gate must say so: $OUTPUT"
    [[ "$OUTPUT" == *"CI_GATE_BASE: measuring $HEAD_SHA against main at $BASE_SHA"* ]] ||
        fail "the gate must announce which base it measured against: $OUTPUT"
    grep -F -- "--set-metadata ci_gate_sha=$HEAD_SHA" "$CALLS" >/dev/null ||
        fail "the gate must stamp the SHA it proved onto the bead"
    grep -F -- "--set-metadata ci_gate_base_sha=$BASE_SHA" "$CALLS" >/dev/null ||
        fail "the gate must stamp the base SHA it compared against"
    grep -F -- '--set-metadata ci_gate_inherited=none' "$CALLS" >/dev/null ||
        fail "a clean pass must record that nothing was let through as inherited: $(cat "$CALLS")"
    grep -F -- '--set-metadata ci_gate_result=2 checks green' "$CALLS" >/dev/null ||
        fail "the gate must stamp what it proved, not just that it passed: $(cat "$CALLS")"
    ! grep -q '^CLOSE ' "$CALLS" || fail "the gate itself must never close the bead"

    # The shipped terminal update + close, run with the same fake CLI.
    local close="$TMP/close.sh"
    extract_shipped direct-close "$close"
    : >"$CALLS"
    (
        PATH="$BIN:$PATH" GC_TEST_CALLS="$CALLS" \
        WORK="$WORK_ID" MERGED_SHA="$HEAD_SHA" MERGED_SHORT="${HEAD_SHA:0:7}" TARGET=main \
        bash "$close"
    ) || fail "the shipped close chain did not run"
    grep -q '^CLOSE ' "$CALLS" || fail "the happy path must close the bead"
    grep -F -- '--unset-metadata rejection_reason' "$CALLS" >/dev/null ||
        fail "the successful close must clear rejection_reason"
    grep -F -- "--set-metadata merged_sha=$HEAD_SHA" "$CALLS" >/dev/null ||
        fail "the close must record the merged SHA, which is the SHA the gate proved"
}

# A repository with no hosted CI at all has nothing for a branch to degrade.
# Rejecting here would make the gate unusable for every repo without a forge
# CI, which is the same class of mistake as freezing a repo with a red base.
test_zero_checks_on_both_sides_allows() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    empty_board "$BASE_SHA"
    empty_board "$HEAD_SHA"

    run_direct_chain
    assert_allowed "a repository that publishes no checks on either side"
    [[ "$OUTPUT" == *"CI_GATE_NO_HOSTED_CI"* ]] ||
        fail "a repo with no hosted CI must be told so explicitly, not silently passed: $OUTPUT"
    grep -F -- 'publishes no CI on this path' "$CALLS" >/dev/null ||
        fail "the bead must record that it closed without any hosted verdict: $(cat "$CALLS")"

    # The grace window still applies: checks that register a moment after the
    # push must not be missed just because the first poll was empty.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    fixture "check-runs.$HEAD_SHA.1.json" <<'JSON'
{"total_count": 0, "check_runs": []}
JSON
    fixture "check-runs.$HEAD_SHA.2.json" <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"},
  {"name": "Lint", "status": "completed", "conclusion": "skipped"}
]}
JSON
    fixture "status.$HEAD_SHA.json" <<'JSON'
{"state": "success", "total_count": 0, "statuses": []}
JSON
    CI_GRACE_OVERRIDE=120 CI_TIMEOUT_OVERRIDE=120 run_direct_chain
    assert_allowed "a head whose checks register on the second poll"
    [[ "$OUTPUT" == *"CI_GATE_GREEN"* ]] ||
        fail "a board that appears inside the grace window must be read, not treated as absent: $OUTPUT"
}

# The base publishes checks and this head publishes none. CI ran for the target
# and did not run here, so coverage the target already has was lost on this
# branch: a removed or renamed workflow, or a ref no workflow triggers for.
test_head_with_no_checks_rejects_when_the_base_has_them() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    empty_board "$HEAD_SHA"

    run_direct_chain
    assert_rejected "publishes none"
    grep -F -- "publishes 2 checks" "$CALLS" >/dev/null ||
        fail "the rejection must say how much coverage the base has that this head lost: $(cat "$CALLS")"
    [[ "$OUTPUT" != *"CI_GATE_NO_HOSTED_CI"* ]] ||
        fail "a head with no checks and a base with checks is not a repo without CI: $OUTPUT"
}

# A repository whose CI only runs `on: pull_request` never publishes checks for
# its target tip, so "absent on the base" there means "there is no baseline",
# not "this branch added a failing job". Charging the head's failures to the
# branch on that evidence would freeze exactly the repositories this gate was
# rescoped to unfreeze, so they are reported as unattributable and allowed.
test_a_base_with_no_board_cannot_attribute_a_red_head() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    empty_board "$BASE_SHA"
    red_board "$HEAD_SHA"

    run_direct_chain
    assert_allowed "a red head measured against a base that publishes no board"
    [[ "$OUTPUT" == *"CI_GATE_UNATTRIBUTABLE"* ]] ||
        fail "a head that cannot be compared must say so, not pass quietly: $OUTPUT"
    [[ "$OUTPUT" == *"no baseline"* ]] ||
        fail "the report must say WHY the failures could not be charged to this branch: $OUTPUT"
    [[ "$OUTPUT" == *"$RED_CHECK_ONE"* ]] ||
        fail "the unattributable failures must still be named: $OUTPUT"
    grep -F -- "ci_gate_inherited=" "$CALLS" | grep -F -- "$RED_CHECK_ONE" >/dev/null ||
        fail "unattributable failures must be recorded on the bead like inherited ones: $(cat "$CALLS")"
    [[ "$OUTPUT" != *"CI_GATE_GREEN"* ]] ||
        fail "a red head must never be reported green, even when it cannot be attributed: $OUTPUT"
}

# Pending is a wait, and then it is OUR problem, not the branch's. An unfinished
# check is not evidence of a regression, so blaming the branch for a slow CI
# queue would be the absolute gate leaking back in through the timeout.
test_pending_waits_then_goes_undetermined() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    board_for "$HEAD_SHA" <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Windows x86 / Debug", "status": "in_progress", "conclusion": null},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON

    run_direct_chain
    assert_undetermined "a head board that never finished" "still running"
    [[ "$OUTPUT" == *"Windows x86 / Debug"* ]] ||
        fail "the unfinished checks must be named so the wait can be resumed: $OUTPUT"
    [[ "$OUTPUT" != *"CI_GATE_GREEN"* ]] ||
        fail "an unfinished check board must never be reported green: $OUTPUT"

    # The same board, given a window: it finishes green between polls and the
    # gate proceeds. Pending is a wait, not a verdict.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    fixture "check-runs.$HEAD_SHA.1.json" <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Windows x86 / Debug", "status": "queued", "conclusion": null},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    fixture "check-runs.$HEAD_SHA.2.json" <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Windows x86 / Debug", "status": "completed", "conclusion": "success"},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    fixture "status.$HEAD_SHA.json" <<'JSON'
{"state": "success", "total_count": 0, "statuses": []}
JSON

    CI_TIMEOUT_OVERRIDE=120 run_direct_chain
    assert_allowed "checks that finish green inside the window"
    [[ "$OUTPUT" == *"CI_GATE_GREEN"* ]] || fail "a green board must be reported green: $OUTPUT"

    # A proven regression does not wait for the rest of the board. The verdict
    # cannot improve, and the polecat can start on the named check now.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    base_board_for_red_head "$BASE_SHA"
    board_for "$HEAD_SHA" <<JSON
{"total_count": 2, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "failure"},
  {"name": "Portable tests / Linux amd64", "status": "in_progress", "conclusion": null}
]}
JSON
    CI_TIMEOUT_OVERRIDE=3600 run_direct_chain
    assert_rejected "$RED_CHECK_ONE"
}

# An unrecognized conclusion is not on the accept list, so it is not a pass --
# and against a base where that check passes, it is a regression.
test_unknown_conclusions_are_red_and_regress() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    board_for "$BASE_SHA" <<'JSON'
{"total_count": 1, "check_runs": [
  {"name": "Windows x86 (no Steam)", "status": "completed", "conclusion": "success"}
]}
JSON
    board_for "$HEAD_SHA" <<'JSON'
{"total_count": 1, "check_runs": [
  {"name": "Windows x86 (no Steam)", "status": "completed", "conclusion": "stale"}
]}
JSON

    run_direct_chain
    assert_rejected "Windows x86 (no Steam)"
    grep -F -- "stale" "$CALLS" >/dev/null ||
        fail "the unrecognized conclusion must be quoted so an operator can classify it: $(cat "$CALLS")"

    # The same unknown conclusion on BOTH sides is inherited, not a regression.
    # Default-deny decides what is RED; it does not decide who is to blame.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    board_for "$BASE_SHA" <<'JSON'
{"total_count": 1, "check_runs": [
  {"name": "Windows x86 (no Steam)", "status": "completed", "conclusion": "stale"}
]}
JSON
    board_for "$HEAD_SHA" <<'JSON'
{"total_count": 1, "check_runs": [
  {"name": "Windows x86 (no Steam)", "status": "completed", "conclusion": "stale"}
]}
JSON
    run_direct_chain
    assert_allowed "an unknown conclusion that is equally unknown on the base"
}

# A repo can publish check-runs, legacy commit statuses, or both. Reading only
# one API is a way to mistake silence for success -- and both sides of the
# comparison have to read both.
test_legacy_commit_statuses_are_compared_too() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    statuses_for "$BASE_SHA" <<'JSON'
{"state": "success", "total_count": 1, "statuses": [
  {"context": "buildbot/windows-msvc", "state": "success"}
]}
JSON
    green_board "$HEAD_SHA"
    statuses_for "$HEAD_SHA" <<'JSON'
{"state": "failure", "total_count": 1, "statuses": [
  {"context": "buildbot/windows-msvc", "state": "failure"}
]}
JSON

    run_direct_chain
    assert_rejected "buildbot/windows-msvc"

    # And a legacy status already failing on the base is inherited, exactly as
    # a check-run would be.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    statuses_for "$BASE_SHA" <<'JSON'
{"state": "failure", "total_count": 1, "statuses": [
  {"context": "buildbot/windows-msvc", "state": "failure"}
]}
JSON
    green_board "$HEAD_SHA"
    statuses_for "$HEAD_SHA" <<'JSON'
{"state": "failure", "total_count": 1, "statuses": [
  {"context": "buildbot/windows-msvc", "state": "failure"}
]}
JSON
    run_direct_chain
    assert_allowed "a legacy status that is already failing on the base"
    grep -F -- '--set-metadata ci_gate_inherited=buildbot/windows-msvc' "$CALLS" >/dev/null ||
        fail "an inherited legacy status must be recorded like any other: $(cat "$CALLS")"
}

# Without a base there is no comparison, and no comparison is UNDETERMINED. It
# is emphatically not a pass: falling open here would be a gate that quietly
# stops gating the moment a fetch is stale.
test_base_lookup_failure_is_undetermined_not_a_pass() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$HEAD_SHA"
    git -C "$REPO" update-ref -d "refs/remotes/origin/main"

    run_direct_chain
    assert_undetermined "an unresolvable base ref" "refs/remotes/origin/main"
    [[ "$OUTPUT" != *"CI_GATE_GREEN"* ]] ||
        fail "a green head with no base to compare against is not a proven non-regression: $OUTPUT"

    # The base ref resolves but its board cannot be read: same disposition.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$HEAD_SHA"
    run_direct_chain
    assert_undetermined "an unreadable base board" "for the base commit $BASE_SHA"

    # More checks on the base than one page reports: the board is not fully
    # visible, so "absent on the base" cannot be trusted and nothing is ruled.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$HEAD_SHA"
    board_for "$BASE_SHA" <<'JSON'
{"total_count": 140, "check_runs": [
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    run_direct_chain
    assert_undetermined "a truncated base board" "one page can report"
}

# The upgrade contract. An existing direct-mode rig does not opt in, so this
# change must not make it push anything it did not push before -- not even to
# let CI rule on the exact object.
test_direct_mode_publishes_nothing_by_default() {
    setup_rebased_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    green_board "$PUBLISHED_SHA"
    green_board "$HEAD_SHA"

    run_direct_chain
    assert_allowed "a rebased branch with a green published tip"
    assert_branch_not_republished "the default direct-mode path"
    ! grep -q 'CI_GATE_EXACT' <<<"$OUTPUT" ||
        fail "a rebased head is not the published tip and must not be claimed as exact: $OUTPUT"
    [[ "$OUTPUT" == *"CI_GATE_REBASED_HEAD"* ]] ||
        fail "gating the published tip instead of the landing SHA must be stated, not implied: $OUTPUT"
    grep -F -- "--set-metadata ci_gate_sha=$PUBLISHED_SHA" "$CALLS" >/dev/null ||
        fail "the stamp must name the SHA actually proven, not the one being landed"
    grep -F -- "--set-metadata ci_gate_base_sha=$BASE_SHA" "$CALLS" >/dev/null ||
        fail "the base must be the MOVED target tip the work is about to land on"
    grep -F -- "landing $HEAD_SHA" "$CALLS" >/dev/null ||
        fail "the bead must record that the landed SHA differs from the proven one: $(cat "$CALLS")"

    # A regression on the published tip still rejects, without publishing.
    setup_rebased_case
    trap 'rm -rf "$TMP"' RETURN
    base_board_for_red_head "$BASE_SHA"
    red_board "$PUBLISHED_SHA"
    red_board "$HEAD_SHA"
    run_direct_chain
    assert_rejected "$RED_CHECK_ONE"
    assert_branch_not_republished "a default-path rejection"
}

# The opt-in exists for rigs that want the exact-object guarantee, and it is
# the only thing that makes direct mode push the source branch.
test_the_publish_opt_in_gates_the_exact_landing_sha() {
    setup_rebased_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    green_board "$PUBLISHED_SHA"
    green_board "$HEAD_SHA"

    PUBLISH_HEAD_OVERRIDE=true run_direct_chain
    assert_allowed "the publish opt-in on a green board"
    git -C "$REPO" fetch --quiet origin
    [[ "$(git -C "$REPO" rev-parse "refs/remotes/origin/$BRANCH_NAME")" == "$HEAD_SHA" ]] ||
        fail "ci_gate_publish_head=true must publish the rebased head so CI can rule on it"
    grep -F -- "--set-metadata ci_gate_sha=$HEAD_SHA" "$CALLS" >/dev/null ||
        fail "the opt-in path must gate and stamp the exact SHA being landed"
    if grep -F -- "landing " "$CALLS" >/dev/null; then
        fail "the opt-in path proved the landing SHA itself; there is no divergence to record"
    fi
}

# Every way the gate can fail to reach an answer must stop, not proceed. An
# outage is not a verdict, and it must never reject the branch either.
test_api_failures_are_undetermined_never_green() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"

    # No head check-run fixture: the request fails.
    run_direct_chain
    assert_undetermined "an unreadable check-run API" "could not read check-runs for the head commit"

    # Head check-runs readable, head legacy statuses not. Half an answer is not
    # an answer.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    fixture "check-runs.$HEAD_SHA.json" <<'JSON'
{"total_count": 1, "check_runs": [
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    run_direct_chain
    assert_undetermined "unreadable commit statuses" "could not read commit statuses for the head commit"

    # More checks than one page can report: the gate cannot see the whole board,
    # so it cannot attribute anything on it either way.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    board_for "$HEAD_SHA" <<'JSON'
{"total_count": 140, "check_runs": [
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    run_direct_chain
    assert_undetermined "a truncated check-run page" "one page can report"
}

# The waiver exists for rigs that want no hosted gate at all. It is explicit, it
# is loud, and every bead it lets through carries the mark.
test_the_waiver_is_loud_and_recorded() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    CI_GATE_OVERRIDE=false run_direct_chain
    assert_allowed "an explicit waiver"
    [[ "$OUTPUT" == *"CI_GATE_DISABLED_BY_CONFIG"* ]] ||
        fail "a waived CI gate must announce itself: $OUTPUT"
    grep -F -- '--set-metadata ci_gate_result=disabled' "$CALLS" >/dev/null ||
        fail "a bead closed without CI proof must carry that on the record"
    ! grep -q '^GH ' "$CALLS" ||
        fail "a waived gate should not be querying checks at all: $(grep '^GH ' "$CALLS")"
    assert_branch_not_republished "a waived gate"

    # The waiver is the only way off. A rig with no gh and no github.com origin
    # is undetermined, not green.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    green_board "$BASE_SHA"
    green_board "$HEAD_SHA"
    rm -f "$BIN/gh"
    ORIGIN_REPO_NAME="" run_direct_chain
    assert_undetermined "an unresolvable origin repository" "could not resolve the origin repository"
    [[ "$OUTPUT" == *"ci_gate=false"* ]] ||
        fail "an unresolvable origin must point at the waiver rather than dead-end: $OUTPUT"
    ORIGIN_REPO_NAME="gastownhall/kisakcod"
}

# The pull-request handoff gates the exact object: step 1 already pushed the
# rebased branch, so the gate reads the SHA the PR actually carries -- and
# compares it against the same target tip direct mode uses.
test_mr_mode_gates_the_pr_head_sha() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    PR_NUMBER_OVERRIDE=84
    fixture pull.json <<'JSON'
{"number": 84, "head": {"sha": "beda5d39beda5d39beda5d39beda5d39beda5d39"}}
JSON

    run_mr_chain
    [[ "$CODE" -ne 0 ]] || fail "a PR whose head is not what we pushed must not be gated as ours: $OUTPUT"
    [[ "$OUTPUT" == *"but you pushed"* ]] || fail "the SHA mismatch must be named: $OUTPUT"
    assert_not_closed "an mr-mode head SHA mismatch"

    setup_case
    trap 'rm -rf "$TMP"' RETURN
    PR_NUMBER_OVERRIDE=84
    jq -n --arg sha "$HEAD_SHA" '{number: 84, head: {sha: $sha}}' >"$FIX/pull.json"
    base_board_for_red_head "$BASE_SHA"
    red_board "$HEAD_SHA"

    run_mr_chain
    assert_rejected "$RED_CHECK_ONE"
    [[ "$OUTPUT" == *"left intact for fix-forward"* ]] ||
        fail "an mr-mode rejection must leave the branch intact; deleting it orphans the PR"

    # A PR whose failures the target already has is a PR that may be published.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    PR_NUMBER_OVERRIDE=84
    jq -n --arg sha "$HEAD_SHA" '{number: 84, head: {sha: $sha}}' >"$FIX/pull.json"
    red_board "$BASE_SHA"
    red_board "$HEAD_SHA"
    run_mr_chain
    assert_allowed "an mr-mode head inheriting its base's failures"
    grep -F -- "--set-metadata ci_gate_base_sha=$BASE_SHA" "$CALLS" >/dev/null ||
        fail "mr mode must measure against the same target tip direct mode uses"

    setup_case
    trap 'rm -rf "$TMP"' RETURN
    PR_NUMBER_OVERRIDE=84
    jq -n --arg sha "$HEAD_SHA" '{number: 84, head: {sha: $sha}}' >"$FIX/pull.json"
    green_board "$BASE_SHA"
    green_board "$HEAD_SHA"
    run_mr_chain
    assert_allowed "a green PR head"
    grep -F -- "--set-metadata ci_gate_sha=$HEAD_SHA" "$CALLS" >/dev/null ||
        fail "mr mode must stamp the PR head SHA it proved"
    PR_NUMBER_OVERRIDE=""
}

test_shipped_defaults_are_fail_closed
test_the_gate_rules_before_anything_lands
test_green_to_red_is_a_regression_and_rejects
test_red_to_red_is_inherited_and_allows
test_a_red_base_does_not_freeze_the_repository
test_absent_on_base_and_red_on_head_is_a_regression
test_green_to_green_passes_and_the_bead_closes
test_zero_checks_on_both_sides_allows
test_head_with_no_checks_rejects_when_the_base_has_them
test_a_base_with_no_board_cannot_attribute_a_red_head
test_pending_waits_then_goes_undetermined
test_unknown_conclusions_are_red_and_regress
test_legacy_commit_statuses_are_compared_too
test_base_lookup_failure_is_undetermined_not_a_pass
test_direct_mode_publishes_nothing_by_default
test_the_publish_opt_in_gates_the_exact_landing_sha
test_api_failures_are_undetermined_never_green
test_the_waiver_is_loud_and_recorded
test_mr_mode_gates_the_pr_head_sha

echo "refinery CI regression gate tests passed"
