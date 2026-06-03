# ast-lens pattern-DSL (write-side §4.E / "Subsystem E")

The write-side spine (see `docs/WRITE-SIDE.md`) turns a transform **intent** on
a file into a gated, content-addressed plan/execute pair. Each intent is backed
by an *op* — a `compute_change(file_path, args) -> dict | None` function. Hand
-written ops live in `astlens/ops/*.py` and cost a few hundred lines of Python
apiece.

The **pattern-DSL** is the low-code path to the same place: you author an intent
as a small **YAML** file modelled on [ast-grep](https://ast-grep.github.io/) /
[Comby](https://comby.dev/), and the engine (`astlens/pattern.py`) compiles it
into a `compute_change`-compatible op automatically. A new intent costs ~tens of
lines of YAML instead of ~hundreds of Python — the paper's "intents authored per
engineer-hour" lever.

Everything the spine guarantees still holds: a pattern op **never writes files**
(it returns proposed content); the plan/execute token catches drift; and the
**compile gate** is the non-bypassable final check, so a pattern that produces a
syntactically-broken rewrite is *rejected*, never committed.

---

## Where intents live, and how they register

Drop a `*.yaml` (or `*.yml`) file in `astlens/intents/`. On startup the registry
(`astlens/registry.py`) scans that directory and surfaces each intent as an op
named by its `id`. The scan is **additive and guarded**: it never shadows or
breaks the hand-written Python ops, and a missing engine/dependency or a single
malformed intent degrades gracefully (the bad intent is listed as unavailable
and raises a clear error only when *it* is resolved).

```console
$ bin/op --list
registered ops:
  strip-trailing-ws    available
  fix-imports          available
  rename-symbol        available
  extract-to-package   available
  go-interface-any     available  [pattern] Rewrite Go empty interface{} to the any alias (Go 1.18+).
  no-var               available  [pattern] Replace the `var` keyword with `let` in JS/TS declarations.
  remove-console       available  [pattern] Drop standalone console.log/console.debug statements in JS/TS.

pattern-DSL backend: ast-grep-py
```

A pattern intent is then driven through `bin/op` exactly like any op — the
plan/execute pair, the gate, and the content-addressed token all apply:

```console
$ bin/op remove-console path/to/file.js          # PLAN (read-only) — prints the diff + token
$ bin/op remove-console! path/to/file.js <token>  # EXECUTE — writes iff the gate accepts
```

---

## The YAML schema

A minimal intent:

```yaml
id: remove-console                        # required: unique op id (the CLI name)
language: [js, ts, jsx, tsx]              # required: one name or a list
description: Drop console.log/debug …     # required: one-line summary
pattern: "console.log($$$ARGS)"          # the match (see "rule vs pattern")
# fix: …                                  # the rewrite; omit to DELETE the match
```

### Fields

| Key                 | Req? | Meaning |
| ------------------- | ---- | ------- |
| `id`                | yes  | Stable op id; the name used on the `bin/op` command line. Must be unique (and not collide with a Python op). |
| `language` / `languages` | yes | One language name or a list. Names: `js`/`javascript`, `jsx`, `ts`/`typescript`, `tsx`, `py`/`python`, `go`. A file whose extension maps to none of these yields `None` (unsupported language). |
| `description`       | yes  | One-line human summary, shown by `bin/op --list`. |
| `pattern`           | one of | A single ast-grep pattern string (e.g. `var $NAME = $INIT`). |
| `rule`              | one of | A full ast-grep **rule object** (`kind`, `has`, `inside`, `any`, `all`, `not`, …). Use this when a bare pattern is not selective enough. Exactly one of `pattern` / `rule` must be present. |
| `fix` / `rewrite`   | no   | The rewrite template. Metavariables from the match expand: `$NAME` → the captured node's text, `$$$NAME` → the verbatim source slice the multi-metavariable bound. **Omit `fix` to delete the matched node.** |
| `select`            | no   | Narrow the edit from the whole match to its first child/descendant of this **node-kind**, then apply `fix` there. Lets a rule match a large node but rewrite a single token (e.g. match a `variable_declaration` but rewrite only its `var` keyword), so surrounding structure stays byte-identical. |
| `strip_statement`   | no   | For deletions: also swallow the match's leading indentation and one trailing newline, so removing a statement leaves no blank-line residue. |
| `ast_grep_language` | no   | Override the backend language name (rarely needed; e.g. force `typescript` vs `tsx`). |

### `rule` vs `pattern`

* Reach for `pattern` when a single structural shape says it all
  (`var $NAME = $INIT`).
* Reach for `rule` when you need context — e.g. "a `console.log(...)` **only**
  when it is a standalone statement directly inside a block", which is what
  keeps `remove-console` from mangling a braceless `if (x) console.log(y);`:

  ```yaml
  rule:
    kind: expression_statement
    inside:                       # the statement's parent must be …
      any:
        - kind: statement_block   # … a { … } block …
        - kind: program           # … or the file top level
      stopBy: neighbor            # (the *immediate* parent, not any ancestor)
    has:
      any:
        - pattern: console.log($$$ARGS)
        - pattern: console.debug($$$ARGS)
  ```

The `rule` object is passed straight through to ast-grep, so any rule the
[ast-grep rule reference](https://ast-grep.github.io/reference/rule.html)
documents is available.

---

## Worked example: add a new intent

Say you want `no-debugger`: drop standalone `debugger;` statements in JS/TS.

1. Create `astlens/intents/no-debugger.yaml`:

   ```yaml
   id: no-debugger
   language: [js, ts, jsx, tsx]
   description: Drop `debugger;` statements in JS/TS.
   strip_statement: true
   rule:
     kind: debugger_statement
   # no `fix:` -> delete the matched node
   ```

2. That's it — it is registered automatically:

   ```console
   $ bin/op --list | grep no-debugger
     no-debugger          available  [pattern] Drop `debugger;` statements in JS/TS.

   $ bin/op no-debugger src/app.ts            # see the plan + token
   $ bin/op no-debugger! src/app.ts <token>    # execute (gated)
   ```

3. Add a fixture + a test alongside `tests/test_pattern_dsl.py` asserting it
   transforms a sample as intended and the result still passes the gate.

### Tips for safe intents

* **Let the gate be the safety net, but don't lean on it.** Prefer a `rule`
  that only matches what you mean (e.g. the `inside … stopBy: neighbor` guard)
  over a broad pattern that relies on the gate to reject collateral damage.
* **Use `select` to keep edits surgical.** Rewriting a single token of a larger
  node (the `no-var` pattern) avoids reconstructing — and possibly dropping —
  the parts you didn't mean to touch (a trailing `;`, a second declarator).
* **Test against the gate.** Every example intent's test asserts the rewritten
  file still parses (`gate(...) == accept`). A typed-language intent (`.ts`)
  will gate-*reject* on a host without `tsc` — that is the false-negative-only
  contract working as designed, not a bug.

---

## Bundled intents

| Intent             | Languages       | Effect |
| ------------------ | --------------- | ------ |
| `remove-console`   | js, ts, jsx, tsx | Drops standalone `console.log(...)` / `console.debug(...)` statements; preserves logs used as values and braceless-`if` bodies. |
| `no-var`           | js, ts, jsx, tsx | Rewrites the `var` keyword to `let` (preserving declarators, semicolons, `for (var …)`). |
| `go-interface-any` | go              | Rewrites the empty interface type to the `any` alias (Go 1.18+). |

---

## Backends

Per the paper's two-backend design, the engine picks the best available matcher
at runtime (`astlens.pattern.active_backend()`, also printed by
`bin/op --list`):

| Backend         | When it is used | Notes |
| --------------- | --------------- | ----- |
| `ast-grep-py`   | the `ast-grep-py` wheel is importable (the default; pinned in `requirements.txt`) | Preferred. In-process, no subprocess; embeds the tree-sitter grammars. Full `rule` grammar. |
| `ast-grep-bin`  | no wheel, but an `ast-grep`/`sg` binary is on `PATH` | Shells out to `ast-grep scan --rule <cfg> --json`. Full `rule` grammar. |
| `fallback`      | neither of the above | A minimal pure-Python matcher for the **simplest subset only**: a single-line `pattern` (no `rule`) using `$NAME` / `$$$REST` metavariables and a flat `fix` (or a deletion). Anything outside the subset returns `None` (the engine declines rather than risk a wrong edit). |

The fallback is deliberately conservative because the *gate*, not the matcher,
is the final safety net — a fallback that over-reached would only widen the set
of diffs the gate has to reject. For full structural matching, keep
`ast-grep-py` installed (it is in `requirements.txt`).

> To author/test intents against the real backend in this pack's venv:
> `.venv/bin/pip install -r requirements.txt` (installs `ast-grep-py` +
> `pyyaml`), then `.venv/bin/python -m pytest tests/test_pattern_dsl.py -q`.
