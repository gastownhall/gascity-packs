# Gas City Packs

Reusable Gas City packs that define portable workflow behavior outside the Gas
City SDK core.

## Language

**GC Workflow Pack**:
A standalone pack named `gc` that provides reusable planning, design,
decomposition, implementation, review, build, and GitHub workflow behavior.
_Avoid_: Core SDK workflow, built-in SDK workflow

**Interactive Workflow Skill**:
A human-driven skill that interviews, drafts an artifact, and stops only when
the human explicitly approves the result.
_Avoid_: Long-running formula, autonomous workflow

**Workflow Formula**:
A durable formula that orchestrates repeatable multi-step work after its inputs
are sufficiently explicit.
_Avoid_: Skill script, prompt-only workflow

**Graph Formula**:
A version 2 workflow formula whose work input is a convoy rather than an
individual bead.
_Avoid_: Bead-scoped formula, issue formula

**Convoy Input**:
The target convoy a graph formula uses as its work container.
_Avoid_: Issue input, bead ID input

**Convoy**:
A special bead type that encapsulates one or more bead graphs as a work
grouping.
_Avoid_: Arbitrary metadata group, single wrapped bead

**Convoy Head**:
The special convoy bead that identifies the grouping but is not itself routed
or worked by implementation sessions.
_Avoid_: Work item, implementation member

**Convoy Member Graph**:
A bead graph encapsulated by a convoy and eligible for execution policy.
_Avoid_: Convoy head, loose task list

**Nested Convoy**:
A convoy inside another convoy that groups part of a task forest and carries
group-level planning metadata.
_Avoid_: Epic, dependency blocker

**Convoy Tree**:
A single-membership tree of convoys and runnable beads produced by
decomposition.
_Avoid_: Overlapping convoy graph, multi-parent grouping

**Planning Metadata**:
Metadata authored by planning/decomposition to describe intent, grouping, and
integration policy.
_Avoid_: Execution metadata, routing state

**Execution Metadata**:
Metadata authored by drain or runtime orchestration to route and reserve work.
_Avoid_: Planning metadata, artifact context

**Drain Policy**:
The execution choice drain applies to a convoy, such as separate sessions or
same-session execution.
_Avoid_: Decomposition output, planning metadata

**Build Workflow**:
The lifecycle workflow that moves an approved plan from decomposition through
implementation, review, and finalization.
_Avoid_: Decomposition, single implementation task

**Interactive Build Start**:
The first build step where an agent interviews the user to create requirements
before later design, decomposition, implementation, and review phases.
_Avoid_: Required preexisting artifact set, noninteractive build input

**Hybrid Build Workflow**:
A workflow whose interactive front half is skill-driven and whose approved
implementation back half is durable formula-driven.
_Avoid_: Pure formula build, pure manual skill flow


**Gap Analysis Loop**:
A build workflow loop that checks implementation coverage against the approved
plan/context and routes fixes until the gap analysis passes.
_Avoid_: Initial implementation, code review loop

**Review Fix Loop**:
A build workflow loop that runs review and routes fixes until review passes.
_Avoid_: Gap analysis, report-only review

**Verdict Report**:
A durable markdown report with a small structured header for formula-readable
verdict data followed by freeform human-readable analysis.
_Avoid_: Prose-only loop input, fully rigid review schema

**Fix Convoy**:
A convoy created for one gap-analysis or review-fix iteration.
_Avoid_: Reusing initial implementation convoy, unscoped fix work

**Runnable Member**:
A non-convoy bead in a convoy member graph that can be routed and worked when
ready.
_Avoid_: Convoy head, nested convoy

**Work Anchor**:
A runnable member selected for execution whose durable task bead remains the
identity and completion anchor for the work.
_Avoid_: Formula step, session prompt

**Do-Work Workflow Instance**:
The graph.v2 `do-work` formula materialized for one work anchor.
_Avoid_: Raw task bead, manual nudge

**Do-Work Item Phase**:
The middle implementation/review/finalization portion of `do-work` that acts on
one work anchor without owning worktree setup or teardown.
_Avoid_: Full do-work lifecycle, shared setup

