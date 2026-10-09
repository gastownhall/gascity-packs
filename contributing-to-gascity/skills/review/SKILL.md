---
name: review
description: Review a diff against gastownhall/gascity's actual quality bar — a read-only code review you can run on any branch, including before a PR exists. Runs the mechanical gates (make build + make check + make check-docs if docs touched), classifies test failures as pre-existing noise vs new regressions, and audits the diff against the full Gas City adoption-review checklist (B1-B36) — zero hardcoded roles, ZFC, the Bitter Lesson, the test tiers, the code conventions, config-nil semantics, store-write errors, timeout isolation, startup-vs-reload safety, goroutine lifecycle, do*/cmd* split, env hermeticity, and more. Self-contained — you (or your coding agent) run every check by reading this skill; no internal tools required. Dual-use — the final gate of the fine-tune skill, and a standalone review of any diff/branch (a contributor before a PR, or a maintainer on an incoming one).
---

# Review a Gas City Diff

You are reviewing a diff against
[gastownhall/gascity](https://github.com/gastownhall/gascity) — your own branch
before you push, or someone else's incoming contribution. This skill is the audit
a Gas City maintainer's adoption review runs on a diff, front-loaded so the
findings get fixed before they cost a review round-trip. It is read-only and needs
no PR to exist; run it on any branch.

Run it on the branch from inside a local checkout of `gastownhall/gascity`.
Two parts: **Part A** is the mechanical gates (build/lint/vet/test/docs); **Part
B** is the codebase audit (the B-rules). Do both. Produce the Part C report.

This is self-applicable: read each rule and check it against your diff with
`grep`/`git`/`go`. There is no agent to dispatch — the checklist *is* the
knowledge.

> **Baseline for the diff:** these commands compare your work against the main
> you branched from. If `origin` is `gastownhall/gascity`, use `origin/main`. If
> you're working from a fork, fetch upstream first
> (`git fetch upstream && git merge-base HEAD upstream/main`) and substitute
> `upstream/main`. Below, `main` means "the upstream main you're targeting."

## Part A — Mechanical gates

### A1. Determine scope

```bash
git diff main...HEAD --name-only
```

Set scope flags:

- `docs/**`, `*.mdx`, `docs/docs.json`, README, `engdocs/**` → also run `make check-docs`
- `Makefile`, `go.mod`, CI files → flag for careful review
- `cmd/gc/*.go` or `internal/**/*.go` only → `make build && make check` is sufficient

### A2. Run the gates in order

Each depends on the previous being green.

```bash
make build        # allow several minutes
make check        # allow several minutes — runs fmt-check, lint, vet, test
make check-docs   # only if docs/engdocs touched
```

Report status per sub-target. `make check` runs `fmt-check lint vet test`.

### A3. Classify test failures

`fmt-check`, `lint`, and `vet` failures are **always real blockers** — fix them.

For **test** failures, separate pre-existing flakes from regressions you
introduced. You don't have the maintainers' baseline table, so establish it
yourself: run the failing test on a clean `main` checkout.

```bash
git worktree add /tmp/gascity-baseline main
cd /tmp/gascity-baseline && go test -race -run 'TestNameThatFailed' ./path/to/package/... 2>&1 | tail -20
git worktree remove /tmp/gascity-baseline
```

| Result on clean `main` | Meaning |
|---|---|
| Test also fails on `main` | Pre-existing flake/baseline — not yours, note it and move on |
| Test passes on `main` | **Regression you introduced** — blocker, fix before push |

Environment-dependent and race-detector-flaky tests exist; verifying against
`main` is how you tell them apart from a real break.

## Part B — Codebase audit (the B-rules)

> The B-rule set is non-contiguous: **B32 is reserved and currently unused**, so
> the active audit is B1–B31 and B33–B36. A complete pass covers every numbered
> rule below — the absence of a B32 entry is intentional, not a missing check.

Read the diff and check each rule. The rules are grouped into **review
lenses** — cover all five, not just the ones that feel obvious for your change.
Each rule names the failure mode and, where useful, the public PR that taught it
(real precedent you can read).

### Design invariants (B1–B6)

**B1. Zero hardcoded roles (HARD RULE).**
```bash
git diff main...HEAD -- '*.go' | grep -iE 'mayor|deacon|polecat|sheriff|rider|marshal' | grep -v _test.go
```
Any hit outside test fixtures is a blocker. Gas City has zero hardcoded role
names in product code — roles are config-driven.

**B2. Zero Framework Cognition (ZFC).** No `if stuck then restart` logic, no
keyword/regex meaning-detection, no hardcoded semantic thresholds, no quality
judgments in Go code. Reasoning belongs to the model, not the framework.

**B3. Bitter Lesson alignment.** Flag heuristics/decision trees a smarter model
would sidestep. Test: imagine a 10× more capable model — does this code become
unnecessary? If yes, it's the wrong shape.

**B4. SDK self-sufficiency.** No SDK operation may depend on a specific
`[[agent]]` entry existing.

**B5. No status files.** Grep for PID/lock/state-file writes in `.gc/runtime/`
or `/tmp/`. State lives in the store, not on disk.

**B6. Layering invariants.** Layer N never imports Layer N+1. `internal/`
packages are peers — no cross-primitive imports. `internal/beads` must not import
`cmd/gc/`.

### Change impact / blast radius (B7, B9–B13, B15–B16, B18, B21, B23, B25–B26, B31, B35–B36)

**B7. Code conventions.** Unit tests next to code; `t.TempDir()`;
`//go:build integration` tag on integration tests; cobra/toml usage; atomic file
writes; no `panic` in library code; error wrapping with `%w`; no role names;
tmux invoked with `-L <socket>`; agent config field sync; raw string constants
extracted (not duplicated literals).

**B9. Code quality checklist.** Tests pass, vet clean, exported functions
documented, no premature abstractions, happy path + edge cases covered, errors
carry context, no hardcoded values.

**B10. Scope discipline.** Fix what the issue asks. Don't fold in adjacent
features or refactoring — note them as out-of-scope instead.

**B11. Config nil semantics.** A new config field where the consumer needs to
distinguish "not set" from "explicitly empty" must use `*string` (pointer), an
`Effective*()` accessor, and patch/override updates.

**B12. Store-write error propagation — retain and retry, never delete and
succeed.**
```bash
git diff main...HEAD | grep -E '_ = .*store\.|_ = .*SetMetadata'
```
A function returning `bool` after a store write must return `false` on write
error. In an error handler for a failed store write, never call `store.Delete`,
`store.CloseAll`, or a successor-state write as "recovery" — return the error or
set a failure state so callers can retry. Never paper over a store error by
deleting the source-of-truth record. (e.g. `SetMetadataBatch` silently
returned `true` on failure; a prune-on-error path removed records whose
terminal write had failed.)

**B13. Timeout / concurrency isolation.** New timeouts/semaphores must affect
only the intended subsystem. A shared `shellCommand` path needs splitting. Use
config constants, not magic numbers.

**B15. Infrastructure-agent guards.** Loops iterating agents must exclude
`control_dispatcher` / infrastructure agents from work-related config.

**B16. Startup vs reload safety.** `newCityRuntime` runs at startup only.
`buildOrderDispatcher` / `update()` run on config reload too. One-time sweeps
must be startup-only — putting them in a reload path corrupts in-flight state.

**B18. Map-key domain separation.** A map serving multiple consumers (pool +
named-session) must be filtered before it's passed to each consumer, or keys
leak across domains.

**B21. Config hot-reload snapshot safety.** Code in the `update()` / `buildStores()`
chain must use the passed `cfg` parameter, not `cs.cfg` (which is stale during
reload).

**B23. Fix-scope completeness + parallel code paths (the #1 adoption-review
finding).** For an entity with multiple states
(pending/in-flight/dead/active/creating), verify the fix handles **all** states,
not just the one in your repro. Then: for every function you modified, grep all
its callers; for every pattern you fixed (a missing nil-guard, a hardcoded
string, a wrong env lookup), grep the **entire** codebase for sibling instances
of the same pattern and fix them too. Fixing one call site while identical
siblings stay broken is the most common reason a PR bounces.

**B25. Constant grep radius.** When you introduce or use a named constant, grep
the entire codebase for the raw string value to find other occurrences that
should use the constant too — don't limit the search to your diff. (e.g. a
raw `"order-tracking"` string diverged from the `labelOrderTracking` constant.)

