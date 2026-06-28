---
name: plan-implementation
description: Plan the implementation for a gastownhall/gascity issue before writing code — front-loading the analysis a maintainer's adoption review will check. Runs the competing-PR and architectural-refactor gates (don't start work that's already in flight or about to be superseded), maps blast radius (Phase 2), aligns the plan to repo conventions and the right test tier, and applies the design-capture discipline (land architectural work with an engdocs/design artifact). Produces a structured plan and the B-rule convention-trigger checklist. Self-contained — git + gh + the sibling skills, no internal tooling. Use when starting a new fix/feature branch.
---

# Plan the Implementation

You have an issue number (from [`find-work`](../find-work/SKILL.md), or one you
filed with [`write-issue`](../write-issue/SKILL.md)) and you're about to implement
a change for [gastownhall/gascity](https://github.com/gastownhall/gascity). This
skill front-loads the analysis the maintainer's adoption review will run — so you
address the concerns *before* writing code, when they're cheap.

The output is a written plan. **No code is written until the plan is done and you
confirm it.**

> `main` below means the upstream main you're targeting — `origin/main` if origin
> is `gastownhall/gascity`, else `upstream/main`.

## Phase 1 — Issue analysis

Read the issue; extract what's broken, where it lives, why it matters.

```bash
gh issue view <number> --repo gastownhall/gascity --json title,body,labels,comments
gh issue list --repo gastownhall/gascity --search "<keywords>" --state all --limit 10
gh pr list   --repo gastownhall/gascity --search "<keywords>" --state all --limit 10
```

### Competing-PR gate (BLOCKING)

Before anything else, check whether an open PR already targets this issue, or
whether it's already fixed:

```bash
gh pr list   --repo gastownhall/gascity --state open --search "<issue number>" --json number,title,author,createdAt
gh issue view <number> --repo gastownhall/gascity --json state
```

**If a competing PR exists or the issue is closed, STOP.** Pick a different issue
or, if you still think yours adds value, say so explicitly in the plan and decide
consciously. Don't silently start work someone else is already doing — it wastes
effort and creates merge conflicts.

### Architectural-refactor gate (BLOCKING)

The competing-PR check catches *issue-level* duplicates; it misses *area-level*
ones. Before scoping a fix, check whether the file/package you'll touch sits
inside an active architectural refactor. If it does, a narrow fix gets superseded
and your time is wasted.

```bash
# Accepted / Implementing design docs:
grep -lE "^\| Status \|.*\b(Accepted|Implementing|Implemented)\b" engdocs/design/*.md

# Open maintainer PRs consolidating your target area (substitute a keyword
# from the subsystem you're touching; skim hits for any that unify/refactor/
# supersede it):
gh pr list --repo gastownhall/gascity --state open --search "<your-subsystem-keyword> in:title" --json number,title

# Recently-merged PRs that used "Supersedes" (the area is being consolidated):
gh pr list --repo gastownhall/gascity --state merged --search "supersedes in:body" --limit 5 --json number,title
```

**If your area has an Accepted/Implementing design doc OR an open consolidation
PR touching it, STOP** and choose one of:

- **Point-fix** — a single-line change the refactor can absorb. Ask in the issue
  whether that's wanted.
- **Wait** for the refactor to land, then rebase.
- **Pivot** to an issue outside the refactor area.

Read the relevant design doc before writing any code. Its `Status` field and
`## Phase N` headings tell you which parts are live and which are queued; a fix
landing in a queued phase won't survive rebase. (Gas City precedent: a single broad refactor
superseded eight narrow session-model PRs; another superseded two env-projection
PRs.)

## Phase 2 — Blast radius

Map the impact surface with the [`map-blast-radius`](../map-blast-radius/SKILL.md)
skill: enumerate the functions you'll touch, their callers and execution contexts, the
config-field sync chain, domain-boundary crossings, and concurrency. Carry its
`HIGH`/`MED` findings into the plan's `Risks` and `Blast radius` sections.

## Phase 3 — Convention alignment

Verify the plan follows these patterns before writing code:

### Architecture patterns

