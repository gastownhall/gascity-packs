# Can a gc pack inject a Claude Code `PreToolUse` hook? — Findings

**Question.** Can a self-contained gc (Gas City) pack contribute a Claude Code
**`PreToolUse`** hook (claude provider) that auto-prepends `bin/outline <file>`
output to a `Read` on large files — implementing "Subsystem B: Outline-discipline"
from the paper (§4)?

**Answer. Yes — and the path already exists in gc core.** A pack ships
`overlay/per-provider/claude/.claude/settings.json` with a `PreToolUse` block;
gc **deep-merges** it into the projected Claude `settings.json` rather than
overwriting it. This is the *same* overlay mechanism codex/cursor/gemini already
use, and gc has dedicated, hooks-aware Claude-settings merge code. No gc-core
change is required to land the hook. (One caveat about the matcher string, noted
under Risks.)

---

## 1. How gc projects Claude settings/hooks

For the **claude** provider, the base `hooks` block (`SessionStart`,
`PreCompact`, `UserPromptSubmit`) is emitted by **gc core (Go)** — confirmed:
the live `/Users/jayse/Code/.gc/settings.json` and the per-agent
`/Users/jayse/Code/.gc/agents/<name>/.gc/settings.json` both contain it, yet
there is **no** `claude` directory under
`/Users/jayse/Code/.gc/system/packs/core/overlay/per-provider/` (only
codex, copilot, cursor, gemini, kiro, omp, opencode, pi). So for claude the
*baseline* is code-generated, not file-copied.

But that baseline is then **merged** with overlay-provided settings. gc does not
treat the Claude settings file as code-owned-and-overwritten; it treats it as a
**merge target**. Evidence (symbols + strings in the `gc` binary,
`/opt/homebrew/bin/gc`):

- `github.com/gastownhall/gascity/internal/config.deepMergeProvider`
- Vendored `github.com/apapsch/go-jsonmerge/v2` (RFC-7386-style JSON merge)
- Format strings:
  - `"merging Claude settings from %s: %w"`
  - `"upgrading Claude settings from %s: %w"`
  - `"projecting Claude settings: %w"`
  - `"empty Claude settings from %s (file present but zero bytes)"`
  - `"invalid Claude settings override at %s: ... is not a JSON object; expected a JSON object; fix or remove the file to proceed with install"`
- The projection target string `.claude/settings.json`.

The phrase **"Claude settings *override*"** plus a `deepMergeProvider` step is
the tell: gc reads an override/overlay settings file and deep-merges it onto the
generated baseline. The baseline `hooks` already proves gc can carry a `hooks`
map into the projected claude `settings.json`; merging in one more event
(`PreToolUse`) is the same data path.

## 2. The per-provider overlay mechanism (what gc actually does)

The overlay engine lives in `internal/overlay` (symbols recovered from the
binary). The relevant functions:

- `overlay.CopyDirForProviders` — walks a `per-provider/<provider>/…` tree and
  materialises it into the provider's projected config dir.
- `overlay.copyOrMergeFile` + `overlay.IsMergeablePath` — **per-file decision:
  copy vs merge.** Mergeable JSON files are merged, not clobbered.
- `overlay.MergeSettingsJSON` — the settings.json merger.
- `overlay.mergeHooksMap` + `overlay.mergeHookArray` — **hooks-aware merge.**
  gc specifically understands the `hooks` object and the hook *arrays* inside
  it, so an overlay can *add* a hook event/entry without dropping the baseline
  ones.
