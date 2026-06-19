---
name: contributing
description: The full external-contributor lifecycle for gastownhall/gascity — write a good issue, find priority work, open a PR, and self-review before pushing. Use when someone wants to contribute to Gas City and needs to know which step they're on and which command runs it. Routes each step to the right tool (this pack's write-issue skill for filing; the pr-pipeline pack's pr commands for triage, planning, review, and the pre-push gate).
---

# Contributing to Gas City

You are an external contributor to
[gastownhall/gascity](https://github.com/gastownhall/gascity). This skill is the
map of the whole journey — from "I noticed something" to "my PR is ready to
push" — and which command runs each step.

It stitches together two packs:

- **this pack (`contributing`)** owns step 1: writing a high-quality issue.
- **the `pr-pipeline` pack** owns steps 2-4: finding work, planning and building
  the PR, and the pre-push self-review gate. This pack imports it, so its
  `gc pr-pipeline pr ...` commands are available alongside the skills here.

Nothing here pushes a branch or opens a PR for you — those stay explicit human
actions. Each step produces an artifact (an issue, a plan, a report) you act on.

## The lifecycle

```
   ┌─ 1. write a good issue ────────────────┐   (this pack: write-issue)
   │                                         │
   │   ┌─ 2. find priority work ─────────┐   │   (pr-pipeline: mol-pr-triage)
   │   │                                 │   │
   ▼   ▼                                 │   │
   3. plan & build the PR ───────────────┘   │   (pr-pipeline: pr plan + pr blast-radius)
   │                                         │
   ▼                                         │
   4. self-review before pushing ◀───────────┘   (pr-pipeline: pr review + pr ship)
```

| Step | What you do | Command | Owned by |
|------|-------------|---------|----------|
| 1 | Write a high-quality issue | follow the [write-issue](../write-issue/SKILL.md) skill | this pack |
| 2 | Find a priority issue to work on | `gc sling <rig>/<agent> mol-pr-triage --formula` | pr-pipeline |
| 3a | Plan a PR from an issue | `gc pr-pipeline pr plan <issue> --rig <rig>` | pr-pipeline |
| 3b | Map the impact surface | `gc pr-pipeline pr blast-radius "<scope>" --rig <rig>` | pr-pipeline |
| 4a | Self-review the outgoing PR | `gc pr-pipeline pr review <pr-number> --rig <rig>` | pr-pipeline |
| 4b | Run the pre-push gate | `gc pr-pipeline pr ship --rig <rig>` | pr-pipeline |

## Two entry points

The lifecycle is one loop, but you join it at different places depending on what
you're starting from.

### A. PR a priority issue (someone else's issue, or a triage pick)

You want to help, but you don't have a specific bug in mind yet. Start at
**step 2**.

1. **Find work** — run triage to scan open issues and rank them into a
   contributor work-queue:

   ```bash
   gc sling <rig>/<agent> mol-pr-triage --formula
   ```

   `mol-pr-triage` has no wrapper command; it's dispatched as a formula and
   writes a ranked queue. Pick an issue that's unassigned and in scope for you.

2. **Plan the PR** for the issue you picked — go to **step 3**.

### B. PR your own issue (something you found)

You hit a bug or have a change in mind. Start at **step 1**.

1. **Write the issue** first, with the [write-issue](../write-issue/SKILL.md)
   skill. Filing it before you code gives a maintainer a chance to redirect the
   approach, flag a duplicate, or point at a design constraint — cheaper than
   finding that out on the PR.

2. **Plan the PR** on the issue you just filed — go to **step 3**.

## Step 3 — plan & build the PR

Both entry points converge here. You have an issue number.

1. **Plan it.** This front-loads the analysis a maintainer's review will check,
   before any code is written — competing-PR and architectural-refactor gates,
   blast radius, repo conventions, and a plan audited against recurring review
   findings:

   ```bash
   gc pr-pipeline pr plan <issue> --rig <rig>
   ```

   The plan lands in `.gc/pr-pipeline/plans/issue-<issue>.md`. No code is
   written. Read it before you start.

2. **Map blast radius** for any change that isn't trivially local — refactors,
   anything touching shared state, lifecycle, or dispatch:

   ```bash
   gc pr-pipeline pr blast-radius "<scope>" --rig <rig>
   ```

3. **Implement** against the plan. Keep the change scoped to what the issue
   asks; note anything adjacent as out-of-scope rather than folding it in.

> Shortcut: `mol-pr-from-issue` chains issue → plan → implement → ship-gate in
> one routed run. It halts at branch-ready by default (no push, no PR):
>
> ```bash
> gc sling <rig>/<agent> mol-pr-from-issue --formula --var issue_number=<N>
> ```

## Step 4 — self-review before pushing

Catch the structural and correctness defects a careful maintainer review would
flag, so your PR lands with few or no review comments.

1. **Score the change** against the 11-category scorecard (correctness, contract
   fidelity, blast radius, concurrency, error handling, security, resource
   lifecycle, release safety, test evidence, architectural consistency,
   debuggability):

   ```bash
   gc pr-pipeline pr review <pr-number> --rig <rig>
   ```

   It writes a scorecard to `.gc/pr-pipeline/reviews/pr-<pr-number>.md` and gives
   a verdict (`block` / `request_changes` / `approve`). Apply the fixes it
   surfaces.

2. **Run the pre-push gate** — simplify, iterate the self-review until clean, run
   the mechanical checks (build / vet / test / docs), and produce a readiness
   report:

   ```bash
   gc pr-pipeline pr ship --rig <rig>
   ```

   It **stops at the report.** Pushing the branch and opening the PR are your
   call — make them once the report is clean.

## Notes

- Replace `<rig>` with your rig name and `<agent>` with your city's coding worker.
  The pr-pipeline wrapper commands dispatch to a default coding-worker agent;
  pass `--agent <name>` if your city's worker is named differently.
- The pr-pipeline commands are read-only outside their own `.gc/pr-pipeline/`
  output paths, except `pr ship`, which may modify the diff during its simplify
  and review-iteration stages.
- For the deeper mechanics of each pr-pipeline formula, see the
  [pr-pipeline README](../../../pr-pipeline/README.md).
