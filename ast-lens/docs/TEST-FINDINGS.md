# ast-lens — Test Hardening Findings

Output of bringing the `bin/outline.py` test suite to industry-standard
coverage (≥90% line). The emitter was treated as the system-under-test and was
**not modified**; this document records the genuine bugs, spec-vs-implementation
gaps, and deliberately-untested defensive branches surfaced along the way.

- Suite: `tests/test_outline.py` (156 tests, all passing).
- Coverage of `bin/outline.py`: **98.35% line / 96.84% branch**
  (3 statements, 5 branch arms uncovered — all defensive; see below).
- Runner: `tests/run.sh` (pytest + branch coverage, fails under the gate;
  `tests/run.sh --lint` additionally runs `ruff check`). Gate is 90% line,
  enforced by `[tool.coverage.report] fail_under` in `pyproject.toml` and
  overridable via `COV_MIN=<n>`.

---

## 1. Genuine finding: truncation does not guarantee `|outline| ≤ budget`

**Severity: spec-conformance gap (not a crash).** Left unfixed per task
instructions (do not edit the emitter).

The paper's Algorithm 1 (§5.1) specifies the emission loop as

> `While |outline| > budget: outline ← truncateStep(outline)`

i.e. truncation iterates until the outline is within the token budget, and
§5.3 calls the truncation precedence *normative* (`|outline| ≤ budget` is the
post-condition).

`truncate()` in `bin/outline.py` implements the four precedence steps as a
single non-iterating pass (drop nested → collapse private decls → drop doc →
collapse imports). Once all four steps are exhausted there is **no final hard
clamp**: if the surviving header + public-declaration bullets still exceed the
budget, the function returns content that is over budget.

**Reproduction** (`tests/fixtures/public_only.go`, 216 LoC, 20 public funcs,
no private decls / doc / imports):

```
outline(public_only.go, budget=30)  → est_tokens ≈ 163   (budget was 30)
```

All four truncation steps run (step 1 drops the nested bullets; steps 2–4 are
no-ops because there are no private decls, no doc, and no imports), leaving an
irreducible floor of public-decl bullets ≈ 163 tokens — ~5× the requested
budget.

**Why it is not caught in practice:** the default budget is 300 tokens and real
files rarely have enough *public* top-level declarations to overflow 300 tokens
once nested/private/doc/imports are shed, so the overshoot is latent. It would
bite a file with a very large public API surface under a tight budget.

**Test that documents it (asserts the *actual* behaviour, not the paper's
contract):** `TestRenderExtractEdges::test_public_only_floor_above_small_budget`
asserts `est_tokens(out) > 100` at `budget=100`. The general-budget test
`TestCompression::test_default_budget_keeps_outline_bounded` likewise only
asserts a generous `≤ 2× budget` bound rather than the paper's `≤ budget`,
precisely because the strict bound does not hold.

**Suggested fix (NOT applied):** after the four precedence steps, add a final
hard clamp — e.g. drop trailing public-decl bullets (or whole sections) until
`est_tokens ≤ budget`, mirroring the paper's `While` loop, optionally emitting a
`(+N more decls)` marker. This would make the `≤ budget` post-condition true and
let the tests assert it.

---

## 2. Minor observations (working as designed; noted for completeness)

These are *not* bugs — they are emitter design choices that the tests pin down
so future refactors don't regress them silently.

- **Python imports DO surface.** An earlier note in the original suite implied
  the quoted-string import extractor yields nothing for Python. In fact
  `import_names()` has a dedicated Python regex arm, so over-threshold
  Python files with imports render a `## Imports` section
  (`tests/fixtures/imports_only.py`,
  `TestBoundaries::test_imports_only_file`). Go/TS surface via the quoted-path
  arm.

- **Empty `import ()` blocks are dropped cleanly.** A Go `import ()` produces a
  non-empty `imports` list but zero extractable names, so `render`'s
  `if names:` guard omits the `## Imports` header entirely rather than emitting
  an empty section (`tests/fixtures/empty_import.go`,
  `test_empty_import_block_omits_imports_section`).

- **Sanitisation cap interacts with doc-line keep.** Verbatim doc is capped at
  240 chars (`VERBATIM_CAP`) *before* the 3-line `DOC_KEEP_LINES` slice, so a
  package doc whose first line is long can be truncated to a single surfaced
  line. The full App D pattern set is therefore verified at the `sanitise()`
  unit level (`TestSanitisationPatternSet`), with end-to-end surfacing checked
  on `injection.ts` and `sanitise_doc.go`.

- **`is_private("", …)` is `True` for every language.** A nameless decl is
  treated as private (defensive default) — pinned by
  `TestHelperUnits::test_is_private_empty_name_is_private`.

- **Threshold semantics.** The guard is `loc < threshold`, so a file at exactly
  `threshold` LoC (200) **is** outlined; 199 passes through. Pinned by
  `TestBoundaries::test_threshold_boundary_199_200_201`.

---

## 3. Deliberately-untested defensive branches

The following branches remain uncovered (3 statements, 5 branch arms). Each is a
guard against a malformed/degenerate AST shape that valid source does not
produce; covering them would require fabricating broken tree-sitter nodes, which
yields brittle tests of internal helpers. They are listed here so the coverage
gap is intentional and auditable rather than accidental.

| Location (line) | Branch | Why unreached by valid input |
|---|---|---|
| `find_name` 180→187 | named-children loop falls through to the `_depth < 2` recursion-then-return arm | Reached only when a decl has a `_spec`/`_declarator` child whose own `find_name` returns `None`; valid Go/TS spec/declarator nodes always carry an identifier. |
| `find_name` 185→181 | recursion into a `_spec`/`_declarator` child returns `None`, continue the loop | Same as above — the inner identifier is always present for valid declarations. |
| `unwrap` 231 | `inner is None: break` | An `export_statement` / `decorated_definition` with **zero** non-decorator/non-export named children (e.g. a malformed bare `export`). Valid re-exports (`export { x }`, `export default …`) always carry an inner node. |
| `collect_significant` 251→261 (partial) | the `walk` child matches neither the significant-`if` nor the span≥10 `elif`, then the depth-guarded recursion arm | A frequently-taken arm whose *false* side (a small, unnamed, non-significant child at max recursion depth) is the uncovered edge; covered on the true side by `test_collect_significant_universal_fallback`. |
| `extract` 298–299 | const/var regex name-dig when `find_name` returns `None` | `find_name` resolves a name for every *valid* const/var, including destructuring patterns (it returns the pattern node `{ a, b }` / `[a, b]`). The dig only runs on `ERROR`-node consts (syntactically broken source), which the parse-failure guard usually rejects before extraction. |

All other graceful-degradation paths (missing tree-sitter runtime, unknown
language, parse-returns-`None`, parser bytes/str signature variants,
`Parser(language)` vs `.language` vs `set_language()` API shims, extract-raises,
non-UTF-8 bytes, directory/short-file `has_skip`, sub-threshold / no-decls /
unsupported-extension passthrough) **are** covered — see `TestParserRuntime`,
`TestParserVersionShim`, `TestRenderExtractEdges`, `TestHelperUnits`,
`TestLanguagesEndToEnd`, and `TestPassthrough`.