- `overlay.copyCanonicalJSONFile` — canonical (stable-key) JSON writes.
- `overlay.CopyDirForProviders.providerPreserveExisting` and the string
  `"overlay: preserving existing nil data; no entry for key %q"` — **preserve-
  existing semantics** (the overlay augments; it doesn't blow away user keys).

Pack overlays (not just the core pack) are honoured. Evidence:

- `//go:embed pack.toml all:assets formulas orders all:overlay skills` — every
  pack manifest treats a top-level **`overlay/`** directory as first-class,
  exactly like `skills/`, `formulas/`, `orders/`. So `ast-lens/overlay/...` is a
  recognised pack-overlay root.
- `main.materializeCityRootPackOverlays`, `main.resolveOverlayDir`, and strings
  `"gc init: materializing pack overlay %s: %v"`, `"pack overlay %q -> %q: %w"`.
- Embedded README: *"Installation walks the pack overlay during `gc start` /
  `gc rig boot`,"* and *"`internal/bootstrap/packs/core/overlay/per-provider/<provider>/`
  (e.g. `codex/.codex/hooks.json`, `cursor/.cursor/hooks.json`)."* with a line
  **"Claude-specific settings (this directory)."** and a **`## Merge Strategy`**
  section whose recoverable fragments read:
  *"# (the GC baseline), those extensions are preserved. This matches the …
  line is replaced with the union of existing and required entries, never …
  and per-provider hook overlays."*

That "**union of existing and required entries, never** [replaced]" wording is
the explicit contract: overlay hook entries are **unioned** with the baseline.

**Shape that other providers use** (and which claude mirrors):
`/Users/jayse/Code/.gc/system/packs/core/overlay/per-provider/codex/.codex/hooks.json`
already uses the Claude-style schema — `hooks` → event → `[{matcher, hooks:[{type,command}]}]`.
The claude overlay uses the identical schema, written to `.claude/settings.json`.

### Merge behaviour — conclusion

A pack-provided `overlay/per-provider/claude/.claude/settings.json` is
**deep-merged** into the projected claude `settings.json`. claude is *not*
special-cased to discard overlays; it has a *dedicated, hooks-aware* merger
(`MergeSettingsJSON` / `mergeHooksMap` / `mergeHookArray` + `deepMergeProvider`)
that **preserves the core-generated `SessionStart`/`PreCompact`/`UserPromptSubmit`
hooks and adds `PreToolUse`** alongside them. Determined by static analysis of
the shipped `gc` binary (symbols + embedded README/format strings) **without
mutating any live state** — no `gc` mutating command was run.

> Residual uncertainty (couldn't be settled read-only without a build/run):
> the exact override **source path** gc reads for the claude provider. Two
> possibilities, both pointing at the same overlay file:
> (a) gc materialises pack `overlay/per-provider/claude/.claude/settings.json`
> into the projected `.claude/settings.json` and merges over the baseline; or
> (b) gc merges that overlay file in directly as the "Claude settings override".
> Either way the **deliverable file location is correct** and the merge is
> additive. Validate on a scratch city with
> `gc config explain` / re-projection (see Validation below) before shipping.

## 3. The Claude Code `PreToolUse` hook contract

A `PreToolUse` hook fires **before** a tool runs and receives the pending call
as **JSON on stdin**:

```json
{ "hook_event_name": "PreToolUse",
  "tool_name": "Read",
  "tool_input": { "file_path": "/abs/path/file.py", ... } }
```

To surface the outline back to the agent without blocking the `Read`, the hook
prints **JSON to stdout** using the advisory shape:

```json
{ "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "<outline markdown>" } }
```

Claude Code injects `additionalContext` into the model's context for the turn.
Because we **omit** `permissionDecision`, the `Read` proceeds unmodified — this
is the paper's **warn-mode** ("The hook never blocks the `Read`… the warning is
*rich* — outline content, not just text"). These field names
(`hookSpecificOutput`, `hookEventName`, `additionalContext`, `tool_name`,
`file_path`) are all present as literals in the `gc` binary, confirming gc's own
claude hooks speak this contract.

> Note on terminology: the paper says the hook "prepends the Markdown output to
> the `Read` result." Claude Code's `PreToolUse` API does not let a hook rewrite
> the tool's *return value*; the supported mechanism is `additionalContext`,
> which the model sees together with the `Read` output in the same turn. The
> net effect (agent sees the outline alongside the file) is identical; the
> wording "prepend" is satisfied by context injection, not result mutation.

### The precise hook command line

Projected into `.claude/settings.json` (this is the deliverable overlay):

```json
{ "type": "command",
  "command": "export PATH=\"$HOME/go/bin:$HOME/.local/bin:$PATH\" && bash \"$CLAUDE_PROJECT_DIR/packs/ast-lens/hooks/outline-on-read.sh\"" }
```

…under `hooks.PreToolUse[0]` with `"matcher": "Read"`. The `export PATH` prefix
mirrors gc's existing hook commands. The hook delegates to a small,
self-contained script (full file:
`/Users/jayse/Code/packs/ast-lens/hooks/outline-on-read.sh`) that:

1. reads the PreToolUse JSON from stdin and extracts `tool_name` +
   `tool_input.file_path` (via `jq`, with a grep/sed fallback);
2. bails silently unless it is a `Read` on an existing regular file;
3. runs `<pack>/bin/outline <file_path>` — the emitter is the threshold gate
   (Alg 1): it stays silent for `<200` LoC, unsupported types, `// outline:skip`
   / `# outline:skip`, or any parse failure;
4. if the emitter produced Markdown, emits the `hookSpecificOutput.additionalContext`
   JSON; otherwise prints nothing;
5. appends one telemetry line to `.beads/telemetry/outline-events.jsonl` when a
   `.beads` project root is discoverable (best-effort, never fatal);
6. **always `exit 0`** — a hook failure must never break a `Read`.

Escape hatch `BLACKRIM_DISABLE_OUTLINE_HOOK=1` short-circuits the hook (paper §4).

`$CLAUDE_PROJECT_DIR` is Claude Code's built-in project-root variable; the path
`packs/ast-lens/hooks/outline-on-read.sh` assumes the pack lives at
`<project>/packs/ast-lens`. If gc projects the pack elsewhere, adjust this single
path (or have gc rewrite it at projection time, as it does for its own `gc …`
hook commands).

### Verified behaviour (prototype)

The script was exercised against the live emitter:

- Large supported file (`outline.py`, 493 LoC) → emits valid
  `hookSpecificOutput.additionalContext` JSON containing the outline. ✔
- Non-`Read` tool, sub-threshold file, nonexistent file, unsupported `.txt`,
  `# outline:skip` file, malformed-JSON stdin, empty stdin, and
  `BLACKRIM_DISABLE_OUTLINE_HOOK=1` → **all silent, `exit 0`, zero stderr**. ✔
- Telemetry line written under a `.beads` root. ✔

## 4. Risks / caveats

1. **Fires on every `Read`.** With `"matcher": "Read"` the hook runs for every
   `Read`. Cost is one `jq` parse + one emitter spawn. The emitter short-circuits
   cheaply for small/unsupported files, but it still re-parses large files on
   *every* `Read` (the emitter is stateless/no-cache by design, paper §4.A).
   - **Latency:** tree-sitter parse is tens of ms on a 3000-line file (paper),
     but a Python cold-start (interpreter + tree-sitter import) per `Read` adds
     overhead. The pack venv (`bin/outline` → `.venv/bin/python`) keeps imports
     local but not free. If this bites, add the emitter cache the paper defers,
     or gate by extension in the matcher.
2. **`matcher` semantics — verify before shipping.** Some Claude Code builds
   treat `matcher` as a regex over tool names; `"Read"` matches `Read` but the
   anchoring/altation rules vary by version. The hook script defends against
   over-matching (it re-checks `tool_name == "Read"` and passes through
   otherwise), so a loose matcher is *safe* but may spawn the script needlessly.
   Confirm the matcher dialect for the target Claude Code version.
3. **Block-mode not implemented.** The paper escalates warn→block at a 7-day
   80% hit-rate. This prototype is warn-mode only; block-mode would require
   reading the telemetry/hit-rate and returning a `permissionDecision: "deny"`
   (or `"ask"`) — deferred, and intentionally out of scope here.
4. **`$CLAUDE_PROJECT_DIR` path coupling.** The command hard-codes the pack
   sub-path. If the pack is vendored at a different location, the hook silently
   no-ops (script-not-found → the `[ -x "$OUTLINE_BIN" ]` / dirname guards exit
   0). Safe, but the outline simply won't appear — so the path must match the
   real projection layout.
5. **Sanitisation already handled.** File contents flow into the outline only
   through the emitter, which sanitises (`outline.py:sanitise()`); the hook never
   echoes raw source. The only strings the hook interpolates are the file path
   (into a fixed sentence) and the already-sanitised Markdown, both JSON-escaped
   via `jq -R -s` / `json.dumps`. Low injection surface.
6. **`jq` dependency.** The script prefers `jq` (present on this box: 1.8.1) and
   falls back to grep/sed for parsing and `python3` for JSON emission. If *both*
   `jq` and `python3` are absent it passes through (no outline) rather than
   risk emitting non-JSON to a stdout that Claude Code parses as JSON.
7. **`PreToolUse` vs. `PostToolUse`.** Injecting *before* the read means the
   outline reaches the model in the same turn as the `Read` result, which is the
   intended discipline. If a future Claude Code version changed `PreToolUse`
   stdout handling, `PostToolUse` (which can wrap the result) is the fallback
   surface; the same emitter/script applies with a different output shape.

---

## 5. Recommended path

Ship the pack-overlay approach — **no gc-core change needed**:

```
packs/ast-lens/
├─ overlay/per-provider/claude/.claude/settings.json   # PreToolUse → Read, merged by gc
└─ hooks/outline-on-read.sh                             # stdin JSON → bin/outline → additionalContext
```

gc's `overlay.MergeSettingsJSON` / `mergeHooksMap` deep-merges the `PreToolUse`
entry alongside the core baseline hooks; the emitter remains the single source
of truth for the threshold and sanitisation (paper's "one emitter, three
surfaces"). Validate the merge on a throwaway city before relying on it:

- `gc config explain` (and re-projection via `gc rig boot` / `gc start`) on a
  scratch city, then inspect the resulting `.claude/settings.json` to confirm
  `PreToolUse` appears **and** the baseline `SessionStart`/`PreCompact`/
  `UserPromptSubmit` hooks survive.
- `gc lint` the pack to confirm the `overlay/` tree is accepted.

If a future gc version were found to special-case claude and *discard* overlay
settings (contradicted by all evidence above, but worth the 5-minute check),
the minimal core change would be: add `claude` to the `per-provider` overlay set
so `CopyDirForProviders` materialises `claude/.claude/settings.json`, and ensure
`deepMergeProvider` runs `MergeSettingsJSON` over it against the generated
baseline (the merge code already exists — it would only need to be *invoked* for
the claude target).