**Shared Worktree Lifecycle**:
The single setup and teardown envelope created by a same-session drain so all
item phases run in one worktree and branch.
_Avoid_: Per-item worktree, conversational affinity

**Sequential Item Drain**:
A same-session drain mode where item phases run one at a time in dependency
order inside the shared lifecycle.
_Avoid_: Parallel item execution, branch fanout

**Item Serial Gate**:
A dependency gate in same-session drain that prevents item phases from
interleaving after one item starts.
_Avoid_: Lazy materialization, parallel phase scheduling

**Source-Attached Item Phase**:
A do-work item phase materialized for one work anchor while retaining that
anchor as the item completion source.
_Avoid_: Detached item work, drain-owned completion

**Dependency-Ordered Serial Drain**:
A same-session serial drain whose item order is a topological ordering of the
work-anchor dependency graph, using convoy traversal order only as a tie-breaker.
_Avoid_: Naive convoy-order serialization, dependency-blind sequence

**Live Ready Check**:
A readiness query that bypasses stale cached state and observes current bead
dependency/status state before selecting the next item.
_Avoid_: Cached ready list, precomputed drain queue

**Pinned Continuation Session**:
A session currently bound to a continuation group whose work discovery must not
fall through to unrelated routed queue work.
_Avoid_: Normal pooled session, target agent route

**Terminal Drain Session**:
A pinned continuation session that is expected to finish its assigned drain work
and close rather than return to normal pool work.
_Avoid_: Reusable worker session, unpinned idle session

**Claim-Time Pinning**:
The transition where a normal session becomes pinned after it claims a work bead
that carries continuation metadata.
_Avoid_: Pre-created special session, drain-owned session launch

**Continuation Preassignment**:
Assigning all open work in the same continuation group to the session that first
claims grouped work.
_Avoid_: Lazy reservation, routed queue sharing

**Hard Continuation Affinity**:
The rule that `gc.continuation_group` is a hard session-affinity contract, not a
soft routing preference.
_Avoid_: Prefer same session, best-effort affinity

**Sling Materialization**:
Using `gc sling <target> <bead-id> --on <formula>` to compile, attach, start,
route, and wake a graph workflow for a work anchor.
_Avoid_: Direct prompt, hand-rolled formula expansion

**Drain Convoy Enumeration**:
The core drain behavior that walks a convoy tree, skips convoy heads and nested
convoys as work, and selects runnable members for item materialization.
_Avoid_: Sling-owned traversal, convoy-head execution

**Terminal Runnable Member**:
A runnable member that no other runnable member in the same convoy depends on.
_Avoid_: Convoy completion bead, convoy head

**Root Runnable Member**:
A runnable member that has no dependency blockers inside its convoy.
_Avoid_: Convoy head, first listed item

**Member Graph Root**:
A direct child of a convoy head that anchors one convoy member graph.
_Avoid_: Convoy head, arbitrary descendant

**Task Forest**:
The one-or-more bead graphs produced by decomposition for a plan.
_Avoid_: Single task DAG, convoy policy

**Convoy Declaration**:
The machine-readable part of a task plan that names the convoy head and member
graph roots to create.
_Avoid_: Drain policy, route configuration

**Task Payload**:
The machine-readable section of a task plan that declares runnable beads,
nested convoys, and dependencies.
_Avoid_: Epic payload, implementation script input

**Intent Context**:
Reference material that helps an agent understand the desired outcome without
expanding what it owns.
_Avoid_: Work ownership, task assignment

**Review Context Bundle**:
A caller-provided set of named context items with descriptions explaining how a
reviewer should use them.
_Avoid_: Hardcoded convoy graph input, branch-only review

**Implementation Context Bundle**:
A caller-provided set of named context items passed to sessions implementing
work anchors in a convoy.
_Avoid_: Ownership boundary, required plan artifact shape

**Context Bundle File**:
A structured YAML or JSON file that lists named context items and descriptions.
_Avoid_: Many scalar formula vars, implicit artifact layout

