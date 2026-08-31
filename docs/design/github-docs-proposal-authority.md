# GitHub docs proposal authority boundary

## Status

Proposed implementation boundary for one upstream PR. This document describes
the dogfood implementation on `fix/github-followup-handoff-copy`; it does not
describe functionality available on `upstream/main`.

## Outcome

An opted-in pull-request docs reviewer can publish a concise GitHub Check Run
and, only for a validated same-repository proposal, open one App-owned stacked
documentation follow-up PR. It never writes the contributor branch, merges a
PR, or exposes a City admin run page or rendered diff as the review surface.

The original PR remains the review surface. The check either links to the
App-owned follow-up PR or says that action is required. It must not link to an
admin dashboard, a City run locator, or inline proposal-diff text.

## Evidence base

The proposed boundary is reconstructed from the dogfood branch rather than
from a released upstream implementation:

| Dogfood evidence | What it establishes |
| --- | --- |
| `github/scripts/github_intake_docs_patch.py` | Strict canonical review and proposal validation, including exact schemas, SHA-pinned evidence, bounded inputs, documentation-only diffs, and digest verification. |
| `github/scripts/github_intake_docs_patch_worker.py` | The untrusted reviewer receives a sanitized assignment, no GitHub credentials, and emits no candidate when output is unavailable or invalid. |
| `github/scripts/github_intake_docs_impact_pipeline.py` | The trusted intake boundary captures exact-head evidence, binds the candidate to the exact assignment bytes, and rejects invalid candidates before projection. |
| `github/scripts/github_intake_docs_impact.py` | The trusted App alone may create a `gas-city/docs-…` stacked branch and follow-up PR after rechecking the PR head. |
| `github/tests/test_github_intake_docs_{patch,patch_worker,impact_pipeline,impact}.py` | Existing dogfood regression examples for validator, worker, pipeline, and App publication boundaries. |

The eventual PR must preserve the design intent but not copy the retired
dogfood behavior that points a check to a City review page or treats that page
as the proposal-diff UI.

## Minimal self-contained upstream change

Land these pieces together. None is independently useful or safe to ship in
isolation.

| Module | Responsibility |
| --- | --- |
| `github/scripts/github_intake_docs_patch.py` | Canonical proposal/review validator. Require exact fields; exact identity; SHA-256 of the exact UTF-8 diff; documentation-only, non-binary paths; SHA-pinned evidence; bounded claims, checks, files, and diff size. |
| `github/scripts/github_intake_docs_patch_worker.py` | Validate the complete sanitized assignment, run the isolated reviewer with scrubbed environment, and atomically write only a fully validated candidate. Missing, timed-out, oversized, malformed, or mismatched output removes/produces no candidate. |
| `github/scripts/github_intake_docs_impact_pipeline.py` | Fetch exact-base-to-head evidence, reject any file list that is truncated or contains a file without complete usable patch evidence, bind the outbox envelope to the raw assignment digest, and project only a canonical matching review. |
| `github/scripts/github_intake_docs_impact.py` | Persist/project the first exact review; create a follow-up only from a validated `proposal-ready` review; recheck the current head before apply, push, and PR creation; publish only compact GitHub-native check text. |
| `github/scripts/github_intake_service.py` and `github/scripts/github_intake_common.py` | Supply exact PR identity/evidence and narrowly scoped App API helpers plus durable idempotency records for one review and one follow-up per proposal identity. |
| `github/agents/docs-impact-reviewer/{agent.toml,prompt.template.md}` and `github/pack.toml` | Configure the City reviewer as credential-free and instruct it to emit the exact validator-compatible contract; do not grant it GitHub write authority. |
| `github/skills/developer-experience-techdocs/` | Vendor the reviewer methodology so the packaged agent has stable documentation-review guidance without depending on a separately installed skill. |
| `github/tests/test_github_intake_docs_{patch,patch_worker,impact_pipeline,impact}.py` | Cover each trust boundary below. |
| `github/README.md` | Document only the user-visible GitHub lifecycle and its limits. Do not document an admin run/diff page. |

Excluded from this PR: `github_intake_docs_review_workspace.py`, any City-run
page route, any check output that contains a rendered diff, and any UI/API for
browsing reviewer runs. A review workspace may be reconsidered later only if
it remains internal to the reviewer and is not a user-facing proposal surface.

The pack exposes this reviewer without selecting a scheduler, queue, host, or
credential source. An installation opts in by dispatching immutable
assignments to `docs-impact-reviewer`, submitting valid candidates to the
trusted bridge, and independently invoking the lifecycle one-shot intake and
reconciliation operations. This is operational wiring owned by the
installation, not an implied pack deployment.

## Authority and data flow

```text
GitHub PR exact head
  -> trusted intake captures complete bounded evidence
  -> credential-free reviewer receives one immutable assignment
  -> strict validator accepts one digest- and identity-bound candidate
  -> trusted App publishes GitHub Check Run
       -> same-repository proposal: App-owned `gas-city/docs-…` follow-up PR
       -> every other result: action-required check, no branch or PR mutation
```

