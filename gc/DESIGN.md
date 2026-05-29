---
title: GC Workflow Pack V0
status: Implemented V0
created_at: 2026-05-25
updated_at: 2026-05-26
sources:
  - ~/gc-packs.md
  - ../CONTEXT.md
  - /data/projects/gascity/engdocs/design/convoy-first-formulas-and-drain-v0.md
---

# Design: GC Workflow Pack V0

## Summary

Replace the current basic `gc` pack with a convoy-native planning and build
workflow pack.

The pack provides:

- interactive skills for `gather-requirements`, `plan-implementation`, `create-beads`, and the interactive
  front half of `build`
- public durable formulas for `implement`, `gap-analysis`, `review`, and
  `do-work`
- visible internal formulas or helpers for `build-run`, `do-work-item`,
  fix-convoy synthesis, final publishing, and same-session shared-lifecycle
  implementation
- GitHub adapter skills and formulas for issue triage, PR review, and issue
  fix workflows
- scripts for task-payload validation, convoy/bead creation, context bundle
  validation, verdict report validation, and artifact-path resolution

Every formula that uses `contract = "graph.v2"` is convoy-native. It consumes
the reserved graph target `convoy_id`, never legacy `issue` or `bead_id`
variables. A bare bead target is normalized by Gas City core into a visible
singleton convoy before formula execution.

The pack owns workflow behavior and prompt contracts. Gas City core owns the
runtime mechanics: graph.v2 `convoy_id`, singleton convoy normalization,
synthetic drain-unit convoys, drain control beads, graph.v2 drain
materialization, continuation-affinity hook behavior, and convoy membership
primitives.

## Current System

The current `gc` pack is a starter implementation:

- [gc/README.md](./README.md) documents three manual planning skills and one
  `implement` formula.
- [gc/skills/gather-requirements/SKILL.md](./skills/gather-requirements/SKILL.md) writes
  `requirements.md`.
- [gc/skills/plan-implementation/SKILL.md](./skills/plan-implementation/SKILL.md) writes `implementation-plan.md`.
- [gc/skills/create-beads/SKILL.md](./skills/create-beads/SKILL.md) writes
  `tasks.md` and then runs `assets/scripts/create_beads_from_tasks.py`.
- the legacy bead-creation script reads a payload with `epics[]` and `beads[]`,
  creates epic/task beads, and wires dependencies.
- [gc/formulas/implement.formula.toml](./formulas/implement.formula.toml) is a
  single formula that takes `plan_slug` and optional `work_beads`, routes those
  beads, waits for closure, then runs inline gap-analysis and review loops.

This does not match the desired v0:

- task grouping is `epics[]`, not nested `convoys[]`
- formula input is plan/bead scoped, not convoy scoped
- implementation, gap analysis, review, fix synthesis, and publish behavior are
  fused into one formula
- context is implicit artifact layout instead of explicit context bundles
- review and gap-analysis reports are prose/metadata driven instead of verdict
  reports with a small structured header
- same-session implementation cannot preserve one shared worktree lifecycle
  around item work

## Design Goals

- Make convoys the workflow ownership boundary.
- Keep planning/design/decomposition interactive and separately callable.
- Make implementation, gap analysis, review, and fix loops durable formulas.
- Keep all v2 formula inputs convoy-first and fail fast on legacy `issue` or
  `bead_id` usage.
- Separate context from ownership. A context bundle helps agents understand the
  work, but the convoy is the only implementation boundary.
- Preserve composability by factoring reusable public formulas and visible
  internal helpers.
- Let build run a full lifecycle from idea to reviewed code without requiring
  initial artifacts.
- Keep push and PR creation explicit opt-ins.

## Non-Goals

- Do not add hardcoded roles to Go or pack scripts.
- Do not make the `gc` pack part of Gas City SDK core.
- Do not duplicate the existing bugflow or adopt-pr workflow internals in the
  GitHub adapter formulas. The GitHub workflows are thin edge adapters over
  the generic `gc` primitives.
- Do not require standalone `create-beads` to generate context bundles.
- Do not close convoy heads as a side effect of implementation or build.
- Do not make direct `implement` run gap-analysis or review loops.

## Runtime Prerequisites

This pack assumes the Gas City core design in
`engdocs/design/convoy-first-formulas-and-drain-v0.md`:

- targeted graph.v2 formulas receive reserved `convoy_id`
- graph.v2 formulas reject `issue`, `bead_id`, and user-supplied `convoy_id`
- targeting a normal bead creates or reuses a visible singleton convoy
- graph.v2 formula success does not auto-close input convoys or source beads
- graph.v2 drain steps can materialize item formulas against convoy inputs
- drain control beads can create drain-unit convoys and item workflow roots
- synthetic convoys are visible but inert

The pack also depends on existing convoy membership behavior:

- `gc convoy create <name> <ids...>` creates a `type=convoy` bead and tracks
  members
- `gc convoy add <convoy-id> <issue-id>` records membership through the
  canonical `tracks` relation
- convoy integration branch metadata is the unprefixed `target` field, exposed
  by `gc convoy target`

Shared-session implementation additionally depends on continuation-affinity
hook behavior:

- executable work with `gc.continuation_group` and
  `gc.session_affinity=require` must stay on one session
- a pinned continuation session must not fall through to unrelated routed work
- same-session continuation uses live ready checks rather than cached ready
  lists

If a runtime prerequisite is missing, the affected formula must fail before
creating work rather than silently degrading to bead-scoped behavior.

### Runtime Capability Gate

<!-- REVIEW: added per runtime-prerequisites-contract -->

Every launchable formula starts with a pack-owned capability gate before any
pack side effect. The gate may report failure on the already-created formula
run bead, but it must not create workflow roots, drain controls, routed beads,
convoys, worktrees, fix work, branch refs, or pack artifacts before all required
capabilities for that formula pass.

Capability failures use deterministic codes and include the affected formula,
missing primitive, checked phase, and next action.

| Capability | Required by | Detection phase | Failure code |
| --- | --- | --- | --- |
| graph.v2 targeted invocation and reserved `convoy_id` injection | `implement`, `do-work`, `same-session-implement` | formula entry | `GC_CONTRACT_GRAPH_V2_UNAVAILABLE` |
| reserved-input collision rejection for `convoy_id`, `issue`, and `bead_id` | all graph.v2 formulas | formula entry | `GC_CONTRACT_RESERVED_INPUT` |
| visible singleton convoy normalization for bare bead targets | `implement`, `do-work` | formula entry | `GC_CONTRACT_SINGLETON_CONVOY_UNAVAILABLE` |
| convoy membership primitives and stable member traversal | `create-beads`, `implement`, `same-session-implement` | pre-create or pre-drain | `GC_CONTRACT_CONVOY_MEMBERSHIP_UNAVAILABLE` |
| graph.v2 drain materialization and dispatcher wakeup | `implement`, separate-session drain, `do-work` | pre-drain | `GC_CONTRACT_DRAIN_MATERIALIZER_UNAVAILABLE` |
| drain control beads and drain-unit convoys | `implement`, `same-session-implement` | pre-drain | `GC_CONTRACT_DRAIN_UNAVAILABLE` |
| core shared-drain context `shared`, item formula reference, `single_lane = true`, and selected `on_item_failure` policy | `same-session-implement` | pre-drain | `GC_CONTRACT_SHARED_DRAIN_UNAVAILABLE` |
| structured `gc hook` statuses: `work`, `wait`, `empty` | same-session drain, continuation sessions | pre-drain | `GC_CONTRACT_HOOK_STATUS_UNAVAILABLE` |
| hard continuation affinity and `gc runtime drain-continue` | same-session drain | pre-drain | `GC_CONTRACT_CONTINUATION_UNAVAILABLE` |
| monotonic `gc.closed_seq` or equivalent ready-state watermark | same-session drain, build recovery | pre-drain | `GC_CONTRACT_CLOSED_SEQ_UNAVAILABLE` |
| verification sandbox runner for generated or task-authored verification commands | `do-work`, `build-run`, `fix-convoy` | pre-verification | `GC_CONTRACT_SANDBOX_UNAVAILABLE` |
| conditional create/update store primitives for idempotency and locks | `build-run`, `fix-convoy`, `publish` | pre-state-machine | `GC_CONTRACT_STORE_PRIMITIVE_UNAVAILABLE` |

The capability gate is validated with fake-city and temp-city tests that
disable each primitive independently and assert that bead, relation, artifact,
worktree, and ref counts are unchanged after failure.

### Runtime Capability Handshake

<!-- REVIEW: added per runtime-capability-handshake -->

The authoritative runtime signal is the core dry-run prepare API:

```bash
gc runtime prepare \
  --contract graph.v2 \
  --formula <formula-name> \
  --target <bead-or-convoy-id> \
  --capabilities <comma-separated-primitives> \
  --reject-type epic \
  --dry-run \
  --json
```

Formula implementations may call the matching in-process API, but the CLI JSON
shape is the compatibility contract. V0 requires core contract id
`graph.v2.drain.v1` or a later compatible contract whose `semantics_hash`
matches the formula asset lock file. If core does not expose the prepare API,
the pack fails closed with `GC_CONTRACT_PREPARE_UNAVAILABLE`; it does not infer
support from command presence or best-effort probing.

Successful prepare returns:

```json
{
  "schema": "gc.runtime-prepare.v1",
  "contract_id": "graph.v2.drain.v1",
  "semantics_hash": "sha256:<core-semantics>",
  "formula": "implement",
  "target": {
    "requested_id": "pp-123",
    "kind": "convoy",
    "normalized_convoy_id": "pp-123",
    "normalization_side_effects": []
  },
  "capabilities": {
    "graph_v2": {"status": "ok", "version": "1"},
    "drain": {"status": "ok", "version": "1"},
    "hook_status": {"status": "ok", "version": "1"},
    "closed_seq": {"status": "ok", "version": "1"},
    "store_cas": {"status": "ok", "version": "1"}
  }
}
```

Failure returns the same schema with `ok=false`, deterministic `code`,
`primitive`, `checked_phase`, `retryable`, `human_action`, and
`side_effects_committed=false`. The only side effect allowed before pack
validation is the already-created formula run bead. Workflow roots, drain
controls, routed beads, worktrees, branch refs, pack artifacts, fix convoys, and
publish records are forbidden before prepare succeeds.