**B26. Golden-snapshot / doc-output drift.** When a change alters user-visible
output (CLI output, log lines, error messages, `fmt.Fprintf` strings), grep
`docs/` and `testdata/` for the old strings. Tutorial golden files
(`docs/tutorials/*.md`) and `.txtar` fixtures hardcode command output that goes
stale. **Extension:** the same applies to Go struct field doc comments and
generated reference docs — when a struct field or exported function changes
behavior, re-read its doc comment against the implementation; if it feeds
`cmd/genschema`, run `go run ./cmd/genschema` + `make check-docs` and re-grep
`docs/reference/` for the stale phrase.

**B31. Hard-fail conversion → examples audit + release note.** When a fix turns
silent degradation (default fallback, version downgrade, skipped validation,
silent success on missing data) into a hard error, anyone relying on the old
silent behavior will see new failures. (1) Grep `examples/` (especially
`examples/gastown/city.toml`) for configs that would newly hard-fail and update
them in the same PR. (2) Flag the behavior change under a `Release note:` heading
in the PR body.

**B35. Pack-binding qualification on routing/pool stamping.** Anything that
stamps `gc.routed_to`, names a pool, or routes work by pack binding must use the
binding-qualified name (`<binding>/<pool>`), not the bare pool name. Qualifying
when the binding is empty is also a bug.
```bash
git diff main...HEAD | grep -E 'gc\.routed_to|pool\.Name|PoolName|qualifyPool'
```

