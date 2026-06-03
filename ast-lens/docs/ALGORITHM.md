# ast-lens — The Algorithm, Mapped to the Paper

How `bin/outline.py` implements the read-side algorithm of *"The AST as LLM
Lens"*. This describes the **actual implemented behaviour** and flags where it
intentionally diverges from or simplifies the paper. For per-function detail see
[REFERENCE.md](./REFERENCE.md); for the system view see
[ARCHITECTURE.md](./ARCHITECTURE.md).

Paper labels used here: **Alg 1** = outline emission pipeline (§5.1), **§5.3** =
truncation precedence, **§5.4 / App D** = sanitisation, **App B** = per-language
significance, **App C** = the Markdown schema.

---

## 1. The pipeline (Alg 1)

Paper Algorithm 1:

```
if loc(f) < θ or skip-comment present:  return ∅          # outline not required
lang ← detectLang(f)
ast  ← parse_lang(f)
if ast is nil:                          return passthrough(f)   # graceful degradation
decls ← topLevelDecls(ast)
sig   ← significantNested_lang(ast)
doc   ← sanitise(packageDoc(ast))
outline ← render(decls, sig, doc)
while |outline| > B:  outline ← truncateStep(outline)
return outline
```

Implemented in **`outline(path, budget, threshold, fmt)`** as:

| Alg 1 step | Implementation |
|---|---|
| read file | `open(path,"rb").read()`; any error → `""` (passthrough) |
| `loc(f)` | `src.count(b"\n") + 1` |
| `loc < θ` or skip → ∅ | `EXT_LANG` lookup; if lang unknown **or** `loc < threshold` **or** `has_skip(path)` → `""` |
| `detectLang` | `EXT_LANG[ext]` |
| `parse_lang` setup | `load_parser(lang)`; `None` (missing runtime) → `""` |
| `parse`; `ast is nil` → passthrough | `do_parse(parser, src)`; `None` tree or any exception → `""` |
| `topLevelDecls` + `significantNested` + `packageDoc` | `extract(lang, root, src)` → `(decls, imports, doc)` |
| (empty file guard) | if no decls **and** no imports → `""` |
| `render` | `render(path, lang, loc, decls, imports, doc, src)` |
| `while |outline|>B: truncateStep` | `truncate(md, decls, budget)` — **one ordered pass**, not a loop |
| (schema hygiene) | `drop_empty_sections(md)` + collapse stray `\n{3,}` |
| (output shape) | `fmt=="json"` → JSON envelope; else Markdown |

### Divergences from Alg 1
- **Soft budget, single pass.** The paper loops `truncateStep` until
  `|outline| ≤ B`. ast-lens runs the §5.3 precedence as one ordered pass and
  measures size with a **cheap proxy** (`est_tokens` ≈ chars/4), not a real
  tokenizer. Consequently the budget is a *soft target*: a public-heavy file can
  exceed B because the precedence never sheds public top-level decls (see §3).
- **Empty-file guard.** ast-lens adds a "no decls and no imports → ``""``" check
  not spelled out in Alg 1, so a parseable but declaration-less file passes
  through rather than emitting a bare header.
- **`detectLang` is extension-only** (`EXT_LANG`); no content sniffing.
- **One substrate.** The paper's reference uses native ASTs per language
  (`go/parser`, CPython `ast`, `acorn`, `ts.createSourceFile`). ast-lens uses
  **canonical tree-sitter + per-grammar wheels** for all four languages — a
  deliberate clean-room substitution. Behaviour is contract-equivalent, not
  byte-equivalent.

---

## 2. Language detection & parsing

- **`EXT_LANG`** maps extensions to languages: `.go`→go, `.py`→python,
  `.ts`/`.mts`/`.cts`→typescript, `.tsx`→tsx, `.js`/`.jsx`/`.mjs`/`.cjs`→javascript.
- **`load_parser(lang)`** lazily imports `tree_sitter`, looks the grammar up in
  **`_GRAMMAR`** (module name + candidate factory functions — TS and TSX share one
  package but expose `language_typescript` / `language_tsx`), and constructs a
  `Parser`, tolerating both the ≥0.22 constructor form and older
  `set_language`/`.language` setters. Any failure → `None` → passthrough.
- **`do_parse(parser, src)`** tolerates tree-sitter's bytes-vs-str `parse()`
  signature drift by trying both.

This is the "polyglot via one substrate, graceful fallback" commitment (Alg 1 /
§4.2): a missing runtime or grammar is a passthrough, not an error.

---

## 3. Extraction (`extract`) — the model behind the schema

