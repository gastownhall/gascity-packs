# Contributing

The external-contributor lifecycle for
[gastownhall/gascity](https://github.com/gastownhall/gascity), distributed as a
Gas City pack.

It gives an outside contributor the full journey of landing work upstream — and
carries Gas City's **actual** standards at every step. This is not generic PR
discipline: the adoption-review audit (B1–B36), the blast-radius dimensions, the
design-capture rule, the five test tiers, and the code conventions a Gas City
maintainer reviews against are all **baked into the skill text**, so your own
coding agent applies them by reading the skill.

## Self-contained by design

This pack has **no imports** and depends on nothing you might not have — no
internal agents, no sibling pack, no maintainer-only tooling. Every skill is a
self-applicable checklist. You run the workflow with `git`, `gh`, and your
coding agent reading the skills; that's it.

> The generic [pr-pipeline] pack is still the right choice for a city that wants
> contributor discipline without Gas City's particular standards. This pack is
> the gas-city-specific instantiation — it trades portability for baked-in
> standards.

## The lifecycle

It starts at a **router** — GATE 0, *"a priority issue, or your own?"* — that
feeds two step-1 variants (do **1a or 1b** depending on what you're starting
from); both converge on step 2.

| Step | What you do | Skill |
|------|-------------|-------|
| 0 | **Start here.** Route on entry: priority issue → 1a; your own issue/bug → 1b | [`start-contribution`](skills/start-contribution/SKILL.md) |
| 1a | Find a priority issue to work on (someone else's, or a triage pick) | [`find-work`](skills/find-work/SKILL.md) |
| 1b | Write a high-quality issue (something you found) | [`write-issue`](skills/write-issue/SKILL.md) |
| 2 | Plan the implementation (incl. blast-radius mapping as Phase 2) | [`plan-implementation`](skills/plan-implementation/SKILL.md) |
| 3 | Fine-tune the diff (incl. the review as its final gate) | [`fine-tune`](skills/fine-tune/SKILL.md) |

Two sub-skills are **a phase of a parent skill AND a standalone utility** — not
pipeline steps of their own. Run each as part of its parent, or directly:

- [`map-blast-radius`](skills/map-blast-radius/SKILL.md) — Phase 2 of
  `plan-implementation`; standalone for ad-hoc impact mapping (scoping a refactor,
  mapping a change for someone else).
- [`review`](skills/review/SKILL.md) — the final gate of `fine-tune`; standalone
  to review any diff/branch against the Gas City standard (incl. before a PR
  exists, or as a maintainer on an incoming contribution).

Step 1 has two mutually-exclusive variants — the router (step 0) picks one, then
both lead to step 2:

- **Implement/fix a priority issue** — step 1a (`find-work` to triage), then plan it (step 2).
- **Implement/fix your own issue** — step 1b (`write-issue`), then plan it (step 2).

The [`start-contribution`](skills/start-contribution/SKILL.md) skill is the
operational map and the entry router: it runs GATE 0, branches to 1a or 1b, and
links each step to its skill.

## Three ways to run it

The same lifecycle, the same standards, three delivery modes:

- **Skills (agent-read)** — your coding agent applies a step by *reading* the
  skill text. This is the default for a contributor working with a coding agent:
  no orchestration, no city required. Start at
  [`start-contribution`](skills/start-contribution/SKILL.md).
- **Formulas (gc-orchestrated)** — thin `mol-contributing-*` wrappers let a city
  *dispatch* a single step to a transient worker session as a gc formula. Each
  wrapper is orchestration only: it resolves the run's root bead, records state,
  writes the output artifact, and enforces blocking early-exits — then **delegates
  every standard to its sibling skill**. The skill stays the single source of
  truth; the formula never restates the audit, the gates, or the dimensions.
- **Mayor-orchestrated lifecycle (whole-process)** — the
  [`orchestrate-contribution`](skills/orchestrate-contribution/SKILL.md) skill
  drives the *whole* lifecycle as a **mayor loop**: it dispatches the per-step
  formulas in order and **pauses at each of the four human gates** (see [The
  gating model](#the-gating-model)). It owns only dispatch + gate; every standard
  stays in the skills, every step's mechanics stay in the formulas. No formula is
  modified — the loop consumes the root-bead notes the formulas already emit.

| Formula                                | Applies skill                                                  | Models on (pr-pipeline) |
| -------------------------------------- | -------------------------------------------------------------- | ----------------------- |
| `mol-contributing-find-work`           | [`find-work`](skills/find-work/SKILL.md)                       | `mol-pr-triage`         |
| `mol-contributing-plan-implementation` | [`plan-implementation`](skills/plan-implementation/SKILL.md)   | `mol-pr-start`          |
| `mol-contributing-map-blast-radius`    | [`map-blast-radius`](skills/map-blast-radius/SKILL.md)         | `mol-pr-blast-radius`   |
| `mol-contributing-review`              | [`review`](skills/review/SKILL.md)                             | `mol-pr-review`         |
| `mol-contributing-fine-tune`           | [`fine-tune`](skills/fine-tune/SKILL.md)                       | `mol-pr-ship`           |

There is no formula for `write-issue`: issue authoring sits upstream of the PR
flow (you have nothing to orchestrate against yet), so use that skill directly.

Formula outputs land under `.gc/contributing/` (work-queue, plan, blast-radius,
review, and fine-tune reports), and run state is recorded in the molecule's
root-bead notes. Like the skills, the formulas stop before pushing —
`mol-contributing-fine-tune` ends at the readiness report and never runs
`git push` or `gh pr create`.

## The gating model

The lifecycle has **four human gates** — pick an issue (GATE 1), confirm the plan
before any code (GATE 2), review the readiness report (GATE 3), and the entry
branch itself (GATE 0). Those gates are **real**, but there is deliberately **no
single end-to-end formula** that runs the whole lifecycle unattended. Here's why.

A `mol-contributing-*` formula runs in an **unattended transient worker session** —
nobody is at the keyboard. A formula gate can only *auto-proceed* or
*halt-and-stop*; it cannot interactively pause and resume the same run. But the
contributor gates are interactive human decisions, and one step (implementation)
is done by a human by hand. So the gates are realized at **formula boundaries / the
mayor layer**, not inside a worker:

- In **per-step formula** mode, each formula ends by writing its artifact and
  printing `Next: dispatch mol-contributing-<X>`. That handoff line **is** a gate —
  a city operator reads the artifact and decides whether to dispatch the next step.
- In **mayor-orchestrated** mode, [`orchestrate-contribution`](skills/orchestrate-contribution/SKILL.md)
  formalizes the same boundary into a loop: dispatch a step → read the root-bead
  notes the worker wrote → surface the artifact + recommended action to the human →
  **wait for the decision** → dispatch the next step. The pause works because the
  mayor is the attended agent actually talking to the human. Across long waits it
  uses `gc handoff`, and a fresh mayor resumes from the bead notes.

The mayor loop never auto-pushes, never opens a PR, and never auto-implements —
GATE 2, GATE 3, and the final stop are preserved.

## Why two map skills

Two skills describe the same lifecycle, one per audience:

- [`start-contribution`](skills/start-contribution/SKILL.md) — the **contributor
  entry**. A coding agent reads each step's skill and **implements by hand**. No
  city, no `gc`.
- [`orchestrate-contribution`](skills/orchestrate-contribution/SKILL.md) — the
  **mayor umbrella**. A city operator **dispatches** the steps to transient workers
  and gates each one.

They are split because a single skill would carry one `description` for two very
different trigger contexts and two registers — "apply by hand" vs. "dispatch +
gate" — and would mis-route both. Keeping them separate makes each `description`
precise. `orchestrate-contribution` **reuses `start-contribution`'s GATE 0 branch
logic rather than restating it**, so the entry skill stays the single source of
truth for the map.

## Nothing here pushes for you

Each step produces an artifact you act on — an issue body, a plan, a blast-radius
report, an audit verdict, a readiness report. The `fine-tune` skill stops at the
readiness report. **Pushing the branch and opening the PR are your call.**

## Usage

In your city's `pack.toml`:

```toml
[imports.contributing]
source = "../packs/contributing"   # path; or git URL when published
```

Then the skills load for your coding agent. You can also read them directly from
this directory — they're self-contained Markdown.

## Migrating from the previous version

The current pack is **0.4.0**. If you adopted an earlier version, the skill and
formula **names** changed during the lifecycle rework — nothing else about how a
step behaves did. Every standard baked into the skills (the B1–B36 adoption
audit, the blast-radius dimensions, the five test tiers, the gating model) is
unchanged, outputs still land under `.gc/contributing/`, and nothing here pushes
a branch or opens a PR. **The only break is the names**, so update any reference
that pins one:

| Old name | New name |
|----------|----------|
| `contributing` (entry skill) | [`start-contribution`](skills/start-contribution/SKILL.md) |
| `plan-pr` | [`plan-implementation`](skills/plan-implementation/SKILL.md) |
| `blast-radius` | [`map-blast-radius`](skills/map-blast-radius/SKILL.md) |
| `ship` | [`fine-tune`](skills/fine-tune/SKILL.md) |
| `check` | [`review`](skills/review/SKILL.md) |
| `mol-contributing-triage` | `mol-contributing-find-work` |
| `mol-contributing-start` | `mol-contributing-plan-implementation` |
| `mol-contributing-blast-radius` | `mol-contributing-map-blast-radius` |
| `mol-contributing-ship` | `mol-contributing-fine-tune` |

(`mol-contributing-review` keeps its name.) To upgrade:

- **Skills (agent-read):** enter at [`start-contribution`](skills/start-contribution/SKILL.md)
  instead of `contributing`; the renamed steps link from there.
- **Formulas (gc-orchestrated):** update any `gc sling mol-contributing-*` call
  that uses an old formula name per the table above.
- **New in 0.4.0:** the [`orchestrate-contribution`](skills/orchestrate-contribution/SKILL.md)
  mayor-mode umbrella, which drives the whole lifecycle by dispatching the
  per-step formulas and gating each one. It's additive — existing per-step and
  agent-read usage keeps working unchanged.

## Pack contents

```
contributing/
├── pack.toml                                    schema=2; no imports (self-contained)
├── README.md
├── skills/                                      agent-read + mayor-mode maps
│   ├── start-contribution/SKILL.md              entry router (GATE 0); the lifecycle map
│   ├── orchestrate-contribution/SKILL.md        mayor loop: dispatch the steps, gate each
│   ├── write-issue/SKILL.md                     file a maintainer-grade issue
│   ├── find-work/SKILL.md                       triage open issues into a work-queue
│   ├── plan-implementation/SKILL.md             adoption-review-aware implementation planning
│   ├── map-blast-radius/SKILL.md                map the impact surface of a change
│   ├── fine-tune/SKILL.md                       pre-push fine-tuning loop (ends with review)
│   └── review/SKILL.md                          mechanical gates + the B1–B36 audit
├── formulas/                                    gc-orchestrated mode (thin wrappers over the skills)
│   ├── mol-contributing-find-work.formula.toml            -> find-work
│   ├── mol-contributing-plan-implementation.formula.toml  -> plan-implementation
│   ├── mol-contributing-map-blast-radius.formula.toml     -> map-blast-radius
│   ├── mol-contributing-review.formula.toml               -> review
│   └── mol-contributing-fine-tune.formula.toml            -> fine-tune
├── doctor/                                      preflight checks (gc, gh, git present)
│   ├── check-gc.sh   + gc/doctor.toml
│   ├── check-gh.sh   + gh/doctor.toml
│   └── check-git.sh  + git/doctor.toml
└── tests/
    ├── test_contributing_skill_frontmatter.py   skills have name + description
    ├── test_contributing_pack_structure.py      self-contained; doctor scripts executable
    └── test_contributing_formulas.py            formulas parse; each references a real skill
```

## Tests

```sh
python3 -m pytest contributing/tests/
```

[pr-pipeline]: https://github.com/gastownhall/gascity-packs/tree/main/pr-pipeline
