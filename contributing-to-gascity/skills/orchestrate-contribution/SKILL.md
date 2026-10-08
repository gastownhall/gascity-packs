---
name: orchestrate-contribution
description: Mayor-mode orchestration of the gastownhall/gascity contributor lifecycle — the whole-process umbrella. Use when a city operator/mayor wants to DISPATCH the contributor steps to transient worker sessions (the mol-contributing-* formulas) rather than apply them by hand, walking GATE 0 → find-work/write-issue → plan-implementation → fine-tune and pausing at each human gate. The mayor owns only dispatch + gate; every standard stays in the sibling skills, every step's mechanics stay in the existing formulas. Never auto-pushes, never opens a PR, never auto-implements. For a contributor applying the steps by hand, use start-contribution instead.
---

# Orchestrate a Contribution (Mayor Mode)

You are the **mayor** — the attended orchestrator of a Gas City. This skill drives
the *whole* external-contributor lifecycle for
[gastownhall/gascity](https://github.com/gastownhall/gascity) by **dispatching**
each step to a transient worker session as a `mol-contributing-*` formula, then
**pausing at each human gate** to talk to the human before dispatching the next
step.

You own **only two things: dispatch and gate.** Every standard lives in the
sibling skills; every step's mechanics live in the existing formulas. You do not
restate the triage tiers, the planning gates, the audit, or the readiness
criteria — the formulas already apply them. You sequence the steps and you talk to
the human at the boundaries between them.

> **Why this is a separate skill from
> [`start-contribution`](../start-contribution/SKILL.md).** Same lifecycle, two
> audiences. `start-contribution` is the *contributor* entry: a coding agent reads
> each step's skill and implements by hand, no city required. This skill is the
> *mayor* loop: it slings formulas to transient workers and gates each one. The
> two registers — "apply by hand" vs. "dispatch + gate" — and their trigger
> contexts are different enough that one shared `description` would mis-route both.
> This skill **reuses `start-contribution`'s GATE 0 branch logic rather than
> restating it** — that skill stays the single source of truth for the map.

## Why the gates live here, not in a formula

A formula runs in an **unattended transient worker** — nobody is at the keyboard
to answer "which issue?" or "is this plan OK?". A formula gate can only
*auto-proceed* or *halt-and-stop*; it cannot interactively pause and resume the
same run. The contributor lifecycle's gates are interactive human decisions, and
one of its steps (implementation) is done by a human by hand. So the gates belong
at the **mayor** — the agent that is actually in a conversation with the human.
Each `mol-contributing-*` formula already ends by writing its artifact and printing
`Next: dispatch mol-contributing-<X>`. **That handoff line is the gate** — and
crossing it is your job.

## The loop

```
START
  └─ GATE 0  (entry branch — reuse start-contribution's branch logic)
       Ask the human: "Looking for a priority issue, or do you have your own in mind?"
        A) priority  → gc sling … mol-contributing-find-work
                       → work-queue report
                       → GATE 1: human picks an issue
        B) own issue → apply the write-issue SKILL directly (no formula; issue
                       authoring sits upstream of the PR flow)
                                   │
                                   ▼   (both branches yield an issue number N)
  gc sling … mol-contributing-plan-implementation --var issue=N
       → plan artifact
       → GATE 2: human confirms the plan BEFORE any code is written
                                   │
  ── human implements by hand ──    (NOT dispatched — implementation stays by hand)
                                   │
  gc sling … mol-contributing-fine-tune
       → readiness report (review is its final phase)
       → GATE 3: human reviews the readiness report
                                   │
  STOP — push the branch / open the PR is the human's call (unchanged)
```

## Gate mechanics (every GATE, same shape)

When a dispatched step finishes, the worker has recorded its outcome in the
**molecule root-bead notes** and exited. At each gate:

1. **Read the outcome.** Pull the root-bead notes the formula wrote — `status:
   complete`, the artifact path, and the one recommended next action:

   ```bash
   NOTES=$(gc bd show "$ROOT_ID" --json | jq -r '.[0].notes // ""')
   # find-work → report_path:, recommended:, tier counts
   # plan-implementation → plan_path:, plan_status: (or status: blocked + gate:)
   # fine-tune → report_path:, readiness: (ready | blocked), blockers:
   ```

2. **Surface it to the human.** Show the artifact path and the single recommended
   next action — not the whole artifact. If the formula recorded `status: blocked`
   (a competing PR, an architectural refactor, a wrong repo), surface the
   `gate:`/`detail:` and stop; do not dispatch onward.

3. **Wait for the human decision.** *This is the gate.* It lives here, at the
   mayor, because you are the one talking to the human.

4. **Act on the decision.** On **go**, dispatch the next step's formula. On
   **stop**, halt. On **redo**, re-dispatch the same step (optionally with
   different vars).

### Dispatch form

```bash
# Branch A, step 1a — triage into a work-queue
gc sling <rig>/<agent> mol-contributing-find-work --formula

# Step 2 — plan the chosen issue (GATE 1 produced issue number N)
gc sling <rig>/<agent> mol-contributing-plan-implementation --formula --var issue=N

# Step 3 — fine-tune the implemented branch
gc sling <rig>/<agent> mol-contributing-fine-tune --formula
```

Branch B (own issue) has **no formula** — issue authoring sits upstream of the PR
flow, so apply the [write-issue](../write-issue/SKILL.md) skill directly, then
proceed to Step 2 with the new issue number.

## Surviving long waits

Human gates can be open for hours or days. The bead notes carry all the run state,
so you do not hold the loop in memory: use `gc handoff` across a long wait, and a
fresh mayor incarnation resumes the loop with full context by re-reading the
root-bead notes. The gate you were waiting on is wherever `status:` and the last
artifact path say it is.

## Hard guarantees (do not cross these)

- **Never auto-push and never `gh pr create`.** The loop STOPS after GATE 3. Push
  and PR-open are the human's call — same as every skill and formula in this pack.
- **Never auto-implement.** Implementation between GATE 2 and fine-tune is done by
  a human by hand; you do not dispatch it.
- **Never collapse a gate.** Do not dispatch the next step until the human has
  decided at the current gate. GATE 2 (plan confirmation, before any code) and
  GATE 3 (readiness review) are load-bearing.

## Notes

- No `mol-contributing-*` formula needs changing — this loop only *consumes* the
  root-bead notes contract they already emit (`status:`, `report_path:`,
  `recommended:`, `plan_path:`, `readiness:`, …).
- The standards stay in the skills; the step mechanics stay in the formulas; this
  skill adds only the mayor's dispatch-and-gate sequencing over them.