Checks are proactive when the prepare API can answer before core normalization:
reserved variable collisions, `type=epic` target rejection, graph.v2 target
support, drain support, hook status support, continuation affinity,
`gc.closed_seq`, store CAS, and publish prerequisites. Checks are reactive only
for effects core owns after prepare has accepted them, such as the visible
singleton convoy created for an allowed bare task target. Reactive checks must
record the normalized target id in the checkpoint before any pack side effect.

Conformance tests pin the `semantics_hash` and run every required primitive in
isolation. If a future core build changes graph.v2 target normalization, drain
manifest semantics, `gc hook` status predicates, continuation affinity, or store
CAS behavior without updating the contract id/hash, formula installation and
launch fail closed.

### Reserved Graph Inputs

<!-- REVIEW: added per reserved-convoy-id-input -->

`convoy_id` is a reserved graph.v2 system input. Formula manifests must not
declare `[vars.convoy_id]`, rig variables must not define it, and task payload
or inherited metadata must not set it. Core injects the normalized target convoy
only after targeted invocation has resolved a convoy or created/reused a visible
singleton convoy for a bare bead target.

The following collisions fail before formula execution with
`GC_CONTRACT_RESERVED_INPUT`: user CLI variables, rig variables, order
variables, inherited metadata, task payload metadata, or formula defaults named
`convoy_id`; legacy `issue` or `bead_id` inputs on graph.v2 formulas; and
attempts to route a `type=epic` bead as a graph.v2 target.

## Pack Surface

### Interactive Skills

`gather-requirements`

- Input: freeform human idea.
- Output: approved `requirements.md`.
- Behavior: interview one question at a time, inspect repo for discoverable
  answers, write front matter with `status: draft|approved`.

`plan-implementation`

- Input: approved `requirements.md`.
- Output: approved `implementation-plan.md`.
- Behavior: repo-grounded architecture document, concrete enough for
  decomposition.

`create-beads`

- Input: approved `requirements.md` and `implementation-plan.md`.
- Output: approved `tasks.md`, then created beads and convoys.
- Behavior: validate the task forest against requirements/design before bead
  creation. Human approval is required before creation.

`build`

- Input: none required.
- Output: durable build artifact set and, optionally, pushed branch or PR.
- Behavior: interactive front half creates requirements, design, and
  decomposition artifacts with human approval gates. After decomposition is
  approved, the skill launches durable `build-run`.

`gh-issue-triage`

- Input: full canonical GitHub issue URL.
- Output: structured triage report artifact and one GitHub triage comment keyed
  by the issue body hash.
- Behavior: run or reuse idempotent issue triage. It may use a disposable
  triage worktree to create reproduction artifacts, but it does not create
  implementation convoys.

`gh-pr-review`

- Input: full canonical GitHub PR URL.
- Output: structured review report artifact and one sticky normal PR comment
  for the reviewed head SHA.
- Behavior: delegate review judgment to the generic report-only `review`
  formula, then gate or post the PR comment according to posting policy.

`gh-issue-fix`

- Input: full canonical GitHub issue URL.
- Output: issue-fix run artifacts, optional draft or ready PR, and one sticky
  issue status comment.
- Behavior: run/reuse triage, generate approved requirements from triage,
  proceed through durable design/decompose/build behavior, publish only when
  explicitly requested, and never merge in v0.

### Public Formulas

`implement`

- Input: graph.v2 target convoy, optional `context_path`, optional
  `drain_policy`, optional branch/publish settings.
- Output: aggregate implementation summary.
- Behavior: validates the convoy, drains it into implementation work, waits for
  selected runnable anchors to close, writes summary, optionally pushes/opens PR
  on success.
- Default drain policy: `separate`.
- Same-session must be explicit.
- Direct `implement` does not run gap-analysis or review.

`do-work`

- Input: graph.v2 target convoy, optional context bundle and branch variables.
- Output: commits, per-item implementation summary, closed owned work anchors.
- Behavior: full lifecycle for an implementation convoy. For drain-unit convoys
  it reads `gc.drain_member_id` to find the underlying task. For a broader
  convoy invoked directly, it treats the whole convoy as the ownership boundary.

`gap-analysis`

- Input: context bundle, implementation summary, and diff/artifact references.
- Output: verdict report.
- Behavior: report-only. It does not create fix work or reopen anchors.

`review`

- Input: diff/branch/commit subject, optional context bundle, optional
  implementation summary.
- Output: verdict report.
- Behavior: report-only. It does not create fix work or reopen anchors.

### Visible Internal Formulas And Helpers

`build-run`

- Durable back half launched by the `build` skill after decomposition approval.
- Runs implementation, gap-analysis fix loop, review fix loop, and finalization.

`do-work-item`

- Reusable middle phase for item implementation inside an existing worktree
  lifecycle.
- Owns item-level implementation, verification, commit, source-anchor closure,
  and per-item summary.
- Not a normal launch target.

`same-session-implement`

- Shared-lifecycle implementation helper.
- Creates one worktree setup/teardown envelope and runs `do-work-item` phases
  one at a time inside it.
- Uses dependency-ordered serial gates and live ready checks.

`fix-convoy`

- Synthesizes a new fix convoy from a failed verdict report.
- Visible internal in v0 because finding-to-task mapping is model judgment.

`publish`

- Handles final push and PR creation when explicitly enabled.
- PR creation implies push.
- Push without PR creation is valid.
- PR title/body are generated from final report and artifact references unless
  caller supplied overrides.

`github-issue-triage`

- Targetless graph.v2 formula.
- Input: `github_issue_url`.
- Output: source snapshot, `triage-report.md`, triage comment body, and
  canonical source/run metadata.
- Behavior: full URL validation, issue snapshot fetch, body-hash idempotency,
  optional disposable triage worktree for reproduction artifacts, report
  validation, and create-or-update triage comment.

`github-pr-review`

- Targetless graph.v2 formula.
- Input: `github_pr_url`, optional `post_mode = "human_gate"|"auto"`.
- Output: PR snapshot, generic review report, rendered comment, and PR comment
  URL/id.
- Behavior: key attempts by PR head SHA, reuse/update the same comment for the
  same head, create a new review attempt for new heads, and never mutate code.

`github-issue-fix`

- Targetless graph.v2 formula.
- Input: `github_issue_url`, `mode = "interactive"|"autonomous"`, and
  `pr_mode = "none"|"draft"|"ready"`.
- Output: GitHub fix run artifact tree, sticky status comment, build final
  report, and optional PR URL.
- Behavior: run idempotent triage first, resume latest active fix run by
  default, generate requirements from triage, run durable planning/build
  phases, edit one issue status comment at major transitions, and never merge.

`drain`

- Visible internal drain pattern, not a supported normal launch target.
- In v0, executable drain behavior is represented by graph.v2 `[steps.drain]`
  control-bead steps. Core owns that primitive; the pack may ship helper docs or
  wrapper formulas around it for composition.
- The v0 pack does not recursively enumerate convoy members before formula
  instantiation. Any older "sling convoy enumeration" language in context docs
  is superseded for this design by the graph.v2 drain step contract.

### Formula Contract Matrix

<!-- REVIEW: added per formula-boundaries -->

| Formula | Launch path | Input contract | Drain permission | Publish permission | Generated-work validation | Legacy fallback |
| --- | --- | --- | --- | --- | --- | --- |
| `implement` | public formula or launch skill | graph.v2 target-required convoy; reserved target injected by core | yes | optional push/PR after implementation success | validates task payload references and verification policy before routing | reject `issue`, `bead_id`, and user `convoy_id` |
| `do-work` | public formula, usually materialized by drain | graph.v2 target-required drain-unit or implementation convoy | no | no | validates context, ownership, `files:`, and verification commands | reject `issue`, `bead_id`, and user `convoy_id` |
| `gap-analysis` | public report formula or launch skill | targetless report contract: context bundle, implementation summary, diff/artifact references | no | no | none; report-only | reject convoy/bead fallback vars |
| `review` | public report formula or launch skill | targetless report contract: diff/branch/commit subject, optional context and summary | no | no | none; report-only | reject convoy/bead fallback vars |
| `build-run` | visible internal formula launched only by `build` | artifact-set contract plus approved initial implementation convoy reference | invokes `implement` | optional after all loops pass | validates fix-convoy payloads before creation or execution | reject direct public launch and stale approvals |
| `same-session-implement` | visible internal helper invoked by `implement` | graph.v2 target-required convoy plus core shared drain manifest | owns shared-lifecycle drain | no | validates selected anchors, `files:`, verification policy, `single_lane = true`, and core shared-drain support | reject normal launch and legacy target vars |
| `fix-convoy` | visible internal helper invoked by `build-run` | failed verdict report plus source convoy/run metadata | no | no | required before bead or convoy creation | reject unknown report schemas and unsafe generated payloads |
| `do-work-item` | reusable graph.v2 item formula inside existing lifecycle | drain-unit item phase; not a normal target | no | no | validates ownership and verification command before execution | reject direct public launch |
| `publish` | visible internal helper invoked by `implement` or `build-run` | final report, branch/ref, remote, and PR options | no | yes | sanitizes generated PR metadata | reject missing preflight or unsafe refs |
| `github-issue-triage` | public GitHub adapter formula or launch skill | targetless full GitHub issue URL | no | GitHub issue comment only | validates report schema, body hash, reproduction artifacts, and comment body | reject shorthand URLs |
| `github-pr-review` | public GitHub adapter formula or launch skill | targetless full GitHub PR URL plus optional post mode | no | GitHub PR comment only | validates PR head SHA, review report, rendered comment, and human gate result | reject code mutation and formal review events |
| `github-issue-fix` | public GitHub adapter formula or launch skill | targetless full GitHub issue URL plus mode and PR mode | invokes `build-run` after generated planning artifacts | optional draft or ready PR only | validates triage handoff, generated requirements, sticky comment, PR ownership, and build result | never merge in v0 |

### GitHub Adapter Extension

The GitHub adapter workflows live in the `gc` pack for v0. They are thin edge
adapters, not copies of bugflow or adopt-pr. GitHub-specific formulas own URL
normalization, source snapshots, GitHub comments, PR publication, and durable
adapter metadata. Generic planning, implementation, gap-analysis, review,
fix-convoy, and publish behavior stays in the existing `gc` formulas.

