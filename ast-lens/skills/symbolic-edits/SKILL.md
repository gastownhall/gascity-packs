---
name: symbolic-edits
description: Make STRUCTURAL source edits through compile-gated symbolic ops instead of free-text editing. For renaming a symbol across files, cleaning up an import block, or extracting a declaration into a new package, run `bin/op <op> <file> [--k v]` to get a read-only PLAN (diff + predicted gate verdict + a content-hash token), review it, then `bin/op <op>! <file> <token> [--k v]` to execute — the op computes the change correctly and a false-negative-only compile gate refuses to write anything it cannot prove parses. Use whenever a structural change spans references, imports, or package boundaries. Ordinary line edits still use `Edit`.
---

# Symbolic Edits

## Overview

Hand-editing a structural change with the `Edit` tool is two gambles at once.
You gamble that you found *every* site — every reference to the symbol you are
renaming, every caller that needs an import rewritten — and you gamble that the
text you typed still parses. Miss one call site and the build breaks; fat-finger
a brace and the build breaks. Neither failure is caught until something later
tries to compile, by which point the broken tree has already poisoned the task.

This pack ships a write-side *lens* that removes both gambles. An op
(`bin/op`) **computes** the structural change from the AST — it finds the sites,
not you — and a **compile gate** stands between the computed change and the
disk. The gate is *false-negative-only* by construction: it materialises the
proposed files into a scratch copy, runs the language's native syntax check, and
**writes only if every touched file passes**. It can reject a change that would
in fact have worked (you re-plan), but it can never accept one that breaks the
program. A syntactically-broken result cannot reach the tree.

**The discipline: for a supported structural edit, plan with `bin/op`, review
the plan, then execute — do not hand-edit.** Planning is read-only and emits a
unified diff plus a content-addressed token; execution commits that exact plan
through the gate. This is the agent-facing half of the pack's compile-gated
write discipline.

## When to Use

Reach for `bin/op` — not `Edit` — when the change is one of these **structural**
shapes:

- **Rename a symbol across files** — a function, type, const, or var whose name
  appears in callers, not just at its declaration. `rename-symbol` (Go) drives
  the rename through gopls, so it is compile-aware and updates every reference.
- **Clean up / re-canonicalise an import block** — drop unused imports and sort
  or group the rest into the language's canonical form. `fix-imports` (Go +
  Python) defers to the language's own formatter (goimports/gofmt, ruff).
- **Extract a declaration into a new package** — lift one exported Go decl out
  to a brand-new sibling package and rewrite in-package callers to the qualified
  name, importing the new package where needed. `extract-to-package` (Go).

In short: when the edit *spans references, imports, or package boundaries*,
let the op compute it and let the gate guard it.

**When NOT to use:**

- **Ordinary edits still use `Edit`.** Changing a function body, fixing a
  literal, editing a comment, tweaking config, writing prose — anything that is
  not one of the three supported structural ops — is a normal `Edit`. `bin/op`
  is *not* a general code editor; it does exactly these ops and nothing else.
- **Unsupported language for the op.** `rename-symbol` and `extract-to-package`
  are Go-only; `fix-imports` is Go + Python. For a structural change in a
  language an op does not cover, fall back to `Edit` (and the gate is not there
  to catch you — edit carefully).
- **The op declines.** If the plan is a "no change" plan (no token, no diff),
  the op cannot do this safely — e.g. a single-name `var` extract is supported
  but a grouped `var (...)` block is not. Do not force it with `Edit` blind to
  why; read the op's scope, narrow the request, or accept that it is out of
  scope.

## Process

The flow is a pair `⟨op, op!⟩`: a read-only **plan**, then a **review**, then an
**execute**. The trailing `!` selects execute.

### Step 1 — Plan (read-only)

```bash
bin/op <op> <file> [--k v ...]
```

`bin/op` is shipped with this pack; invoke it by its pack-relative path if it is
not on `PATH`. Planning **never writes**. It runs the op against the current
file, runs the *real* gate against the proposed change in a throwaway copy to
predict the verdict, and renders a five-section Markdown plan:

