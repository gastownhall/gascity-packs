# ast-lens — Architecture

How the pack fits together. For the emitter's per-function detail see
[REFERENCE.md](./REFERENCE.md); for the algorithm-to-paper mapping see
[ALGORITHM.md](./ALGORITHM.md); for configuration see [CONFIG.md](./CONFIG.md).
The user-facing overview lives in the [pack README](../README.md) — this document
is the engineer-facing system view and does not repeat it.

ast-lens is a clean-room implementation of the **read side** of *"The AST as LLM
Lens"* (Blackrim AST paper, §4 system / §5 algorithm). It does not depend on
Blackrim's `gt`. The whole pack exists to make **outline-first reading** the
default: an agent reads a compact Markdown *structural outline* of a large source
file before (or instead of) paying the full-file read tax.

---

## 1. The core model: one emitter, three surfaces (+ a discipline layer)

The paper's architectural commitment (§4.1, "three entry points, one emitter") is
that there is exactly **one** canonical outline emitter, reachable through several
**discovery surfaces**. ast-lens realises that commitment with one emitter and
three surfaces, wrapped by a fourth "discipline" layer of prompt fragments that
*teach* the surface rather than execute it.

```
                         ┌───────────────────────────────────────┐
                         │      bin/outline.py  (the emitter)      │
                         │  pure · stateless · read-only · Alg 1   │
                         │  Markdown (or --format json) or "" )    │
                         └───────────────────────────────────────┘
                                          ▲
                 ┌────────────────────────┼────────────────────────┐
                 │                        │                         │
        ┌────────┴────────┐    ┌──────────┴──────────┐    ┌─────────┴─────────┐
        │  Surface 1: CLI │    │ Surface 2: Skill    │    │ Surface 3: Hook   │
        │  bin/outline    │    │ skills/read-with-   │    │ hooks/outline-on- │
        │  (wrapper →     │    │ outline/SKILL.md    │    │ read.sh (claude   │
        │   venv python)  │    │ (agent invokes CLI) │    │ PreToolUse → Read)│
        └─────────────────┘    └─────────────────────┘    └───────────────────┘
                                          ▲
                         ┌────────────────┴────────────────┐
                         │   Discipline layer (prompt)      │
                         │   template-fragments/            │
                         │   read-with-outline.template.md  │
                         │   (CLAUDE.md / global_fragments) │
                         └──────────────────────────────────┘
```

**The emitter is the single source of truth** for the threshold gate, the schema,
the truncation precedence, and sanitisation. Every surface ultimately shells out
to (or instructs the agent to shell out to) the same `bin/outline`. There is one
schema, computed in one place — so the CLI, the skill's worked example, and the
hook's injected context all agree.

### The emitter (Subsystem A, §4.2)
- **`bin/outline.py`** — the Python implementation. Pure function
  `outline(path, budget, threshold, fmt) → str`; emits Markdown (App C schema) or
  the empty string on any passthrough condition. See REFERENCE.md.
- **`bin/outline`** — a tiny bash wrapper. Resolves the pack's own
  `.venv/bin/python` if present, else system `python3`; `exec`s
  `bin/outline.py "$@"`. **On any failure it `exit 0` with no output** — graceful
  passthrough per Alg 1, so a caller (notably the hook) can never be broken by it.
- **`.venv/`** — the self-contained virtualenv built by `setup.sh` from
  `requirements.txt` (canonical `tree-sitter` + the four per-language grammar
  wheels). Keeps the emitter's heavy imports local and out of the host environment.

### Surface 1 — CLI (mechanism)
`bin/outline <file>` (or `--format json`). Used by humans, by agents directly, and
by the hook. This is the paper's `gt outline <file>` surface (mechanism, not
discipline).

### Surface 2 — Agent-facing skill (discipline)
**`skills/read-with-outline/SKILL.md`** — a gc skill (YAML frontmatter `name` +
`description`, free-form Markdown body). It describes the outline-first discipline,
the App C schema, the line-span navigation loop, and a worked example. gc
discovers it by directory convention (`skills/<name>/SKILL.md` under the pack
root); once the pack is imported it surfaces as `ast-lens.read-with-outline` in
`gc skill list`. Maps to the paper's `read-with-outline` skill (§4.B item 2).

### Surface 3 — PreToolUse hook (discipline, mechanical)
**`hooks/outline-on-read.sh`** + **`overlay/per-provider/claude/.claude/settings.json`**.
The Claude Code `PreToolUse` hook fires before every `Read`; the script runs the
emitter on the read path and, if the emitter produced anything, injects it back as
`additionalContext`. **Warn-mode only** — it never sets a `permissionDecision`, so
the `Read` is never blocked or modified. Maps to the paper's PreToolUse
outline-discipline hook (§4.B item 1). See §3 below and
[hook-projection-findings.md](./hook-projection-findings.md).

