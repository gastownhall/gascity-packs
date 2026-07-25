#!/usr/bin/env bash
set -euo pipefail

# Regression suite for the refinery's three pre-close gates.
#
# Reproduction: on a live rig the refinery merged every bead whose LOCAL checks
# passed, and nothing anywhere in its assets read the hosted verdict. The target
# branch went success:9 (07-22) -> failure:3 (07-23) -> failure:11 (07-24), every
# failure a cross-platform target a Linux polecat cannot build. The fix is three
# fail-closed gates between a rebased branch and `gc bd close`: the refinery's
# own review of the diff, hosted CI green on the exact SHA being landed, and
# automated review comments addressed.
#
# The gates ship as an executable block inside mol-refinery-patrol, so this
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
RED_CHECK_ONE="Windows x86 SP / Release"
RED_CHECK_TWO="Portable tests / macOS arm64"

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
if "review-diff" not in steps:
    sys.exit("formula lost the pre-PR review step")
description = steps["merge-push"]["description"]


def fenced(section_marker):
    section = description[description.index(section_marker):]
    return section.split("```bash", 1)[1].split("```", 1)[0]


if what == "gate-block":
    begin = description.index("# BEGIN REFINERY_MERGE_GATE")
    end = description.index("# END REFINERY_MERGE_GATE", begin)
    fragment = description[begin:end]
elif what == "direct-chain":
    fragment = fenced("**0c. Gate chain")