The proposal identity must contain repository IDs/names, PR number, base SHA,
head SHA, head repository IDs/names, and base ref. The review identity must
match the source identity exactly. The pipeline compares the candidate envelope
digest with the raw assignment bytes, then compares both review identity and
skill with that assignment. This prevents a candidate from another revision,
PR, repository, or reviewer skill from gaining publication authority.

## Fail-closed rules

The following conditions stop before review projection and App mutation:

- GitHub reports more changed files than the evidence collector obtained, a
  file has no textual patch, or any patch/aggregate limit is exceeded. Do not
  silently inspect a prefix of the file list.
- The assignment has missing/extra fields, an incomplete proposal identity,
  unsorted or duplicate paths, non-SHA-pinned evidence references, or evidence
  not bound to the assignment head SHA.
- The reviewer is absent, times out, emits malformed/oversized output, produces
  an incomplete proposal, changes the identity or skill, or cannot pass strict
  review/proposal validation.
- The proposal has missing/extra fields; an unmatched diff digest; non-doc,
  traversal, binary, symlink, or mismatched diff paths; missing claim evidence
  or release scope; or missing/invalid check records.
- The PR head changes before candidate projection, before patch application,
  before pushing the bot branch, or before creating the follow-up PR.

For each condition, retain no usable candidate and create no follow-up. When a
check already exists, complete it as action-required/stale using compact GitHub
text; never substitute an unverifiable conclusion.

## Follow-up PR authority

`create_followup_pull_request` is authorized only when all of these predicates
hold after validation: the verdict is `proposal-ready`; proposal status is
`proposed`; the proposal identity exactly matches the current PR context; the
head repository ID and name equal the base repository; the head ref is present;
and the remote head still equals the reviewed SHA at every mutation boundary.

The App fetches the reviewed SHA into a temporary detached checkout, runs
`git apply --check`, applies the already validated docs-only patch, creates a
new `gas-city/docs-<pr>-<digest>` branch, and opens it with the original PR head
as its base. It must never push to the contributor head ref, call a merge API,
or ask the reviewer worker to do either. Any failure falls back to the compact
action-required result without a branch mutation.

### Compensating stale-source semantics

The App rechecks the source PR head immediately after each terminal Check Run
mutation and immediately after follow-up PR creation. If the source head has
changed, the durable source run becomes `stale` with an `action_required`
conclusion, and the App overwrites the Check with compact stale text so no
successful conclusion remains. If a follow-up was created, the App closes only
that PR after re-reading it and verifying its stable proposal marker, exact
expected `gas-city/docs-…` ref, same base/head repository, and the configured
GitHub App bot login. A marker or branch-looking name supplied by a contributor
is not authority to adopt or close a PR. The marker is represented exactly as
exactly one standalone `<!-- gas-city-docs-followup:<artifact-sha256> -->`
body line; substrings, variants, and duplicate marker lines do not match. It
never closes or modifies the
contributor PR or branch. A failed compensating close leaves the source Check
action-required and records the close as pending rather than widening
authority.

## Test plan for the eventual implementation

1. Validator tests reject every missing/extra proposal field, incomplete
   identity, unpinned evidence, absent claim release scope, absent check field,
   digest mismatch, unsafe/truncated diff, and non-documentation path.
2. Worker tests reject assignments with incomplete evidence bundles or proposal
   identities; prove an unavailable, oversized, malformed, or mismatched
   adapter result leaves no candidate artifact.
3. Pipeline tests model a compare response whose page/file count or patch data
   is incomplete and assert it does not queue/project/publish. They also prove
   wrong assignment digest, identity, skill, or stale head never reaches the
   App projector.
4. App tests prove a valid same-repository result creates only an App-owned
   branch and stacked PR; forked heads, stale heads, invalid proposals, and
   follow-up failures create neither. Assert no command targets the author ref
   and no merge helper/API is called.
5. GitHub-native UX tests assert proposal-ready check output links only to the
   stacked follow-up PR (when created), contains no inline diff, and contains
   no City admin/run/dashboard URL. The action-required fallback gives a clear
   next action without exposing an internal run surface.
6. Run the focused four test modules, then the complete `github/tests`
   discovery suite. Add a mocked GitHub integration seam only at the App API
   boundary; validator and assignment tests use real serialization/validation.

## Acceptance criteria for one upstream PR

- The whole authority chain above lands atomically with its focused tests.
- Incomplete or truncated evidence cannot produce a reviewer candidate,
  proposal, bot branch, follow-up PR, pass conclusion, or merge action.
- A valid same-repository proposal opens at most one App-owned docs follow-up
  branch/PR per proposal identity; retries reuse it.
- No code path writes the contributor branch or invokes PR merge.
- The original GitHub PR/check is the only user-facing review surface. No admin
  run/diff page is linked, documented, or required to act on a proposal.