**Context Item**:
One named file reference in a context bundle.
_Avoid_: Typed context schema, inline command, ownership item

**Ownership Boundary**:
The explicit set of work an agent or formula is allowed to change or complete.
_Avoid_: Context, background material

**Drain**:
A workflow primitive that applies execution policy to a convoy's member graphs
before those graphs are assigned.
_Avoid_: Implement mode, worker choice

**Visible Internal Formula**:
A formula shipped in the pack for inspection, copying, and composition but not
presented as a supported direct launch target.
_Avoid_: Hidden implementation detail, public launch surface

**Implementation Convoy**:
A convoy whose member graphs are the complete code-writing ownership boundary
for a worker.
_Avoid_: Task list, item selection

**Implement Formula**:
The public lifecycle formula that executes an implementation convoy.
_Avoid_: Drain, do-work-item

**Execution Frontier**:
The ready subset of an implementation convoy that may be claimed and worked
right now.
_Avoid_: Full convoy, assignment

**Continuation Claim**:
The act of reserving all unfinished members of an implementation convoy for
the session that first claims ready work from that convoy.
_Avoid_: Routing, drain slicing, continuation group

**Same-Session Policy**:
The execution policy that all members of a drained bead graph should be worked
by the same live session when they become ready.
_Avoid_: Convoy meaning, wrapper semantics

**Public Workflow Formula**:
A user-facing workflow formula that can be launched directly to accomplish an
end-to-end lifecycle phase.
_Avoid_: Internal helper formula

**Reusable Subformula**:
A workflow formula factored for composition by other formulas rather than
direct human invocation.
_Avoid_: Public workflow, inline duplicated steps

**Launch Skill**:
A thin skill that explains, validates, or starts a corresponding workflow
formula without owning the durable orchestration itself.
_Avoid_: Manual wrapper, duplicate formula

**Plan Artifact Set**:
The durable files for one planned unit of work, keyed by a plan slug and rooted
under an artifact root.
_Avoid_: Workflow folder, plan directory

**Plan Slug**:
A stable human-readable key that names one plan artifact set.
_Avoid_: Run ID, branch name

**Artifact Root**:
The directory under which plan artifact sets are stored.
_Avoid_: Output directory, workspace

## Relationships

- A **GC Workflow Pack** is imported by a city and is not bundled into the Gas
  City SDK core.
- An **Interactive Workflow Skill** may produce artifacts consumed by a
  **Workflow Formula**.
- A **Launch Skill** starts or guides a **Workflow Formula**.
- A **Public Workflow Formula** may compose one or more **Reusable Subformulas**
  while remaining directly inspectable and runnable.
- A **Plan Artifact Set** belongs to exactly one **Plan Slug** and lives under
  one **Artifact Root**.
- A **Graph Formula** uses a **Convoy Input** when it operates on work.
- A **Convoy** has exactly one **Convoy Head** and one or more **Convoy Member
  Graphs**.
- A **Convoy Member Graph** starts at a **Member Graph Root**.
- A **Task Forest** may contain multiple disjoint member graph roots.
- Decomposition outputs a **Task Forest** wrapped by a **Convoy**.
- A **Convoy Declaration** belongs in the decomposition artifact and defines the
  convoy head plus member graph roots before execution policy is applied.
- A **Task Payload** contains `convoys[]` and `beads[]`, not `epics[]`.
- `convoys[]` may nest and may carry metadata.
- The nested convoy structure is a **Convoy Tree**.
- Each **Runnable Member** belongs to exactly one immediate convoy.
- Each **Nested Convoy** belongs to exactly one parent convoy.
- Decomposition uses **Nested Convoys**, not epics, for planning groups that
  carry metadata such as branch or integration policy.
- **Planning Metadata** inherits from parent convoy to nested convoy to runnable
  bead, with child values overriding parent values.
- Decomposition authors **Planning Metadata** only.
- Decomposition does not author **Drain Policy**.
- Drain and runtime orchestration author **Execution Metadata**.
- **Drain Policy** is chosen by drain at execution time.
- A **Build Workflow** chooses the drain policy for implementation.
- **Implement Formula** executes an existing convoy.
- **Build Workflow** is artifact-driven and may ensure or create the convoy
  before invoking **Implement Formula**.