All GitHub adapter formulas are targetless `graph.v2` formulas. They accept
only full canonical GitHub URLs:

```text
https://github.com/<owner>/<repo>/issues/<number>
https://github.com/<owner>/<repo>/pull/<number>
```

V0 rejects shorthand inputs such as `org/repo#123`, `#123`, bare numbers, and
URLs without the `https://github.com/` scheme. Each formula creates or reuses a
canonical GitHub source bead keyed by the object identity, then creates
workflow-specific run/root state. The shared source bead records current
GitHub snapshot metadata such as repo, number, kind, title, body hash, state,
labels, author, PR head SHA, and PR base branch. Workflow-specific metadata
records the latest triage, review, or fix run.

The v0 source bead convention is explicit and intentionally boring:

- source beads are normal `type=task` beads used only as non-runnable
  index/cache records; they are not routed, assigned, or used as readiness
  gates
- lookup is by `gc.kind=github_source`, `gc.github.kind=issue|pull`,
  `gc.github.repo=owner/repo`, and `gc.github.number=<number>`
- create/update uses `--external-ref <canonical-url>` and flat
  `gc.github.*` metadata, including `gc.github.url`,
  `gc.github.snapshot_path`, `gc.github.body_hash` for issues, and
  `gc.github.head_sha` for pull requests
- changing GitHub title, labels, assignee, state, or author refreshes source
  metadata but does not invalidate workflow reuse unless the workflow-specific
  key changes

#### GitHub API Boundary

GitHub operations go through pack-owned wrapper scripts under
`assets/scripts/`. The default implementation calls `gh api`, but formulas call
only the stable wrapper surface so users can replace the backend later.

Required wrapper capabilities:

- parse and validate full issue and PR URLs
- fetch issue snapshots
- fetch PR snapshots including head SHA, base branch, author, and diff refs
- resolve the authenticated GitHub actor
- create or update issue comments
- create or update PR comments
- push a branch when publish policy allows it
- create or update a draft or ready PR
- search existing PRs by workflow marker and author

The wrappers must return typed JSON and non-zero exit on ambiguity or missing
capabilities. Formula prompts must not call `gh` directly except as an explicit
diagnostic after a wrapper has failed.

#### Script Asset Layout

All pack helper scripts live under `gc/assets/scripts/`. Existing helpers move
from the legacy script directory to `gc/assets/scripts/` with no compatibility
shims. Formula text uses `{{pack_root}}/assets/scripts/...`; skills, README
examples, and human documentation use `<pack-root>/assets/scripts/...`.

Tests must assert there are no remaining legacy script-directory references
after the migration and that executable shell helpers remain executable.

#### Human Gate Pattern

The GitHub adapter workflows use a shared human-gate pattern, but each parent
workflow owns the meaning of iteration. The shared gate only sends mail to
`human`, records the gate summary and attachments, waits for the human reply,
and emits a durable result:

```yaml
schema: gc.human-gate-result.v1
gate_name: <name>
decision: approved|rejected|needs_iteration
attachments:
  - name: <name>
    path: <path>
    description: <description>
human_message_id: <message-id>
```

`needs_iteration` is parent-specific:

- issue triage updates or reruns the triage report/comment for the current
  body hash
- PR review updates or reruns the review/comment for the current head SHA
- issue fix creates or resumes fix work, updates the PR branch/body when
  needed, then loops through review/publish gates

#### Issue Triage

`github-issue-triage` is idempotent by issue body hash only:

```text
triage_body_hash = sha256(issue.body)
```

If a triage report/comment already exists for the same repo, issue number, and
body hash, the formula returns the existing artifact and updates the canonical
source metadata without rerunning triage. Title, label, assignee, and state
changes do not invalidate triage. A body hash change creates a new triage run
and a new body-hash-keyed triage comment. If the comment for the current hash
was deleted, the formula creates a replacement and updates metadata.

The terminal triage report lives at:

```text
<artifact-root>/github/issues/<owner>/<repo>/<number>/triage/<body-hash>/triage-report.md
```

Report front matter:

```yaml
schema: gc.github-issue-triage-report.v1
repo: owner/repo
issue_number: 123
body_hash: sha256:<hash>
verdict: reproduced|not_reproduced|needs_info|not_a_bug|duplicate|security_sensitive
priority: p0|p1|p2|p3
recommended_next_action: fix|test_hardening|close|ask_reporter|defer|security_process
reproduction_artifact_path: ""
reproduction_diff_path: ""
```

The triage formula may create a disposable triage worktree under the artifact
tree to produce reproduction evidence. Allowed outputs are failing test
patches, repro scripts, logs, and environment notes. It must not commit,
publish, or create implementation convoys. Reproduction diffs are evidence for
later work; issue-fix may use or adapt them but does not apply them blindly.

Triage auto-posts ordinary public comments for `reproduced`,
`not_reproduced`, `needs_info`, `not_a_bug`, and `duplicate`. It must human-gate
before posting details for `security_sensitive` or priority `p0`. A
`post_mode` variable may force `human_gate` or `auto`, but security-sensitive
public output remains gated.

#### PR Review

`github-pr-review` keys review attempts by repo, PR number, and PR head SHA. If
the head SHA is unchanged and a report/comment or waiting human gate exists,
the formula resumes or updates that attempt. A new head SHA creates a new
review attempt and comment.

The formula delegates review judgment to the generic targetless `review`
formula and maps the verdict report to a normal PR comment outcome:

| Review report | GitHub comment outcome |
| --- | --- |
| `verdict=pass`, `severity=none` | `approve` |
| `verdict=fail`, max severity `minor` | `comment` |
| `verdict=fail`, max severity `major` | `request_changes` |
| `verdict=fail`, max severity `blocker` | `block` |

V0 posts normal PR comments only. It does not submit GitHub formal review
events, does not approve through the GitHub review API, and does not request
changes through the formal review API. It never checks out worktrees for code
mutation, pushes commits, amends contributor branches, or creates follow-up
PRs.

Default `post_mode` is `human_gate`; `post_mode=auto` posts directly after
report and comment validation. For the same head SHA, one sticky workflow
comment is created or updated. If the sticky comment was deleted, a replacement
is created. New head SHAs get new review comments.

#### Issue Fix

`github-issue-fix` always invokes issue triage first. Because triage is
idempotent, this either returns an existing body-hash-keyed report/comment or
creates a new one. The fix workflow may continue only when triage returns:

- `reproduced` with `recommended_next_action=fix`
- `not_reproduced` with `recommended_next_action=test_hardening`

It stops without build for `needs_info`, `not_a_bug`, `duplicate`,
`security_sensitive`, or unknown verdicts. `needs_info` is terminal for the fix
run; a later body change starts or reuses a new triage run. Security-sensitive
issues stop with `security_process_required` and avoid normal public
implementation and PR flow.

`github-issue-fix` supports:

```toml
[vars.mode]
description = "Human gate policy: interactive or autonomous."
default = "interactive"

[vars.pr_mode]
description = "PR publication mode: none, draft, or ready."
default = "none"
```

`mode=interactive` still auto-generates approved requirements from triage, but
human-gates design, decomposition/start, and public publication checkpoints.
`mode=autonomous` generates design and decomposition non-interactively and
continues through build without those front-half gates. `pr_mode` is
independent of `mode`: autonomous does not imply PR creation.

`pr_mode=none` performs no PR publication. `pr_mode=draft` pushes and opens or
updates a draft PR after implementation, gap-analysis, and review all pass.
`pr_mode=ready` pushes and opens or updates a ready-for-review PR after the
same internal quality gates pass. V0 never merges automatically.

The fix workflow keeps one sticky GitHub issue status comment. It creates the
comment on first status update and stores the comment id/url on the canonical
source or run metadata. Later transitions edit the same comment. If the comment
was deleted, the workflow creates a replacement and updates metadata. The
status comment is updated at major durable transitions only: triage
completed/reused, generated planning artifacts, implementation started, PR
opened/updated, failure/blocked states, and terminal completion.

Rerunning issue-fix for the same issue resumes the latest active nonterminal
run by default. If no active run exists, it creates a new run. If the issue body
hash changed while a run is active, issue-fix runs/reuses triage for the new
hash and asks the human whether to continue the old run with updated context or
start fresh.

Each issue-fix run owns one generated implementation convoy. Fix convoys
created by `build-run` remain iteration-specific. The generated requirements
artifact is mechanically derived from the triage report and issue body and is
marked `status: approved` in both interactive and autonomous modes. For
`not_reproduced` plus `test_hardening`, requirements, PR text, and comments must
say test hardening and must not claim a confirmed bug fix.

Existing PR reuse is author-safe. The workflow may update an existing PR only
when all of the following are true:

- the PR has the workflow marker for the same issue/source bead
- the PR targets the same repo/base
- the PR author is the authenticated GitHub actor resolved by the wrapper
- the PR is nonterminal and compatible with requested `pr_mode`

If a matching marker exists on a PR by another author, the workflow records
`foreign_pr_exists` and asks the human whether to stop, create a separate PR, or
handle it manually. It never updates someone else's PR.

#### GitHub Artifact Layout

GitHub adapter artifacts live under:

```text
<artifact-root>/github/
  issues/<owner>/<repo>/<number>/
    source.json
    triage/
      <body-hash>/
        triage-report.md
        comment.md
        repro.patch
        logs/
    fix/
      <run-id>/
        requirements.md
        implementation-plan.md
        tasks.md
        context.yaml
        status-comment.md
        build/
          final-report.md
  pulls/<owner>/<repo>/<number>/
    source.json
    reviews/
      <head-sha>/
        review.md
        comment.md
```

The `fix/<run-id>/` directory intentionally uses the same build-compatible
layout as the generic `build` flow so `build-run` can consume it without
GitHub-specific special cases.

### Drain Manifest Contract

<!-- REVIEW: added per drain-execution-semantics -->

Core drain control plus core `DrainManifestV1` is the sole authority for drain
item selection, materialization state, replay, and item outcome reconciliation.
Pack artifacts may copy or summarize manifest data, but they are derived views
and are never used as the source of truth.

