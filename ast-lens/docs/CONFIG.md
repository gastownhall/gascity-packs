# ast-lens — Configuration

Every configuration knob the pack exposes, what it does, its default, and exactly
where it is read. For the emitter internals see [REFERENCE.md](./REFERENCE.md);
for the algorithm see [ALGORITHM.md](./ALGORITHM.md). Install/uninstall is covered
in [INSTALL.md](./INSTALL.md).

The two headline defaults map to the paper's hyperparameters (App F /
reproducibility checklist): **budget B = 300 tokens**, **threshold θ_L = 200 LoC**.

---

## Quick reference

| Knob | Type | Default | Read where | Effect |
|---|---|---|---|---|
| `--budget` | CLI flag (int) | `DEFAULT_BUDGET` (300) | `main` argparse | Soft token budget for one outline |
| `--threshold` | CLI flag (int) | `DEFAULT_THRESHOLD` (200) | `main` argparse | LoC floor below which a file is not outlined |
| `--format` | CLI flag (`md`\|`json`) | `md` | `main` argparse | Output shape: Markdown or JSON envelope |
| `AST_LENS_BUDGET` | env (int string) | `300` | `DEFAULT_BUDGET` at import | Default for `--budget` |
| `AST_LENS_THRESHOLD` | env (int string) | `200` | `DEFAULT_THRESHOLD` at import | Default for `--threshold` |
| `BLACKRIM_DISABLE_OUTLINE_HOOK` | env (`=1`) | unset | `hooks/outline-on-read.sh` | Makes the PreToolUse hook a no-op |
| `outline:skip` | in-file comment | absent | `has_skip` (emitter) | Per-file opt-out (first 5 lines) |
| `PYTHON` | env (path) | `python3` | `setup.sh` | Interpreter used to build the venv |

---

## CLI flags (`bin/outline.py` → `main`)

Defined in `main()` via `argparse`:

```
bin/outline <file> [--budget N] [--threshold N] [--format {md,json}]
```

(`bin/outline` is the bash wrapper that resolves the venv and execs
`bin/outline.py`.)

### `file` (positional, required)
Path to the source file to outline. Unsupported extensions (anything outside
`EXT_LANG`: `.go`, `.py`, `.ts/.tsx/.mts/.cts`, `.js/.jsx/.mjs/.cjs`) pass through
to empty output.

### `--budget N` (int, default `DEFAULT_BUDGET` = 300)
The target token budget **B** for one outline, measured against the cheap
`est_tokens` proxy (≈ chars/4). Passed to `outline(...)` → `truncate(...)`, which
applies the §5.3 precedence (drop nested → collapse private → drop doc → collapse
imports) until the estimate fits.

**Soft target.** Public top-level decls are never dropped, so a public-heavy file
can exceed the budget. Lowering it tightens truncation; raising it (or
`--budget 100000`, as the tests do) effectively disables truncation so the full
schema renders.

Default source: `DEFAULT_BUDGET`, which reads env `AST_LENS_BUDGET` (below).

### `--threshold N` (int, default `DEFAULT_THRESHOLD` = 200)
The LoC floor **θ_L**. In `outline(...)`, if `loc < threshold` the emitter returns
`""` (Alg 1 "outline not required"). Raise it to make the emitter (and therefore
the hook) silent on more files; lower it to outline smaller files. `loc` is
`src.count(b"\n") + 1`.

Default source: `DEFAULT_THRESHOLD`, which reads env `AST_LENS_THRESHOLD` (below).

### `--format {md, json}` (default `md`)
- `md` — the rendered Markdown (App C schema), or `""` on passthrough. The CLI
  writes nothing on the empty case.
- `json` — a JSON envelope `{"file", "lang", "loc", "tokens_outline", "markdown"}`
  (2-space indent) for programmatic consumers. `tokens_outline = est_tokens(md)`.

---

## Environment variables

### `AST_LENS_BUDGET` (default `"300"`)
Read **once at module import** in `bin/outline.py`:
`DEFAULT_BUDGET = int(os.environ.get("AST_LENS_BUDGET", "300"))`. Sets the default
for `--budget`. Because it is read at import time, it applies to every invocation
of the emitter (including via the hook) unless overridden by an explicit
`--budget`. Maps to paper $\budget$.