- **Build Workflow** requires no initial inputs.
- **Build Workflow** begins with **Interactive Build Start** to create
  requirements and then derives later artifacts from there.
- **Build Workflow** is a **Hybrid Build Workflow**.
- Public `build` is a skill-driven entry point.
- The durable formula back half is a visible internal formula, tentatively
  `build-run`.
- The build skill hands the durable formula back half the approved artifact set
  path, generated context bundle path, initial implementation convoy id, drain
  policy, and loop limits.
- **Build Workflow** orchestrates planning, design, and decomposition as phases.
- `gather-requirements`, `plan-implementation`, and `create-beads` remain separately callable interactive
  skills for humans.
- `create-beads` writes `tasks.md` and creates the approved beads/convoy after
  human approval.
- **Build Workflow** reuses the convoy id produced by decomposition.
- **Build Workflow** generates the initial context bundle after decomposition
  approval from requirements, design, and tasks artifacts.
- **Build Workflow** creates a new convoy target branch by default for
  build-managed work.
- Build-created target branch names are deterministic from the plan slug, with
  a collision suffix when needed.
- Build push and PR creation are opt-in settings.
- Push and PR opt-in settings exist on both **Build Workflow** and **Implement
  Formula**.
- Push without PR creation is a valid finalization mode.
- PR creation implies the target branch has been pushed first.
- PR title and body are generated from the final report and plan artifact set,
  with links or references to durable artifacts where useful.
- Direct **Implement Formula** push/PR happens after implementation succeeds.
- **Build Workflow** push/PR happens only after implementation, gap-analysis,
  and review loops all pass.
- Direct **Implement Formula** does not run gap-analysis or review before
  push/PR.
- Use **Build Workflow** for implementation with gap-analysis and review loops.
- Standalone `create-beads` does not need to emit a context bundle in v0.
- **Build Workflow** requires explicit human approval before advancing from
  planning to design, from design to decomposition, and from decomposition to
  implementation.
- After decomposition is approved for implementation, **Build Workflow** runs
  implementation, gap-analysis fixes, review fixes, and finalization without
  additional human approval by default.
- **Build Workflow** owns validation, implementation, review, and final handoff
  for an approved plan artifact set.
- **Build Workflow** generates the context bundle for downstream implementation,
  gap-analysis, and review steps as part of its own work.
- **Build Workflow** does not close convoy heads directly.
- **Build Workflow** runs review only after **Implement Formula** succeeds.
- If implementation fails, **Build Workflow** stops and summarizes failures.
- After successful implementation, **Build Workflow** runs a **Gap Analysis
  Loop**.
- After gap analysis passes, **Build Workflow** runs a **Review Fix Loop**.
- Gap-analysis workflow reports findings and verdict only in v0.
- Gap-analysis is a public durable formula with a thin launch skill.
- Gap-analysis consumes any **Context Bundle File**; it does not require a file
  named `tasks.md`.
- Gap-analysis uses both implementation summary and diff/artifacts when
  available.
- Each failed gap-analysis or review iteration creates a new **Fix Convoy**.
- A model step synthesizes each **Fix Convoy** from the gap-analysis or review
  report.
- Fix-convoy synthesis is visible internal in v0, not a public launch target.
- Finding-to-task mapping is model judgment, not hardcoded formula logic.
- Fix loops route fixes through **Implement Formula** using the **Fix Convoy**.
- **Fix Convoys** inherit the original implementation drain policy.
- **Fix Convoys** use the same per-item commit and summary behavior as initial
  implementation.
- Gap-analysis and review fix loops default to a maximum of 10 iterations each.
- If a fix loop reaches its maximum iteration count without passing, **Build
  Workflow** fails hard with a summary.
- Gap-analysis and review reports are written as durable files in the plan
  artifact set.