**B36. Sweeps walk every rig.** Maintenance sweeps, orphan reapers, and
lifecycle reconcilers must walk every rig in the city, not just HQ. The bug:
accepting a `cityStore` and only iterating that store, silently skipping
rig-scoped beads. Verify the loop covers `cfg.Rigs` and that progress counters
are preserved across the loop, not reset per rig.

### Debuggability & operability (B12, B17, B22, B24, B28, B30, B34)

**B17. Goroutine lifecycle (CLI vs server).** CLI commands exit immediately —
fire-and-forget goroutines die. Return a `<-chan struct{}` completion signal, and
callers must `defer`-block on the done channel on **all** return paths, not just
the happy path. (e.g. both `waitForSession` failure and an early `Attach`
return leaked a background goroutine.)

**B22. Dead-code audit.** Grep for functions/methods your PR introduces that have
zero callers — including helpers added "for completeness" (e.g. a `Len()` on a
wrapper). Diff new `func ` lines, then grep each name across the codebase.

**B24. Verify-before-delete.** Before pruning/closing/removing a record, verify
its expected successor/terminal state actually exists in the store
(`store.Get(id)` → exists check → prune). Fail open: a store-lookup error
**retains** the record rather than deleting it.

**B28. Error-context wrapping.** Every new `return err` / `return fmt.Errorf(...)`
must name the operation and entity that failed (bead ID, agent name, rig name,
file path). Bare `return err` that drops context is a finding. The convention is
`fmt.Errorf("adding rig %q: %w", name, err)`. A production error without context
is invisible in logs.

