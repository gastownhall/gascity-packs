# `bin/outline.py` — Function & Constant Reference

A complete, function-by-function reference for the ast-lens outline emitter
(`bin/outline.py`). For the algorithm narrative see [ALGORITHM.md](./ALGORITHM.md);
for the pack architecture see [ARCHITECTURE.md](./ARCHITECTURE.md); for the knobs
see [CONFIG.md](./CONFIG.md).

The emitter is a clean-room, from-spec implementation of the read side of *"The
AST as LLM Lens"* (the Blackrim AST paper): §5 algorithm, App B significance, App
C schema, App D sanitisation. It is a **pure, stateless, read-only** function that
emits a compact Markdown structural summary of one source file. On any failure
path it returns the empty string (graceful passthrough), so it can never break a
caller's `Read`.

Paper-section citations below use the in-tree labels: **Alg 1** = the outline
emission pipeline (§5.1), **§5.3** = truncation precedence, **§5.4 / App D** =
sanitisation, **App B** = per-language significance, **App C** = the Markdown
schema, **§4.2** = the pure/stateless emitter commitments.

---

## Module docstring & imports

- Lines 1–22. The module docstring records the four design commitments the
  implementation honours (pure/read-only/stateless §4.2; polyglot-via-one-
  substrate with fallback-to-passthrough per Alg 1; normative truncation
  precedence §5.3; sanitisation §5.4) and states it is a from-spec build that
  deliberately does **not** match Blackrim's reference `gt outline` byte-for-byte.
- `from __future__ import annotations` (PEP 563 deferred annotations).
- `import sys, os, re, json, argparse` — the entire dependency surface of the
  module proper. tree-sitter is imported lazily inside `load_parser` so the file
  can be imported (and short-circuit to passthrough) even when the parser runtime
  is absent.

---

## Module constants

### `DEFAULT_BUDGET: int`
Default token budget **B** for a single outline. Read from env
`AST_LENS_BUDGET`, falling back to `"300"`, parsed as `int`. Maps to the paper's
$\budget = 300$ (App F / problem formulation). Used as the `argparse` default for
`--budget`. The budget is a **soft** target (see `est_tokens` / `truncate`).