- Gap-analysis and review reports are **Verdict Reports**.
- **Verdict Reports** expose machine-readable `verdict`, `severity`, and
  `findings[]` fields in a structured header, then freeform markdown analysis.
- Gap-analysis and review loops write immutable per-iteration report files and
  maintain a latest report pointer or copy for convenience.
- Each synthesized **Fix Convoy** writes a durable per-iteration fix task plan
  linked from the corresponding report.
- **Fix Convoy** task plans use the same task payload and convoy schema as
  decomposition output, with metadata linking back to the failed report and
  iteration.
- **Build Workflow** always writes a final report artifact summarizing the
  artifacts, implementation summaries, gap-analysis iterations, review
  iterations, branch/PR info, and final status.
- Failed **Build Workflow** runs also write a durable final status report.
- The active build artifact set uses a fixed final report path such as
  `final-report.md`.
- Build finalization happens only after both loops pass.
- Review workflows consume a **Review Context Bundle** instead of requiring live
  convoy graph inspection.
- A task plan file such as `tasks.md` can be sufficient review context when it
  describes intended work and ownership.
- Review workflows may consume the same **Context Bundle File** passed to
  implementation.
- `context_path` is optional but strongly recommended for review workflows.
- Review workflows may still run against a diff or subject without extra
  context.
- Review workflows consume implementation summaries when available.
- Review is a public durable formula with a thin launch skill.
- Review workflows report findings and verdict only in v0.
- Review workflows do not reopen work anchors or create follow-up task beads in
  v0.
- **Drain** is a **Visible Internal Formula**, not a supported public launch
  target.
- Users may inspect, copy, and adapt **Drain**, but launch skills should route
  normal users through public lifecycle formulas.
- **Implement Formula** is the public entry point for executing a convoy.
- **Implement Formula** is a public durable formula with a thin launch skill,
  not a hybrid workflow.
- **Implement Formula** validates the convoy, invokes **Drain**, waits for
  implementation completion, and records a summary or handoff.
- **Implement Formula** succeeds when all selected non-convoy work anchors are
  closed.
- **Implement Formula** fails if any selected work anchor remains open or failed
  after execution.
- **Implement Formula** does not close failed work anchors.
- Work anchors closed before implementation starts count as already satisfied.
- Implementation summaries distinguish already-closed anchors, anchors closed by
  the current run, and anchors left open or failed.
- Implementation summaries are written as durable files when an artifact or
  summary path is provided.
- Same-session drain produces per-item implementation summaries plus an
  aggregate summary.
- Separate-session drain also produces per-item implementation summaries plus an
  aggregate summary.
- `do-work-item` writes per-item implementation summaries.
- **Implement Formula** writes the aggregate implementation summary.
- **Build Workflow** always provides a durable implementation summary path.
- Direct **Implement Formula** runs without a summary path record their summary
  on the implement workflow bead rather than inventing an implicit file path.
- **Implement Formula** does not close the convoy head.
- **Implement Formula** defaults to separate-session drain policy.
- Same-session implementation must be selected explicitly.
- **Implement Formula** requires a convoy and accepts an **Implementation
  Context Bundle**.
- The convoy is the ownership boundary; the context bundle is useful reference
  material for each session implementing individual beads.
- Formulas pass context through a **Context Bundle File**, typically via a
  `context_path` variable.
- `context_path` is optional for **Implement Formula**.
- A **Context Bundle File** contains freeform **Context Items** with only
  `name`, `path`, and `description`.
- v0 context is file-reference based only.
- Context item paths are relative to the context file location by default;
  absolute paths are accepted but not preferred.
- If `context_path` is provided, formulas fail fast when referenced context
  files are missing.
- Missing optional `context_path` is treated as an empty context bundle.
- Formula prompts present context bundles as named file references and
  descriptions.
- Formula prompts do not inline context file contents into every bead
  description.
- The **Convoy Head** is skipped for route target and same-session metadata.
- **Nested Convoys** are skipped for route target and same-session metadata.
- **Drain** applies execution policy to **Convoy Member Graphs**, not to the
  **Convoy Head**.