**B30. Package-level mutable state must be race-safe.** Any `var Foo bool/int/map`
at package scope that's written by config reload (or any non-`init` path) and
read by request/compile/instantiate paths must use `sync/atomic` or a mutex. The
idiom is `atomic.Bool` with exported `SetFoo`/`IsFoo` accessors; snapshot once at
the top of the read path.
```bash
git diff main...HEAD | grep -E '^\+var [A-Z][a-zA-Z]+ +(bool|int|int64|map)'
```
(Canonical: `internal/formula/compile.go` `formulaV2Enabled atomic.Bool`.)

**B34. Safety-predicate fail-closed.** A boolean predicate used as a safety gate
(`HasUnpushedCommits`, `HasStashes`, `IsRepo`, `Exists`, `IsClean`, `IsHealthy`)
must fail **closed** — returning `false` on internal error means "can't
determine" gets treated as "safe to proceed", which is dangerous for destructive
ops (prune/remove/reap/delete). Either return `(bool, error)` and propagate, or
add an explicit precondition probe that fails-closed first.

### Test evidence quality (B8, B14, B19–B20, B27, B33)

**B8. Test-tier boundaries.** Five tiers: unit, testscript (`.txtar`),
integration (`//go:build integration`), docsync, coordination. Put a new test in
the right tier. A test needing more than 2 env vars belongs in a unit test, not a
testscript.

**B14. Regression-test depth.** A bug fix tests through the full write path and
reads the state back from the store. Assertions must discriminate the exact bug
path, and you must test **every** branch the fix introduces (early-exit, timeout,
error, success), not just the happy path.

**B19. do*()/cmd*() split.** CLI commands split into `cmdFoo()` (wiring) +
`doFoo()` (pure logic with injected deps), so the logic is unit-testable.

**B20. Test-double conventions + env hermeticity.** No mock libraries — use
hand-written fakes next to the interface, with a compile-time
`var _ Interface = (*Fake)(nil)`. Tests that set environment variables must use
`t.Setenv()` (auto-restores), never raw `os.Setenv` + manual defer.
```bash
git diff main...HEAD -- '*_test.go' | grep -nE '\bos\.Setenv\b'
```
Each hit is a finding. (e.g. a test that didn't clear `GC_BEADS` failed for
devs with it exported.)

**B27. Polling over fixed sleeps in tests.** New test code uses `waitFor*` /
`pollFor*` helpers (timeout + interval) instead of bare `time.Sleep` for state
sync. The codebase has `waitForCondition`, `waitForFile`, `waitForBeadStatus`,
`waitForSession`, `pollForCondition`, etc.
```bash
git diff main...HEAD -- '*_test.go' | grep -n 'time\.Sleep'
```
Each hit should justify why a polling helper won't work.

**B33. Test save/restore for package-level state.** A test that reads/writes
package-level mutable state (feature flags, global counters, mode switches) must
save the prior value and restore it on cleanup — even when the variable defaults
to `false`:
```go
prev := IsFooEnabled()
SetFooEnabled(true)
t.Cleanup(func() { SetFooEnabled(prev) })
```
Hardcoded-`false` cleanup corrupts later tests that run with the flag on.

### Portability (B29)

**B29. Ambient env-var contamination — use the canonical projection layer.**
When code reads an env var (`os.Getenv("GC_BEADS")`), verify a parent `gc`
process in a nested launch can't pollute it. Gas City launches child `gc`
processes and env vars leak downward. Subprocess env construction belongs in
`cmd/gc/bd_env.go` (the model is `applyCanonicalDoltTargetEnv`, which explicitly
overwrites stale ambient `GC_DOLT_HOST/PORT`), not inlined into command handlers.
```bash
git diff main...HEAD | grep -E 'os\.Getenv|os\.LookupEnv'
```
Trace each new read: could it be inherited from a parent `gc` with a conflicting
value?

## Part C — Report

Output exactly this format. Keep each B-line to one concern with a `file:line`
ref.