### Discipline layer — prompt fragment (system-prompt instruction)
**`template-fragments/read-with-outline.template.md`** — a Go-template fragment
(`{{ define "read-with-outline" }} … {{ end }}`) carrying the "outline first,
Read second" rule, the token-economics rationale, and the asymmetric trade-off
(reading-too-much wastes tokens; reading-too-little produces *wrong* work).
Opted into a city via `global_fragments` in `city.toml`; it lands in the
framework-wide prompt-cache prefix every agent sees. Maps to the paper's
"CLAUDE.md instruction" (§4.B item 3).

> Mechanism vs. discipline (paper §4.1): the **CLI is the mechanism**; the **hook,
> skill, and prompt fragment are the discipline** that make the mechanism the
> default. The pack ships all four.

---

## 2. Data flow: a `Read` → hook → emitter → injected outline

The headline path is the PreToolUse hook auto-prepending an outline to a `Read`:

```
agent issues Read(file_path=/abs/foo.ts)
        │
        ▼
Claude Code fires PreToolUse hook  ── stdin: {tool_name:"Read",
        │                                      tool_input:{file_path:…}}
        ▼
overlay/.../settings.json command:
   export PATH=… && bash $CLAUDE_PROJECT_DIR/packs/ast-lens/hooks/outline-on-read.sh
        │
        ▼
hooks/outline-on-read.sh
   0. BLACKRIM_DISABLE_OUTLINE_HOOK=1 ?  ── yes → exit 0 (no-op)
   1. resolve PACK_DIR, require bin/outline executable  ── else exit 0
   2. read stdin JSON                                   ── empty → exit 0
   3. parse tool_name + tool_input.file_path (jq, grep/sed fallback)
        ── not Read / no file / not a regular file → exit 0
   4. outline_md = bin/outline <file_path>              ── the gate is the emitter
        │
        ▼
   bin/outline → .venv/bin/python bin/outline.py <file_path>
        │
        ▼
   outline(path, B=300, θ=200, fmt=md)   (Alg 1)
        ├─ unsupported ext / loc<θ / outline:skip / no parser / parse error
        │     → ""  (silent passthrough)
        └─ else → render → truncate(§5.3) → drop_empty_sections → Markdown
        │
        ▼
   (back in hook) outline_md empty?  ── yes → exit 0 (nothing to inject)
   5. best-effort telemetry: append one JSON line to
        <project>/.beads/telemetry/outline-events.jsonl   (never fatal)
   6. emit stdout JSON:
        {"hookSpecificOutput":{"hookEventName":"PreToolUse",
                               "additionalContext":"<intro sentence>\n\n<outline_md>"}}
        (jq -R -s, python3 json.dumps fallback)
   exit 0   (ALWAYS)
        │
        ▼
Claude Code injects additionalContext into the model's context for THIS turn,
then runs the Read unmodified. The agent sees the outline alongside the file.
```

Key invariants:
- **The emitter is the gate.** The hook does *not* re-implement the LoC threshold,
  language detection, or skip logic — it asks the emitter and only injects when the
  emitter has something to say (paper §4.1 "one emitter, one schema").
- **Sanitisation happens inside the emitter.** The hook never echoes raw file
  bytes; the only strings it interpolates are the file path (into a fixed sentence)
  and the already-sanitised Markdown, both JSON-escaped.
- **`exit 0` always.** Every step in the hook is guarded and reaches the final
  `exit 0`; `set -e`/`-u`/pipefail are deliberately *not* used. A hook failure must
  never break a `Read`.
