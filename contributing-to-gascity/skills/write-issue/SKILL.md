---
name: write-issue
description: Write a high-quality issue for gastownhall/gascity as an external contributor. Enforces the investigation a maintainer would otherwise have to redo — confirm the bug actually exists on the current main (not just your branch or version), search for duplicates first, map blast radius, and produce a body with file:line root-cause refs and at least two fix candidates. Prevents the common "filed from memory, never verified against main" failure mode that gets issues bounced back.
---

# Write an Issue

You are an external contributor filing an issue to
[gastownhall/gascity](https://github.com/gastownhall/gascity). A good issue does
the investigation up front so a maintainer can act on it without redoing your
work. A vague issue — wrong file paths, missed duplicate, no root cause — costs
the maintainer the whole investigation before they can even triage it, so it
sits.

This skill makes you do that investigation in the right order.

## When to use

- You hit a bug, footgun, or surprising behavior while using `gc` and want it
  fixed upstream.
- You have a feature request or architectural concern worth surfacing — the
  investigation discipline below applies to non-bug issues too.

**Do NOT skip this skill and call `gh issue create` directly.** Issues filed
from raw notes or memory routinely cite paths from an old version or a local
branch, miss an existing duplicate, and lack the `file:line` root-cause refs a
maintainer needs to act. A misfiled issue is worse than no issue: someone has to
redo the investigation before they can respond.

## Workflow

Run these **in order**. Don't skip ahead.

### 1. Triage the observation

Decide three things:

- **Upstream-relevant?** Does this affect code in `gastownhall/gascity`, or is
  it specific to your own deployment / config? If it's local-only, stop — don't
  file it upstream.
- **Scope:** bug / feature / docs?
- **Rough priority:** P1 (breaks many users / data loss / unrecoverable) / P2
  (significant friction, workaround exists) / P3 (polish, nice-to-have).
  Priority is about how many users hit it and how recoverable it is — not how
  loud it was for you. Most ergonomics issues are P3.

### 2. Search for duplicates (REQUIRED — do not skip)

Before any investigation:

```bash
# 2-3 searches with different keyword combinations
gh issue list --repo gastownhall/gascity --state all --search "<core-symptom-keywords>" --limit 20
gh issue list --repo gastownhall/gascity --state all --search "<file-or-component-name>" --limit 20
gh pr list   --repo gastownhall/gascity --state all --search "<core-symptom-keywords>" --limit 20
```

If you find a match:

- **Open issue, no resolution:** add your repro / extra context as a comment.
  Done — don't open a second issue.
- **Open issue, already in flight (assignee or recent activity):** same — comment
  and link, done.
- **Closed-fixed:** check whether the fix is in the version of `gc` you observed
  the bug on. If the fix shipped and you still hit it, that's a *regression* —
  file a NEW issue and reference the original.
- **Closed-wontfix / not-planned:** read the discussion first. There may be a
  deliberate decision you're missing. Don't silently refile.

### 3. Verify the bug exists on current main (REQUIRED)

The most common failure mode: a bug seen on an old version or a feature branch
is reported as if it's on `main`, but `main` already fixed it (or never had the
buggy code). Always verify against an up-to-date checkout of the
`gastownhall/gascity` main you're targeting.

> **Which remote?** If you cloned `gastownhall/gascity` directly, its main is
> `origin/main`. If you forked first and cloned your fork, your `origin` is the
> fork — add the upstream once (`git remote add upstream
> https://github.com/gastownhall/gascity && git fetch upstream`) and use
> `upstream/main` everywhere `origin/main` appears below.

```bash
# from your local clone (use upstream/main instead if origin is your fork)
git fetch origin && git log -1 origin/main --oneline   # confirm the tree is current
git checkout origin/main

# locate the symptom in code
grep -rn "<error-string-or-symbol>" --include="*.go" --include="*.py" --include="*.toml"

# read the relevant function(s) and confirm the buggy path is on main
sed -n '<line-range>p' <file>

# look for recent fixes that might already be in flight
git log --oneline -20 -- <affected-files>
git log --oneline -S "<key-symbol-or-comment>" -20
```

| Finding | Action |
|---|---|
| Buggy code path present on main | Continue to step 4 |
| Buggy code path absent on main (already refactored) | Find the commit that fixed it (`git log`). Don't file — the fix is already in. If it hasn't been released yet, that's worth noting on the relevant PR instead |
| Buggy code path present, but a recent commit/PR already addresses it | Reference that PR in your issue, or comment on it — don't duplicate |

### 4. Check architectural alignment (REQUIRED — do not skip)

The area you're touching may already be governed by an accepted design doc in
`engdocs/design/`. If it is, your fix candidates need to align with the design's
prescribed behavior, not work around it. Filing candidates that contradict an
accepted design wastes a maintainer's review and risks a "this conflicts with §X
of doc Y" reply.

```bash
# from your origin/main checkout

# 1. list accepted / implementing design docs
grep -lE "^\| Status \|.*\b(Accepted|Implementing|Implemented)\b" engdocs/design/*.md

# 2. for each candidate, grep for your symptom's keywords
grep -nE '<symptom-keyword>' engdocs/design/<candidate>.md

# 3. if a doc covers the area, read its relevant section in full —
#    especially any "Rules:" or invariant lists. The design's contract is
#    what a maintainer will hold your fix candidates against.

# 4. check whether an open PR is already continuing the refactor in this area
gh pr list --repo gastownhall/gascity --state open --search "<area-keyword>" --limit 20
```

