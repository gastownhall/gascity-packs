---
name: find-work
description: Find a good gastownhall/gascity issue to work on as an external contributor. Scans open issues, classifies them into actionability tiers (grab now / good candidate / investigate / skip), and — critically — detects competing PRs and maintainer-decision gates so you don't pick an issue that's already in flight or that needs a maintainer's product/design call before any PR is realistic. Self-contained — plain gh queries you run yourself, no internal tooling. Use when you want to contribute but don't have a specific bug in mind yet.
---

# Find Work

You want to contribute to
[gastownhall/gascity](https://github.com/gastownhall/gascity) but don't have a
specific bug in mind. This skill scans the open issues and ranks them into a
contributor work-queue — and, most importantly, filters out the issues that look
grabbable but aren't: ones already covered by an open PR, or ones that need a
maintainer decision before any PR makes sense.

Run the `gh` queries yourself (or have your coding agent run them). The output is
a ranked list and a single recommended pick.

## 1. Pull the landscape

```bash
# Open issues, richest fields first
gh issue list --repo gastownhall/gascity --state open --limit 100 \
  --json number,title,labels,assignees,milestone,createdAt,updatedAt,comments

# Open PRs (to cross-reference against issues)
gh pr list --repo gastownhall/gascity --state open --limit 100 \
  --json number,title,body,author,createdAt
```

Bias toward unassigned bugs at `priority/p0`–`p1` on the current milestone — those
are the highest-value, lowest-ambiguity picks for an outside contributor.

## 2. Competing-work detection (CRITICAL — get this right)

For **every** candidate you'd consider grabbing, check for a competing PR using
**all three** methods. A single search misses PRs that reference the issue by
number in the body, by title keywords, or only via GitHub's cross-reference
linkage.

```bash
# a) by issue number
gh pr list --repo gastownhall/gascity --state open --search "<issue-number>"
# b) by issue title keywords
gh pr list --repo gastownhall/gascity --state open --search "<key phrases from the title>"
# c) by the issue's cross-reference timeline
gh api repos/gastownhall/gascity/issues/<number>/timeline --paginate \
  --jq '.[] | select(.source.issue.pull_request) | .source.issue.html_url'
```

If **any** method finds an open PR targeting the issue → **Tier 4 (skip)**.
Picking a contested issue wastes your time and creates merge conflicts.

## 3. Maintainer-decision gates (run on every Tier 1/2 candidate)

Competing-work checks catch duplicate PRs but miss issues where the fix needs a
maintainer **product or design decision** before any PR is realistic. Apply these
four blocking gates — if one fires, demote to Tier 3 (investigate, don't grab):

- **DD — Design-doc conflict.** Grep `engdocs/design/*.md` for the issue's symbols;
  if an `Accepted`/`Implementing` doc contradicts the issue's proposed direction,
  the fix needs a maintainer's call. Demote.
- **AU — Author uncertainty.** The issue body ends with "?" or contains phrasing
  like "is this a bug or", "intended behavior", "Or at least", "Is X supposed
  to", or proposes 2+ alternatives without committing. Demote.
- **MA — Maintainer-ambivalent comment.** A maintainer comment says "good point"
  / "we should" but gives no directive and links no PR. The direction isn't
  settled. Demote.
- **PD — Product decision disguised as a bug.** The "Expected/Actual" sections
  argue a product opinion ("should be lighter", "feels counter-intuitive") rather
  than pointing at a concrete defect. Demote.

Emit a `Gates: [DD AU MA PD]` line on every Tier 1/2 entry, marking which fired.
**The recommended pick must pass all four.**

Also flag (don't demote): comment-thread scope drift — retracted repros, adjacent
follow-ups, or 3+ clarifying exchanges with no maintainer commitment.

## 4. Classify into tiers

| Tier | Meaning | Criteria |
|---|---|---|
| **1 — GRAB NOW** | Clear, unblocked, high-value | Unassigned, clear bug, current milestone, p0/p1, no competing PR, all decision gates pass |
| **2 — GOOD CANDIDATE** | Solid but needs some investigation | p1/p2 bug, fixable, no competing PR, gates pass |
| **3 — INVESTIGATE FIRST** | Unclear scope or needs a maintainer call | A decision gate fired, or scope is ambiguous |
| **4 — SKIP** | Don't grab | Assigned, covered by an open PR, post-release, or a pure design discussion |

## 5. Output

```
Gas City work-queue — <date>

Open issues: <count> (by milestone / priority)

Tier 1 — GRAB NOW
  #<n> <title>  [p<x>, milestone]  Gates: [....]  — <one-line why it's a clean pick>
Tier 2 — GOOD CANDIDATE
  #<n> <title>  [p<x>]  Gates: [....]  — <what to investigate first>
Tier 3 — INVESTIGATE FIRST
  #<n> <title>  — gate fired: <DD/AU/MA/PD + why>
Tier 4 — SKIP
  #<n> <title>  — <covered by PR #m / assigned / design discussion>

Recommended next pick: #<n> — <rationale; confirm it passes all four gates>
```

## 6. Hand off to planning

Once you've picked an issue, plan the PR with
[`plan-implementation`](../plan-implementation/SKILL.md) — it runs the competing-PR and
architectural-refactor gates again at code-time (the landscape may have changed),
maps blast radius, and aligns the plan to repo conventions before you write code.

## When to re-run

- After main gets new merges (the landscape shifts).
- After you ship a PR and want the next pick.
- Periodically, to catch newly filed issues.