`extract` walks `root.named_children` once and produces `(decls, imports, doc)`:

1. **Unwrap** each child with `unwrap` (peels `export_statement` /
   `decorated_definition`, recording `exported`).
2. **Classify** via **`DECL_KINDS[lang]`** into language-neutral *categories*
   (`func`, `method`, `type`, `class`, `interface`, `enum`, `const`, `var`,
   `import`, `decorated`). Categories are the paper's Tier-2 §8.2 idea, used from
   the start so significance/visibility/render rules key off categories rather than
   raw grammar node names.
3. **Package/module doc** (`packageDoc`): the leading comment(s), or — for Python —
   the leading `expression_statement` docstring (quotes stripped). Captured only
   while no decls/doc seen yet, and only if length > 3.
4. **Imports** are collected as raw nodes and resolved later by `import_names`.
5. **Name resolution** via `find_name` (recursing one level into Go
   `*_spec` and TS/JS `variable_declarator` wrappers). A nameless `const`/`var`
   (e.g. `const foo = () => {}`) digs the bound identifier from the pre-`=`
   signature text.
6. **Significance**: for `func`/`method`/`class`, `collect_significant` walks the
   body and stores `Decl.nested`.

### Visibility (`is_private`, App B conventions)
- **Go** — capitalisation: first char not uppercase ⇒ private.
- **Python** — leading underscore ⇒ private.
- **TS/JS** — driven by the `export` keyword (`exported` from `unwrap`); no
  `export` ⇒ private.
- Empty name ⇒ private.

Drives the `*(private)*` marker and the §5.3 step-3 collapse.

### Imports (`import_names`)
- **Python** (unquoted): regex `from X.Y` / `import X.Y`, first dotted segment
  kept. Python imports *do* surface. Caveat: a combined `import a, b, c` line
  matches only the first name (`a`).
- **Go**: every quoted spec, reduced to its last path segment
  (`github.com/x/y` → `y`).
- **TS/JS**: every quoted spec, kept whole.

---

## 4. Per-language significance (App B)

App B specifies a **hybrid** classifier: a *per-language fixed list* of
significant nested constructs **plus** a *universal fallback* (any named/labelled
inner construct, or any construct with line-span ≥ 10).

Implemented in **`collect_significant(lang, body, src)`** + the **`SIGNIFICANT`**
table:

| Language | Fixed list (`SIGNIFICANT[lang]`, node→label) |
|---|---|
| Go | `go_statement`→go, `defer_statement`→defer, `select_statement`→select, `type_switch_statement`→switch, `func_literal`→closure |
| Python | `function_definition`→def, `class_definition`→class, `with_statement`→with, `try_statement`→try |
| TypeScript / TSX | `arrow_function`→arrow, `function_declaration`→func, `try_statement`→try, `jsx_element`→jsx |
| JavaScript | (same as TypeScript) |

The walk (depth-limited to `< 3`) emits, per named descendant:
- **Fixed-list match** → `"<label>: <name>"` (or bare `<label>` if unnamed), unless
  the label is `arrow`/`closure` and the span is `< 5` (suppresses trivial
  arrow/closure noise).
- **Universal fallback** → if span ≥ 10 **and** the node has a name,
  `"<node_type>: <name>"`.
- De-duped on `(start_line, label)`; **capped at 4 entries per decl**.

### How this maps to App B's prose, and where it's *lighter*
App B's prose lists finer predicates — Go "defer blocks ≥ 3 lines", "select/switch
with ≥ 3 cases", "type assertions on interface values"; Python "@dataclass",
"async def/await", "decorators with non-trivial bodies"; TS/JS "useEffect /
useMemo / useCallback", "React component (JSX root)", "JSX trees ≥ 10 lines",
"try/catch with ≥ 3-line catch". ast-lens implements a **light** version:
- It surfaces the *construct kind* (go/defer/select/switch/closure, def/class/with/
  try, arrow/func/try/jsx) and falls back to the generic *named-or-span-≥-10* rule
  for everything else.
- It does **not** count `defer`/`select`/`switch` cases or measure catch-body
  length; the span/name heuristics approximate those thresholds (e.g. the `arrow`/
  `closure` span ≥ 5 guard stands in for "non-trivial").
- `useEffect`/`useMemo`/`useCallback` and `@dataclass` are not special-cased by
  name; they surface via the generic arrow/decorated/named paths when substantial.

This is the README's "the significance pass is light" caveat made precise. The
*universal fallback* (named, or line-span ≥ 10) is implemented faithfully.

---

