---
name: mayor-ide-affordances
description: Make fleet work legible and actionable inside the GasCity Cockpit (the VS Code extension an operator drives the city from). When coordinating or dispatching on a Cockpit-ready city, prefer durable beads with complete handoff metadata (work_dir, branch, pr_url) so the operator can jump bead -> worktree -> diff; keep bead titles/types/priorities meaningful for the Beads explorer's filters; leave tool-approvals and prompt-for-input pending for the operator to answer in-editor instead of pre-empting them; and keep what you say structured for the chat panel. Use whenever you (the Mayor, or any agent dispatching or coordinating) act on a city an operator is watching through the Cockpit.
---

# Mayor IDE Affordances

## Overview

When a city is **Cockpit-ready** (see the `cockpit-readiness` skill), the operator is no
longer only at a terminal — they have an adaptive surface *inside VS Code*: live
status/agents/event panes, a Beads explorer across cities, an interactive chat with you
(the Mayor) and any agent, native tool-approval / prompt-for-input, and code-in-context
(jump from a bead to the polecat worktree and its diff).

An **IDE affordance** is a small, deliberate choice in how you record and route work so
that surface *lights up* — so the operator can see and act on what's happening without
attaching to a tmux pane or grepping for a worktree. None of this is new machinery: the
Cockpit reads the same beads, metadata, sessions, and `/v0` endpoints you already use.
This skill is the discipline of leaving the right traces.

This is the read/coordinate counterpart to the existing handoff contract: polecats already
stamp `work_dir` / `branch` / `target` on work beads. Your job is to **rely on and
preserve** those affordances when you dispatch, summarize, and converse — not to invent
new ones.

## When to Use

- You are **dispatching work** (sling / routing a bead) on a Cockpit-ready city — set
  routing and metadata so the dispatch is visible and the result is reviewable in-editor.
- You are **coordinating or reporting** and an operator is watching through the Cockpit —
  prefer durable, well-shaped beads over ephemeral chatter for anything they should see.
- An agent you manage **pauses for a tool-approval or a question** — the operator can now
  answer it natively in VS Code; let them, rather than auto-approving or guessing.
- You are **conversing in the Mayor chat panel** — structure replies so the transcript
  renders well.

**When NOT to use:**

- The city is **not** Cockpit-ready (no extension/discovery) — then optimize for the
  terminal/dashboard as usual; these affordances cost nothing but buy nothing.
- For routine agent-to-agent protocol signals (MERGE_READY, drains, nudges) — keep those
  ephemeral; do not inflate them into beads just to surface them (see the litmus test).
- To edit code or worktrees — code navigation in the Cockpit is **read-only** (v1); never
  treat the operator's in-editor view as an invitation to mutate an agent sandbox.

## The affordances

### 1. Bead → worktree → diff: keep handoff metadata complete

The Cockpit lets the operator jump from a bead to the polecat worktree where it is being
worked and see the diff (PRD stories 27–28). That only works if the bead carries the
handoff metadata the contract already defines:

| Field | Why the Cockpit needs it |
|-------|--------------------------|
| `work_dir` | open the worktree for the work in flight |
| `branch` | show the branch / diff for the bead |
| `pr_url` | deep-link to the PR once the refinery records it |
| `target` | show what it merges into |

When you dispatch or reassign, **preserve** these — don't strip or overwrite them — and
when work stalls, prefer fixing the bead's metadata over narrating state in chat.

### 2. Beads explorer: keep titles, types, and priorities meaningful

The operator filters/groups beads by status, rig, assignee, type, and priority (stories
7–9). A wall of `task` / `priority 2` / terse titles defeats that. When you create or
shape work: give it a **specific title**, the **right type** (epic / task / bug / convoy),
an honest **priority**, and a real **description**. Structure (parent/child, deps) is what
the dependency-graph view renders (story 11) — set it deliberately.

### 3. Dispatch visibly: route through the normal sling/`gc.routed_to` path

