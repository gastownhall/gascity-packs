---
name: contributing
description: The full external-contributor lifecycle for gastownhall/gascity — write a good issue, find priority work, plan the implementation (which maps blast radius as its Phase 2), and fine-tune the diff (which reviews it as its final gate). Use when someone wants to contribute to Gas City and needs to know which step they're on and which skill runs it. Self-contained — every step is a skill in this pack with Gas City's actual standards baked in — no internal tooling, no sibling pack.
---

# Contributing to Gas City

You are an external contributor to
[gastownhall/gascity](https://github.com/gastownhall/gascity). This skill is the
map of the whole journey — from "I noticed something" to "my implementation/fix is
ready to push" — and which skill runs each step.

Everything lives in this one pack. Each step carries Gas City's **actual**
standards (the adoption-review audit, the blast-radius dimensions, the
design-capture rule, the test tiers) baked into the skill text, so your coding
agent applies them by reading. There's nothing to install beyond `git`, `gh`, and
a local checkout.

Nothing here pushes a branch or opens a PR for you — those stay your explicit
call. Each step produces an artifact (an issue, a plan, a report) you act on.

## The lifecycle

Three steps — but the first has two variants: you do **1a or 1b** depending on
what you're starting from, and both converge on step 2. The two later steps each
carry a sub-skill that is *both* a phase of the step and a standalone utility —
not extra steps in the line.

```
   1a. find priority work ──┐   (find-work)     someone else's issue / triage pick
        ── or ──            │
   1b. write a good issue ──┤   (write-issue)   something you found
                            ▼
   2. plan the implementation   (plan-implementation)
        └ Phase 2: map blast radius   (map-blast-radius — also standalone)
                            │
                            ▼
   3. fine-tune the diff         (fine-tune)
        └ final gate: review the diff   (review — also standalone)
```

| Step | What you do | Skill |
|------|-------------|-------|
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

## Step 1 — start where you are (1a or 1b)

The lifecycle is one loop; you join it at 1a or 1b depending on what you're
starting from. They are mutually exclusive — pick one, then both lead to step 2.

### 1a — implement/fix a priority issue (someone else's issue, or a triage pick)

You want to help but don't have a specific bug in mind. Run
[find-work](../find-work/SKILL.md) to scan open issues, rank them into a
contributor work-queue, and filter out anything already covered by an open PR or
blocked on a maintainer decision. Pick an unassigned, in-scope issue that passes
the decision gates, then go to **step 2**.

### 1b — implement/fix your own issue (something you found)

You hit a bug or have a change in mind. Write the issue first with
[write-issue](../write-issue/SKILL.md). Filing it before you code gives a
maintainer a chance to redirect the approach, flag a duplicate, or point at a
design constraint — far cheaper than finding that out on the PR. Then go to
**step 2**.

## Step 2 — plan the implementation

Both variants converge here; you have an issue number. Run
[plan-implementation](../plan-implementation/SKILL.md). It front-loads the analysis
the maintainer's review will check — the competing-PR and architectural-refactor
gates, blast radius, convention alignment, the design-capture decision, and a plan
audited against the recurring review findings. **No code is written until the plan
is confirmed.**

Its **Phase 2** maps the blast radius with the
[map-blast-radius](../map-blast-radius/SKILL.md) skill — callers, execution
contexts, config-field sync chains, domain boundaries, and concurrency. That same
skill runs standalone too: reach for it any time you need an ad-hoc impact map
(scoping a refactor, anything touching shared state, lifecycle, config, or
dispatch), even outside this lifecycle.

## Step 3 — implement, then fine-tune the diff

Implement against the plan, keeping the change scoped to what the issue asks (note
anything adjacent as out-of-scope). Then run [fine-tune](../fine-tune/SKILL.md):
the design-capture gate, a simplify pass, a self-review loop against the recurring
adoption-review findings, optional performance measurement, and — as its final
gate — the review skill. It combines them into one readiness report. **It stops at
the report. Pushing the branch and opening the PR are your call.**

Fine-tune's final gate is the [review](../review/SKILL.md) skill: the mechanical
gates (`make build` / `make check` / `make check-docs`) with baseline-vs-regression
classification, plus the full B1–B36 codebase audit. That skill runs standalone
too — review any diff/branch against the Gas City standard before a PR exists, or
as a maintainer on an incoming contribution.

## Notes

- The whole pack is self-contained — no `[imports.*]`, no internal agents, no
  maintainer-only tooling. If you can read these skills and run `git`/`gh`, you
  have everything.
- This is the gas-city-specific lifecycle. A city wanting generic contributor
  discipline without Gas City's particular standards can use the `pr-pipeline`
  pack instead; this pack bakes those standards in.