### `AST_LENS_THRESHOLD` (default `"200"`)
Read **once at module import**:
`DEFAULT_THRESHOLD = int(os.environ.get("AST_LENS_THRESHOLD", "200"))`. Sets the
default for `--threshold`. Maps to paper $\threshold$. This is the canonical way
to raise the LoC floor pack-wide (the paper's per-project `ship.toml [outline]
threshold_loc`; ast-lens reads it from the environment instead).

### `BLACKRIM_DISABLE_OUTLINE_HOOK` (default unset)
Read by the **hook script** `hooks/outline-on-read.sh` at step 0:

```bash
if [ "${BLACKRIM_DISABLE_OUTLINE_HOOK:-}" = "1" ]; then
  exit 0
fi
```

Set to `1` to make the PreToolUse hook a no-op **without touching settings** — the
`Read` proceeds with no outline injected. This is the paper's §4 hook escape
hatch. It disables only the *hook surface*; the CLI and skill still work, and the
emitter itself is unaffected.

### `PYTHON` (default `python3`, build-time only)
Read by `setup.sh`: `PY="${PYTHON:-python3}"`. Selects the interpreter used to
create the pack's `.venv`. Not a runtime knob — it only affects `./setup.sh`.

> Not read by ast-lens: the paper's `ship.toml [outline] threshold_loc` and
> `[outline.sanitisation] additional_patterns`. ast-lens takes the threshold from
> `AST_LENS_THRESHOLD` and uses a fixed `INJECTION_PATTERNS` set in code; there is
> no `ship.toml` integration.

---

## In-file directive: `outline:skip`

A per-file opt-out. If any of a file's **first five lines** contains the literal
string `outline:skip`, the emitter returns `""` for that file (passthrough),
regardless of size or language.

```go
// outline:skip
package big
```
```python
# outline:skip
```

Read by **`has_skip(path)`** in `bin/outline.py`, which opens the file (utf-8,
`errors="replace"`), scans up to 5 lines, and returns `True` on the first match.
`outline(...)` short-circuits to `""` when `has_skip` is true. Any read error in
`has_skip` is swallowed (returns `False`). The detection is a plain substring
match, so any comment syntax works (`//`, `#`, `/* */`, …) as long as the literal
appears in the first five lines. This is the paper's §4/§5 `// outline:skip` /
`# outline:skip` escape hatch — the mitigation for files that violate the
token-cost-linear-in-LoC assumption (e.g. huge generated arrays).

---

## Hook command configuration (overlay)

The PreToolUse wiring lives in
`overlay/per-provider/claude/.claude/settings.json` and is deep-merged into the
projected Claude `settings.json` by gc (see
[ARCHITECTURE.md](./ARCHITECTURE.md) §3 and
[hook-projection-findings.md](./hook-projection-findings.md)):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          { "type": "command",
            "command": "export PATH=\"$HOME/go/bin:$HOME/.local/bin:$PATH\" && bash \"$CLAUDE_PROJECT_DIR/packs/ast-lens/hooks/outline-on-read.sh\"" }
        ]
      }
    ]
  }
}
```

Tunable points:
- **`matcher`** — `"Read"`. Narrowing this (e.g. by extension, if a future Claude
  Code build supports it) would reduce needless hook spawns; the script re-checks
  `tool_name == "Read"` regardless, so a loose matcher is safe but wasteful.
- **`command` `export PATH`** — prepends `$HOME/go/bin` and `$HOME/.local/bin` so
  `jq` / `python3` are found; mirrors gc's own hook commands.
- **`$CLAUDE_PROJECT_DIR/packs/ast-lens/...`** — assumes the pack is vendored at
  `<project>/packs/ast-lens`. If projected elsewhere, the hook silently no-ops
  (guards `exit 0`); adjust this path to match the real layout.

The hook deliberately does **not** carry budget/threshold flags — it calls
`bin/outline <file>` with defaults so the emitter remains the single source of
truth (Alg 1 gate + §5.3 + §5.4). To change budget/threshold for the hook surface,
set `AST_LENS_BUDGET` / `AST_LENS_THRESHOLD` in the environment the hook runs in.

---

## Prompt-fragment opt-in (`global_fragments`)

The discipline fragment `template-fragments/read-with-outline.template.md`
(`{{ define "read-with-outline" }}`) is not auto-applied. Opt it into every
agent's system prompt via `city.toml`:

```toml
global_fragments = [ ..., "read-with-outline" ]
```

This injects the "outline first, Read second" rule into the framework-wide
prompt-cache prefix (the paper's "CLAUDE.md instruction" surface). It is
documentation/discipline only — no runtime parameters.

---

## Where defaults are defined (single-glance)

```python
# bin/outline.py
DEFAULT_BUDGET    = int(os.environ.get("AST_LENS_BUDGET", "300"))      # B
DEFAULT_THRESHOLD = int(os.environ.get("AST_LENS_THRESHOLD", "200"))   # theta_L
DOC_KEEP_LINES = 3        # package-doc lines kept before truncation   §5.3(4)
VERBATIM_CAP   = 240      # chars of verbatim doc per decl             §5.4(1)
```

`DOC_KEEP_LINES` (3) and `VERBATIM_CAP` (240) are **fixed constants**, not exposed
as flags or env vars — they encode the paper's normative §5.3(4) "first three doc
lines" and §5.4(1) "240-char verbatim cap". Change them by editing the source.