- **Warn-mode.** No `permissionDecision` is set, so the `Read` proceeds. Block-mode
  (the paper's warn→block escalation at 80% 7-day hit-rate) is **not implemented**.

The other surfaces are simpler flows over the same emitter: the **skill/fragment**
path is the agent *choosing* to run `outline <file>` first, reading the structural
map, and then issuing a targeted `Read offset/limit` using a printed `L<start>–<end>`
anchor; the **CLI** path is a human or tool running `bin/outline` directly.

---

## 3. How the hook is wired into a Claude provider (gc projection)

ast-lens contributes the hook as a **pack overlay**, not a gc-core change:

```
packs/ast-lens/
└─ overlay/per-provider/claude/.claude/settings.json   # PreToolUse → Read entry
```

gc treats a top-level `overlay/` directory as first-class (alongside `skills/`,
`formulas/`, `orders/`). At `gc start` / `gc rig boot`, gc materialises the pack
overlay and **deep-merges** the `PreToolUse` block into the projected Claude
`settings.json` (via its hooks-aware `MergeSettingsJSON` / `mergeHooksMap` /
`mergeHookArray` + `deepMergeProvider` code) — it does **not** overwrite the
core-generated `SessionStart` / `PreCompact` / `UserPromptSubmit` hooks; the new
event is unioned alongside them. The overlay's command is:

```json
{ "type": "command",
  "command": "export PATH=\"$HOME/go/bin:$HOME/.local/bin:$PATH\" && bash \"$CLAUDE_PROJECT_DIR/packs/ast-lens/hooks/outline-on-read.sh\"" }
```

`$CLAUDE_PROJECT_DIR` is Claude Code's built-in project root; the path assumes the
pack lives at `<project>/packs/ast-lens`. If the pack is vendored elsewhere the
hook silently no-ops (the script's `dirname` / `[ -x bin/outline ]` guards
`exit 0`) — safe, but the outline won't appear, so the path must match the real
projection layout. The full analysis (merge mechanism, the `matcher` caveat,
validation steps) is in
[hook-projection-findings.md](./hook-projection-findings.md).

---

## 4. Component map (where each thing lives)

| Component | Path | Role | Paper § |
|---|---|---|---|
| Emitter (impl) | `bin/outline.py` | Pure outline function; the single source of truth | §5, App B/C/D, §4.2 |
| Emitter (wrapper) | `bin/outline` | venv-resolving bash shim; `exit 0` passthrough on failure | Alg 1 |
| Runtime venv | `.venv/` (built) | tree-sitter + grammars, isolated | §4.2 |
| Runtime deps | `requirements.txt` | `tree-sitter` + 4 grammar wheels | §4.2 |
| Bootstrap | `setup.sh` | Idempotently builds `.venv` | — |
| Skill (Surface 2) | `skills/read-with-outline/SKILL.md` | Agent-facing discipline + schema + worked example | §4.B(2) |
| Prompt fragment | `template-fragments/read-with-outline.template.md` | System-prompt "outline first" rule | §4.B(3) |
| Hook script (Surface 3) | `hooks/outline-on-read.sh` | PreToolUse → run emitter → inject `additionalContext` | §4.B(1) |
| Hook wiring | `overlay/per-provider/claude/.claude/settings.json` | `PreToolUse`/`Read` entry, deep-merged by gc | §4.1 |
| Pack manifest | `pack.toml` | `[pack]` name/schema/version; wiring notes | — |
| Tests | `tests/` | 156 read-side + write-side behavioral tests against paper contracts | §5.3/§5.4 |
| Docs | `docs/` | this set + `hook-projection-findings.md` | — |

### Write side — implemented (phase 2)
The write-side subsystems are implemented under `astlens/` — see
[WRITE-SIDE.md](WRITE-SIDE.md). The **compile gate** (§5.6, false-negative-only: it
rejects any change it can't prove syntactically safe), the stateless content-addressed
**plan/execute pair** contract (§4.C / §5.5), and three compound symbolic ops (§4.D),
driven by `bin/op`:

| Op | Scope | Backed by |
|----|-------|-----------|
| `fix-imports` | Go + Python | `goimports` / `ruff` |
| `rename-symbol` | Go (cross-file, compile-aware) | `gopls` rename |
| `extract-to-package` | Go (exported decl, conservative) | `tree-sitter-go` + `gofmt` |

Also implemented: the YAML **pattern-DSL** (§4.E) — author new ops as YAML intents
([PATTERN-DSL.md](PATTERN-DSL.md)); the agent-facing **`symbolic-edits`** skill +
prompt fragment; and **refinery integration** — a plan filed as a bead, applied gated
through the merge path ([REFINERY-INTEGRATION.md](REFINERY-INTEGRATION.md)). The paper
had deferred the pattern-DSL; it ships here.

---

## 5. Degradation & safety posture

The pack is built to **degrade to a no-op** rather than fail:

- **No venv / missing deps** → `bin/outline` falls back to system `python3`; if
  tree-sitter or a grammar is missing, `load_parser` returns `None` and the
  emitter returns `""`. The hook injects nothing. Importing the pack can never
  break a `Read`.
- **Sub-threshold / unsupported / `outline:skip` / parse error** → emitter `""`,
  hook silent (Alg 1 passthrough).
- **Sanitisation** (§5.4/App D) runs *inside* the emitter on all verbatim doc
  text, so adversarial vendored code surfaces flagged (`[sanitised] …`), never as
  raw instructions.
- **Telemetry is best-effort** — written only when a `.beads` project root is
  discoverable, never on the exit path.
- **Escape hatches**: `BLACKRIM_DISABLE_OUTLINE_HOOK=1` (disable hook),
  `outline:skip` (per-file opt-out), `--threshold` / `AST_LENS_THRESHOLD` (raise
  the floor). See [CONFIG.md](./CONFIG.md).

### Honest caveats (carried from the README)
- The **300-token budget is soft**: the truncation precedence never sheds *public*
  top-level decls, so public-heavy files can exceed it.
- **Activation is deliberate**: the hook fires on *every* `Read` once enabled and
  re-parses large files each time (the emitter is stateless / no-cache by design).
  Validate the overlay projection path on a scratch city before enabling town-wide.
- **Block-mode is not implemented** (warn-mode only).
- Multi-line signatures truncate to their first line; the significance pass is
  light.