| Finding | Action |
|---|---|
| No design doc covers the area | Continue to step 5 |
| Design doc covers the area, describes a DIFFERENT paradigm than your fix implies | Don't draft fix candidates from scratch. Read the section. Either revise your candidates to align with the design, or note in the body that the symptom contradicts the design's invariant `<X>` (with file/line ref) and ask which way to fix |
| Design doc covers the area, your fix lands in the SAME paradigm | Cite the doc section in your "Root cause" — frame the bug as "violates §X of doc Y". Signals you did the homework |
| Design doc covers the area and the relevant phase is queued | Your candidates may be superseded. Propose a narrow point-fix the upcoming work can absorb, or open a comment on the design discussion instead of a fresh issue |

### 5. Reduce to a minimum reproduction

Distill the observation to the smallest reproduction someone else can run:

- The exact `gc` subcommand or API call that triggers it
- The city/rig state required (running, supervisor mode, …)
- Expected vs. actual behavior
- If timing-sensitive: the race window

If you can't write a clean repro, that's a signal you don't understand the bug
well enough yet. Investigate more, or file with an explicit "repro is
best-effort" caveat — and tag it P3, because triage will have to figure it out.

### 6. Map blast radius (for non-trivial bugs)

For anything touching reconciler, controller, lifecycle, dispatch, or any
subsystem with cross-cutting effects, do a blast-radius pass:

- Who calls the affected function? Are any on hot paths (tick loops, reconciler
  loops, hot HTTP routes)?
- Does it interact with config reload? Goroutine lifecycle? Shared state?
- What test layer would catch it (unit, acceptance, integration)? Does any
  existing test cover the path?

This feeds the "Root cause" and "Fix candidates" sections.

### 7. Draft fix candidates (≥ 2)

Force yourself to name **at least two** fix candidates before writing the body. A
single-candidate issue forecloses the discussion. Two candidates expose the
trade-offs (correctness vs. backwards-compat, complexity vs. blast radius,
point-fix vs. structural).

Each candidate gets:

- A one-line description
- A rough scope (LOC, files touched)
- The trade-off it represents

Mark which one you'd recommend and why — but leave the decision to the
maintainer.

### 8. Write the body using this template

```markdown
## Summary

<1-2 sentences. The maintainer should know whether to read further.>

## Symptom

<What you observe. Literal log lines, error strings, UI behavior. Not root
cause yet.>

## Reproduction

<Concrete, copy-pasteable steps. If timing-sensitive, note the race window.>

Result: `<expected>` → got: `<actual>`.

## Root cause

<Tie the symptom to specific code with `path/to/file.go:LINE` references.>

The buggy invariant is `<X>` (`<path>:<line>`). It's violated when `<Y>`
because `<Z>` (`<path>:<line>`).

## Fix candidates

**A. <name>** — <one-line description>.
- Scope: <LOC / files>
- Trade-off: <what gets better / what gets worse>

**B. <name>** — <one-line description>.
- Scope: <LOC / files>
- Trade-off: <what gets better / what gets worse>

**Recommendation:** <A or B> because <reason>. Maintainer's call.

## Adjacent / out of scope

<Anything you noticed that's related but shouldn't be part of this fix. Helps
the maintainer scope the work.>
```

### 9. File with labels

```bash
gh issue create --repo gastownhall/gascity \
  --title "<kind: short imperative title>" \
  --body-file /tmp/issue-body.md \
  --label "kind/<bug|feature|docs>,priority/p<1|2|3>,status/needs-triage"
```

**Title conventions** (match the existing issue list):

- `bug: <component>: <symptom>` — e.g. `bug: city stuck in adopting_sessions on supervisor restart`
- `feat: <component>: <capability>` — e.g. `feat: per-agent watchdog gating`
- `docs: <area>: <correction>` — e.g. `docs: deacon: point at "gc bd formula show"`

Include `status/needs-triage` unless a maintainer has already agreed to take it
directly.

## After filing

Once the issue exists, you can pick it up yourself: run
[plan-implementation](../plan-implementation/SKILL.md) on the issue number to plan the implementation (it re-runs the
competing-PR and architectural-refactor gates at code-time, maps blast radius, and
aligns the plan to repo conventions before you write code). The
[start-contribution](../start-contribution/SKILL.md) skill is the full lifecycle
map if you want the whole journey from here to a ready-to-push PR.

## Anti-patterns

- ❌ **Filing without verifying the bug still exists on main.** The failure mode
  this skill exists to prevent. Always do step 3.
- ❌ **Filing without a duplicate search.** Wastes everyone's time when it's
  already tracked.
- ❌ **Filing without checking active design docs.** Fix candidates that
  contradict an accepted `engdocs/design/*.md` invariant get retracted on the
  first maintainer pass. Run step 4 before drafting — even when you "already know
  the fix".
- ❌ **Symptoms-only body, no root-cause file:line refs.** The maintainer has to
  redo your investigation. P3 at minimum, or write the refs.
- ❌ **Single fix candidate.** Forecloses the design space.
- ❌ **Skipping "out of scope".** Adjacent-looking issues that aren't part of the
  fix cause scope creep; naming them upfront prevents it.
- ❌ **Filing as P1 because it felt big.** Priority is reach and recoverability,
  not how loud it was for you.

## Quick checklist before `gh issue create`

- [ ] Searched duplicates (3+ searches) — none open
- [ ] Confirmed the bug exists on the upstream main today (`git rev-parse origin/main`, or `upstream/main` if origin is your fork)
- [ ] Checked `engdocs/design/*.md` for accepted docs covering this area; cited
      the relevant section OR confirmed none applies
- [ ] Have `file:line` refs for the root cause
- [ ] Have ≥ 2 fix candidates with trade-offs named (and they don't contradict an
      active design invariant)
- [ ] Reduced to a minimum reproduction OR caveated explicitly
- [ ] Body has all required sections
- [ ] Labels include kind, priority, and `status/needs-triage`