```
Gas City review — <branch>

Part A — Mechanical gates:
  make build       : ✅ / ❌
  fmt-check        : ✅ / ❌
  lint             : ✅ / ❌
  vet              : ✅ / ❌
  test             : ✅ clean / ⚠️ baseline-only / ❌ NEW: <test names>
  make check-docs  : ✅ / ❌ / n/a

Part B — Codebase audit:
  Design invariants:
    B1  Zero hardcoded roles   : ✅ / ❌ <file:line>
    B2  ZFC                    : ✅ / ⚠️ <concern>
    B3  Bitter Lesson          : ✅ / ⚠️ <concern>
    B4  SDK self-sufficiency   : ✅ / ❌
    B5  No status files        : ✅ / ❌
    B6  Layering               : ✅ / ❌ <import>
  Change impact / blast radius:
    B7  Code conventions       : ✅ / ⚠️ <which box>
    B9  Quality checklist      : ✅ / ⚠️ <which box>
    B10 Scope discipline       : ✅ / ⚠️
    B11 Config nil semantics   : ✅ / ⚠️ / n/a
    B12 Store write errors     : ✅ / ⚠️
    B13 Timeout isolation      : ✅ / ⚠️ / n/a
    B15 Infra agent guards     : ✅ / ⚠️ / n/a
    B16 Startup vs reload      : ✅ / ⚠️ / n/a
    B18 Map key separation     : ✅ / ⚠️ / n/a
    B21 Config snapshot safety : ✅ / ⚠️ / n/a
    B23 Fix scope completeness : ✅ / ⚠️ <missed sibling/state>
    B25 Constant grep radius   : ✅ / ⚠️ <raw string>
    B26 Doc/code drift         : ✅ / ⚠️ <stale doc/struct/ref> / n/a
    B31 Hard-fail examples     : ✅ / ⚠️ <example needing update> / n/a
    B35 Pack-binding qualify   : ✅ / ⚠️ <bare pool name> / n/a
    B36 Sweep walks every rig  : ✅ / ⚠️ <HQ-only sweep> / n/a
  Debuggability & operability:
    B17 Goroutine lifecycle    : ✅ / ⚠️ / n/a
    B22 Dead code audit        : ✅ / ⚠️ <dead func>
    B24 Verify-before-delete   : ✅ / ⚠️ / n/a
    B28 Error context wrapping : ✅ / ⚠️ <bare return err> / n/a
    B30 Package race-safety    : ✅ / ⚠️ <var> / n/a
    B34 Safety-predicate close : ✅ / ⚠️ <fail-open predicate> / n/a
  Test evidence quality:
    B8  Test tier              : ✅ / ⚠️
    B14 Regression depth       : ✅ / ⚠️
    B19 do*()/cmd*() split     : ✅ / ⚠️ / n/a
    B20 Test doubles + env     : ✅ / ⚠️ <os.Setenv> / n/a
    B27 Polling over sleeps    : ✅ / ⚠️ <time.Sleep> / n/a
    B33 Save/restore pkg state : ✅ / ⚠️ <hardcoded cleanup> / n/a
  Portability:
    B29 Ambient env contamination: ✅ / ⚠️ <var name> / n/a

Verdict: READY TO PUSH / NEEDS FIXES
```

## When to use

This skill is **dual-use** — a phase of a parent skill AND a standalone utility:

- As the **final gate of [`fine-tune`](../fine-tune/SKILL.md)** (its Stage 3),
  run automatically before a push.
- **Standalone**, to review any diff/branch against the Gas City standard —
  before opening a PR, after fixing findings a previous run flagged, when you're
  unsure a change meets the bar, or as a maintainer reviewing an incoming
  contribution (it needs no PR to exist).

Mechanical-gate failures and B-rule findings are not equal: `fmt-check`/`lint`/`vet`
and a real test regression are hard blockers; B-rule `⚠️` findings are things a
maintainer will flag — fix them, or consciously decide to leave one and say why
in the PR body.
