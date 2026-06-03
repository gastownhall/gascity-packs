# ast-lens — Documentation

Engineer-facing docs for the **ast-lens** gc pack: a clean-room implementation of
*outline-first reading* from *"The AST as LLM Lens"*. Agents read a compact
Markdown structural outline of a large source file instead of paying the full-file
read tax.

Start with the [pack README](../README.md) for the high-level overview and quick
start. This `docs/` set is the deeper reference.

## Index

| Doc | What it covers |
|---|---|
| [INSTALL.md](./INSTALL.md) | Install, build the venv, wire the pack into a city, and uninstall. |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | The "one emitter, three surfaces" model (CLI / skill / hook) plus the prompt-fragment discipline layer; data flow from `Read` → hook → emitter → injected outline; where every component lives. |
| [ALGORITHM.md](./ALGORITHM.md) | The emitter algorithm mapped to the paper: Alg 1 pipeline, App B significance, §5.3 truncation precedence, §5.4/App D sanitisation, App C schema — and where the implementation deliberately diverges or simplifies. |
| [REFERENCE.md](./REFERENCE.md) | Exhaustive function-by-function and constant-by-constant reference of `bin/outline.py`: signatures, behaviour, params, returns, and the paper section each implements. |
| [CONFIG.md](./CONFIG.md) | Every configuration knob: the `--budget` / `--threshold` / `--format` flags, the `AST_LENS_BUDGET` / `AST_LENS_THRESHOLD` / `BLACKRIM_DISABLE_OUTLINE_HOOK` env vars, the `outline:skip` directive, defaults (B=300, θ=200), and where each is read. |
| [hook-projection-findings.md](./hook-projection-findings.md) | Research note: can a gc pack contribute a Claude Code `PreToolUse` hook, and how gc deep-merges the overlay's hooks into projected Claude settings. Background for the hook surface. |

## Reading paths

- **New to the pack?** [pack README](../README.md) → [ARCHITECTURE.md](./ARCHITECTURE.md).
- **Installing / wiring into a city?** [INSTALL.md](./INSTALL.md) → [CONFIG.md](./CONFIG.md).
- **Understanding or modifying the emitter?** [REFERENCE.md](./REFERENCE.md) +
  [ALGORITHM.md](./ALGORITHM.md).
- **Debugging the auto-prepend hook?** [ARCHITECTURE.md](./ARCHITECTURE.md) §2–3 →
  [hook-projection-findings.md](./hook-projection-findings.md) → [CONFIG.md](./CONFIG.md).

## At a glance

- **Emitter:** `bin/outline` (wrapper) → `bin/outline.py` (pure, stateless,
  read-only). Markdown by default, `--format json` for tools. Empty output
  (passthrough) on sub-threshold / unsupported / `outline:skip` / missing parser /
  parse error — it can never break a `Read`.
- **Languages:** Go, Python, TypeScript, JavaScript (canonical `tree-sitter` + per-grammar wheels).
- **Defaults:** budget **B = 300** tokens (soft), threshold **θ_L = 200** LoC.
- **Surfaces:** CLI, `read-with-outline` skill, Claude `PreToolUse` hook, plus the
  `read-with-outline` prompt fragment.
- **Paper:** §5 algorithm, App B significance, App C schema, App D sanitisation —
  implemented from spec, contract-equivalent (not byte-equivalent) to Blackrim's `gt outline`.