### `DEFAULT_THRESHOLD: int`
Default LoC threshold **θ_L** below which a file is not outlined. Read from env
`AST_LENS_THRESHOLD`, falling back to `"200"`, parsed as `int`. Maps to the
paper's $\threshold = 200$ LoC. Used as the `argparse` default for `--threshold`
and as the gate in `outline()` (Alg 1's "outline not required" branch).

### `DOC_KEEP_LINES: int = 3`
Number of package/module-doc lines kept in the rendered blockquote before a
`> (truncated)` marker is appended. Implements §5.3 step 4 ("package-doc lines
beyond the first three"). Consumed in `render()`.

### `VERBATIM_CAP: int = 240`
Maximum characters of verbatim doc text emitted per top-level decl. Implements
§5.4(1) ("verbatim text per top-level decl is capped at 240 characters").
Consumed in `sanitise()`.

### `EXT_LANG: dict[str, str]`
File-extension → language-name map used by `outline()` to detect language
(`detectLang` in Alg 1). Covers Go (`.go`), Python (`.py`), TypeScript
(`.ts`/`.mts`/`.cts` → `typescript`, `.tsx` → `tsx`), and JavaScript
(`.js`/`.jsx`/`.mjs`/`.cjs` → `javascript`). An extension absent from this map
yields passthrough.

### `INJECTION_PATTERNS: list[str]`
The literal prompt-injection / role-impersonation / model-control strings that
`sanitise()` flags (case-insensitively) with a `[sanitised] ` prefix. This is the
App D pattern set: `IGNORE PREVIOUS`, `IGNORE ALL PREVIOUS`, `SYSTEM:`,
`ASSISTANT:`, `USER:`, the ChatML tokens `<|im_start|>` / `<|im_end|>`, the
LLaMA-family `<s>` / `</s>`, the instruct markers `[INST]` / `[/INST]`, and the
Anthropic-style `Human:` / `Assistant:`. Patterns are **flagged, never dropped**
(conservative-biased: false positives acceptable, false negatives not).

### `DECL_KINDS: dict[str, dict[str, str]]`
Per-language map of **tree-sitter node type → language-neutral declaration
category**. Categories (`func`, `method`, `type`, `class`, `interface`, `enum`,
`const`, `var`, `import`, `decorated`) are deliberately language-neutral — the
paper's Tier-2 §8.2 "category" idea, adopted from the start so the rest of the
code (visibility, render bucketing, significance) keys off categories, not raw
grammar names. Entries:
- **go**: `function_declaration`→func, `method_declaration`→method,
  `type_declaration`→type, `import_declaration`→import, `const_declaration`→const,
  `var_declaration`→var.
- **python**: `function_definition`→func, `class_definition`→class,
  `decorated_definition`→decorated, `import_statement`/`import_from_statement`→import.
- **typescript**: function/class/interface/type-alias/enum declarations,
  `lexical_declaration`→const, `variable_declaration`→var, `import_statement`→import,
  `abstract_class_declaration`→class.
- **javascript**: function/class declarations, lexical/variable declarations,
  imports.
- `DECL_KINDS["tsx"]` aliases `DECL_KINDS["typescript"]` (line 96).

Consumed by `extract()` to classify each top-level node.

### `SIGNIFICANT: dict[str, dict[str, str]]`
Per-language fixed list of **significant nested constructs** (App B), expressed
as `node_type → display_label`. Entries:
- **go**: `go_statement`→go, `defer_statement`→defer, `select_statement`→select,
  `type_switch_statement`→switch, `func_literal`→closure.
- **python**: `function_definition`→def, `class_definition`→class,
  `with_statement`→with, `try_statement`→try.
- **typescript**: `arrow_function`→arrow, `function_declaration`→func,
  `try_statement`→try, `jsx_element`→jsx.
- **javascript**: same as typescript.
- `SIGNIFICANT["tsx"]` aliases `SIGNIFICANT["typescript"]` (line 110).

Consumed by `collect_significant()`. This is the *fixed list* half of the paper's
hybrid scheme; the *universal fallback* (named, or line-span ≥ 10) lives in the
same function.

### `_GRAMMAR: dict[str, tuple[str, list[str]]]`
Language → (tree-sitter grammar **module name**, list of **language-factory
function names** to try) map. Drives dynamic grammar loading in `load_parser`:
- go → (`tree_sitter_go`, `["language"]`)
- python → (`tree_sitter_python`, `["language"]`)
- javascript → (`tree_sitter_javascript`, `["language"]`)
- typescript → (`tree_sitter_typescript`, `["language_typescript"]`)
- tsx → (`tree_sitter_typescript`, `["language_tsx"]`)

The two-name list exists because TS and TSX share one grammar package but expose
two different language factories.

### `TYPE_KINDS: set[str]` (line 326)
The decl categories rendered under the `## Types` heading: `{"type",
"interface", "enum", "class"}`. Consumed by `render()` to split decls into the
Types / Functions / Values buckets. (Defined just above `render` rather than with
the other top-of-file constants.)

---

## Functions

### `est_tokens(s: str) -> int`
**Cheap tokenizer proxy.** Returns `(len(s) + 3) // 4`, i.e. ceil(chars / 4) — the
standard ~4-chars-per-token heuristic. The budget is measured against this proxy,
not a real LLM tokenizer, which is why the budget is a **soft** target.
- **Param** `s` — any string.
- **Returns** estimated token count (int).
- **Paper** §5.3 budget machinery; the proxy is an intentional simplification of
  the paper's $|\outline(\file)|$ "token count under the LLM tokenizer".

### `sanitise(text: str) -> str`
**The §5.4 / App D sanitisation pre-pass** over verbatim file content (package
doc, top-of-file comments). Steps, in order:
1. Empty input → `""`.
2. For each line, if any `INJECTION_PATTERNS` literal appears (case-insensitive,
   `pat.lower() in line.lower()`), prefix the line with `"[sanitised] "`. App D
   "escape" step. Flagged, never dropped.
3. Collapse runs of 3+ newlines to exactly 2 (`re.sub(r"\n{3,}", "\n\n", …)`) —
   §5.4(3), defeats layout-injection.
4. If the result exceeds `VERBATIM_CAP` (240) chars, truncate to the cap,
   `rstrip()`, and append `" …"` — §5.4(1).
- **Param** `text` — raw verbatim doc text.
- **Returns** sanitised (flagged + collapsed + capped) text.
- **Note** the implementation applies the steps in the order escape → collapse →
  truncate; the paper lists them truncate → escape → collapse, but the set of
  output guarantees is identical.

### `load_parser(lang: str)`
**Returns a tree-sitter `Parser` configured for `lang`, or `None`** (→
passthrough). Robust against multiple tree-sitter API generations:
1. Lazy-imports `tree_sitter.Language` / `Parser`; ImportError → `None`.
2. Looks `lang` up in `_GRAMMAR`; unknown lang → `None`.
3. `__import__`s the grammar module, finds the first present factory function
   from the candidate list, builds a `Language(factory())`.
4. Tries `Parser(language)` (tree-sitter ≥ 0.22 constructor form); on `TypeError`
   falls back to `Parser()` then `p.language = language`, then `p.set_language(language)`
   (older APIs).
5. Any exception anywhere → `None`.
- **Param** `lang` — a language name (a value from `EXT_LANG`).
- **Returns** a `Parser` or `None`.
- **Paper** Alg 1 `parse_lang` setup; "graceful fallback-to-passthrough on
  missing runtime".

### `do_parse(parser, src: bytes)`
**Version-tolerant parse.** tree-sitter's `parse()` accepts `bytes` in some
versions and `str` in others; this tries `src` (bytes) then
`src.decode("utf-8","replace")` (str), swallowing `TypeError` to retry and any
other exception to `None`.
- **Params** `parser` — a tree-sitter Parser; `src` — source bytes.
- **Returns** a parsed `Tree`, or `None` on failure (→ passthrough).
- **Paper** Alg 1 `parse`; the "AST is nil → passthrough" branch.

### `node_text(src: bytes, node) -> str`
**Extracts the source text of a node** as a `str`. Prefers `node.text`
(decoding bytes if needed); falls back to slicing `src[node.start_byte:node.end_byte]`.
All decoding uses `errors="replace"`.
- **Params** `src` — source bytes; `node` — a tree-sitter node.
- **Returns** the node's text.

### `find_name(node, _depth=0)`
**Best-effort declaration-name node finder.** Resolution order:
1. `node.child_by_field_name("name")` if present.
2. Else the first named child whose type is `identifier`, `type_identifier`, or
   `property_identifier`.
3. Else (recursing up to `_depth < 2`) descend into wrapper nodes whose type ends
   in `_spec` / `_declarator` or is `lexical_declaration` / `variable_declaration`
   — this handles Go (`type_spec`/`const_spec`/`var_spec`) and TS/JS
   (`variable_declarator`), where the identifier hangs off an inner node.
- **Params** `node` — a declaration node; `_depth` — recursion guard (internal).
- **Returns** the name node, or `None`.

### `clean_doc(text: str) -> str`
**Strips comment chrome** from a doc blob line-by-line: removes a leading
`/**`/`/*`/`*/`/`*`/`//`(+)/`#`(+) run (and one optional following space) per
`re.sub(r"^\s*(/\*\*?|\*/|\*|//+|#+)\s?", "", ln)`, trims, and drops blank lines.
- **Param** `text` — a raw comment/docstring blob.
- **Returns** chrome-free doc text (`"\n"`-joined).
- **Note** applied to the doc *before* `sanitise` in `render()`.

### `is_private(lang: str, name: str, exported: bool) -> bool`
**Per-language visibility rule.** Empty name → `True` (private). Then:
- Go: private iff the first character is not uppercase (Go capitalisation rule).
- Python: private iff the name starts with `_`.
- TS/JS (default branch): private iff `exported` is `False` (i.e. driven by the
  `export` keyword, captured upstream by `unwrap`).
- **Params** `lang`; `name` — the decl's name; `exported` — whether an `export`
  wrapper was peeled.
- **Returns** `True` if private/unexported.
- **Paper** App B per-language conventions; gates the `*(private)*` marker and the
  §5.3 step-3 collapse.

### `unwrap(node)`
**Peels `export_statement` / `decorated_definition` wrappers** to the carried
declaration, recording whether an `export` was seen. Loops while the node type is
a wrapper: sets `exported=True` for `export_statement`; then finds the inner decl
via field `declaration`/`definition`, else the first named child that is not a
`decorator`/`export`; breaks if none.
- **Param** `node` — a top-level child node.
- **Returns** `(inner_node, exported: bool)`.
- **Paper** supports App B visibility (TS `export`, Python decorators).

### `collect_significant(lang: str, body, src: bytes)`
**The App B significance classifier** (fixed list + universal fallback). Walks the
body's named descendants (depth-limited to `< 3`), and for each child computes its
line span (`end_point[0] - start_point[0] + 1`):
- If the child type is in `SIGNIFICANT[lang]` **and** (the label is not
  `arrow`/`closure` **or** span ≥ 5): emit `"<label>: <name>"` (or bare `<label>`
  when no name), with the 1-based span. The span ≥ 5 guard suppresses trivial
  arrow/closure noise.
- Else if span ≥ 10 **and** the node has a name: emit `"<node_type>: <name>"`
  (the universal fallback for unrecognised-but-substantial named constructs).
- De-dupes on `(start_line, label-or-"blk")` via a `seen` set.
- **Caps the result at 4 entries per decl** (`found[:4]`).
- **Params** `lang`; `body` — the decl's body node (or the decl itself);
  `src` — source bytes.
- **Returns** `list[tuple[str, int, int]]` of `(label, l0, l1)` (1-based lines).
- **Paper** App B (per-language fixed list + universal fallback "named or line-span
  ≥ 10"). Note this implements a **lighter** version than the full prose rules
  (e.g. "defer ≥ 3 lines", "switch ≥ 3 cases" are approximated by the generic
  span/name heuristics).

### `first_sig_line(src: bytes, node) -> str`
**Computes a decl's signature line** = the node's first source line, stripped,
with a trailing `{` or `(` removed, capped at 120 chars (body elided).
- **Params** `src`; `node`.
- **Returns** the signature string.
- **Paper** App C — the backticked signature on each decl bullet. **Caveat:**
  multi-line signatures collapse to their first line only (documented limitation).

### `extract(lang: str, root, src: bytes)`
**The core top-level walk** — Alg 1's `topLevelDecls` + `packageDoc` +
significance harvest. Iterates `root.named_children`:
1. `unwrap`s each child (peeling export/decorator) and classifies via
   `DECL_KINDS[lang]`.
2. **Module/package doc**: while no decls and no doc yet, if the node is a
   `comment` (any lang) or a Python `expression_statement` (the leading
   docstring), capture its text. Python docstrings get their surrounding quotes
   stripped. Only captured if length > 3.
3. Skips nodes with no recognised kind. `import` kinds are collected into
   `imports` (raw nodes, parsed later by `import_names`).
4. For a decl: resolves its name via `find_name`; if a `const`/`var` has no name
   (e.g. `const foo = () => {}`), digs the bound identifier out of the
   pre-`=` signature text by regex. Builds a `Decl` with kind, name,
   `first_sig_line` signature, 1-based start/end lines, and `is_private(...)`.
5. For `func`/`method`/`class`, runs `collect_significant` over the node's `body`
   field (or the node itself) and stores it in `Decl.nested`.
- **Params** `lang`; `root` — the AST root node; `src` — source bytes.
- **Returns** `(decls: list[Decl], imports: list[node], doc: str)`.
- **Paper** Alg 1 (`topLevelDecls`, `significantNested`, `packageDoc`).

### `import_names(lang: str, src: bytes, nodes)`
**Resolves import statement nodes to short module names.** For Python (unquoted
imports) regex-matches `from X.Y …` / `import X.Y` and keeps the first dotted
segment. For other langs, pulls every quoted string; for Go keeps the last
path segment (`a/b/c` → `c`), otherwise keeps the full quoted spec.
- **Params** `lang`; `src`; `nodes` — the import nodes from `extract`.
- **Returns** `list[str]` of import names (order-preserving, with duplicates).
- **Paper** App C `## Imports` line. **Behavioural notes:** Python imports are
  unquoted, so the regex branch handles them and they *do* surface (e.g.
  `import os` → `os`, `from collections import OrderedDict` → `collections`); the
  quoted-string branch is for Go/TS/JS only. One quirk: a single multi-name Python
  `import a, b, c` line is matched by `import\s+([\w.]+)`, which captures only the
  first name (`a`) — so a combined import statement under-reports. Go specs are
  reduced to their last path segment (`github.com/x/y` → `y`); TS/JS keep the full
  quoted module specifier.

### `render(path, lang, loc, decls, imports, doc, src) -> str`
**Renders the App C Markdown schema** from the extracted model. Builds:
- Header: `# <basename> (<loc> LoC, <N> decls)`.
- Doc blockquote (if any): `clean_doc` then `sanitise`, first `DOC_KEEP_LINES`
  lines as `> …`, plus `> (truncated)` if more existed.
- `## Imports`: `import_names(...)[:24]` joined with `, ` (only if non-empty).
- `## Types`: each decl whose kind ∈ `TYPE_KINDS`, as
  `` - `<sig>`<vis> (L<l0>–<l1>) ``, where `<vis>` is `" *(private)*"` when private.
- `## Functions`: each `func`/`method`, same bullet shape, **plus** indented
  `  - <label> (L<a>–<b>)` sub-bullets for each `Decl.nested` entry.
- `## Values`: the remaining (`others`) decls, **public only**
  (`if not d.private`), capped at 12, as `` - `<name>` (<kind>, L<l0>–<l1>) ``.
- Joins with `\n`, `rstrip()`s, appends a trailing newline.
- **Params** `path`; `lang`; `loc`; `decls`; `imports`; `doc`; `src`.
- **Returns** the rendered (pre-truncation) Markdown.
- **Paper** App C schema + `render` in Alg 1. Note the en-dash `–` in spans (test
  suite keys on this) and that `## Values` intentionally shows only public values.

### `truncate(md: str, decls, budget: int) -> str`
**The §5.3 truncation precedence**, applied by trimming the *rendered text*
section-by-section (re-render is deliberately avoided). Returns immediately if
`est_tokens(md) <= budget`. Otherwise, in order, re-checking `fits()` after each:
1. **Drop nested bullets** — every `  - ` line (private-owned-first is
   *approximated*, since the text-level pass cannot cheaply distinguish
   private-owned nested constructs). Covers §5.3 steps 1–2.
2. **Collapse private decls** — drop every line containing `*(private)*`, count
   them, append `_(+N private decls)_`. §5.3 step 3.
3. **Drop the doc blockquote** — every `>`-prefixed line. §5.3 step 4 (the
   implementation drops the whole doc rather than only lines beyond the first
   three; `DOC_KEEP_LINES` already bounded it upstream in `render`).
4. **Collapse imports** — replace the import list line with `(<k> imports)` where
   `k = commas + 1`. §5.3 step 5.
Returns the trimmed text (`rstrip` + trailing newline) at whichever step it fits,
or after step 4 regardless.
- **Params** `md` — rendered Markdown; `decls` — the decl list (unused by the
  text-level passes but kept for signature parity with a re-render strategy);
  `budget` — token budget.
- **Returns** the budget-reduced Markdown.
- **Paper** §5.3 normative precedence. **Divergence:** the paper's precedence is
  normative and operates on the model (private-nested first, public-nested
  longest-first, with literal `[N nested constructs truncated]` markers); this
  implementation is a *best-effort text-level approximation* using collapse
  markers like `_(+N private decls)_` and `(k imports)`, and the budget is soft
  (measured via `est_tokens`). Public top-level decls are **never** dropped.

### `drop_empty_sections(md: str) -> str`
**Removes `## Section` headers left content-less** after truncation. For each
`## ` line, scans forward until the next `## `/`# ` header; if no non-blank,
non-collapse-marker (`_(+`) line is found in between, the header is omitted.
- **Param** `md` — (typically post-`truncate`) Markdown.
- **Returns** Markdown with empty section headers removed (`rstrip` + newline).
- **Paper** schema-hygiene step; keeps the App C output well-formed after §5.3
  cuts.

### `has_skip(path) -> bool`
**Detects the `outline:skip` escape hatch.** Opens the file (utf-8,
`errors="replace"`), reads up to the **first 5 lines**, returns `True` if any
contains the literal `outline:skip`. Any exception → `False`.
- **Param** `path` — file path.
- **Returns** `True` if the file opts out.
- **Paper** §5 / §4 escape hatch (`// outline:skip` / `# outline:skip` in the first
  five lines).

### `outline(path, budget, threshold, fmt)`
**The top-level pipeline (Alg 1).** The single entry point used by `main`, the
CLI wrapper, the hook, and the tests. Steps:
1. Read the file as bytes; any error → `""` (passthrough).
2. `loc = bytes.count(b"\n") + 1`.
3. Detect `lang` via `EXT_LANG`. If lang is unknown, `loc < threshold`, or
   `has_skip(path)` → `""` (Alg 1 "outline not required").
4. `load_parser(lang)`; `None` → `""` (missing runtime → passthrough).
5. `do_parse`; `None` tree → `""`; harvest with `extract`; any exception → `""`
   (parse failure → passthrough).
6. If no decls and no imports → `""`.
7. `render` → `truncate` → `drop_empty_sections` → collapse stray 3+ blank runs.
8. If `fmt == "json"`, return a JSON envelope `{file, lang, loc, tokens_outline,
   markdown}` (indent 2); else return the Markdown.
- **Params** `path`; `budget`; `threshold`; `fmt` (`"md"` | `"json"`).
- **Returns** the outline string, or `""` on any passthrough condition.
- **Paper** Alg 1 end-to-end (with §5.3 truncation and §5.4 sanitisation invoked
  via `render`/`truncate`). **Divergence from Alg 1's `while` loop:** the paper
  loops `truncateStep` until `<= budget`; here truncation is a single ordered
  pass and the budget is soft, so public-heavy files can exceed B (the
  precedence never sheds public top-level decls).

### `main(argv=None)`
**CLI entry point.** Builds an `argparse` parser with positional `file` and
options `--budget` (default `DEFAULT_BUDGET`), `--threshold` (default
`DEFAULT_THRESHOLD`), `--format` (`{md, json}`, default `md`). Calls
`outline(...)`, writes any non-empty result to `stdout`, returns `0`.
- **Param** `argv` — optional arg vector (defaults to `sys.argv[1:]`); useful for
  testing.
- **Returns** `0` (exit code).
- **Note** writing nothing on the empty-string case is what makes the CLI a silent
  passthrough — the property the hook and the `bin/outline` wrapper rely on.

### Module guard
`if __name__ == "__main__": raise SystemExit(main())` — runs the CLI when invoked
directly (`bin/outline.py <file>`), propagating `main`'s return as the exit code.

---

## Class

### `Decl`
A `__slots__` value object for one top-level declaration. Slots:
`kind` (category str), `name` (str), `sig` (signature line str), `l0`/`l1`
(1-based start/end lines), `private` (bool), `nested` (list of
`(label, l0, l1)` significance tuples, defaulted to `[]` in `__init__`).
`__init__(self, kind, name, sig, l0, l1, private)` sets all but `nested`.
Constructed in `extract`, consumed in `render`.

---

## Coverage note

Every top-level `def` in `bin/outline.py` is documented above: `est_tokens`,
`sanitise`, `load_parser`, `do_parse`, `node_text`, `find_name`, `clean_doc`,
`is_private`, `unwrap`, `collect_significant`, `first_sig_line`, `extract`,
`import_names`, `render`, `truncate`, `drop_empty_sections`, `has_skip`,
`outline`, `main` — plus the `Decl` class, the `__main__` guard, and every module
constant (`DEFAULT_BUDGET`, `DEFAULT_THRESHOLD`, `DOC_KEEP_LINES`, `VERBATIM_CAP`,
`EXT_LANG`, `INJECTION_PATTERNS`, `DECL_KINDS`, `SIGNIFICANT`, `_GRAMMAR`,
`TYPE_KINDS`).