Dispatching a bead to a pool from the Cockpit maps to the existing sling / `gc.routed_to`
semantics (story 14). When you route work, use that same mechanism so the Cockpit's view
of "what's dispatched where" stays accurate — don't hand-assign in ways that bypass it.

### 4. Approvals & prompts: leave them for the operator, don't pre-empt

When an agent pauses for a `tool-approval` or `prompt-for-input`, the Cockpit aggregates
it across all sessions and lets the operator answer **inline** (stories 23–26). So:

- Don't blanket-approve to "keep things moving" when the operator is actively watching —
  a pending approval is a feature now, not a stall.
- Set an agent's **permission mode** intentionally; the operator can also adjust it in
  the Cockpit, so leave it in a state that matches how much oversight they want.
- Surface a genuine blocker as a clear pending question rather than burying it.

### 5. Chat & transcripts: structure what you say

The Mayor chat is backed by the structured transcript model (roles + turns). For replies
the operator reads in the chat panel: lead with the answer, use short structure (lists,
fenced code/commands), and keep tool-call context legible. Treat each turn as something
that will be rendered, not just logged.

## Worked Example

The operator, in the Cockpit, asks you to "get the auth-refactor moving and let me review
it."

1. **Shape the bead.** Title it `Refactor session auth to token boundary`, type `task`,
   priority set honestly, with a real description and the parent epic linked — so it reads
   well in the Beads explorer and graph.
2. **Dispatch visibly.** Sling it to the polecat pool via the normal routing
   (`gc.routed_to`), so the Cockpit shows it dispatched.
3. **Preserve handoff metadata.** When the polecat stamps `work_dir` / `branch`, leave
   them; the operator clicks the bead → opens the worktree → sees the diff. You add
   nothing; you just don't get in the way.
4. **Let the operator gate it.** When the agent hits a risky tool-approval, leave it
   pending; the operator approves it inline in VS Code. You report status in chat as a
   short structured summary, not a wall of prose.

## Why This Matters

- **The operator's context stops being scattered.** Bead, code, diff, conversation, and
  approvals live in one editor surface — but only if the traces you leave connect them.
- **You reuse mechanisms, add no risk.** Every affordance rides existing beads/metadata/
  routing/approval paths. There is no new Mayor subsystem here — just disciplined use.
- **Oversight gets cheaper.** Meaningful bead shape + visible dispatch + honest pending
  approvals turn the Cockpit from a pretty dashboard into a control surface.

## Verification Gate

When acting on a Cockpit-ready city:

- [ ] Work beads you dispatch/own carry complete handoff metadata (`work_dir`, `branch`,
      and `pr_url`/`target` once known) — the bead→worktree→diff path resolves.
- [ ] New/shaped beads have a specific title, correct type, honest priority, real
      description, and correct parent/deps — they filter and graph cleanly.
- [ ] Dispatch went through the normal sling/`gc.routed_to` path (visible in the Cockpit),
      not an out-of-band assignment.
- [ ] You did not auto-approve tool-calls the operator would want to gate, and permission
      mode reflects the intended level of oversight.
- [ ] Chat replies are structured for rendering (answer-first, short, fenced commands).

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack contributes a
skill by placing `skills/<name>/SKILL.md` under the pack root, with YAML frontmatter
carrying at minimum `name` and `description`. This file lives at
`cockpit/skills/mayor-ide-affordances/SKILL.md`, so it is picked up automatically —
`pack.toml` does not enumerate skills. Once the `cockpit` pack is imported into a city
(vendored under `packs/cockpit` and registered via a direct `source = "packs/cockpit"`
import), the skill surfaces in `gc skill list` binding-qualified as
`cockpit.mayor-ide-affordances`, and the materializer projects it into the per-agent
skills sink at `gc start`. To make the Mayor lead with these affordances by default,
optionally add `mayor-ide-affordances` to the Mayor's prompt fragments; otherwise it is
available as an on-demand skill. Verify with `gc skill list` (and `gc lint .`).