Core `DrainManifestV1` is stored on the drain control bead as
`gc.drain_manifest.v1` and exposed through the typed core manifest API/SSE
surface. The pack must not assume a separate `gc runtime drain-status` command
unless the runtime capability handshake advertises it. The core manifest
contains the core-owned fields: item index, member id, drain-unit/root keys and
ids, reservation owner, materialization status, outcome bead/kind, and failure
reason. Pack reports may derive richer fields for operator display, including:

- schema version, manifest id, generation, source convoy id, drain policy,
  formula name, artifact root, and creating run id
- selected work anchors with source bead id, key path, immediate convoy id,
  dependency ids, drain-unit convoy id, item workflow id, status, and result
  class
- the selected item order accepted by core, the pack's requested topological
  order hash, and whether the requested order matched core manifest order
- materialization state for each item: `pending`, `materialized`, `claimed`,
  `closed`, `failed`, `skipped`, or `abandoned`
- `gc.closed_seq` at manifest creation, latest observed `gc.closed_seq`, and
  the live-ready reconciliation timestamp
- pinned session id, continuation group, heartbeat timestamp, stale threshold,
  and recovery classification for same-session drains, when advertised by core
  or computed as a derived pack status projection

Drain prepare computes the selected anchor set from non-convoy runnable members
only. Ordinary convoy membership must not block readiness, affect orphan
detection, or make convoy heads runnable. Authored dependencies and generated
convoy dependencies are the only readiness edges. For `context = "separate"`,
the pack can accept core's canonical manifest order. For same-session policy,
the pack asks core for `context = "shared"` and validates that the selected
manifest order is a safe serial order for the dependency graph. If core exposes
only canonical convoy membership order, the pack must either create the shared
drain from a convoy whose membership has already been topologically linearized
or fail closed with `GC_CONTRACT_DRAIN_ORDER_UNSUPPORTED`. V0 does not silently
run same-session work in a non-topological order.

Separate-session drain is a graph.v2 `[steps.drain] context = "separate"` step
that asks core to materialize one `do-work` workflow per selected anchor. The
pack does not run recursive pre-instantiation member enumeration itself. Any
core-internal materializer must remain behind the same prepare and manifest
contract.

Same-session is a pack-facing `drain_policy`, not a core drain context. The
emitted graph.v2 drain step uses core `[steps.drain] context = "shared"` and an
item formula reference:

```toml
drain_policy = "same-session"

[steps.drain]
context = "shared"
formula = "do-work-item"
on_item_failure = "skip_remaining"

[steps.drain.item]
single_lane = true
```

`do-work-item` is a graph.v2 item formula, not a public launch target. It takes
the drain-unit convoy supplied by core, reads `gc.drain_member_id` and
`gc.drain_item_index`, validates the source work anchor and `files:` ownership,
runs the implementation phase inside the caller's already-created shared
worktree lifecycle, writes an item summary, and closes only the owned source
anchor on success. The static verifier rejects any item formula with more than
one executable lane, any nested public launch target, and any attempt to create
or tear down a second worktree lifecycle.

Same-session v0 adopts core `on_item_failure = "skip_remaining"` to protect the
shared worktree after a failed item. Summaries must say every later unstarted
manifest item is skipped by manifest order, not only dependency successors. A
future dependency-selective policy would require `continue` plus a separate
pack-owned reconciler and is out of v0.

`gc hook` for a pinned continuation session returns exactly one structured
status:

| Status | Predicate |
| --- | --- |
| `work` | one manifest item assigned to this session is ready, unclaimed by another session, and all predecessor anchors are terminal-success or already closed |
| `wait` | no item is currently claimable, but at least one selected anchor is open, awaiting materialization, blocked by a nonterminal predecessor, or pending live-ready reconciliation |
| `empty` | every selected anchor is terminal and manifest generation, live-ready reconciliation, and the latest `gc.closed_seq` watermark agree that no runnable or awaiting-materialization item remains |

The pinned session calls:

```bash
gc runtime drain-continue <drain_control_id> \
  --item-index <n> \
  --last-work <source_anchor_or_item_root_bead_id>
```

after the current item phase has written its summary and the source anchor is
closed or already terminal. `drain-continue` is a forward notification, not
proof of drain success. It may advance assignment only for the recorded drain
control, item index, last-work bead, manifest generation, and pinned session
identity. Mismatch fails with a typed non-mutating error; success is proven only
by the manifest reaching a terminal summary with every selected anchor
classified.

Heartbeat recovery is fail-closed. A session stale beyond the manifest
threshold is classified as `session_stale`, `session_lost`, or
`session_unknown`. V0 does not steal same-session work into a different
session; it writes an abnormal drain summary and cleanup instructions instead.

### Public Vocabulary And Error Ownership

<!-- REVIEW: added per terminology-error-ownership -->

Public tokens use snake_case. Hyphenated forms are accepted only as deprecated
aliases in human-facing diagnostics during the migration window; structured
metadata, reports, tests, and formula decisions use the canonical token.

| Concept | Canonical token | Notes |
| --- | --- | --- |
| continuation affinity unavailable | `affinity_unavailable` | result class for same-session drain failure |
| stale pinned session | `session_stale` | heartbeat expired but session identity is known |
| lost pinned session | `session_lost` | runtime reports the session cannot resume |
| no claimable work yet | `wait` | `gc hook` status, not a terminal result |
| terminal drain idle | `empty` | valid only after manifest and `gc.closed_seq` reconciliation |
| drain continuation command | `drain-continue` | command name only; not success proof |
| legacy epic target | `GC_CONTRACT_LEGACY_EPIC_INPUT` | pre-normalization target rejection |

Core owns errors for runtime contract discovery, graph.v2 target normalization,
reserved graph variables, hook status shape, drain manifest authority,
continuation affinity, and store CAS. The pack owns errors for task payload
schema, metadata inheritance, context bundles, generated-work validation,
approval records, build-run state, and publish policy. When both layers can
detect a problem, the earlier no-side-effect layer owns the public error code.

## Artifact Model

Artifacts live under an artifact root, defaulting to:

```text
<rig-root>/plans/<plan-slug>/
```

Build uses a deterministic plan slug. If build creates a branch, the default
target branch is deterministic from the plan slug with a collision suffix when
needed.

Required artifact paths:

```text
requirements.md
implementation-plan.md
tasks.md
context/implementation-context.yaml
implementation/summary.md
gap-analysis/attempt-<n>.md
gap-analysis/latest.md
review/attempt-<n>.md
review/latest.md
fixes/<source>-attempt-<n>-tasks.md
final-report.md
```

`final-report.md` is written for success and failure. It summarizes artifacts,
implementation summaries, gap-analysis iterations, review iterations,
branch/PR information, and final status.

### Metadata, Branch, And Artifact Rules

<!-- REVIEW: added per typed-metadata-inheritance -->

Planning payloads may set only typed planning fields. They may not set runtime
metadata namespaces such as `gc.*`, `workflow_*`, `design_review.*`, routing
state, assignment state, drain state, approval state, or publish result fields.
Unknown metadata keys fail validation unless the payload schema version
explicitly allows them.

The canonical stored integration branch key is `target`, matching
`gc convoy target`. Formula callers may pass a `target_branch` variable as an
override, but payloads and persisted metadata normalize to `target`; the alias
is never stored. Branch precedence is:

1. explicit formula `target_branch`
2. runnable bead `target`
3. nearest parent convoy `target`, walking outward
4. repository default branch

Branches must be repository-relative names, not full refs. They must pass git
ref validation, reject control characters, spaces, `..`, leading slash, trailing
slash, protected/default branch names for publish, and names outside the
configured workflow prefix when a prefix is configured.

Inherited planning fields in v0 are `target`, `labels`, `plan_slug`,
`artifact_root`, and `files`. Child values override parent values. List fields
merge by stable de-duplicated order unless the child sets an explicit empty
list. Scalar fields override. Artifact paths are relative to the artifact root,
must use safe slugs matching `[a-z0-9][a-z0-9._-]{0,80}`, and must reject
absolute paths, traversal, symlink escapes, and paths outside the artifact root.

`files:` is an enforced edit boundary for unattended generated work and
same-session item phases. A worker that needs to edit outside the declared
scope must stop with an ownership-scope failure or obtain an explicit human
approval recorded in the work summary.

## Context Bundle Contract

Formulas accept context through a single `context_path` variable. The file is
YAML or JSON:

```yaml
items:
  - name: Requirements
    path: ../requirements.md
    description: Product requirements and acceptance criteria.
  - name: Design
    path: ../implementation-plan.md
    description: Engineering design and constraints.
```

Rules:

- Each item has only `name`, `path`, and `description`.
- Paths are relative to the context bundle file by default.
- Absolute paths are accepted only when their canonical path is under a
  configured allowed root for the current rig.
- If `context_path` is provided, missing referenced files fail fast.
- Missing optional `context_path` means an empty bundle.
- Formula prompts include named file references and descriptions, not inlined
  file contents.
- Validators canonicalize every item path before use and reject traversal,
  symlink escapes, unsafe binary files, oversized files, device files, sockets,
  known secret locations, and files matching configured secret globs.
- Diagnostics include bundle path, item name, original path, resolved path,
  failure class, and corrective action.
- Context files, diffs, verdict reports, summaries, and item descriptions are
  untrusted prompt data. Prompts must fence or otherwise label them as data
  subordinate to the workflow instructions, never as instructions to the agent.

Build generates the implementation context bundle after decomposition approval
from requirements, design, and tasks. Standalone decompose does not need to
generate it in v0.

## Default-Deny Security Policy

<!-- REVIEW: added per security-default-deny -->

Unattended generated work is denied unless the repository or workflow artifact
explicitly grants the required capability. The default repository policy is:

- context access is limited to the validated context bundle entries and formula
  artifacts needed for the current phase
- generated implementation and fix work must declare `files:`; missing
  `files:` fails with `GC_SECURITY_FILES_SCOPE_REQUIRED`
- verification commands are denied unless they match the repository allowlist
  or a command-specific human approval record authorizes the sandboxed
  execution request
- network access is disabled for verification and generated scripts unless the
  allowlist grants it for that command
- environment variables are cleared except for an explicit allowlist; known
  token, key, cookie, and credential names are always redacted from prompts and
  command environments
- writes are limited to the worktree paths covered by `files:` plus the current
  artifact directory; symlink escapes, absolute paths, traversal, and device
  files are rejected
- process execution has configured timeouts, process-tree cleanup, output size
  limits, and no background process survival after the phase ends

