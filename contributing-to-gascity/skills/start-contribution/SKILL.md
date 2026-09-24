---
name: start-contribution
description: Entry router for contributing to gastownhall/gascity — start here. Decides which step of the contributor lifecycle the user is on and dispatches the right skill, then walks the rest (plan the implementation, which maps blast radius as its Phase 2, and fine-tune the diff, which reviews it as its final gate). Use when someone wants to contribute to Gas City and you must route them to the correct step. Self-contained — every step is a skill in this pack with Gas City's actual standards baked in — no internal tooling, no sibling pack. For a city operator dispatching the lifecycle to transient workers, see orchestrate-contribution instead.
---

# Start a Contribution to Gas City

You are routing an external contributor to
[gastownhall/gascity](https://github.com/gastownhall/gascity). This skill is the
**lifecycle start**: it decides which step the contributor is on and which skill
runs it, then walks the rest of the journey to a push-ready diff.

This is a decision procedure for *you, the agent* — not a brochure for the
contributor. Follow the directives below in order.

Each step carries Gas City's **actual** standards (the adoption-review audit, the
blast-radius dimensions, the design-capture rule, the test tiers) baked into the
referenced skill, so you apply them by reading that skill. Nothing here pushes a
branch or opens a PR — those stay the contributor's explicit call. Each step
produces an artifact (an issue, a plan, a report) to act on.

## GATE 0 — route on entry (do this first)

**Ask the user:** *"Are you looking for a priority issue to work on, or do you
already have your own issue/bug in mind?"*

- **A — priority issue** → run [`find-work`](../find-work/SKILL.md) (step 1a), then
  go to **Step 2**.
- **B — own issue/bug** → run [`write-issue`](../write-issue/SKILL.md) (step 1b),
  then go to **Step 2**.

The two branches are mutually exclusive; both converge on Step 2. Do not skip the
question — the entry branch *is* the start of the lifecycle.

## The lifecycle at a glance

```
   GATE 0 — start here: priority issue, or your own?
        │
   A ───┼── 1a. find priority work   (find-work)      someone else's issue / triage pick
        │
   B ───┼── 1b. write a good issue    (write-issue)    something you found
        ▼
   2. plan the implementation   (plan-implementation)
        ├── Phase 2: map blast radius   (map-blast-radius — also standalone)
        ▼
   3. fine-tune the diff         (fine-tune)
        └── final gate: review the diff   (review — also standalone)
```

| Step | What you do | Skill |
|------|-------------|-------|
| 0 | Route the contributor on entry (priority issue → 1a, own issue → 1b) | **this skill** |
| 1a | Find a priority issue to work on (someone else's, or a triage pick) | [find-work](../find-work/SKILL.md) |
| 1b | Write a high-quality issue (something you found) | [write-issue](../write-issue/SKILL.md) |
| 2 | Plan the implementation (incl. blast-radius mapping as Phase 2) | [plan-implementation](../plan-implementation/SKILL.md) |
| 3 | Fine-tune the diff (incl. the review as its final gate) | [fine-tune](../fine-tune/SKILL.md) |

Two sub-skills are **a phase of a parent AND a standalone utility** — not pipeline
steps of their own:

- [map-blast-radius](../map-blast-radius/SKILL.md) — Phase 2 of
  `plan-implementation`; run standalone for ad-hoc impact mapping (scoping a
  refactor, mapping a change for someone else).
- [review](../review/SKILL.md) — the final gate of `fine-tune`; run standalone to
  review any diff/branch against the Gas City standard (incl. before a PR exists,
  or as a maintainer on an incoming contribution).

## Step 1 — execute the GATE 0 branch you took

### 1a — implement/fix a priority issue (branch A)

Run [find-work](../find-work/SKILL.md): scan open issues, rank them into a
contributor work-queue, and filter out anything already covered by an open PR or
blocked on a maintainer decision. Pick an unassigned, in-scope issue that passes
the decision gates, then go to **Step 2**.

### 1b — implement/fix your own issue (branch B)

Run [write-issue](../write-issue/SKILL.md): file the issue *before* writing code.
Filing first gives a maintainer the chance to redirect the approach, flag a
duplicate, or point at a design constraint — far cheaper than finding that out on
the PR. Then go to **Step 2**.

## Step 2 — plan the implementation

Both branches converge here with an issue number. Run
[plan-implementation](../plan-implementation/SKILL.md). It front-loads the analysis
the maintainer's review will check — the competing-PR and architectural-refactor
gates, blast radius, convention alignment, the design-capture decision, and a plan
audited against the recurring review findings. **No code is written until the plan
is confirmed.**

Its **Phase 2** maps the blast radius with the
[map-blast-radius](../map-blast-radius/SKILL.md) skill — callers, execution
contexts, config-field sync chains, domain boundaries, and concurrency. That same
skill runs standalone any time you need an ad-hoc impact map.

## Step 3 — implement, then fine-tune the diff

Implement against the plan, keeping the change scoped to what the issue asks (note
anything adjacent as out-of-scope). Then run [fine-tune](../fine-tune/SKILL.md):
the design-capture gate, a simplify pass, a self-review loop against the recurring
adoption-review findings, optional performance measurement, and — as its final
gate — the [review](../review/SKILL.md) skill (mechanical gates with
baseline-vs-regression classification, plus the full B1–B36 codebase audit). It
combines them into one readiness report.

**It stops at the report. Pushing the branch and opening the PR are the
contributor's call.**

## Notes

- The whole pack is self-contained — no `[imports.*]`, no internal agents, no
  maintainer-only tooling. If you can read these skills and run `git`/`gh`, you
  have everything.
- This is the gas-city-specific lifecycle. A city wanting generic contributor
  discipline without Gas City's particular standards can use the `pr-pipeline`
  pack instead; this pack bakes those standards in.
- **Two ways to drive this lifecycle.** This skill is the *contributor* entry: you
  read each step's skill and implement by hand. A *city operator* who wants to
  dispatch the steps to transient worker sessions and gate each one at the mayor
  uses [orchestrate-contribution](../orchestrate-contribution/SKILL.md) instead —
  same lifecycle, same standards, but run as a mayor-orchestrated loop over the
  `mol-contributing-*` formulas. That skill reuses this one's GATE 0 branch rather
  than restating it.
