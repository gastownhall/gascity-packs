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

Three steps — the first has two variants (do **1a or 1b** depending on what
you're starting from); both converge on step 2.

| Step | What you do | Skill |
|------|-------------|-------|
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

Step 1 has two mutually-exclusive variants — pick one, then both lead to step 2:

- **Implement/fix a priority issue** — step 1a (`find-work` to triage), then plan it (step 2).
- **Implement/fix your own issue** — step 1b (`write-issue`), then plan it (step 2).

The [`contributing`](skills/contributing/SKILL.md) skill is the operational map;
it explains both variants and links each step to its skill.

## Two ways to run it

The same lifecycle, the same standards, two delivery modes:

- **Skills (agent-read)** — your coding agent applies a step by *reading* the
  skill text. This is the default for a contributor working with a coding agent:
  no orchestration, no city required.
- **Formulas (gc-orchestrated)** — thin `mol-contributing-*` wrappers let a city
  *dispatch* a step to a polecat session as a gc formula. Each wrapper is
  orchestration only: it resolves the run's root bead, records state, writes the
  output artifact, and enforces blocking early-exits — then **delegates every
  standard to its sibling skill**. The skill stays the single source of truth; the
  formula never restates the audit, the gates, or the dimensions.

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

## Pack contents

```
contributing/
├── pack.toml                       schema=2; no imports (self-contained)
├── README.md
├── skills/                         agent-read mode
│   ├── contributing/SKILL.md       the lifecycle map (both step-1 variants)
│   ├── write-issue/SKILL.md        file a maintainer-grade issue
│   ├── find-work/SKILL.md          triage open issues into a work-queue
│   ├── plan-implementation/SKILL.md   adoption-review-aware implementation planning
│   ├── map-blast-radius/SKILL.md   map the impact surface of a change
│   ├── fine-tune/SKILL.md          pre-push fine-tuning loop (ends with review)
│   └── review/SKILL.md             mechanical gates + the B1–B36 audit
├── formulas/                       gc-orchestrated mode (thin wrappers over the skills)
│   ├── mol-contributing-find-work.formula.toml            -> find-work
│   ├── mol-contributing-plan-implementation.formula.toml  -> plan-implementation
│   ├── mol-contributing-map-blast-radius.formula.toml     -> map-blast-radius
│   ├── mol-contributing-review.formula.toml               -> review
│   └── mol-contributing-fine-tune.formula.toml            -> fine-tune
├── doctor/                         preflight checks (gc, gh, git present)
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