- **Drain** applies execution policy only to **Runnable Members**.
- **Drain** selects ready non-convoy **Runnable Members** as **Work Anchors**.
- Each selected **Work Anchor** becomes one **Do-Work Workflow Instance**.
- **Drain Materialization** is the boundary that turns selected runnable members
  into graph.v2 item work.
- **Drain Convoy Enumeration** is owned by core drain, not by `gc sling` or
  pack formulas.
- Drain owns convoy tree traversal, selected-member manifests, route metadata,
  and item formula materialization.
- `gc sling` targets the input convoy whole for graph.v2 formula launch; it does
  not recursively explode a convoy into standalone formula launches.
- A separate-session drain materializes the full `do-work` lifecycle per work
  anchor.
- A same-session drain creates one **Shared Worktree Lifecycle** and runs a
  **Do-Work Item Phase** for each work anchor inside that lifecycle.
- Separate-session drain is implemented through core **Drain Materialization**
  of one full `do-work` lifecycle per selected runnable member.
- Same-session drain uses a dedicated shared-lifecycle materializer rather than
  recursive full `do-work` materialization.
- `do-work` is the public full-lifecycle work formula.
- `do-work-item` is an internal reusable subformula used by `do-work` and
  same-session drain.
- Full-lifecycle `do-work` invokes `do-work-item` so per-item behavior is
  identical between separate and same-session modes.
- `do-work-item` owns item-level implementation, commit/finalization, source
  work-anchor closure, and per-item summary.
- Same-session mode still commits separately per item by default.
- Same-session mode uses one branch for the drain group, with separate commits
  per item.
- The convoy has a branch.
- Gas City's existing convoy branch metadata is `target`, set via
  `gc convoy target`.
- New GC pack formulas use `target_branch` to refer to the convoy integration
  branch.
- If no convoy target branch is set, work formulas default to the repository
  default branch.
- Separate-session items target the convoy branch and handle merge conflicts
  themselves.
- Full-lifecycle and same-session wrappers own workspace setup/teardown.
- `do-work-item` must not be exposed as a normal launch target because it
  requires an existing worktree lifecycle.
- Same-session drain does not materialize full per-item `do-work` workflows,
  because per-item setup and teardown would fragment the shared code context.
- Same-session drain uses **Sequential Item Drain** for v0.
- Same-session drain must not run item phases in parallel against the shared
  worktree.
- **Sequential Item Drain** chooses the next item through `bd ready` semantics,
  not a drain-authored sequence.
- Same-session drain uses **Item Serial Gates** so once an item phase starts,
  no other item phase can become ready until that item phase completes.
- Same-session **Item Serial Gates** must follow **Dependency-Ordered Serial
  Drain**.
- Convoy traversal order is only a tie-breaker among dependency-independent
  ready items.
- Same-session drain must reject cyclic or dependency-incompatible item graphs
  instead of materializing a deadlocking serial chain.
- Same-session drain serializes all open non-convoy members in the drained
  convoy, not only the current ready frontier.
- Closed members are skipped or treated as already satisfied when building the
  serial chain.
- Same-session drain materializes **Source-Attached Item Phases** inside the
  shared lifecycle.
- A **Source-Attached Item Phase** keeps its work anchor as the source and
  completion anchor.
- Item phase entry depends on shared setup, original task dependencies, and the
  prior item serial gate when present.
- A **Do-Work Item Phase** closes its own **Work Anchor** on success.
- Same-session drain selects the next item with a **Live Ready Check**, not from
  a cached ready list.
- Same-session drain must observe newly closed anchors before advancing to a
  dependent item.
- A **Pinned Continuation Session** searches only assigned in-progress work and
  assigned ready/open work.
- A **Pinned Continuation Session** must not fall through to unassigned
  `gc.routed_to` pool work.
- A session stores pinned continuation state on the session bead, not on the
  work bead.
- Session pinned metadata includes the continuation group and, when applicable,
  the drain id that created the pin.
- A same-session drain uses a **Terminal Drain Session**.
- A **Terminal Drain Session** does not clear its pin and resume pool work.
- When a **Terminal Drain Session** has no remaining assigned drain work, it
  closes instead of falling through to unrelated routed queue work.