elif what == "mr-chain":
    fragment = fenced("**3b. Gate chain")
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
# fixture models an API failure, which the gates must never read as a pass.
# Sequenced fixtures (<name>.1.json, <name>.2.json) model checks that finish
# between polls.
write_gh_stub() {
    cat >"$BIN/gh" <<'SH'
#!/usr/bin/env bash
printf 'GH %s\n' "$*" >>"$GC_TEST_CALLS"
serve() {
    name="$1"
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
    printf 'HTTP 502: upstream unavailable (%s)\n' "$name" >&2
    return 1
}
case "$*" in
    *graphql*) serve threads ;;
    */check-runs*) serve check-runs ;;
    */commits/*/status*) serve status ;;
    */issues/*/comments*) serve issue-comments ;;
    */pulls/*/comments*) serve review-comments ;;
    */pulls/*/reviews*) serve reviews ;;
    *pulls?state=open*) serve pulls ;;
    */pulls/*) serve pull ;;
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
            show) cat "$GC_TEST_BEAD_JSON" ;;
            update) printf 'UPDATE %s\n' "$*" >>"$GC_TEST_CALLS" ;;
            close) printf 'CLOSE %s\n' "$*" >>"$GC_TEST_CALLS" ;;
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
PR_NUMBER="${GATE_TEST_PR_NUMBER:-}"
GC_RIG="kisakcod"
. "$GATE_BLOCK"
CI_POLL_SECONDS=0
CI_TIMEOUT_SECONDS="$GATE_TEST_CI_TIMEOUT"
CI_ZERO_CHECK_GRACE_SECONDS="$GATE_TEST_CI_GRACE"
CI_GATE="$GATE_TEST_CI_GATE"
. "$GATE_CHAIN"
echo "CHAIN_COMPLETED"
SH
}

# A real repository, because the review gate diffs real refs and the direct
# chain really pushes. `origin` is a local bare repo, so --force-with-lease
# behaves exactly as it does against GitHub.
setup_case() {
    TMP=$(mktemp -d)
    BIN="$TMP/bin"
    FIX="$TMP/fixtures"
    CALLS="$TMP/calls"
    BEAD="$TMP/bead.json"
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
}

# Records the review-diff step's verdict on the bead.
write_bead() {
    local sha=$1 verdict=$2 acceptance=$3 evidence=$4 defect=$5
    jq -n \
        --arg id "$WORK_ID" \
        --arg branch "$BRANCH_NAME" \
        --arg sha "$sha" \
        --arg verdict "$verdict" \
        --arg acceptance "$acceptance" \
        --arg evidence "$evidence" \
        --arg defect "$defect" \
        '[{id: $id, status: "in_progress", metadata: {
             branch: $branch, target: "main",
             review_sha: $sha, review_verdict: $verdict,
             review_acceptance: $acceptance, review_evidence: $evidence,
             review_defect: $defect}}]' >"$BEAD"
}

# The verdict a real, cited review produces: names the criterion, names the
# file the diff touches, names the production call site.
pass_bead() {
    write_bead "$HEAD_SHA" pass \
        "Acceptance: SP int truncation removed from the candidate route path" \
        "src/route.c adds route_candidate and the legacy db_load path in src/route.c now calls it; traced the caller, boundary at 0 and INT_MAX handled" \
        ""
}

fixture() {
    cat >"$FIX/$1"
}

green_ci_fixtures() {
    fixture check-runs.json <<JSON
{"total_count": 2, "check_runs": [
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"},
  {"name": "Lint", "status": "completed", "conclusion": "skipped"}
]}
JSON
    fixture status.json <<'JSON'
{"state": "success", "statuses": []}
JSON
}

no_pr_fixtures() {
    fixture pulls.json <<'JSON'
[]
JSON
}

clean_review_fixtures() {
    fixture pulls.json <<'JSON'
[{"number": 84}]
JSON
    fixture issue-comments.json <<'JSON'
[]
JSON
    fixture review-comments.json <<'JSON'
[]
JSON
    fixture reviews.json <<'JSON'
[]
JSON
    fixture threads.json <<'JSON'
{"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": []}}}}}
JSON
}

run_chain() {
    local chain=$1
    CODE=0
    set +e
    OUTPUT=$(
        PATH="$BIN:$PATH" \
        GC_TEST_CALLS="$CALLS" \
        GC_TEST_BEAD_JSON="$BEAD" \
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
    run_chain "$chain"
}

run_mr_chain() {
    local chain="$TMP/mr-chain.sh"
    extract_shipped mr-chain "$chain"
    run_chain "$chain"
}

assert_not_closed() {
    ! grep -q '^CLOSE ' "$CALLS" ||
        fail "$1: the bead was closed anyway: $(grep '^CLOSE ' "$CALLS")"
}

assert_rejected() {
    local stage=$1 disposition=$2 needle=$3
    [[ "$CODE" -eq 1 ]] || fail "$stage must reject with exit 1 (got $CODE): $OUTPUT"
    [[ "$OUTPUT" == *"GATE_REJECTED $WORK_ID $stage"* ]] ||
        fail "$stage must report GATE_REJECTED naming the gate: $OUTPUT"
    grep -F -- '--status=open' "$CALLS" >/dev/null ||
        fail "$stage must put the bead back in the pool"
    grep -F -- '--assignee=' "$CALLS" >/dev/null ||
        fail "$stage must release the refinery claim"
    grep -F -- "--set-metadata rejection_reason=$stage:" "$CALLS" >/dev/null ||
        fail "$stage must write a rejection_reason naming the gate: $(cat "$CALLS")"
    grep -F -- "--set-metadata recovery.disposition=$disposition" "$CALLS" >/dev/null ||
        fail "$stage must write recovery.disposition=$disposition"
    grep -F -- "$needle" "$CALLS" >/dev/null ||
        fail "$stage rejection_reason must be specific enough to act on (want '$needle'): $(cat "$CALLS")"
    grep -F -- 'gc.routed_to' "$CALLS" >/dev/null ||
        fail "$stage must route the bead back to the polecat pool"
    assert_not_closed "$stage"
    [[ "$OUTPUT" == *"left intact for fix-forward"* ]] ||
        fail "$stage must leave the branch intact for fix-forward: $OUTPUT"
}

assert_undetermined() {
    local label=$1 needle=$2
    [[ "$CODE" -ne 0 ]] || fail "$label must not pass: $OUTPUT"
    [[ "$OUTPUT" == *"GATE_UNDETERMINED"* ]] ||
        fail "$label must report GATE_UNDETERMINED: $OUTPUT"
    [[ "$OUTPUT" == *"$needle"* ]] ||
        fail "$label must say why it could not be determined (want '$needle'): $OUTPUT"
    ! grep -F -- '--status=open' "$CALLS" >/dev/null ||
        fail "$label is our fault, not the branch's: it must not reject the bead"
    assert_not_closed "$label"
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
for name in ("ci_timeout_seconds", "ci_zero_check_grace_seconds"):
    if int(variables[name]["default"]) <= 0:
        raise SystemExit(f"{name} must leave a real window; 0 would reject every honest branch")
bots = variables["review_bots"]["default"]
for bot in ("gemini-code-assist[bot]", "chatgpt-codex-connector[bot]"):
    if bot not in bots:
        raise SystemExit(f"review_bots must cover {bot}")

steps = {step["id"]: step for step in data["steps"]}
if steps["merge-push"]["needs"] != ["review-diff"]:
    raise SystemExit("merge-push must depend on the review step; a skippable review is not a gate")
prompt = open(sys.argv[2], encoding="utf-8").read()
for needle in ("Pre-Close Gates", "zero check-runs", "gemini-code-assist[bot]",
               "chatgpt-codex-connector[bot]", "recovery.disposition"):
    if needle not in prompt:
        raise SystemExit(f"refinery prompt must document {needle}")
if 'FORBIDDEN: Reading polecat code to "understand what they were trying to do."' in prompt:
    raise SystemExit("the prompt cannot forbid reading the diff and also require reviewing it")
PY
}

# Direct mode is the default and is what produced the incident, so it must run
# every gate the pull-request path runs, and it must gate the SHA it lands.
test_direct_mode_runs_all_three_gates_before_it_merges() {
    python3 - "$FORMULA" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    data = tomllib.load(handle)
description = {step["id"]: step for step in data["steps"]}["merge-push"]["description"]
direct = description[description.index('**If MERGE_STRATEGY = "direct"'):description.index('**If MERGE_STRATEGY = "mr"')]
merge_script = direct.index("git worktree add --detach")
for call in ("gate_review", "gate_ci", "gate_bot_reviews"):
    if call not in direct:
        raise SystemExit(f"direct mode must run {call}")
    if direct.index(call) > merge_script:
        raise SystemExit(f"{call} must rule before direct mode touches the target branch")
if direct.index("gate_review") > direct.index("gate_ci"):
    raise SystemExit("the review verdict must precede publication and CI")
if 'git push origin "HEAD:$BRANCH"' not in direct:
    raise SystemExit("direct mode must publish the exact SHA it intends to land so CI can rule on it")
for unset in ("--unset-metadata rejection_reason", "--unset-metadata recovery.disposition"):
    if unset not in direct:
        raise SystemExit(f"the successful close must clear {unset.split()[-1]}")

mr = description[description.index('**If MERGE_STRATEGY = "mr"'):]
close = mr.index("--set-metadata merge_result=pull_request")
for call in ("gate_review", "gate_ci", "gate_bot_reviews"):
    if mr.index(call) > close:
        raise SystemExit(f"mr mode must run {call} before it closes the bead")
PY
}

# Stage 1, the live shape from the affected city: acceptance unmet because the
# candidate has no production call site. It must reject BEFORE anything is
# published, and without asking GitHub anything.
test_review_gate_rejects_a_cited_defect_before_anything_is_published() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    write_bead "$HEAD_SHA" reject "" "" \
        "Acceptance unmet: src/route.c adds route_candidate but no production route call site reaches it; legacy db_load path remains the only path"

    run_direct_chain
    assert_rejected "Review gate" "acceptance-unmet" "no production route call site"
    ! grep -q '^GH ' "$CALLS" ||
        fail "a review rejection must not need GitHub at all: $(grep '^GH ' "$CALLS")"
    [[ "$(git -C "$REPO" rev-parse "origin/$BRANCH_NAME")" == "$PUBLISHED_SHA" ]] ||
        fail "a review rejection must happen before the branch is published"
}

# A gate an agent satisfies by asserting "looks good" manufactures false
# confidence. Every one of these must refuse rather than pass.
test_review_gate_refuses_verdicts_that_cite_nothing() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN

    write_bead "" "" "" "" ""
    run_direct_chain
    assert_undetermined "an unreviewed diff" "review_verdict is 'unset'"

    : >"$CALLS"
    write_bead "$HEAD_SHA" pass "Acceptance: the candidate route is wired in" "LGTM" ""
    run_direct_chain
    assert_undetermined "a rubber-stamp approval" "review_evidence"

    : >"$CALLS"
    write_bead "$HEAD_SHA" pass \
        "Acceptance: SP int truncation removed from the candidate route path" \
        "I read the whole change carefully and traced the logic end to end; everything looks correct and I am confident it behaves" \
        ""
    run_direct_chain
    assert_undetermined "an approval citing no file in the diff" "cites no file this diff touches"

    : >"$CALLS"
    pass_bead
    jq '.[0].metadata.review_sha = "0000000000000000000000000000000000000000"' "$BEAD" >"$BEAD.tmp"
    mv "$BEAD.tmp" "$BEAD"
    run_direct_chain
    assert_undetermined "an approval of a different SHA" "review_sha"

    : >"$CALLS"
    write_bead "$HEAD_SHA" reject "" "" "this is wrong"
    run_direct_chain
    assert_undetermined "an uncitable rejection" "review_defect"
}

# The incident itself: hosted CI red on the head SHA.
test_red_ci_rejects_and_does_not_close() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead

    fixture check-runs.json <<JSON
{"total_count": 3, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "failure"},
  {"name": "$RED_CHECK_TWO", "status": "completed", "conclusion": "timed_out"},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    fixture status.json <<'JSON'
{"state": "failure", "statuses": []}
JSON

    run_direct_chain
    assert_rejected "CI gate" "ci-red" "$RED_CHECK_ONE"
    grep -F -- "$RED_CHECK_TWO" "$CALLS" >/dev/null ||
        fail "a timed_out check is red too and must be named"
    [[ "$(git -C "$REPO" rev-parse "origin/$BRANCH_NAME")" == "$HEAD_SHA" ]] ||
        fail "the reviewed SHA must be published so CI can rule on it, and left there for fix-forward"
}

# Several commits in the incident carried no checks at all. Nothing ran cannot
# prove nothing is broken.
test_zero_check_runs_is_not_green() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead

    fixture check-runs.json <<'JSON'
{"total_count": 0, "check_runs": []}
JSON
    fixture status.json <<'JSON'
{"state": "pending", "statuses": []}
JSON

    run_direct_chain
    assert_rejected "CI gate" "ci-red" "zero check-runs"
}

# Pending must WAIT, never pass — and the wait must be bounded.
test_pending_checks_wait_and_never_pass() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead

    # A red-free but unfinished board, with the wait window already exhausted.
    fixture check-runs.json <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Windows x86 / Debug", "status": "in_progress", "conclusion": null},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    fixture status.json <<'JSON'
{"state": "pending", "statuses": []}
JSON

    run_direct_chain
    assert_rejected "CI gate" "ci-red" "still running"
    [[ "$OUTPUT" != *"CI_GATE_GREEN"* ]] ||
        fail "an unfinished check board must never be reported green"

    # The same board, given a window: it finishes green between polls and the
    # gate proceeds. Pending is a wait, not a verdict.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    fixture check-runs.1.json <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Windows x86 / Debug", "status": "queued", "conclusion": null},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    fixture check-runs.2.json <<'JSON'
{"total_count": 2, "check_runs": [
  {"name": "Windows x86 / Debug", "status": "completed", "conclusion": "success"},
  {"name": "Portable tests / Linux amd64", "status": "completed", "conclusion": "success"}
]}
JSON
    fixture status.json <<'JSON'
{"state": "success", "statuses": []}
JSON
    no_pr_fixtures

    CI_TIMEOUT_OVERRIDE=120 run_direct_chain
    [[ "$CODE" -eq 0 ]] || fail "checks that finish green inside the window must pass: $OUTPUT"
    [[ "$OUTPUT" == *"CI_GATE_GREEN"* ]] || fail "a green board must be reported green: $OUTPUT"
}

# An unrecognized conclusion is not on the accept list, so it is not a pass.
test_unknown_conclusions_default_to_red() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead

    fixture check-runs.json <<'JSON'
{"total_count": 1, "check_runs": [
  {"name": "Windows x86 (no Steam)", "status": "completed", "conclusion": "stale"}
]}
JSON
    fixture status.json <<'JSON'
{"state": "success", "statuses": []}
JSON

    run_direct_chain
    assert_rejected "CI gate" "ci-red" "Windows x86 (no Steam)"
}

# Stage 3: the two bots that review every PR on this rig.
test_unaddressed_bot_comments_reject() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    green_ci_fixtures
    fixture pulls.json <<'JSON'
[{"number": 84}]
JSON
    fixture issue-comments.json <<'JSON'
[
  {"id": 9001, "user": {"login": "gemini-code-assist[bot]", "type": "Bot"},
   "created_at": "2026-07-23T09:00:00Z",
   "body": "The retry loop in src/route.c can spin forever when the transport returns EAGAIN."}
]
JSON
    fixture review-comments.json <<'JSON'
[]
JSON
    fixture reviews.json <<'JSON'
[]
JSON
    fixture threads.json <<'JSON'
{"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": []}}}}}
JSON

    run_direct_chain
    assert_rejected "Review-comment gate" "review-comments-unaddressed" "gemini-code-assist[bot]"
    grep -F -- 'PR #84' "$CALLS" >/dev/null ||
        fail "the rejection must name the pull request the comments are on"
}

# The two shapes that would make the gate free: a bot answering a bot, and a
# one-word acknowledgement. Neither is addressing anything.
test_bot_replies_and_one_word_acks_do_not_address_anything() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    green_ci_fixtures
    fixture pulls.json <<'JSON'
[{"number": 84}]
JSON
    fixture issue-comments.json <<'JSON'
[
  {"id": 9001, "user": {"login": "chatgpt-codex-connector[bot]", "type": "Bot"},
   "created_at": "2026-07-23T09:00:00Z",
   "body": "route_candidate never checks the return of route_legacy in src/route.c."},
  {"id": 9002, "user": {"login": "github-actions[bot]", "type": "Bot"},
   "created_at": "2026-07-23T09:05:00Z",
   "body": "Coverage report: 84% of statements covered, no change from the base commit."},
  {"id": 9003, "user": {"login": "polecat-nux", "type": "User"},
   "created_at": "2026-07-23T09:06:00Z",
   "body": "done"}
]
JSON
    fixture review-comments.json <<'JSON'
[]
JSON
    fixture reviews.json <<'JSON'
[]
JSON
    fixture threads.json <<'JSON'
{"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": []}}}}}
JSON

    run_direct_chain
    assert_rejected "Review-comment gate" "review-comments-unaddressed" "chatgpt-codex-connector[bot]"
}

# An unresolved inline thread is unaddressed even when the PR has plenty of
# unrelated conversation: inline comments are cleared in their own thread.
test_unresolved_inline_thread_rejects() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    green_ci_fixtures
    fixture pulls.json <<'JSON'
[{"number": 84}]
JSON
    fixture issue-comments.json <<'JSON'
[
  {"id": 9100, "user": {"login": "polecat-nux", "type": "User"},
   "created_at": "2026-07-23T12:00:00Z",
   "body": "Rebased onto main and re-ran the portable suites locally, all green."}
]
JSON
    fixture review-comments.json <<'JSON'
[
  {"id": 501, "in_reply_to_id": null, "user": {"login": "gemini-code-assist[bot]", "type": "Bot"},
   "created_at": "2026-07-23T10:00:00Z",
   "body": "This drops the SP truncation guard; int overflow is reachable from the candidate path."}
]
JSON
    fixture reviews.json <<'JSON'
[]
JSON
    fixture threads.json <<'JSON'
{"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
  {"isResolved": false, "comments": {"nodes": [{"databaseId": 501}]}}
]}}}}}
JSON

    run_direct_chain
    assert_rejected "Review-comment gate" "review-comments-unaddressed" "inline_comment"
}

# Every accepted form of "addressed", then the close. This is the happy path,
# end to end: gates rule, the merge lands, and the terminal update clears both
# rejection fields before the close.
test_addressed_comments_pass_and_the_happy_path_closes() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    green_ci_fixtures
    fixture pulls.json <<'JSON'
[{"number": 84}]
JSON
    fixture issue-comments.json <<'JSON'
[
  {"id": 9001, "user": {"login": "gemini-code-assist[bot]", "type": "Bot"},
   "created_at": "2026-07-23T09:00:00Z",
   "body": "The retry loop in src/route.c can spin forever when the transport returns EAGAIN."},
  {"id": 9002, "user": {"login": "polecat-nux", "type": "User"},
   "created_at": "2026-07-23T11:00:00Z",
   "body": "Bounded the retry loop in src/route.c at 5 attempts with backoff; EAGAIN now surfaces to the caller."}
]
JSON
    fixture review-comments.json <<'JSON'
[
  {"id": 501, "in_reply_to_id": null, "user": {"login": "gemini-code-assist[bot]", "type": "Bot"},
   "created_at": "2026-07-23T10:00:00Z",
   "body": "This drops the SP truncation guard."},
  {"id": 502, "in_reply_to_id": null, "user": {"login": "chatgpt-codex-connector[bot]", "type": "Bot"},
   "created_at": "2026-07-23T10:05:00Z",
   "body": "Prefer a named constant for the retry ceiling."}
]
JSON
    fixture reviews.json <<'JSON'
[
  {"id": 700, "user": {"login": "chatgpt-codex-connector[bot]", "type": "Bot"},
   "state": "CHANGES_REQUESTED", "submitted_at": "2026-07-23T10:05:00Z",
   "body": "The candidate route path is not reachable from production yet."},
  {"id": 701, "user": {"login": "chatgpt-codex-connector[bot]", "type": "Bot"},
   "state": "APPROVED", "submitted_at": "2026-07-23T12:00:00Z",
   "body": "Wiring now reaches the candidate route."}
]
JSON
    fixture threads.json <<'JSON'
{"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
  {"isResolved": true, "comments": {"nodes": [{"databaseId": 501}]}},
  {"isResolved": true, "comments": {"nodes": [{"databaseId": 502}]}}
]}}}}}
JSON

    run_direct_chain
    [[ "$CODE" -eq 0 ]] || fail "the happy path must clear every gate: $OUTPUT"
    [[ "$OUTPUT" == *"CHAIN_COMPLETED"* ]] || fail "the gate chain did not complete: $OUTPUT"
    [[ "$OUTPUT" == *"REVIEW_GATE_CLEAR"* ]] || fail "the review-comment gate did not report clear: $OUTPUT"
    grep -F -- "--set-metadata ci_gate_sha=$HEAD_SHA" "$CALLS" >/dev/null ||
        fail "the CI gate must stamp the SHA it proved onto the bead"
    ! grep -q '^CLOSE ' "$CALLS" ||
        fail "the gates themselves must never close the bead"

    # The shipped terminal update + close, run with the same fake CLI.
    local close="$TMP/close.sh"
    extract_shipped direct-close "$close"
    : >"$CALLS"
    (
        PATH="$BIN:$PATH" GC_TEST_CALLS="$CALLS" GC_TEST_BEAD_JSON="$BEAD" \
        WORK="$WORK_ID" MERGED_SHA="$HEAD_SHA" MERGED_SHORT="${HEAD_SHA:0:7}" TARGET=main \
        bash "$close"
    ) || fail "the shipped close chain did not run"
    grep -q '^CLOSE ' "$CALLS" || fail "the happy path must close the bead"
    grep -F -- '--unset-metadata rejection_reason' "$CALLS" >/dev/null ||
        fail "the successful close must clear rejection_reason"
    grep -F -- '--unset-metadata recovery.disposition' "$CALLS" >/dev/null ||
        fail "the successful close must clear recovery.disposition"
    grep -F -- "--set-metadata merged_sha=$HEAD_SHA" "$CALLS" >/dev/null ||
        fail "the close must record the merged SHA that the CI gate proved"
}

# Every way the gates can fail to reach an answer must stop, not proceed. An
# outage is not a verdict.
test_api_failures_are_undetermined_never_green() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead

    # No check-run fixture at all: the request fails.
    run_direct_chain
    assert_undetermined "an unreadable check-run API" "could not read check-runs"

    # Checks are green, but asking whether the branch has a PR fails. An empty
    # answer here would read as "no PR, nothing to review" — a silent pass.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    green_ci_fixtures
    run_direct_chain
    [[ "$CODE" -ne 0 ]] || fail "a failed PR lookup must not pass as 'no pull request': $OUTPUT"
    [[ "$OUTPUT" == *"could not ask GitHub whether"* ]] ||
        fail "a failed PR lookup must say so: $OUTPUT"
    assert_not_closed "a failed PR lookup"

    # Comments readable, thread resolution not. Resolution is half the
    # definition of addressed, so without it nothing is determined.
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    green_ci_fixtures
    clean_review_fixtures
    rm -f "$FIX/threads.json"
    run_direct_chain
    assert_undetermined "unreadable review-thread resolution" "review-thread resolution"
}

# A branch with no pull request has no automated review surface — but that is
# an answer from GitHub, not an assumption.
test_direct_mode_without_a_pr_says_so_out_loud() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    green_ci_fixtures
    no_pr_fixtures

    run_direct_chain
    [[ "$CODE" -eq 0 ]] || fail "a branch with no PR must still pass the other gates: $OUTPUT"
    [[ "$OUTPUT" == *"has no pull request"* ]] ||
        fail "the absence of a review surface must be stated, not assumed: $OUTPUT"
}

# The waiver exists for rigs with no hosted CI. It is explicit, and every bead
# it lets through carries the mark.
test_the_ci_waiver_is_loud_and_recorded() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
    no_pr_fixtures

    CI_GATE_OVERRIDE=false run_direct_chain
    [[ "$CODE" -eq 0 ]] || fail "an explicit waiver must not wedge the queue: $OUTPUT"
    [[ "$OUTPUT" == *"CI_GATE_DISABLED_BY_CONFIG"* ]] ||
        fail "a waived CI gate must announce itself: $OUTPUT"
    grep -F -- '--set-metadata ci_gate_result=disabled' "$CALLS" >/dev/null ||
        fail "a bead closed without CI proof must carry that on the record"
    ! grep -F -- 'check-runs' "$CALLS" >/dev/null ||
        fail "a waived CI gate should not be querying checks at all"
    [[ "$OUTPUT" == *"has no pull request"* ]] ||
        fail "waiving CI must not waive the review-comment gate: $OUTPUT"
}

# The pull-request handoff gates the SHA the PR actually carries.
test_mr_mode_gates_the_pr_head_sha() {
    setup_case
    trap 'rm -rf "$TMP"' RETURN
    pass_bead
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
    pass_bead
    PR_NUMBER_OVERRIDE=84
    jq -n --arg sha "$HEAD_SHA" '{number: 84, head: {sha: $sha}}' >"$FIX/pull.json"
    fixture check-runs.json <<JSON
{"total_count": 1, "check_runs": [
  {"name": "$RED_CHECK_ONE", "status": "completed", "conclusion": "failure"}
]}
JSON
    fixture status.json <<'JSON'
{"state": "failure", "statuses": []}
JSON

    run_mr_chain
    assert_rejected "CI gate" "ci-red" "$RED_CHECK_ONE"
    PR_NUMBER_OVERRIDE=""
}

test_shipped_defaults_are_fail_closed
test_direct_mode_runs_all_three_gates_before_it_merges
test_review_gate_rejects_a_cited_defect_before_anything_is_published
test_review_gate_refuses_verdicts_that_cite_nothing
test_red_ci_rejects_and_does_not_close
test_zero_check_runs_is_not_green
test_pending_checks_wait_and_never_pass
test_unknown_conclusions_default_to_red
test_unaddressed_bot_comments_reject
test_bot_replies_and_one_word_acks_do_not_address_anything
test_unresolved_inline_thread_rejects
test_addressed_comments_pass_and_the_happy_path_closes
test_api_failures_are_undetermined_never_green
test_direct_mode_without_a_pr_says_so_out_loud
test_the_ci_waiver_is_loud_and_recorded
test_mr_mode_gates_the_pr_head_sha

echo "refinery merge gate tests passed"