1. **Target** — op, absolute file, repo root, args.
2. **Scope** — the relpaths that will change (a rename can touch many files).
3. **Diff** — a unified ` ```diff ` per changed file.
4. **Predicted verdict** — `ACCEPT` / `REJECT`, with the reason.
5. **Plan token** — a 64-hex content hash, plus the ready-to-run `op!` line.

`--k v` pairs become the op's args (e.g. `--symbol Foo --new-name Bar`); a bare
`--flag` means `flag=True`.

### Step 2 — Review the plan

Read the **diff** and the **predicted verdict** before committing anything.

- Verdict `ACCEPT` → the gate has already proved (in scratch) that every touched
  file parses. The diff is what will land, byte-for-byte.
- Verdict `REJECT`, or a "no change" plan with **no token** → do not proceed.
  The op declined or the gate would refuse. Re-plan with a narrower scope or
  different args, or fall back to `Edit` if the change is not actually one of
  the supported ops.

### Step 3 — Execute (commits through the gate)

```bash
bin/op <op>! <file> <token> [--k v ...]
```

Pass the **token** from the plan and the **same args**. Execute recomputes the
change from the *current* file, re-derives the token, and:

- If the file drifted since you planned (the recomputed token ≠ your token) it
  **aborts**: `REJECT — stale plan, re-plan ...`, writing nothing. A stale token
  is a real conflict, not a nuisance — re-plan against the new state.
- On a matching token it submits to the gate and **writes only on `ACCEPT`**
  (reporting the absolute paths written). On reject it writes nothing.

Exit codes let a script branch without parsing Markdown: plan exits `0` if the
predicted verdict is accept, `3` on reject / nothing-to-do; execute exits `0` on
accept, `3` on reject / stale, `2` on usage errors.

## The Supported Ops

| Op                   | Languages    | Scope it computes |
| -------------------- | ------------ | ----------------- |
| `rename-symbol`      | Go           | Rename a symbol and **every reference to it across the module**, via gopls (compile-aware). |
| `fix-imports`        | Go, Python   | Re-canonicalise **one file's import block** — drop unused, sort/group — via the language's formatter (goimports/gofmt, ruff). |
| `extract-to-package` | Go           | Move **one exported top-level decl** into a new sibling package and rewrite in-package callers to the qualified name, adding the import where needed. |

`bin/op --list` shows which ops resolve on this host; `bin/op --matrix` prints
the gate's per-language syntax-checker matrix.

## Worked Example — rename a symbol across files

You want to rename the Go function `Foo` to `Bar` in `foo.go`. `Foo` is called
from other files in the module, so a hand-edit would have to find every caller —
exactly the structural change `bin/op` is for.

**1. Plan.**

```bash
bin/op rename-symbol foo.go --symbol Foo --new-name Bar
```

```markdown
# Plan: rename-symbol

## Target
- op: `rename-symbol`
- file: `/abs/path/foo.go`
- repo root: `/abs/path`
- args: symbol='Foo', new-name='Bar'

## Scope
- 2 files changed (relative to repo root):
  - `foo.go`
  - `caller.go`

## Diff
```diff
--- a/foo.go
+++ b/foo.go
@@
-func Foo(name string) string {
+func Bar(name string) string {
```
```diff
--- a/caller.go
+++ b/caller.go
@@
-	return Foo("world")
+	return Bar("world")
```

## Predicted verdict
- **ACCEPT** — all 2 touched files passed native syntax check

## Plan token
- `c89147b2…edf0c8`

Execute with: `bin/op rename-symbol! /abs/path/foo.go c89147b2…edf0c8 …`
```

**2. Review.** The **Scope** confirms the op found the second call site in
`caller.go` (a hand-edit might have missed it). The verdict is **ACCEPT** — the
gate already parsed both proposed files in scratch. The diff is what will land.

**3. Execute** with the token and the same args:

```bash
bin/op rename-symbol! foo.go c89147b2…edf0c8 --symbol Foo --new-name Bar
```

```console
ACCEPT — all 2 touched files passed native syntax check
  wrote /abs/path/foo.go
  wrote /abs/path/caller.go
```

If `foo.go` had changed between plan and execute, this would instead print
`REJECT — stale plan, re-plan …` and write nothing — re-plan and review the
fresh diff.

## Why This Matters

- **Correctness — the op finds the sites, not you.** A cross-file rename or an
  extract is computed from the AST (gopls for renames), so every reference and
  every needed import is handled. Free-text editing relies on you spotting them
  all; the op does not.
- **Safety — the gate never commits broken code.** The compile gate is
  false-negative-only: it writes only what it can prove parses, in every touched
  file, and discards anything it cannot. A syntactically-broken structural edit
  cannot reach the tree. The worst case is a reject you recover from by
  re-planning — never a silently-broken build.
- **Reviewable, stateless plans.** The plan is a self-contained diff plus a
  content-addressed token: any agent can emit it and any other can execute it
  later, and a file that drifted in between makes the token mismatch and the
  execute abort rather than commit against stale state.

## Verification Gate

Before treating a structural edit as done:

- [ ] For a rename-across-files / import-cleanup / extract-to-package change, it
      went through `bin/op` (plan → review → `op!`), not a hand `Edit`.
- [ ] The plan's **diff** and **predicted verdict** were reviewed before
      executing; a `REJECT` or token-less "no change" plan was re-planned or
      handed off to `Edit`, not forced.
- [ ] Execute reported `ACCEPT` and the written paths; a `stale plan` abort was
      handled by re-planning against the current file, not retried blindly.
- [ ] Edits that are *not* one of the three supported ops used `Edit` as usual.

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack
contributes a skill by placing `skills/<name>/SKILL.md` under the pack root,
with YAML frontmatter carrying at minimum `name` and `description` (the body is
free-form Markdown, by convention including a "When to Use" trigger section).
This file lives at `ast-lens/skills/symbolic-edits/SKILL.md`, so it is picked up
automatically — `pack.toml` does not enumerate skills. Once the `ast-lens` pack
is imported into a city (`gc import add …`, or vendored under the city's
`packs/`), the skill surfaces in `gc skill list` binding-qualified as
`<binding>.symbolic-edits` (e.g. `ast-lens.symbolic-edits`), and the materializer
projects it into the per-agent skills sink at `gc start`. Verify with
`gc skill list` (and `gc lint .` / `gc doctor` to surface name collisions). This
mirrors how the bundled `core` pack ships its `core.gc-*` skills, and how this
pack's companion `read-with-outline` skill is registered.
