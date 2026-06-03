<div align="center">

# `ast-lens`

### AST-native reading & editing for Gas City agents

Agents **read** a compact AST outline instead of whole files (**~94–98% fewer tokens**),
and **edit** through compile-gated symbolic ops that can't commit a change the gate can't
prove safe. A clean-room implementation of
*[The AST as LLM Lens](https://github.com/jsgerman-oss/research/tree/main/blackrim-ast-paper)*.

[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Gas City](https://img.shields.io/badge/Gas_City-pack-0f766e?style=flat-square)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)]()
[![Lens](https://img.shields.io/badge/lens-Go_Python_TS_JS-444?style=flat-square)]()
[![Tests](https://img.shields.io/badge/tests-269_passing-brightgreen?style=flat-square)]()
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen?style=flat-square)]()
[![Token savings](https://img.shields.io/badge/savings-94--98%25-0f766e?style=flat-square)]()
[![Edits](https://img.shields.io/badge/edits-compile--gated-c2410c?style=flat-square)]()

[**Quick start**](#quick-start) ·
[**How it works**](#how-it-works) ·
[**The emitter**](#the-emitter) ·
[**Write side**](#write-side) ·
[**Install**](#install--uninstall) ·
[**Config**](#configuration) ·
[**Docs**](#documentation) ·
[**Tests**](#tests) ·
[**Lineage**](#research-lineage)

</div>

---

## The read tax

An LLM agent mapping a codebase will `Read` dozens of files before answering a single
question. At ~10 tokens per source line, a 2,700-line file is ~27,000 input tokens —
and most of that is *function bodies the agent never needed to answer a structural
question.* **ast-lens** interposes the abstract syntax tree: it emits a ~300-token
Markdown **outline** of a file's declarations, types, and signatures — each anchored
to its line span — so the agent navigates by structure and fetches a body only when
it has to.

```markdown
# catalog.ts (565 LoC, 15 decls)

> Product catalogue — single source of truth for the storefront.

## Types
- `interface Product` (L55–92)
- `interface CatalogIndex` (L95–99)

## Functions
- `function getProduct(slug: string): Product | undefined` (L496–498)
- `function indexByEra(slug: string, now: Date): CatalogIndex` (L539–564)
```

> _565 lines → a handful. The agent reads this, then `Read offset:496 limit:3` for the
> one body it wants._

## Measured savings

Real files, full `Read` vs. outline (≈4 chars/token):

| File | Lang | LoC | Full → outline | Saved |
|------|:----:|----:|---------------:|------:|
| `catalog.ts` | TS | 564 | 5,511 → 302 tok | **94.5%** |
| `repository.ts` | TS | 511 | 4,877 → 270 tok | **94.5%** |
| `walker_go.go` | Go | 457 | 3,133 → 79 tok | **97.5%** |
| `test_main_endpoints.py` | Py | 1,420 | 13,607 → 803 tok | **94.1%** |

_Public-API-heavy files compress less (~90%) because the outline never drops a public
declaration — see [Caveats](#caveats)._

## What's in the box

| Layer | What it is | File | Paper § |
|-------|------------|------|:-------:|
| **Emitter** | the outline function (Go/Py/TS/JS) | `bin/outline` → `bin/outline.py` | §5 · App B/C/D |
| **Skill** | teaches agents to outline-before-`Read` | `skills/read-with-outline/SKILL.md` | §4.2 |
| **Prompt fragment** | the discipline, in every agent's context | `template-fragments/read-with-outline.template.md` | §4.3 |
| **PreToolUse hook** | auto-prepends the outline to a `Read` | `overlay/…/settings.json` + `hooks/outline-on-read.sh` | §4.1 |
| **Write side** | gate + plan/execute + ops + YAML pattern-DSL + skill | `astlens/`, `bin/op` | §5.5 · §5.6 · §4.D/E |
| **Tests** | 269 behavioral (read + write side) | `tests/` | §5.3 · §5.4 |

This is the paper's read side (_one emitter, three surfaces_ + the system-prompt
discipline) **and** its write side (compile-gated plan/execute symbolic surgery).

## Quick start

```bash
./setup.sh                           # one-time: build the venv (tree-sitter + grammars)
./bin/outline path/to/file.ts        # print the Markdown outline (silent if < 200 LoC)
./bin/outline --format json file.go  # machine-readable
```

## How it works

`outline(file)` is a pure, stateless, read-only function:

1. **Detect** the language by extension; **parse** with canonical `tree-sitter`.
2. **Extract** top-level declarations, significant nested constructs, imports, and the
   sanitised package doc.
3. **Render** the line-anchored Markdown schema.
4. **Truncate** to a ~300-token budget by a normative precedence — private internals
   first, then public-function internals, then private declarations collapse to a count.

It degrades to **empty output (passthrough)** for files under 200 LoC, unsupported
languages, an `outline:skip` comment, a missing parser, or any parse error — so it can
**never break a `Read`**. Verbatim file text surfaced by the lens runs through a
prompt-injection **sanitiser**: the outline auto-prepends to a `Read`, so untrusted
vendored code can't smuggle instructions into agent context.

## Write side

Reading is half the story; the write side lets agents *change* code without silently
breaking it. The contract is **plan → gate → execute**:

- **`op` emits a plan** — a Markdown description of the proposed edit (target, scope,
  diff, predicted verdict) plus a content-hash **token**. Read-only.
- **`op!` executes it** — recomputes the change and writes **only if the compile gate
  accepts**. The gate is _false-negative-only_: it materialises the change in a temp
  copy, runs the language's native syntax check, and rejects anything it can't prove
  safe (no checker ⇒ reject). It never touches the working tree until the verdict is in.

Because plans are stateless and content-addressed, **a plan is a bead payload** — a
polecat emits it, the refinery runs the gated `op!` later. If the file changed since
planning, the token mismatches and execute aborts (re-plan).

```bash
bin/op fix-imports  src/server.go            # plan (read-only)
bin/op fix-imports! src/server.go <token>    # gated execute
```

| Op | Scope | Backed by |
|----|-------|-----------|
| `fix-imports` | Go + Python | `goimports` / `ruff` |
| `rename-symbol` | Go, cross-file, **compile-aware** | `gopls` rename |
| `extract-to-package` | Go, exported decl (conservative) | `tree-sitter-go` + `gofmt` |

`rename-symbol` is type-aware — it renames a package-level `Count` without touching a
shadowing local of the same name; `extract-to-package` `go build`s its result before
returning it. New ops can be authored as **YAML pattern intents** — `remove-console`,
`no-var`, … — via the [pattern-DSL](docs/PATTERN-DSL.md); agents reach the write side
through the **`symbolic-edits` skill**; and a plan can be filed as a **bead** and applied
gated through the refinery ([details](docs/REFINERY-INTEGRATION.md)). Full contract:
[`docs/WRITE-SIDE.md`](docs/WRITE-SIDE.md).

## Install & uninstall

Turn it on for **one rig** or the **whole town**, reversibly:

```bash
./setup.sh                        # build the emitter venv (one-time)

./install.sh --rig myrig          # one rig: skill + PreToolUse hook for its agents
./install.sh --town               # city-wide: + opts the discipline fragment into every agent

./uninstall.sh --rig myrig        # clean reversal (strips the merged hook too)
./uninstall.sh --town --purge     # …and drop the venv
```

Both are idempotent, back up any config they touch, and support `--dry-run`. The pack
imports via a direct `source = "packs/ast-lens"` entry (the gas-town convention); gc
**deep-merges** the Claude `PreToolUse` hook into projected settings without clobbering
the core hooks. Full lifecycle: [`docs/INSTALL.md`](docs/INSTALL.md).

## Configuration

| Knob | Default | Set via |
|------|:-------:|---------|
| Token budget | `300` | `--budget`, `AST_LENS_BUDGET` |
| LoC threshold | `200` | `--threshold`, `AST_LENS_THRESHOLD` |
| Output format | `md` | `--format md\|json` |
| Skip a file | — | `// outline:skip` in its first lines |
| Disable the hook | — | `BLACKRIM_DISABLE_OUTLINE_HOOK=1` |

Full reference: [`docs/CONFIG.md`](docs/CONFIG.md).

## Documentation

| Doc | |
|-----|-|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | the one-emitter / three-surfaces design + data flow |
| [`docs/ALGORITHM.md`](docs/ALGORITHM.md) | the emitter mapped to the paper (Alg 1, §5.3, §5.4, App C) |
| [`docs/WRITE-SIDE.md`](docs/WRITE-SIDE.md) | the compile gate + plan/execute contract + symbolic ops |
| [`docs/REFERENCE.md`](docs/REFERENCE.md) | every function + constant in `outline.py` |
| [`docs/CONFIG.md`](docs/CONFIG.md) | every configuration knob |
| [`docs/INSTALL.md`](docs/INSTALL.md) | install / uninstall, per rig & town |
| [`docs/hook-projection-findings.md`](docs/hook-projection-findings.md) | how the Claude hook merges into gc |

## Caveats

- **The token budget is a soft target.** Public-heavy files exceed it — the truncation
  precedence never drops _public_ top-level declarations (they're the signal). This
  matches the paper's "conformance is an empirical claim."
- **Activation is deliberate.** The PreToolUse hook fires on _every_ `Read` once
  enabled; prefer a single rig first.
- **Warn-mode only.** The paper's 80%-adoption → block-mode escalation is future work.
- Multi-line signatures collapse to their first line; the significance pass is light.

## Tests

```bash
tests/run.sh        # 240 tests + branch coverage, gated at 90% (ruff clean)
```

They assert the paper's **contracts** — read side (passthrough, schema shape, line-span
anchors, public/private, every sanitisation pattern, the truncation precedence,
compression) and write side (gate accept/reject, plan-token drift detection, each op's
correctness) — not byte-equality with any other tool.

## Research lineage

ast-lens is a clean-room build of **_[The AST as LLM Lens: Outline-First Reading and
Compile-Gated Symbolic Surgery](https://github.com/jsgerman-oss/research/tree/main/blackrim-ast-paper)_**,
implemented from the paper's §5 algorithm and appendix — not ported from the reference
`gt`. Both halves are here — outline-first reading **and** compile-gated symbolic surgery —
including the YAML pattern-DSL (§4.E) that the paper itself defers.

## License

MIT © Jay German. See [LICENSE](LICENSE).
