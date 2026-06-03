---
name: read-with-outline
description: Read large source files outline-first. Before Read-ing any code file ≥200 LoC, run `outline <file>` to get a compact structural map, then Read only the specific bodies you need via the L<start>–<end> line-span anchors. Use whenever you are about to open, scan, or navigate a source file (Go, Python, TypeScript, JavaScript).
---

# Read With Outline

## Overview

Reading a whole source file to find one function is wasteful: it floods the
context window with tokens you will not use and buries the structure you
actually need. The `outline` emitter (shipped in this pack at `bin/outline`)
is a read-only, stateless lens that parses a file's AST and prints a compact
Markdown map — top-level declarations, types, functions with their signatures,
imports, and a sanitised doc summary — with every declaration carrying an
`L<start>–<end>` line-span anchor.

**The discipline: outline first, Read second.** For any source file of 200 LoC
or more, run `outline <file>` *before* `Read`. Treat the outline as the primary
lens. Only `Read` a specific region — using the line-span anchors as
`offset`/`limit` — when you need a body the outline does not already answer.
This is the agent-facing half of the pack's outline-first reading discipline.

## When to Use

- You are about to `Read` a source file you have not seen and it is ≥200 LoC.
- You need to locate a specific type, function, or method inside a large file.
- You are mapping the structure of an unfamiliar module before editing it.
- You want a signature, the import set, or "where does X live" — not the body.

**When NOT to use:**

- Files under 200 LoC — `outline` stays silent for them by design; just `Read`.
- Non-source files (Markdown, JSON, config, logs, data) — `outline` only
  handles Go, Python, TypeScript, JavaScript. `Read` these directly.
- You already hold a current outline for the file this session and just need a
  body — skip straight to the targeted `Read`.

## Process

### Step 1 — Run the outline

```bash
outline <path/to/file>
```

`bin/outline` is shipped with this pack. If it is not already on `PATH`, invoke
it by its pack-relative path (e.g. `.../packs/ast-lens/bin/outline <file>`).
It is read-only and never modifies the file. Add `--format json` if you need to
consume the outline programmatically.

### Step 2 — Read the structural summary

The emitter prints Markdown following the schema below. Read it to answer
"what's in this file and where" *without* having opened the file body. The
header gives you the size and decl count; the sections give you types,
functions (with signatures), imports, and a doc summary.

### Step 3 — Decide: is the outline enough?

Often it is. A signature, a private/public marker, the import set, or the
location of a declaration may be all the task needs — answer directly from the
outline and stop. No further `Read` required.

### Step 4 — Read only the bodies you need (line-span anchors)

When you do need an implementation, use the declaration's `L<start>–<end>`
anchor to issue a *targeted* `Read` instead of opening the whole file:

- A decl shown as `(L82–120)` → `Read` with `offset: 82`, `limit: 39`
  (limit ≈ `end − start + 1`).
- Nested significant constructs (e.g. an inner `switch` shown at `(L88–105)`)
  carry their own anchors — read just that span when that is the target.

Pad the span by a few lines if you need surrounding context, but prefer the
narrow window. The point is to fetch *that decl's body*, not re-read the file.

## The Outline Markdown Schema

Every outline follows this canonical, line-span-anchored shape. Specimen for a
hypothetical `state.go` (847 LoC, package `state`):

```markdown
# state.go (847 LoC, 14 decls, package `state`)

> Package state implements user session storage backed by Redis.
> Concurrency: all exported functions are safe for parallel use.
> (truncated at 3 lines)

## Imports
fmt, os, sync, internal/foo, github.com/x/y

## Types
- `User` struct (L23–45) - fields: ID, Name, Email
- `Repository` interface (L48–52) - Save(u User) error

## Functions
- `NewUser(name, email string) *User` (L60–78)
  - go: cleanup goroutine (L66–70)
  - defer: log.Close (L75)
- `(r *userRepo) Save(u User) error` (L82–120)
  - switch: u.Status / 4 cases (L88–105)
- `validate(u User) error` *(private)* (L125–140)
```

How to read it:

- **Header** — `# <file> (<LoC>, <N> decls[, package `<pkg>`])`. Size and
  declaration count at a glance.
- **Doc blockquote** (`>`) — a sanitised, truncated summary of the file/package
  doc. Prose matching prompt-injection patterns is left in place but tagged
  `[sanitised]`; it is marked, never silently dropped.
- **`## Imports`** — the dependency set as a flat comma-separated list.
- **`## Types`** — named types with their kind, an `L<start>–<end>` anchor, and
  a short field/method hint.
- **`## Functions`** — top-level functions and methods with full signatures and
  anchors. `*(private)*` marks unexported/private decls. Indented sub-bullets
  are *significant nested constructs* (goroutines, `defer`, `switch`/`select`,
  `useEffect`, JSX roots, etc.), each with its own line-span anchor.

The schema is **line-span-anchored**: the `L<start>–<end>` on every entry is
exactly what you feed to a targeted `Read --offset/--limit` to pull one body
without re-reading the file. That is the whole navigation loop — outline to
find the span, `Read` the span to get the code.

## Worked Example

You need the body of `Save` in the 847-LoC `state.go` above.

1. `outline state.go` → the outline shows `(r *userRepo) Save(u User) error`
   at `(L82–120)`, with an inner `switch` on `u.Status` at `(L88–105)`.
2. The outline already told you the signature and that the method branches on
   `u.Status` across 4 cases. If that answers the question, stop here.
3. If you need the implementation, `Read state.go` with `offset: 82`,
   `limit: 39` — you get just `Save`, not 847 lines. To inspect only the
   branching, `Read` `offset: 88`, `limit: 18`.

## Why This Matters

- **Token economy.** An outline is a few hundred tokens; the file may be tens
  of thousands. Outline-first reading cuts input-token cost on read-heavy work.
- **Better navigation.** The structural map plus anchors lets you jump straight
  to the relevant decl instead of scrolling a wall of source.
- **Safety.** The emitter sanitises doc text, so injection-style strings in
  comments arrive flagged rather than as raw instructions.

## Verification Gate

Before treating a large source file as "read":

- [ ] For files ≥200 LoC, `outline <file>` was run before any full `Read`.
- [ ] Structural questions (signatures, locations, imports) were answered from
      the outline, not by reading the whole file.
- [ ] Where a body was needed, it was fetched with a targeted `Read`
      offset/limit derived from an `L<start>–<end>` anchor — not a full read.

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack
contributes a skill by placing `skills/<name>/SKILL.md` under the pack root,
with YAML frontmatter carrying at minimum `name` and `description` (the body is
free-form Markdown, by convention including a "When to Use" trigger section).
This file lives at `ast-lens/skills/read-with-outline/SKILL.md`, so it is picked
up automatically — `pack.toml` does not enumerate skills. Once the `ast-lens`
pack is imported into a city (`gc import add …`, or vendored under the city's
`packs/`), the skill surfaces in `gc skill list` binding-qualified as
`<binding>.read-with-outline` (e.g. `ast-lens.read-with-outline`), and the
materializer projects it into the per-agent skills sink at `gc start`. Verify
with `gc skill list` (and `gc lint .` / `gc doctor` to surface name collisions).
This mirrors how the bundled `core` pack ships its `core.gc-*` skills.