- A session starts unpinned and runs the normal full work query.
- **Claim-Time Pinning** happens after the session claims a bead with
  `gc.continuation_group` when the session bead does not already have a pin.
- `gc.continuation_group` is sufficient to trigger **Claim-Time Pinning**; no
  additional terminal-drain marker is required.
- **Claim-Time Pinning** includes **Continuation Preassignment**.
- **Continuation Preassignment** is expected existing behavior and must be
  verified before adding new runtime logic.
- `gc.continuation_group` implies **Hard Continuation Affinity**.
- Any formula that stamps `gc.continuation_group` opts into terminal pinned
  session behavior for that group.
- After **Claim-Time Pinning**, later work discovery for that session follows
  **Pinned Continuation Session** rules.
- Dependencies between convoys expand from **Terminal Runnable Members** of the
  upstream convoy to **Root Runnable Members** of the downstream convoy.
- A **Convoy** does not imply session affinity by itself; **Drain** applies
  execution policy to a convoy.
- **Intent Context** improves agent output quality but does not change the
  **Ownership Boundary**.
- For an implementation workflow, the **Plan Artifact Set** defines intent and
  the **Convoy Input** defines the work membership boundary.
- A **Drain** decides how a broader convoy is sliced before implementation.
- An **Implementation Convoy** is implemented as a whole by the session that
  receives it.
- The **Execution Frontier** is discovered through normal ready-work semantics.
- **Same-Session Policy** is implemented by stamping a shared continuation
  group and route target on the graph members.
- A **Continuation Claim** reserves unfinished same-policy graph members for the
  first session that claims ready work while allowing normal dependency
  readiness to decide when each bead appears.

## Example Dialogue

> **Dev:** "Should the planning workflow live in the SDK core pack?"
> **Domain expert:** "No. It belongs in the **GC Workflow Pack** so cities can
> import, override, and iterate on it separately from Gas City releases."
>
> **Dev:** "Should `$plan` be a formula?"
> **Domain expert:** "No. It is an **Interactive Workflow Skill** because it
> depends on human approval. `$implement` is a **Workflow Formula** because it
> can run durable orchestration from approved artifacts."
>
> **Dev:** "Should `$implement` inline its review loop?"
> **Domain expert:** "No. Keep `$implement` as a **Public Workflow Formula** and
> factor the review loop into a **Reusable Subformula**."
>
> **Dev:** "Where should review reports and final summaries go?"
> **Domain expert:** "They belong in the **Plan Artifact Set**, so formulas can
> compose through files and bead notes can point to durable paths."
>
> **Dev:** "Should a graph formula take an issue ID?"
> **Domain expert:** "No. A **Graph Formula** takes a **Convoy Input** when it
> needs work context."
>
> **Dev:** "Can a worker use the whole design doc?"
> **Domain expert:** "Yes, as **Intent Context**. The worker's **Ownership
> Boundary** is still the convoy or bead it was assigned."
>
> **Dev:** "Should `$implement` decide whether to handle work one item at a
> time?"
> **Domain expert:** "No. **Drain** makes that slicing decision before
> implementation. `$implement` owns the **Implementation Convoy** it receives."
>
> **Dev:** "How does a session keep the whole convoy without working blocked
> items early?"
> **Domain expert:** "Have **Drain** apply **Same-Session Policy** to the
> **Convoy Member Graphs**, then let the **Execution Frontier** expose only
> ready items."
>
> **Dev:** "Does decomposition produce a single graph?"
> **Domain expert:** "No. It may produce a **Task Forest**, and the output of
> decomposition is that forest wrapped by a **Convoy**."
>
> **Dev:** "Should drain infer the convoy from task dependencies?"
> **Domain expert:** "No. Decomposition writes an explicit **Convoy
> Declaration**; drain applies execution policy later."
>
> **Dev:** "Should architecture output epics for grouped work?"
> **Domain expert:** "No. Use **Nested Convoys** so group metadata lives on
> convoys, while dependencies apply to **Runnable Members**."
>
> **Dev:** "Can one convoy block another convoy?"
> **Domain expert:** "Only as shorthand. The dependency expands from upstream
> **Terminal Runnable Members** to downstream **Root Runnable Members**."
>
> **Dev:** "What does the decomposition payload contain?"
> **Domain expert:** "A **Task Payload** with nested `convoys[]`, runnable
> `beads[]`, and dependencies; it does not contain `epics[]`."
>
> **Dev:** "Can one bead appear in two convoys?"
> **Domain expert:** "No. The decomposition output is a **Convoy Tree**; use
> dependencies for cross-slice relationships."
>
> **Dev:** "Where does integration branch metadata live?"
> **Domain expert:** "As **Planning Metadata** on the narrowest convoy that owns
> that policy, inherited by descendant runnable beads."
>
> **Dev:** "Should decomposition decide same-session vs separate execution?"
> **Domain expert:** "No. Decomposition defines tasks and dependencies. **Drain
> Policy** belongs to drain."
>
> **Dev:** "Who chooses the drain policy for a planned implementation?"
> **Domain expert:** "The **Build Workflow** chooses it when it launches drain."