## 5. Rendering — the App C schema (`render`)

App C specimen (Go `state.go`):

```markdown
# state.go (847 LoC, 14 decls, package `state`)

> Package state implements user session storage backed by Redis.
> Concurrency: all exported functions are safe for parallel use.
> (truncated at 3 lines)

## Imports
fmt, os, sync, internal/foo, github.com/x/y

## Types
- `User` struct (L23-L45) - fields: ID, Name, Email
- `Repository` interface (L48-L52) - Save(u User) error

## Functions
- `NewUser(name, email string) *User` (L60-L78)
  - go: cleanup goroutine (L66-L70)
  - defer: log.Close (L75)
- `(r *userRepo) Save(u User) error` (L82-L120)
  - switch: u.Status / 4 cases (L88-L105)
- `validate(u User) error` *(private)* (L125-L140)
```

`render` produces this shape with these implemented specifics:
- **Header** `# <basename> (<loc> LoC, <N> decls)`. ast-lens does **not** append
  the `package <pkg>` clause shown in the App C specimen; the header is filename +
  LoC + decl-count only.
- **Doc blockquote** — `clean_doc` (strip comment chrome) then `sanitise`; first
  `DOC_KEEP_LINES` (3) lines as `> …`; `> (truncated)` if more existed.
- **`## Imports`** — `import_names(...)[:24]`, comma-joined (omitted if empty).
- **`## Types`** — decls whose category ∈ `TYPE_KINDS` (`type`/`interface`/`enum`/
  `class`), as `` - `<sig>`<vis> (L<l0>–<l1>) ``. ast-lens renders the bare
  signature + span; it does **not** add the specimen's `- fields: …` /
  `- Save(...) error` field/method hints.
- **`## Functions`** — `func`/`method` decls, same bullet, **plus** indented
  `  - <label> (L<a>–<b>)` sub-bullets for each significance entry.