Verification command allowlists use absolute resolved command paths or stable
tool identifiers mapped by the repository policy. Wrapper commands are checked
after resolution; `sh`, `bash`, `env`, package managers, network clients, and
download/install commands are denied by default for unattended work.

The verification sandbox is mandatory for every generated or task-authored
verification command. It is a runtime-enforced boundary, not a prompt
instruction. It provides a scratch filesystem rooted under the worktree and
current artifact directory, no network unless explicitly allowed, a cleared
environment plus allowlist, process-tree cleanup, timeout and output caps, and
write access only to declared `files:` plus artifact destinations. Repository
allowlists and human approvals authorize normalized argv, cwd, environment,
network, write scope, and sandbox profile; they do not bypass sandbox
execution. If the sandbox capability is unavailable, the formula fails closed
with `GC_CONTRACT_SANDBOX_UNAVAILABLE`; it does not run the command
unsandboxed.

Human approval for non-allowlisted verification is bound to the exact normalized
execution request: argv, resolved cwd, environment allowlist, network policy,
write prefixes, sandbox profile, source artifact/report hash, run id, actor,
expiry, and one-time or explicit-reuse semantics. A stale, broad, or
hash-mismatched approval is invalid.

Verification `cwd` must resolve under the worktree or a declared artifact
destination; absolute paths, traversal, symlink escapes, and cwd outside the
declared ownership boundary fail validation.

Before commit, the worker runs a mechanical edit-boundary check over
`git diff --name-only`, staged paths, generated artifacts, symlink targets, and
deleted files. Any path outside `files:` or the current artifact directory fails
with `GC_SECURITY_EDIT_SCOPE`. Content-level secret scanning runs on diff hunks,
new files, generated PR metadata, summaries, and final reports before commit or
publish. Secret-scan failure writes a redacted report and blocks both commit and
publish.

Publish authorization is a separate audited record. It stores actor, timestamp,
remote, base branch, head branch, expected commit, token-scope check, branch
collision policy, approval hash, and dry-run result. PR bases must be repository
local, must equal the repo default branch or a configured allowed base, must not
equal the head branch, and must not be protected by a policy that forbids
workflow-created PRs. If no allowed base is configured, v0 defaults to the repo
default branch only. Protected/default-branch and token-scope checks use the
configured host API when available; unreachable or inconclusive detection fails
closed. Branch collision checks query local and remote refs; collisions fail
unless an explicit collision policy names the existing ref, expected commit,
and allowed action.

The zero-config secret denylist includes at minimum `.env`, `.env.*`, `*.pem`,
`*.key`, `*.p12`, `id_*`, `.ssh/**`, `.aws/credentials`, `.netrc`,
`.git/config`, and files matching common token/key/cookie names. The same
baseline applies to context-bundle rejection, prompt redaction, diff scanning,
and pre-publish secret scanning.

## Task Payload Contract

`tasks.md` replaces `epics[]` with nested `convoys[]`.

Example:

```yaml
target_rig: backend
labels:
  - plan:example
convoys:
  - key: implementation
    title: Implement example feature
    metadata:
      target: example/feature
    members:
      - task-b
    convoys:
      - key: api
        title: API slice
        metadata:
          target: example/api
        members:
          - task-a
beads:
  - key: task-a
    title: Add API contract
    type: task
    priority: 2
    description: |
      Implement the API contract.
    acceptance_criteria:
      - API behavior is covered by tests.
    dependencies: []
    files:
      - internal/api/...
    verification:
      - argv: ["make", "test"]
  - key: task-b
    title: Wire caller
    type: task
    priority: 2
    description: |
      Wire the caller to the API.
    acceptance_criteria:
      - Caller uses the new API.
    dependencies:
      - task-a
```

Rules:

- The schema is versioned as `gc.task-payload.v1`. Missing schema is allowed
  only during the migration window when the file has no `epics[]`; unknown
  top-level, convoy, bead, metadata, or verification fields are rejected.
- Keys use `[a-z0-9][a-z0-9._-]{0,80}` and are unique across the payload in v0.
- The output is a convoy tree. A runnable bead belongs to exactly one immediate
  convoy.
- A convoy must contain at least one runnable member directly or through nested
  convoys after expansion.
- Nested convoys carry group metadata and membership, not blocking semantics.
- `beads[].dependencies` reference runnable bead keys only.
- `convoys[].dependencies` is the only convoy-to-convoy shorthand. A downstream
  convoy dependency on an upstream convoy expands from every terminal runnable
  member of the upstream convoy to every root runnable member of the downstream
  convoy.
- Expansion sorts convoy and bead keys lexicographically by key path,
  de-duplicates generated edges, rejects missing references, rejects ambiguous
  references, rejects fanout above the configured limit, and runs cycle checks
  after expansion.
- Planning metadata inherits parent convoy to nested convoy to runnable bead.
  Child values override parent values.
- Decomposition does not author drain policy.
- Convoy heads and nested convoy heads are skipped by implementation routing.

The bead creation script creates runnable beads first, creates convoy heads,
links members with `gc convoy add`, applies inherited planning metadata, and
wires dependencies with `gc bd dep add`.

Created mappings in `tasks.md` record both convoys and runnable beads.

Before creation, validation proves the single-immediate-convoy invariant, root
and terminal runnable member sets, dependency direction, bounded fanout, stable
ordering, and absence of cycles. After creation, validation reloads the city and
checks that each runnable bead belongs to exactly one immediate convoy, each
nested convoy belongs to exactly one parent convoy, no convoy head is routed as
runnable work, and generated dependencies match the dry-run plan.

### Dependency Expansion Algorithm

<!-- REVIEW: added per convoy-dependency-expansion-contract -->

V0 task payloads contain exactly one top-level convoy. Multiple independent
member graphs are represented as multiple root runnable members or nested
convoys under that single top-level convoy. A payload with zero or more than one
top-level convoy fails with `GC_TASK_TOPOLOGY_INVALID`; a future version may add
multi-top-level payloads explicitly.

Expansion input is the parsed `gc.task-payload.v1` document: runnable bead
definitions, convoy definitions, containment edges, authored
`beads[].dependencies`, and authored `convoys[].dependencies`. Expansion is a
pure dry-run algorithm; it emits a creation plan or typed failures before any
bead or convoy exists.

Algorithm:

1. Validate unique keys, allowed fields, top-level convoy cardinality, and the
   single-immediate-convoy containment invariant.
2. Build the containment tree and calculate each convoy's descendant runnable
   set. Descendant traversal never leaves the top-level convoy and never follows
   existing city `tracks` edges.
3. Validate authored bead dependencies. Dependencies may cross nested convoy
   boundaries inside the same top-level convoy, but both endpoints must be
   runnable beads in the payload. Missing, ambiguous, self, external, or convoy
   head endpoints fail with typed errors.
4. For each convoy, compute `root_runnables`: descendant runnable members with
   no incoming authored dependency from another descendant runnable member.
5. For each convoy, compute `terminal_runnables`: descendant runnable members
   with no outgoing authored dependency to another descendant runnable member.
6. For each `convoys[].dependencies` edge from upstream convoy to downstream
   convoy, generate blocker edges from every terminal runnable in the upstream
   convoy to every root runnable in the downstream convoy.
7. Sort generated edges by upstream key path, downstream key path, then authored
   declaration order. De-duplicate generated edges and authored/generated
   duplicates before emitting the creation plan.
8. Count fanout before and after de-duplication. If either count exceeds the
   configured limit, fail with `GC_TASK_FANOUT_LIMIT`.
9. Run cycle detection after generated edges are added. Cycles fail before bead
   creation with the minimal cycle path in diagnostics.
10. Emit deterministic `bd create`, `gc convoy create`, `gc convoy add`, and
    `bd dep add` operations, then reload the city after creation and compare
    actual containment and blocker edges to the dry-run plan.

Failure codes are owned by the pack task validator:

| Code | Meaning |
| --- | --- |
| `GC_TASK_SCHEMA_INVALID` | unknown field, malformed type, missing required key, or invalid schema version |
| `GC_TASK_TOPOLOGY_INVALID` | invalid top-level cardinality, empty convoy, overlapping membership, or containment cycle |
| `GC_TASK_DEPENDENCY_INVALID` | missing, ambiguous, external, self, convoy-head, or wrong-direction dependency |
| `GC_TASK_FANOUT_LIMIT` | generated convoy dependency fanout exceeds the configured limit |
| `GC_TASK_CYCLE` | authored plus generated runnable dependency graph contains a cycle |

Worked example: if convoy `api` contains terminal runnables `api-test` and
`api-docs`, and convoy `ui` contains root runnables `ui-form` and `ui-route`,
then `ui.dependencies: [api]` generates four candidate blocker edges. If
`ui-form` already depends on `api-test`, that duplicate is removed, leaving
three generated edges plus the authored edge in deterministic order.

### Legacy Epic Boundary

<!-- REVIEW: added per legacy-epic-migration-boundary -->

New v0 payloads must not contain `epics[]`. Existing old-layout artifacts,
created mappings that reference epics, and `type=epic` beads are not normalized
into graph.v2 flows. Affected formulas fail closed with
`GC_CONTRACT_LEGACY_EPIC_INPUT` and include the offending artifact or bead id.

Legacy rejection happens in the runtime prepare call before graph.v2 singleton
normalization. The pack passes `--reject-type epic` and requires core to inspect
the raw target id before creating or reusing a singleton convoy. If core cannot
perform this pre-normalization check, prepare fails with
`GC_CONTRACT_PRE_NORMALIZE_TARGET_UNAVAILABLE` and no formula side effects
occur beyond the formula run bead.

Migration from old `epics[]` payloads is out of scope for automatic formula
execution in v0. A future explicit migration tool may convert old artifacts to
`convoys[]`, but until then old epic beads may be used only as read-only
context references, not runnable anchors, convoy heads, singleton targets, or
drain members.

Existing singleton convoys whose only member is a `type=epic` bead are treated
as legacy-contaminated and rejected with `GC_CONTRACT_LEGACY_EPIC_INPUT`.
Old-layout `type=task` epic children are not traversed through their legacy
parent or old `tracks` edges. Directly targeting such a task as a bare bead
fails with `GC_CONTRACT_LEGACY_EPIC_CHILD` unless an explicit v0 payload first
places it in a new convoy. If a city contains both legacy epic-child `tracks`
relations and v0 convoy membership for the same bead, v0 formulas use only the
new convoy membership after the validator confirms there is exactly one
immediate v0 convoy and no legacy parent is part of the target traversal.