## Flagged Ambiguities

- "Core workflow" was used to mean reusable workflow behavior, not SDK-bundled
  behavior. Resolved: use **GC Workflow Pack** for this pack and avoid implying
  it ships inside Gas City's core SDK pack.
- "Skill" was used for both interactive interviewing and durable orchestration.
  Resolved: use **Interactive Workflow Skill** for human approval flows and
  **Workflow Formula** for durable repeatable orchestration.
- "Output" was too vague for workflow files. Resolved: use **Plan Artifact Set**
  for the durable artifact tree, **Artifact Root** for its parent directory,
  and **Plan Slug** for the stable key.
- "Input bead" was used for graph workflows. Resolved: use **Convoy Input** for
  work context and avoid issue- or bead-scoped formula language.
- "Context" and "assignment" were conflated. Resolved: use **Intent Context**
  for reference material and **Ownership Boundary** for the allowed work set.
- "Implement mode" was used to describe convoy slicing. Resolved: slicing is
  the responsibility of **Drain**, and implementation receives an
  **Implementation Convoy**.
- "Ready convoy" was too strong. Resolved: a convoy may contain future work;
  only its **Execution Frontier** is claimable at a given moment.
- "Convoy" was treated as either a wrapper bead or an arbitrary graph.
  Resolved: a **Convoy** is a special bead type with one **Convoy Head** that
  encapsulates one or more **Convoy Member Graphs**.
- "Convoy" was overloaded with session affinity. Resolved: a **Convoy** is the
  grouping that encapsulates member graphs; **Drain** applies
  **Same-Session Policy** when same-session execution is desired.
- "Task DAG" implied a single head. Resolved: decomposition produces a **Task
  Forest** that may have multiple disjoint roots.
- "Convoy output" was underspecified. Resolved: decomposition emits a
  **Convoy Declaration** in the task plan and creates the convoy head alongside
  task beads.
- "Epic" duplicated convoy grouping semantics. Resolved: architecture and
  decomposition should use **Nested Convoys** for grouped work and should not
  use epics as dependency blockers.
- "Convoy dependency" could imply convoy heads block work. Resolved: convoy
  dependencies are shorthand expanded onto runnable members; convoy heads are
  not blockers.
- "Bead creation payload" was too generic and included epics. Resolved: use
  **Task Payload** with nested convoys and runnable beads.
- "Nested convoys" could imply overlapping groups. Resolved: decomposition
  produces a **Convoy Tree** with single membership.
- "Metadata" mixed planning intent with routing state. Resolved: planning and
  decomposition produce **Planning Metadata**; drain/runtime produce
  **Execution Metadata**.
- "Drain policy" was treated as part of decomposition. Resolved:
  **Drain Policy** is execution-time policy chosen by drain, not planning
  output.
- "Build" was vague. Resolved: **Build Workflow** owns the lifecycle from
  approved plan through implementation, review, and finalization.