- **`## Values`** — remaining decls (`const`/`var`/`decorated`/…), **public only**,
  capped at 12, as `` - `<name>` (<kind>, L<l0>–<l1>) `` (a bucket the App C
  specimen doesn't show; consts/vars land here rather than under Types/Functions).
- **Span anchors use an en-dash** `–` (`L<start>–<end>`), the navigation contract:
  feed the span to a targeted `Read offset/limit`.

So the schema is **structurally faithful** (header, doc blockquote, Imports, Types,
Functions with nested sub-bullets, line-span anchors, `*(private)*` marker) with
two intentional simplifications: no package clause in the header, and no
field/method hint text on Type bullets. It also adds a public-only `## Values`
bucket.

---

## 6. Truncation precedence (§5.3)

§5.3 is **normative** in the paper — two implementations must produce identical
truncation. The order:

1. Nested significant constructs inside **private** functions.
2. Nested significant constructs inside **public** functions, longest-first →
   replace with `[N nested constructs truncated]`.
3. **Private top-level decls** collapsed to a count → `(+ 12 private helpers)`.
4. **Package-doc lines** beyond the first three.
5. **Imports** collapsed to a count → `14 imports`.

Implemented in **`truncate(md, decls, budget)`** as an ordered, *text-level* pass
(re-checking `est_tokens(...) ≤ budget` after each step; returns early when it
fits):

| §5.3 step | Implementation |
|---|---|
| 1–2 (nested, private-then-public) | drop **all** `  - ` nested bullets; "private-owned first" is **approximated** (a text-level pass can't cheaply tell which nested bullets belong to private decls) |
| 3 (private decls → count) | drop every line containing `*(private)*`; append `_(+N private decls)_` |
| 4 (doc beyond first three) | drop the whole `>` blockquote (the first-three bound is already enforced upstream by `DOC_KEEP_LINES` in `render`) |
| 5 (imports → count) | replace the import list with `(<k> imports)`, `k = commas+1` |

`drop_empty_sections` then removes any `##` header left content-less by the cuts.

### Divergences from §5.3 (the implementation is best-effort, not byte-normative)
- **Markers differ.** ast-lens uses `_(+N private decls)_` and `(k imports)`; the
  paper specifies `(+ N private helpers)`, `[N nested constructs truncated]`,
  `N imports`. The *intent* (collapse-to-count) matches; the literals do not.
- **Nested cut is coarser.** Steps 1–2 are merged into a single "drop all nested
  bullets" — no private-first / longest-first ordering, no per-group
  `[N … truncated]` marker.
- **Doc cut is whole-blockquote**, relying on the `DOC_KEEP_LINES=3` bound applied
  at render time to satisfy "beyond the first three".
- **Public top-level decls are never dropped** — by design. This is why the budget
  is *soft* and why the README notes "conformance is an empirical claim": a file
  dense in public declarations can exceed B=300.

The behavioral test suite asserts the *contract* (active budget control: a default
outline stays within a small multiple of B, and is far smaller than source), not
byte-identical §5.3 output.

---

## 7. Sanitisation (§5.4 / App D)

§5.4 is the other **normative** pass: every verbatim string the outline surfaces
(package doc, top-of-file comments) lands in agent context unconditionally,
including for adversarial vendored code, so it is sanitised before render.

§5.4 steps: **(1)** truncate verbatim per decl to 240 chars; **(2)** escape lines
matching prompt-injection patterns with a `[sanitised] ` prefix; **(3)** collapse
> 3 consecutive newlines to 2.

Implemented in **`sanitise(text)`** + the **`INJECTION_PATTERNS`** list +
**`VERBATIM_CAP=240`**:
- **Escape** — each line is flagged (case-insensitive substring match) and
  prefixed `"[sanitised] "` if it contains any App D pattern: `IGNORE PREVIOUS`,
  `IGNORE ALL PREVIOUS`, `SYSTEM:`, `ASSISTANT:`, `USER:`, `<|im_start|>`,
  `<|im_end|>`, `<s>`, `</s>`, `[INST]`, `[/INST]`, `Human:`, `Assistant:`. The
  `INJECTION_PATTERNS` list is exactly App D's "Sanitisation Pattern Set".
- **Collapse** — `re.sub(r"\n{3,}", "\n\n", …)` (§5.4(3)).
- **Truncate** — if the result exceeds `VERBATIM_CAP` (240), cut to the cap,
  `rstrip()`, append `" …"` (§5.4(1)).

Properties preserved: **conservative-biased** (false positives — benign prose
flagged — acceptable; false negatives — injection emitted raw — not), and **flagged,
never dropped** (the `[sanitised]` marker stays so a reviewer can spot it).

`sanitise` is invoked from `render` on the doc blockquote (after `clean_doc`).
`outline` also applies a final whole-output `\n{3,}` collapse as belt-and-braces.

### Divergence
- **Step order.** ast-lens runs escape → collapse → truncate; the paper lists
  truncate → escape → collapse. The output guarantees (every injection line
  flagged; no 3+ newline runs; ≤ 240 verbatim chars) are identical.
- The pattern set is **fixed in code**; the paper allows operator extension via
  `ship.toml [outline.sanitisation] additional_patterns` — ast-lens does not read
  such config.

---

## 8. Output schema envelope (App C, two formats)

- **`--format md`** (default): the rendered Markdown string, or `""` on
  passthrough. The CLI writes nothing on the empty case (silent passthrough).
- **`--format json`**: a JSON envelope
  `{"file", "lang", "loc", "tokens_outline", "markdown"}` (indent 2), where
  `tokens_outline = est_tokens(md)`. This is the programmatic-consumer format the
  paper's §4.2 "Format" bullet describes (`--format json`).

---

## 9. Summary of intentional simplifications

| Area | Paper | ast-lens |
|---|---|---|
| Token budget | hard, `while`-loop to ≤ B, real tokenizer | **soft**, single pass, `est_tokens`≈chars/4; never sheds public decls |
| Parse substrate | native ASTs per language | canonical **tree-sitter** + grammar wheels (clean-room) |
| Significance | rich per-language predicates (case counts, hook names, dataclass) | **light**: construct-kind + universal named/span≥10 fallback |
| §5.3 markers | `(+N private helpers)`, `[N nested constructs truncated]`, `N imports` | `_(+N private decls)_`, drop-all-nested, `(k imports)` |
| §5.3 nesting | private-first then public-longest-first | drop **all** nested bullets (coarser) |
| Header | includes `package <pkg>` | filename + LoC + decl-count only |
| Type bullets | with field/method hint | signature + span only |
| Values | (not in specimen) | adds public-only `## Values` bucket |
| Sanitisation order | truncate → escape → collapse | escape → collapse → truncate (same guarantees) |
| Sanitisation patterns | extensible via `ship.toml` | fixed `INJECTION_PATTERNS` |

These are the documented, deliberate divergences. The **contracts** the paper
calls load-bearing — passthrough conditions (Alg 1), the line-span-anchored schema
shape (App C), public/private visibility, sanitisation flagging (§5.4/App D), and
active budget compression (§5.3) — are all honoured, and are exactly what the
behavioral test suite verifies.