Error-code ownership is split: core owns pre-normalization target-type failures
and reserved graph input failures; the pack owns task-payload `epics[]`,
created-mapping, legacy-child, and collision diagnostics.

## Verdict Report Contract

Gap-analysis and review reports are verdict reports: markdown with a small
structured header followed by freeform analysis.

```yaml
---
schema: gc.verdict-report.v1
kind: gap-analysis
verdict: fail
severity: major
findings:
  - id: gap-001
    severity: major
    title: Missing persistence test
    evidence: tests do not exercise restart behavior
    required_fix: add restart coverage
---
```

Rules:

- `verdict` is `pass` or `fail` in v0.
- Blocked, unavailable, or inconclusive states are `fail` with explanation in
  markdown.
- `severity` is the maximum finding severity, or `none` on pass.
- Findings are structured enough for fix-convoy synthesis.
- The markdown body carries nuance and evidence.

## Build Workflow

Build is hybrid:

1. Interactive `build` skill creates requirements.
2. Human approves requirements.
3. Interactive design phase creates engineering design.
4. Human approves design.
5. Interactive decompose phase creates `tasks.md` and the initial convoy.
6. Human approves implementation start.
7. Durable `build-run` executes without more human approval by default.

Approval gates are persisted, not inferred from prose. Each approval record
stores artifact kind, artifact path, canonical content hash, actor, timestamp,
status, and the workflow phase it unblocks. Editing an approved artifact changes
the hash and makes the approval stale. `build-run` validates requirements,
design, decomposition, and implementation-start approvals at entry and fails
closed with `GC_APPROVAL_MISSING` or `GC_APPROVAL_STALE` before invoking
implementation when any approval is missing or stale.

`build-run` receives:

- artifact set path
- context bundle path
- initial implementation convoy id
- drain policy
- gap/review loop limits
- optional push/PR settings

Durable flow:

1. Run `implement`.
2. If implementation fails, stop and write `final-report.md`.
3. Run gap-analysis.
4. If gap-analysis fails, synthesize a fix convoy and run `implement` on it.
5. Repeat gap-analysis loop up to the configured limit.
6. Run review.
7. If review fails, synthesize a fix convoy and run `implement` on it.
8. Repeat review loop up to the configured limit.
9. Finalize report.
10. Optionally push and optionally open PR.

Gap-analysis and review loop limits default to 10. Reaching a loop limit is a
hard failure with a final report.

### Build-Run State Machine

<!-- REVIEW: added per durable-build-run-protocol -->

`build-run` is a durable state machine. It writes an atomic checkpoint under the
artifact set before and after every side effect. The checkpoint includes:

- schema version, run id, active lock id, owner session, and created timestamp
- terminal status: `running`, `succeeded`, `failed`, `recovery_failed`, or
  `publish_partial`
- current phase and subphase
- gap and review loop counters
- artifact root, context bundle path, initial convoy id, current convoy id, and
  drain policy
- immutable report paths, latest report pointers, report hashes, and finding
  fingerprints
- fix plan paths, fix plan hashes, deterministic fix keys, fix convoy ids, and
  implementation workflow ids
- publish preflight result, pushed ref, PR URL, partial-publish marker, and
  recovery status

Checkpoint, report, latest-pointer, fix-plan, and final-report writes use
write-temp, fsync where available, and atomic rename. An active-run lock is
created with a conditional store primitive keyed by artifact root and initial
convoy id. A second `build-run` for the same artifact set must resume the active
run or fail; it must not start a duplicate run.

Resume behavior is phase-specific:

| Last durable phase | Resume behavior |
| --- | --- |
| before implementation launch | revalidate approvals and launch once |
| after implementation workflow id recorded | inspect that workflow and continue from its terminal summary |
| after report path written | verify report hash and update latest pointer if needed |
| after failed report detected | reuse the recorded finding fingerprint and fix key |
| after fix plan written | validate the plan hash before creating or reusing fix convoy |
| after fix convoy metadata recorded | find or complete the convoy by deterministic fix key |
| after fix implementation launch | inspect that workflow and continue from its terminal summary |
| after final report write | treat final report as authoritative unless publish remains pending |
| after push before PR | record partial publish and resume at PR creation or final repair |

Every terminal outcome writes `final-report.md`: success, implementation
failure, loop exhaustion, repeated findings, no-op fix plan, cannot-fix
findings, recovery failure, and partial publish.

Loop convergence uses normalized finding fingerprints across attempts. If the
same blocking or major finding set repeats after a fix attempt, or if a fix plan
maps no findings to executable tasks or explicit cannot-fix records, the loop
fails early with a final report instead of burning the iteration cap. Each
failed finding must map to one fix task or a cannot-fix result with a reason.
Fix convoys carry `gc.fix_consumed_by_run`, source report hash, finding-set
hash, and closure status; `build-run` treats a fix convoy as complete only after
its `implement` summary reaches a terminal result.

#### Lease, Fencing, And Recovery Details

<!-- REVIEW: added per build-run-recovery-idempotency -->

The active-run lock is a fenced lease, not a boolean. The lock record contains
`artifact_root`, `initial_convoy_id`, `run_id`, `lock_id`, `epoch`,
`owner_session`, `heartbeat_at`, `expires_at`, `terminal`, and `last_checkpoint`
path. Acquire, renew, takeover, and release all use conditional store
operations. Every side-effecting write includes the current `lock_id` and
`epoch`; stale owners cannot update checkpoints, latest pointers, fix-convoy
records, publish records, or final reports.

Lease takeover is allowed only when `expires_at` is older than the configured
stale threshold and the old owner cannot be found through runtime status.
Takeover writes a recovery checkpoint before any other side effect. Terminal
locks are immutable except for attaching late diagnostic artifacts; a second
run that finds a terminal lock reads `final-report.md` and exits with the same
terminal result.

Fix-convoy creation is crash-safe through a pending-create record keyed by the
deterministic fix key. The pending record is written before any bead or convoy
creation and contains the source report hash, finding-set hash, fix-plan hash,
expected operation list hash, and lock fence. If core supports atomic convoy
create, the pending record and created convoy id are committed together. If not,
resume reconciles by deterministic key: no beads means retry creation, a
partial convoy with matching hashes is repaired, and any hash mismatch fails
closed with a recovery final report.

State transitions are explicit:

| Phase | Allowed next phases |
| --- | --- |
| `created` | `implementing`, `failed` |
| `implementing` | `gap_analysis`, `failed`, `recovery_failed` |
| `gap_analysis` | `gap_fix_planning`, `review`, `failed` |
| `gap_fix_planning` | `gap_fixing`, `failed` |
| `gap_fixing` | `gap_analysis`, `failed`, `recovery_failed` |
| `review` | `review_fix_planning`, `finalizing`, `failed` |
| `review_fix_planning` | `review_fixing`, `failed` |
| `review_fixing` | `review`, `failed`, `recovery_failed` |
| `finalizing` | `publishing`, `succeeded`, `failed` |
| `publishing` | `succeeded`, `publish_partial`, `failed`, `recovery_failed` |

Machine-readable result classes are `success`, `substantive_failure`,
`retryable_failure`, `timeout`, `unavailable`, `blocked`, `context_invalid`,
`approval_invalid`, `security_rejected`, `recovery_failed`, and
`inconclusive`. Reports may contain prose, but state-machine decisions use only
these result classes plus structured finding fingerprints.

Publish resume is idempotent. After a pushed ref is recorded, resume first
checks the remote ref and commit, then searches existing PRs by head branch,
base branch, head commit, and recorded run id marker before creating a PR. It
must not push a second branch or open a duplicate PR for the same publish
record.

## Implementation Formula

`implement` variables:

```toml
[vars.context_path]
default = ""

[vars.drain_policy]
default = "separate"

[vars.summary_path]
default = ""

[vars.target_branch]
default = ""

[vars.push]
default = "false"

[vars.open_pr]
default = "false"
```

The target convoy is the reserved graph.v2 target input injected by core. It is
not declared as a formula variable.

Validation:

- The reserved target convoy must name a convoy.
- `context_path`, when present, must validate.
- `drain_policy` is `separate` or `same-session`.
- `open_pr=true` implies push.
- If no target branch is set on the convoy or via var, formulas use the repo
  default branch.

Completion:

- Implement succeeds when all selected non-convoy work anchors are closed.
- Work anchors closed before start count as already satisfied.
- Failed or open anchors make implement fail.
- Implement does not close failed anchors.
- Implement does not close the convoy head.
- Direct runs without `summary_path` record summary on the implement workflow
  bead.

Separate policy:

- Use a graph.v2 `[steps.drain] context = "separate"` step to materialize one
  full `do-work` lifecycle per selected runnable anchor through the core drain
  manifest.
- Each item targets the convoy branch.
- Merge conflicts are handled by the item session.

Same-session policy:

- Use `same-session-implement`.
- Create one shared worktree setup/teardown envelope around a core shared drain
  step. Core owns the durable drain control and manifest; the pack records only
  derived run-status views.
- Ask core shared drain to materialize `do-work-item` graph.v2 item phases for
  all selected open non-convoy members. Before launch, the pack validates that
  the accepted core manifest order is dependency-safe; otherwise it fails
  closed.
- Use core shared-drain item serial gates so only one item phase can become
  ready at a time. Same-session v0 uses `on_item_failure = "skip_remaining"`,
  so failed items skip all later unstarted manifest items by order.
- A pinned continuation session discovers same-session work only through
  `gc hook`; it must not run broad ready queries or fall through to unrelated
  routed work while pinned.
- `gc hook` returns exactly one of `work`, `wait`, or `empty`. `wait` means
  dependents may still become ready or materialization is still pending.
  Terminal `empty` is valid only after the drain manifest, live-ready
  reconciliation, and `gc.closed_seq` watermark agree that no runnable or
  awaiting-materialization anchors remain.
- `gc runtime drain-continue` resumes only the recorded drain manifest for the
  pinned session and must fail if the session id, continuation group, convoy id,
  or manifest generation does not match.