- **do*()/cmd*() split** — `cmdFoo()` (wiring) + `doFoo()` (pure logic, injected deps)
- **Provider interfaces** — new implementations pass the conformance suite in `*test/conformance.go`
- **Nil-guard tracker** — optional subsystems use `if tracker != nil`; nil means disabled
- **Config override chain** — `city.toml` → `[agent_defaults]` → `[[agent]]` → `AgentPatch` → `AgentOverride`

### Test strategy (decide BEFORE writing code)

1. **Which tier?**
   - "Does the store handle corrupt X?" → unit test
   - "Does `gc foo` print the right output?" → testscript (`.txtar`)
   - "Does this work with real tmux?" → integration test (`//go:build integration`)
   - "Does the provider shim handle this?" → acceptance test (`test/acceptance/`)
   - "Are components called in the right order?" → coordination test
2. **Fakes, not mocks** — `runtime.NewFake()`, `beads.MemStore`, `fsys.NewFake()`. No gomock. New fakes next to the interface with `var _ Interface = (*Fake)(nil)`.
3. **Error injection** — per-path (`f.Errors["/path"] = err`) or modal (`f.Broken = true`).
4. **Testscript env vars** — only `GC_SESSION`, `GC_BEADS`, `GC_DOLT`. More than 2 → unit test.
5. **Regression depth** — bug fixes test through the full write path; assertions discriminate the exact bug path (B14).

### Branch setup

```bash
git fetch origin
git checkout -b <prefix>/<issue-number>-<short-desc> origin/main
# prefix: fix/ feat/ refactor/ docs/
```

Branch from the upstream main you're targeting; don't `git checkout main` first.

## Phase 3.5 — Design-capture decision

Gas City's strongest contributions land architectural work **with a design
artifact attached** — maintainers author the `engdocs/design/` canon, and a PR
that implements against (or proposes) a design doc clears review in one pass
instead of costing a "what's the intent here?" round-trip. This is the single
highest-leverage thing you can do to make an architectural PR land cleanly.

### Does this change need a design doc?

Write (or update) an `engdocs/design/<name>.md` when **any** of these is true:

- It introduces or changes a **subsystem boundary or cross-cutting mechanism** —
  read-path/routing, store topology, supervisor or session lifecycle, a
  provider/worker interface, the config override chain, an event/wire format, the
  endpoint model.
- It adds a **new package** or a **new public contract/schema** other components
  or packs consume.
- It changes **behavior other components depend on** — `events.jsonl` shape, a
  CLI contract a pack reads, the bd+Dolt contract.
- The work is **cohesive feature-scale**, not a point fix.

Skip the doc (a code-only PR is correct) when the change is a single-function bug
fix, test-only, docs-only, or a behavior-preserving mechanical refactor. Respect
KISS/YAGNI — never write a design doc for a one-liner.

### Two capture mechanisms — know which is which

- `engdocs/design/*.md` — forward-looking **design proposal**. This is the one a
  contributor authors.
- `release-gates/*.md` — per-change acceptance contract tied to a builder-fleet
  deploy. You won't author these, but if your area already has one, cite it the
  same way you'd cite a design doc.

### If the area ALREADY has a design doc or release-gate

You found it in the Phase 1 architectural-refactor gate. Don't start a competing
doc — **implement against it and cite it** by path in the PR body and in the
commit that lands the core change (`implements engdocs/design/<name>.md`).

### If it needs a NEW doc, draft the stub now — before code

Author it in the branch so it's reviewed *with* the diff, not bolted on after.
Confirm the live shape against any existing file in `engdocs/design/` first, then:

```bash
cat > engdocs/design/<short-kebab-name>.md <<'MD'
---
title: "<Title Case Name>"
---

| Field | Value |
|---|---|
| Status | Proposed |
| Date | <YYYY-MM-DD> |
| Author(s) | <your handle> |
| Issue | #<number> |
| Supersedes | N/A |

## Summary

<2-4 sentences: what this changes and the one-line reason it's worth doing.>

## Problem

<What's broken or missing today, for a future maintainer with no context.>

## Design

<The approach. Name the subsystem boundaries it touches and the contract it
establishes — the "why this shape" the review otherwise reverse-engineers.>

## Alternatives considered

<At least one rejected option and why. Pre-empts "did you consider X?".>
MD
```

Register it — add one row to the **Current Design Set** table in
`engdocs/design/index.md`:

```
| `<short-kebab-name>` | Proposed | <one-line note> |
```

Open at `Status: Proposed`; let review move it to `Accepted` and the landing PR
move it to `Implemented`.

## Phase 4 — Plan output

Produce this and confirm it before writing code:

```
Issue: #<number> — <title>

Root cause: <one sentence>

Files to change:
  <file>:<function> — <what changes>

Blast radius: <summary from the map-blast-radius skill>

Design capture:
  Change class: <point-fix | test/docs-only | refactor | architectural>
  [ ] Trigger fired? (subsystem boundary / new package / new contract / feature-scale)
  [ ] Existing engdocs/design doc to cite, OR new stub drafted (Proposed)
  [ ] Registered in engdocs/design/index.md
  (point-fix / test-only / docs-only / refactor → "N/A, code-only PR" + one-line why)

Convention triggers (the B-rules this change must satisfy):
  [ ] Config field sync (B11, B15)
  [ ] Store write error propagation / retain-and-retry (B12)
  [ ] Timeout isolation (B13)
  [ ] do*()/cmd*() split (B19)
  [ ] Test doubles + env hermeticity (B20)
  [ ] Map key separation (B18)
  [ ] Startup vs reload (B16)
  [ ] Goroutine lifecycle (B17)
  [ ] Config snapshot safety (B21)
  [ ] Dead code audit (B22)
  [ ] Fix scope completeness + parallel siblings (B23)
  [ ] Verify-before-delete (B24)
  [ ] Constant grep radius (B25)
  [ ] Golden snapshot / doc drift (B26)
  [ ] Env projection layer (B29)
  [ ] Package-level race-safety (B30)
  [ ] Hard-fail examples audit (B31)
  [ ] Test save/restore of pkg state (B33)

Test plan:
  Unit: <what to test, which fakes>
  Testscript: <which .txtar to add/modify>
  Integration: <if needed>

Risks:
  <what could go wrong, what the maintainer will scrutinize>
```

**Confirm the plan before writing any code.**

## Phase 5 — What the maintainer will check

Gas City adoption reviews run a multi-model automated pass and consistently flag these. Address them proactively — each maps to a
B-rule in [`review`](../review/SKILL.md):

1. **Silent error handling** — `_ = store.Write()` or a `bool` return that doesn't fire `false` on write error (B12)
2. **Shared code paths** — timeouts/semaphores bleeding into unintended subsystems (B13)
3. **Nil/empty distinction** — config fields where "not set" vs "explicitly empty" matters (B11)
4. **Infrastructure-agent contamination** — loops applying work config to `control_dispatcher` (B15)
5. **Goroutine lifecycle** — fire-and-forget goroutines in CLI paths; defer-block done channels on ALL return paths (B17)
6. **Startup vs reload safety** — one-time operations wired into reload paths (B16)
7. **Test specificity** — assertions that could pass for the wrong reason (B14)
8. **Raw string literals** — a constant defined but not used everywhere; grep the ENTIRE codebase (B25)
9. **Dead code introduced by the PR** — helpers added "for completeness", never called (B22)
10. **Incomplete state coverage** — a fix handling one state but not the others the bug also hits (B23)
11. **Verify-before-delete** — pruning without confirming the successor state exists; fail-open (B24)
12. **Missing regression branches** — multiple code paths (early-exit/timeout/error/success), only the happy path tested (B14)
13. **Parallel code-path siblings (the #1 finding)** — fixing one call site while identical siblings stay broken (B23)
14. **Env-var hermeticity** — `os.Setenv` instead of `t.Setenv()` in tests (B20)
15. **Golden-snapshot / doc drift** — changed output without updating tutorial golden files / `.txtar` fixtures (B26)
16. **Package-level mutable-state races** — `var Foo bool` written by reload, read by request paths; must be `atomic.*` (B30)
17. **Hard-fail conversions** — turning silent degradation into a hard error without auditing `examples/` + adding a release note (B31)
18. **Test cleanup that hardcodes state** instead of restoring it (B33)
19. **Env projection inlined** into command handlers instead of `cmd/gc/bd_env.go` (B29)

After the code is written, run [`fine-tune`](../fine-tune/SKILL.md) (which ends by
running [`review`](../review/SKILL.md)) to verify against the full list before you push.
