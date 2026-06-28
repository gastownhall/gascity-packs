---
name: fine-tune
description: The pre-push fine-tuning loop for a gastownhall/gascity PR — the mutating polish pass that ends by reviewing the diff. Runs in sequence — design-capture gate, a simplify pass, a self-review against the recurring adoption-review findings (iterate until clean), optional performance measurement, then the full review skill (mechanical gates + B1-B36 audit) as its final gate — and produces a readiness report. It STOPS at the report; pushing the branch and opening the PR are your call. Self-contained — no internal hooks or tooling required. Use right before you open a PR to gastownhall/gascity.
---

# Fine-Tune — Pre-Push Polish Loop

Your code is written and you're about to open a PR to
[gastownhall/gascity](https://github.com/gastownhall/gascity). This skill runs the
final review stages in sequence, produces one readiness report, and **stops**. It
does not push and does not open a PR — those are your call, made once the report
is clean.

Goal: land the PR with few or no review comments by catching the structural and
correctness defects a careful maintainer review would flag.

> `main` below means the upstream main you're targeting — `origin/main` if origin
> is `gastownhall/gascity`, else `upstream/main`.

## Stage 0 — Design-capture gate (read-only)

The cheapest finding to fix is the one captured before review. Architectural work
on Gas City lands *with* a design artifact under `engdocs/design/`; a missing one
is the most common reason an architectural PR costs an extra "what's the intent?"
round-trip. This gate catches it before push — it's read-only and never authors
the doc (authoring belongs in [`plan-implementation`](../plan-implementation/SKILL.md)
Phase 3.5, before the code).

```bash
git diff --stat main...HEAD
# Was a design artifact added/modified in this branch?
git diff --name-only main...HEAD -- 'engdocs/design/**' 'release-gates/**'
# Or is an existing one cited in a commit body?
git log main..HEAD --format='%B' | grep -iE 'engdocs/design|release-gates'
```

Apply the same trigger test as `plan-implementation` Phase 3.5:

- **Point fix / test-only / docs-only / behavior-preserving refactor** → design
  capture **N/A**. Pass.
- **Architectural** (subsystem boundary, new package, new public contract/schema,
  feature-scale) → the branch must add/modify an `engdocs/design/*.md` (or
  `release-gates/*.md`), **or** cite an existing one in a commit/PR body.

If architectural and no capture is present, check one thing before flagging — does
the touched area already have a contract on `main` this PR implements against?

```bash
git ls-files 'engdocs/design/**' 'release-gates/**' | grep -iE '<pkg-or-feature-keyword>'
```

- **An existing contract covers it** → remedy is **cite it** (`implements engdocs/design/<name>.md`
  in a commit/PR body). Cheap; do it and pass.
- **None exists, none added** → report `Design capture: ⚠️ MISSING`. Don't silently
  block, but the default recommendation is **stop and add the doc** via
  [`plan-implementation`](../plan-implementation/SKILL.md) Phase 3.5 — adding it
  after review fragments the PR.

## Stage 1 — Simplify

Clean up the diff before anyone reviews it: remove dead code, consolidate
duplicates, tighten naming and structure. This stage **can** modify files. If you
have a dedicated simplify tool, run it; otherwise do the pass by hand.

After any change, confirm it still builds:

```bash
go build ./...
```

If the build breaks after simplifying, revert the simplify changes and note it —
don't iterate here.

## Stage 2 — Self-review (iterate until clean)

Converge to **no blocker or major findings** before Stage 3. A single review pass
leaves comments a maintainer (or the repo's automated reviewer) will catch
post-push; iterating a review loop before push is what lands PRs with zero inline
comments.

### Stage 2a — Scan the recurring-finding patterns

Before any deeper review, scan your diff against these patterns — each is a
real, repeatedly-caught adoption-review finding. Fix hits in place; they're cheap
now and noisy after push.

1. **Safety-predicate fail-open** — a `bool`-returning predicate used as a safety
   gate (`HasUnpushedCommits`, `HasStashes`, `IsRepo`, `Exists`) returning `false`
   (= "safe") on internal error. Fail closed: add an error-return path or a
   precondition probe (B34).
2. **Helper error context across reuse contexts** — calling a shared helper from a
   new caller where its existing error message no longer describes the new
   context. Wrap: `fmt.Errorf("<new-context> %q: %w", id, err)` (B28).
3. **Dedup-vs-filter mismatch** — one stage dedups inputs while a downstream stage
   filters per-original-key, silently dropping the deduped-away keys. Dedup
   one-to-many, or filter against every original key (B23).
4. **Wrong working directory for destructive ops** — `git worktree remove`,
   `git clean -fd`, `dolt prune` etc. invoked from *inside* the target. Use the
   parent path as the workdir.
5. **Pipeline output dropped across stages** — a later assignment to an output
   slice/map overwriting entries an earlier stage wrote (listing errors,
   partial-failure markers). Merge/prepend instead of overwriting.
6. **Counter conflation** — a `len(slice)` in a user-facing message mixing
   categories (threshold violations + measurement errors). Track distinct counters.
7. **Struct doc / generated reference drift** — a struct field's doc comment
   describing behavior the code doesn't perform. Fix the doc, then regenerate
   downstream reference docs (`go run ./cmd/genschema`, `make check-docs`) and
   re-grep `docs/reference/` for the stale phrase (B26).

(These are the recurring adoption-review findings that most often bounce a PR in review.)

### Stage 2b — Review loop

Run your code-review tool of choice over the diff (if you have a multi-model
reviewer, use it — different models catch different defects). Classify every
finding:

- **blocker** — a correctness/safety defect that must be fixed before merge
- **major** — a design or precision defect a reviewer will flag (includes any
  Stage 2a pattern)
- **minor** — style or nice-to-have; does not block

Loop (max ~3 iterations): review → fix every blocker and major in place, commit →
review again. Exit when the result is "approve" / "approve with minors only". If
you can't converge in 3 iterations, stop and report **BLOCKED — review not
converging**; decide consciously whether to keep iterating or accept the
remaining majors.

## Stage 2.5 — Performance (perf-touching changes only)

Applies only when the change touches a hot path, claims a speedup, or closes a
perf issue. All other changes: skip, note `Performance: N/A`.

A perf-touching PR is **not ready** until it captures:

1. **Bottleneck attributed from a measurement, not a guess** — name the dominant
   cost with evidence (profile/bench/traced cost). No identified bottleneck →
   `⚠️ UNMEASURED`.
2. **Before/after numbers** — a real bench (`ns/op`, p95, wall-clock under load);
   state the machine.
3. **Honest speedup** — report the *measured* multiplier; if the issue/PR claims a
   number, verify it and flag inflation.
4. **Amdahl residual** — the fraction still un-optimized, listed explicitly.
5. **Correctness guard** — when a fast path replaces a slow-but-correct one,
   confirm it returns the same answer. A fast-but-wrong path is a **blocker**.

If perf-touching and any of 1–4 is missing → report `Performance: ⚠️ UNMEASURED`
(a conscious waive, never a silent pass).

## Stage 3 — Run the review

Run the full [`review`](../review/SKILL.md) skill: mechanical gates (`make build` /
`make check` / `make check-docs`) with baseline-vs-regression classification, plus
the B1–B36 codebase audit. This stage is read-only — it is the review skill's
standalone audit, run here as fine-tune's final gate.

## Stage 4 — Readiness report

Combine the stages into one report:

```
Gas City fine-tune readiness — <branch>

Stage 0 — Design capture:
  Change class: <point-fix | test/docs-only | refactor | architectural>
  Design capture: <N/A, code-only | added/cited engdocs/design/<name>.md | ⚠️ MISSING — waive or add>

Stage 1 — Simplify:
  Changes made: <yes: N files / none needed>
  Build after simplify: ✅ / ❌ (reverted)

Stage 2 — Self-review:
  Iterations: <N>
  blocker: <count — must be 0 to be READY>
  major:   <count — must be 0 to be READY>
  minor:   <count — optional>
  Fix commits: <sha1>, <sha2>, ...
  Remaining minors (if any): <1-line summaries>

Stage 2.5 — Performance (perf-touching only):
  Bottleneck (measured): <attributed cost | N/A>
  Before → after:        <bench numbers + machine>
  Honest speedup:        <measured Nx — flag if inflated>
  Residual / deferred:   <un-optimized fraction>
  Correctness guard:     ✅ same-answer / ⚠️ <risk> / N/A

Stage 3 — Review:
  Part A (mechanical gates): ✅ / ❌
  Part B (codebase audit):   ✅ / ⚠️ <count> findings

  <paste the review skill's report>

Overall: READY / BLOCKED (<what needs fixing>)
```

## Stage 5 — Stop

**This skill stops here.** It does not run `git push`, does not run
`gh pr create`, and does not send anything to a remote. Pushing the branch and
opening the PR are your call — make them once the report says READY.

When you do open the PR, include the Stage 2 + Stage 3 findings summary in the PR
body — it shows the reviewer you did the work.

## After you open the PR — automated review

`gastownhall/gascity` runs an automated reviewer on new PRs; it
typically posts within minutes. When its comments arrive:

1. Evaluate each like any reviewer — verify against the code before fixing; skip
   false positives with a one-line reason.
2. Fix the valid ones, commit, push.
3. Reply to each comment: "Fixed in `<sha>` — <what>" or "Won't fix — <reason with
   file:line>".

Every comment you could have caught with one more Stage 2 pass is one you can
catch before push next time.

## Handling failures

- **Stage 0 design capture MISSING (architectural)** → warning. Default: stop and
  add the doc via `plan-implementation` Phase 3.5. Never auto-author it here.
- **Stage 1 breaks the build** → revert the simplify changes, note it, continue.
- **Stage 2 won't converge in ~3 iterations** → report BLOCKED; decide consciously.
- **Stage 3 fails mechanical gates** → BLOCKED; fix before push.
- **Stage 3 finds B-rule violations** → warnings; fix them or note why you're
  leaving one in the PR body.