- If the pinned session is lost or stale beyond the configured heartbeat, the
  drain fails with `affinity_unavailable`; remaining anchors are reported as
  skipped or not-run and are not silently moved to another session.
- Commit separately per item.
- If the session cannot be resumed, fail the drain rather than moving work to a
  different session.

The drain summary classifies every selected anchor as `succeeded`,
`already_closed`, `failed`, `skipped`, `not_run`, `awaiting_materialization`, or
`affinity_unavailable`. Abnormal completion writes the same aggregate summary
shape as success and leaves dirty worktrees or reservations assigned to the
drain owner for cleanup instructions in the final report.

Operator status for `implement`, same-session drain, and `build-run` exposes
run id, phase, current convoy, selected anchors by summary classification,
active session id, heartbeat age, last checkpoint path, latest report paths,
publish state, and allowed actions. `resume` may continue only from a matching
checkpoint and manifest; `abort` writes an abnormal final report and releases
only reservations owned by the run; `retry` starts from the last failed phase
only when the checkpoint declares the phase retryable.

## Do-Work Formula

`do-work` is the public full-lifecycle work formula. It receives the reserved
graph.v2 target convoy injected by core.

Lifecycle:

1. Resolve the implementation target:
   - if input is a drain-unit convoy, read `gc.drain_member_id`
   - otherwise inspect the convoy members and treat the input convoy as the
     ownership boundary
2. Set up or reuse an isolated worktree on the target branch.
3. Read context bundle references.
4. Implement the assigned ownership boundary only.
5. Run verification named by the task/context where available.
6. Commit a focused change.
7. Write per-item summary.
8. Close the owned source work anchor on success.
9. Tear down or hand off workspace according to caller lifecycle.

`do-work-item` contains steps 4 through 8 for reuse by same-session shared
lifecycle.

Generated and task-authored verification is data, not shell script. Verification
entries use constrained `argv` arrays plus optional `cwd`, timeout, and
environment allowlist. The validator rejects shell strings, redirection,
command substitution, globbing outside declared `files:`, absolute command
paths outside the allowlist, network commands unless explicitly allowed by the
repo, `cwd` outside the validated worktree/artifact scope, and unknown fields.
Repositories may declare allowed verification commands, but allowed commands
still execute inside the sandbox. Otherwise unattended model-generated commands
require an exact human approval record plus sandbox capability. Without
allowlist or matching approval, and without sandbox support, execution fails
closed. Adversarial tests cover unsafe paths, unsafe cwd, unsafe globs, shell
metacharacters, dependency downloads, and attempts to write outside artifact
destinations.

## Gap Analysis And Review

`gap-analysis` and `review` are report-only public formulas.

They do not:

- mutate source beads
- reopen anchors
- synthesize fix work directly
- push branches
- create PRs

They do:

- validate context bundle if provided
- inspect implementation summary and diff/artifacts when available
- write immutable per-attempt reports
- write/update a latest report pointer or copy
- return a verdict report

Build consumes failed reports through `fix-convoy`.

## Fix Convoys

Each failed gap-analysis or review iteration creates a new fix convoy.

Rules:

- The source verdict report is the input.
- A model step maps findings to fix tasks or explicit cannot-fix records.
- Fix task plans use the same `convoys[]` and `beads[]` payload schema as
  decomposition output.
- Fix convoys inherit the original implementation drain policy.
- Fix work uses the same per-item commit and summary behavior as initial
  implementation.
- The fix task plan links to the failed report and iteration.
- Fix-convoy creation is idempotent. The deterministic key is derived from build
  run id, loop kind, iteration, source report hash, normalized finding-set hash,
  and original implementation convoy id.
- Before implementation launch, `fix-convoy` records the deterministic key,
  source report hash, finding-set hash, fix plan hash, generated payload schema
  version, and validation status on the fix convoy or pending creation record.
- Resume finds an existing complete or partial fix convoy by deterministic key,
  repairs missing metadata when hashes match, or fails closed on hash mismatch.
- Generated fix payloads pass the task payload validator, metadata allowlist,
  context bundle policy, `files:` ownership policy, verification command policy,
  artifact destination checks, dependency validation, and unknown-field
  rejection before any bead or convoy is created.

## Publish

Push and PR creation are explicit opt-ins on both direct `implement` and
`build`.

Direct `implement` publish timing:

- after implementation succeeds
- before any gap-analysis or review, because direct implement does not own those
  loops

Build publish timing:

- only after implementation, gap-analysis loop, and review loop all pass

Rules:

- Push without PR is valid.
- PR creation implies push.
- PR title/body default from `final-report.md` and artifact references.
- Publish does not merge, approve, label, or otherwise alter repository review
  policy.
- Publish preflight records authenticated actor, remote URL, remote host,
  required token scopes, current commit, requested branch, PR base, dry-run
  result, and whether a ref already exists.
- Publish rejects protected/default branch targets, unsafe branch names,
  unconfigured remotes, missing auth, insufficient token scope, branch
  collisions without an explicit collision policy, and force pushes in v0.
- Push is performed only as a create-if-absent ref update or an update
  conditioned on the recorded expected remote object id. If the remote cannot
  enforce atomic or lease-checked semantics, publish fails closed; v0 never
  falls back to a plain push. If push succeeds but PR creation fails, the
  checkpoint records `publish_partial` with pushed ref and commit so resume
  opens the PR or repairs `final-report.md` without pushing a second branch.
- PR title and body are sanitized from untrusted final-report and context
  content: size limits, markdown escaping where needed, secret scanning, safe
  artifact references, no raw absolute local paths, no raw HTML, and neutralized
  platform side effects such as issue-closing keywords, user/team mentions, and
  arbitrary external links unless explicitly allowlisted.

## Operability, Approval, And Handoff

<!-- REVIEW: added per operability-approval-handoff-contract -->

Each durable run writes a public status projection at
`<artifact-root>/run-status.json` and mirrors the current status on the run bead
metadata under `gc.workflow.*`. Operators inspect runs through:

```bash
gc workflow runs --artifact-root <path> --status active|stale|terminal --json
gc workflow status --run-id <run-id> --json
gc workflow resume --run-id <run-id> --reason <text>
gc workflow abort --run-id <run-id> --reason <text>
gc workflow retry --run-id <run-id> --phase <phase> --reason <text>
```

Status includes run id, formula, artifact root, current phase/subphase, result
class, owner session, lock id, heartbeat age, stale threshold, selected convoy,
current convoy, drain manifest id, selected anchors by result class, latest
report paths and hashes, pending approval ids, publish state, last checkpoint,
and allowed operator actions.

Heartbeat records are written by the active formula process and pinned
continuation sessions. A heartbeat has `run_id`, `session_id`, `phase`,
`manifest_id`, `lock_id`, `epoch`, `written_at`, `expires_at`, and
`last_observed_closed_seq`. Stale classifications are `session_stale`,
`session_lost`, `lock_stale`, `manifest_stale`, and `publish_partial`. Each
classification maps to allowed actions; same-session work never auto-migrates
to another session in v0.

Operator intervention requires an authorization record containing actor, action,
reason, timestamp, run id, current checkpoint hash, and optional target phase.
`resume` and `retry` must validate the checkpoint hash and lock fence before
continuing. `abort` writes an abnormal `final-report.md`, releases only
reservations owned by the run lock, and leaves dirty worktrees, pushed refs, or
partial PR state documented for manual cleanup.

Approval records live under `<artifact-root>/approvals/`:

```json
{
  "schema": "gc.approval.v1",
  "artifact_kind": "design",
  "artifact_path": "implementation-plan.md",
  "content_hash": "sha256:<canonical-content>",
  "phase_unblocked": "decompose",
  "actor": "user@example.com",
  "status": "approved",
  "recorded_at": "2026-05-25T00:00:00Z"
}
```

`gc workflow approval validate --artifact-root <path> --phase <phase> --json`
is the shared validator for launch skills and formulas. Any edit that changes
the canonical content hash makes the approval stale. Interactive front-half
skills are responsible only for producing artifacts and approval records, then
calling the durable formula. They must not duplicate formula internals,
construct drain manifests, synthesize fix convoys, publish branches, or infer
approval from prose.

## File Changes

Expected pack changes:

- Rewrite [gc/README.md](./README.md) around the new public surface.
- Update [gc/skills/gather-requirements/SKILL.md](./skills/gather-requirements/SKILL.md) for build-compatible
  artifact conventions.
- Update [gc/skills/plan-implementation/SKILL.md](./skills/plan-implementation/SKILL.md) for the same
  artifact conventions.
- Rewrite [gc/skills/create-beads/SKILL.md](./skills/create-beads/SKILL.md) to use
  nested convoys, not epics.
- Add [gc/skills/build/SKILL.md](./skills/build/SKILL.md).
- Add thin launch skills for implement/review/gap-analysis if the pack wants
  human-facing skill entry points for public formulas.
- Add convoy-aware payload creation at
  [gc/assets/scripts/create_beads_from_tasks.py](./assets/scripts/create_beads_from_tasks.py),
  or add a new helper there and retire the old one.
- Add scripts for context bundle and verdict report validation under
  `gc/assets/scripts/`.
- Replace [gc/formulas/implement.formula.toml](./formulas/implement.formula.toml).
- Add formula files for `build-run`, `do-work`, `do-work-item`,
  `gap-analysis`, `review`, `fix-convoy`, `same-session-implement`, and
  `publish`.
- Add GitHub adapter formulas for `github-issue-triage`, `github-pr-review`,
  and `github-issue-fix`.

## Testing

Unit tests:

- capability gate fails without side effects for each missing primitive
- reserved input collision tests cover CLI vars, rig vars, inherited metadata,
  payload metadata, formula vars, `issue`, `bead_id`, and user `convoy_id`
- task payload parser accepts nested `convoys[]` and rejects `epics[]`
- convoy tree validation rejects duplicate keys, overlapping membership,
  unknown dependencies, and cycles
- dependency expansion between convoys produces runnable-bead edges
- metadata inheritance works parent to child with overrides
- generated payload validation rejects unknown fields, unsafe metadata
  namespaces, unsafe artifact paths, unsafe branches, and unsafe `files:`
  scopes
- bead creation dry-run emits `gc bd create`, `gc convoy create`,
  `gc convoy add`, and dependency commands in deterministic order
- created mapping records both convoy heads and runnable beads
- context bundle validation accepts only `name`, `path`, and `description`
- context bundle validation fails missing referenced files
- context bundle validation rejects traversal, symlink escapes, disallowed
  absolute paths, secrets, binaries, and oversized files
- prompt fixture tests assert `fix-synthesis`, `do-work`, `gap-analysis`, and
  `review` fence untrusted context, diffs, reports, summaries, and descriptions
  as data; injection fixtures must not escalate `files:` or verification `argv`
- verdict report validation reads structured header and pass/fail verdict
- formula asset tests enforce graph.v2 formulas do not declare or reference
  `issue`, `bead_id`, or `[vars.convoy_id]`
- formula asset tests enforce expected public/internal formula names and step
  shapes
- build-run checkpoint tests cover atomic writes, active-run locking, resume
  from each side effect, repeated-finding convergence, no-op fix-plan rejection,
  and guaranteed `final-report.md`
- publish dry-run tests cover identity, token scope, remote, branch collision,
  protected/default branches, force rejection, PR base, metadata sanitization,
  and partial-publish resume
- GitHub URL validators reject shorthand and accept only full canonical issue
  or PR URLs
- issue triage idempotency is keyed only by issue body hash
- PR review idempotency is keyed by PR head SHA
- issue-fix reruns resume the latest active run by default
- issue-fix `mode` and `pr_mode` are independent and v0 never merges
- issue-fix existing PR reuse is limited to PRs authored by the authenticated
  GitHub actor
- GitHub workflows use sticky comments where specified and replace deleted
  sticky comments idempotently
- GitHub helper scripts live under `assets/scripts/`, with no legacy
  script-directory compatibility shims

Integration tests, once core prerequisites are available:

- decompose creates a convoy tree and runnable dependencies in a temp city
- direct `implement` on a singleton convoy routes `do-work`
- separate implementation drains a multi-member convoy into item work
- same-session implementation serializes item phases in dependency order
- same-session `gc hook` distinguishes `wait` from terminal `empty` and uses
  drain manifest plus live-ready reconciliation before completion
- same-session affinity loss reports `affinity_unavailable` and does not steal
  work into a different session
- build writes all expected artifacts and stops on implementation failure
- build creates fix convoys from failed verdict reports
- build fails hard after loop limit
- build resumes from crashes after report writes, fix-plan writes, fix-convoy
  creation, implementation launch, final-report writes, and partial publish
- publish can push without PR and PR creation implies push
- GitHub issue triage repeats without duplicate comments for the same body hash
- GitHub PR review repeats without duplicate comments for the same head SHA
- GitHub issue fix resumes the latest active run and preserves one sticky issue
  status comment
- GitHub issue fix can publish no PR, a draft PR, or a ready PR, and never
  merges

High-risk runtime evidence matrix:

<!-- REVIEW: added per high-risk-validation-matrix -->

| Assumption | Fake-city test | Temp-city integration | Core conformance gate | Runtime prerequisite |
| --- | --- | --- | --- | --- |
| graph.v2 prepare fails before side effects | mock missing primitive and assert unchanged bead/artifact/ref counts | launch against unsupported core and inspect no workflow roots | prepare schema, contract id, semantics hash | `gc.runtime-prepare.v1` |
| reserved variables are rejected everywhere | CLI, rig, payload, metadata, and formula-asset collision fixtures | targetless report formula with forbidden graph vars | reserved-input error ownership | graph.v2 reserved input enforcement |
| legacy epic rejection precedes singleton normalization | `type=epic`, old `epics[]`, and old mapping fixtures | bare epic target leaves no singleton convoy | pre-normalization reject support | raw target type inspection |
| ordinary convoy membership is non-blocking | readiness fixture with convoy heads and member tasks | blocked/readiness/orphan/drain selection temp city | convoy head inertness check | convoy membership primitives |
| dependency expansion is deterministic | nested, multi-root, multi-terminal, duplicate-edge, fanout, zero-membership, ancestor/descendant, and cycle fixtures | dry-run/reload creation plan equality | task validator golden output | blocker edge storage |
| separate drain uses core manifest order | malformed drain-unit metadata fixtures | multi-member drain proves separate item materialization | core drain manifest schema | graph.v2 drain materializer |
| same-session emits core shared drain | formula asset rejects `context = "same-session"` and requires `context = "shared"`, `single_lane = true`, and chosen `on_item_failure` | same-session item phases run under one lifecycle | shared-drain context and item verifier | core shared drain |
| same-session order is safe | dependency-order fixture rejects non-topological shared drain order | continuation session serializes items without dependency deadlock | accepted manifest order or topologically linearized convoy | order-safe shared drain |
| same-session hook status is exact | fake `work`, `wait`, `empty`, delayed materialization, and replay fixtures | continuation session waits, resumes, and empties only after reconciliation | hook status schema and `closed_seq` check | structured hook statuses |
| affinity loss is fail-closed | stale/lost session fixture produces `affinity_unavailable` summary | pinned session crash leaves work unstolen | continuation affinity conformance | hard affinity and heartbeat |
| verification sandbox is default-deny | wrapper-command bypass, unsafe `cwd`, network, env, secret, and write-path fixtures | sandboxed command cannot read/write outside scope | sandbox policy probe | sandbox runner support |
| publish preflight prevents unsafe remote mutation | protected branch, branch collision, token, PR base, and metadata fixtures | remote-aware collision and idempotent PR lookup | dry-run publish schema | remote and auth inspection |
| approvals are hash-bound | stale approval after artifact edit, missing front-half gate | build-run refuses stale design/decompose/start approvals | approval validator schema | canonical content hashing |
| build recovery is fenced and idempotent | lock takeover, stale owner, partial fix convoy, partial report, partial publish fixtures | crash/restart at every state-machine side effect | store CAS and lock fencing | conditional store primitives |
| GitHub wrappers are swappable | wrapper fixtures for issue snapshots, PR snapshots, actor, comments, PR create/update, and auth failures | dry-run temp repo using `gh api` where available | wrapper JSON schema | `assets/scripts/github_api.py` |
| GitHub idempotency is stable | body-hash and head-SHA fixtures, deleted comment replacement, stale metadata refresh | repeated triage/review/fix launches on unchanged inputs | source bead metadata keys | canonical GitHub source bead |
| human gate results do not decide iteration semantics | gate result fixtures for approve, reject, and needs-iteration | mail/reply resume smoke test | human gate result schema | mail and bead resume support |

Compatibility and rollout matrix:

| Feature | Required capability | Validator/test gate | Rollout gate | Failure mode |
| --- | --- | --- | --- | --- |
| graph.v2 formula launch | reserved target injection, singleton convoy normalization | formula asset and fake-city capability tests | install formulas only after core advertises graph.v2 | fail closed before work creation |
| task payload creation | convoy membership primitives, dependency storage | schema validator and dry-run/reload invariant checks | enable `create-beads` after validator passes in temp city | reject payload before beads |
| separate drain | graph.v2 drain materializer, drain control beads | temp-city multi-member drain test | enable `implement` separate policy | fail with no routed item work |
| same-session drain | structured `gc hook`, continuation affinity, `gc.closed_seq` | wait/empty, stale-session, dependency-order tests | keep behind explicit `same-session` opt-in | abnormal drain summary |
| build-run loops | conditional store primitives and durable artifact writes | checkpoint/resume and idempotent fix-convoy tests | enable `build` back half after recovery tests | final report with recovery status |
| generated fix work | task payload, command, path, metadata validators | adversarial generated-work tests | no automatic fix execution until validators pass | reject fix plan |
| publish | auth, ref, dry-run, and PR metadata checks | publish dry-run matrix | require explicit push/PR opt-in | no push or partial-publish recovery |
| GitHub issue triage | `gh api` wrapper, sticky comment, triage report schema | body-hash idempotency and security/P0 human-gate tests | enable auto-post only after comment tests pass | terminal triage failure or human gate |
| GitHub PR review | `gh api` wrapper, head-SHA snapshot, review report | head-SHA idempotency and sticky comment tests | default to `post_mode=human_gate` | report written but no public comment |
| GitHub issue fix | triage, build-run, sticky status comment, PR publication wrapper | run-resume, `mode`, `pr_mode`, foreign PR, and no-merge tests | keep `pr_mode=none` default | final report or sticky status failure |

## Rollout

1. Land the design doc and update tests to describe the new contracts.
2. Rewrite decompose payload validation and bead/convoy creation.
3. Add context bundle and verdict report validators.
4. Add public report-only formulas for gap-analysis and review.
5. Split implementation into `implement`, `do-work`, and `do-work-item`.
6. Add same-session shared-lifecycle implementation helper.
7. Add fix-convoy synthesis and build-run loop.
8. Add publish helper and README usage.
9. Move helper scripts to `assets/scripts/` and update formulas, skills, docs,
   and tests to remove legacy script-directory references.
10. Add GitHub wrapper script tests and adapter formula asset tests.
11. Add GitHub issue triage, PR review, and issue fix skills/formulas.
12. Run pack tests, formula asset validation, fake-city capability tests, and
   temp-city integration tests.
13. Exercise against a Gas City core build that includes convoy-first graph.v2,
    drain prerequisites, structured hook statuses, continuation affinity,
    `gc.closed_seq`, and conditional store primitives.
14. Keep same-session drain, automatic fix-convoy execution, and publish opt-ins
    disabled until their matrix rows pass.
15. Roll back by disabling public launch skills and leaving formulas installed
    but fail-closed through the capability gate.

## Requirement Coverage

Covered in v0:

- `$plan`
- `$design`
- `$decompose`
- `$implement`
- `$review`
- `$build`
- `$gh-issue-triage`
- `$gh-pr-review`
- `$gh-issue-fix`

Partially covered:

- GitHub PR creation is covered through `github-issue-fix` `pr_mode` and the
  generic publish helper. V0 never merges.
- GitHub PR review comments are covered by `github-pr-review` as normal PR
  comments, not formal GitHub review events.

Deferred:

- scripted convoy shredders beyond one-by-one
- richer gather policies
- dashboard visualizations
- automatic merging
- formal GitHub review API submissions

## Open Questions

None blocking the GitHub adapter implementation. The next implementation pass
should keep the adapters thin over the generic `gc` primitives and avoid
recreating bugflow/adopt-pr internals.
