# ast-lens — Install / Uninstall

A clean, reversible on/off switch for the `ast-lens` pack at two scopes:

- **Town (city-wide)** — every agent in the city gets outline-first reading:
  the `read-with-outline` skill, the `read-with-outline` prompt fragment (opted
  into `global_fragments`), and the Claude `PreToolUse` hook that auto-prepends
  an `outline` of large files onto a `Read`.
- **Rig (one project)** — only the named rig's agents get the skill + the
  `PreToolUse` hook. (The prompt fragment is a city-wide list and is left alone
  in rig scope — see the table below.)

Both lifecycles are driven by two scripts in the pack root:

```
packs/ast-lens/install.sh     (--town | --rig <name>) [--dry-run] [--city <path>] [--no-reload]
packs/ast-lens/uninstall.sh   (--town | --rig <name>) [--dry-run] [--city <path>] [--purge] [--no-reload]
```

They are **idempotent** (re-running is a no-op), **back up every file they
edit** (`<file>.ast-lens.bak.<timestamp>`), support **`--dry-run`** (prints the
plan, changes nothing), and **fail loudly** on unexpected state (missing city,
unknown rig).

---

## TL;DR

```bash
# Turn it on, city-wide:
packs/ast-lens/install.sh --town

# …or just for one rig:
packs/ast-lens/install.sh --rig whiskeyshop

# Preview without changing anything:
packs/ast-lens/install.sh --town --dry-run

# Turn it off completely (and delete the Python venv):
packs/ast-lens/uninstall.sh --town --purge
packs/ast-lens/uninstall.sh --rig whiskeyshop --purge
```

The scripts auto-discover the city as the directory two levels above the pack
(`…/<city>/packs/ast-lens`). Override with `--city <path>` if the pack lives
elsewhere.

---

## What gets changed where

| Step | Town (`--town`) | Rig (`--rig <name>`) | Mechanism | Reversed by uninstall? |
|---|---|---|---|---|
| **Emitter venv** | `packs/ast-lens/.venv` built via `setup.sh` (skipped if present) | same | `setup.sh` (Python `venv` + `pip`) | only with `--purge` (kept by default) |
| **Pack import** | `<city>/pack.toml` → `[imports.ast-lens]` | `<city>/city.toml` → `[rigs.imports.ast-lens]` under the matching `[[rigs]]` | **`gc import add` / `gc import remove`** (gc-native) | yes — `gc import remove` |
| **Prompt fragment** | `<city>/city.toml` → `"read-with-outline"` appended to `global_fragments` | *(not touched)* | surgical, backed-up edit (no gc-native command exists) | yes — removed from the array |
| **Skill** | `ast-lens.read-with-outline` becomes visible to all agents | visible to the rig's agents | convention-discovered from the import (no extra step) | yes — disappears when the import is removed |
| **Claude `PreToolUse` hook** | materialized into each agent's `.claude/settings.json` and merged into `<city>/.gc/settings.json` at projection | same, for the rig's agents | gc overlay materialization + `MergeSettingsJSON` deep-merge | yes — stripped from every projected `settings.json`, then re-projected |
| **Re-projection** | `gc reload` | `gc reload` | gc-native | n/a |

> **Why `--town` edits `pack.toml` but `--rig` edits `city.toml`:** that split is
> gc's own behaviour. `gc import add <src>` (no `--rig`) writes a **city-scope**
> import to the city-root `pack.toml` `[imports.*]`. `gc import add <src> --rig
> <name>` writes a **rig-scope** import to `city.toml` `[rigs.imports.*]` under
> that rig. The scripts just call the right form; they never hand-edit imports.

---

## How it works (the projection pipeline)

Understanding this explains why uninstall does what it does. Verified against
the gc source in `target/gascity` (`internal/hooks/hooks.go`,
`internal/overlay/merge.go`, `cmd/gc/cmd_start.go`,
`internal/runtime/tmux/adapter.go`).

1. **Import** makes the pack's `skills/`, `template-fragments/`, and `overlay/`
   convention-discoverable. The skill and fragment are picked up with no further
   wiring.
2. **Overlay materialization** (at session start): gc walks the pack's
   `overlay/per-provider/claude/.claude/settings.json` and **merges** it into
   each agent's `<WorkDir>/.claude/settings.json`
   (`overlay.CopyDirForProviders` → `copyOrMergeFile`). The merge is a *union* —
   it adds our `PreToolUse` entry and **never deletes** keys.
3. **Settings projection** (`hooks.installClaude` via `ensureClaudeSettingsArgs`
   on `gc start` / reconcile): gc reads the embedded baseline hooks, reads the
   **override** from `<city>/.claude/settings.json`, deep-merges them
   (`MergeSettingsJSON`, hooks-aware — baseline `SessionStart` / `PreCompact` /
   `UserPromptSubmit` survive), and **regenerates** `<city>/.gc/settings.json`
   (the file every Claude agent is launched with via `--settings`).

The hook command projected is:

```
export PATH="$HOME/go/bin:$HOME/.local/bin:$PATH" && bash "$CLAUDE_PROJECT_DIR/packs/ast-lens/hooks/outline-on-read.sh"
```

under `hooks.PreToolUse[*]` with `"matcher": "Read"`.

### The uninstall subtlety

Because step 2 is a **merge that never deletes**, removing the import does **not**
rewrite the already-materialized `<WorkDir>/.claude/settings.json`. That file is
the *override source* for step 3, so a stale `PreToolUse` would keep getting
re-merged into `.gc/settings.json` on every projection. Therefore `uninstall.sh`
**explicitly strips** our hook entry (identified by the unique
`ast-lens/hooks/outline-on-read.sh` command substring) from **every**
`settings.json` under the city, then re-projects so `.gc/settings.json`
regenerates clean. The strip is surgical: a user's own `Read` matcher (or any
other hook) is preserved; an emptied matcher block / empty `PreToolUse` key is
removed.

---

## Verifying an install

`install.sh` runs these automatically (step 5), but to check by hand:

```bash
# 1. The pack lints clean.
gc lint packs/ast-lens

# 2. The import is registered.
gc import list                       # town: shows `ast-lens`
gc import list --rig whiskeyshop     # rig:  shows `ast-lens`

# 3. The skill is visible (binding-qualified).
gc skill list | grep ast-lens.read-with-outline

# 4. (town) The fragment is opted in.
grep global_fragments city.toml      # includes "read-with-outline"

# 5. The PreToolUse hook is in the projected settings.
grep -l outline-on-read.sh .gc/settings.json .gc/agents/*/.gc/settings.json
```

> **Skill / hook visibility timing.** The skill catalog and the projected
> `settings.json` are (re)built by the running controller. On a **stopped**
> city, `gc reload` no-ops and the skill/hook appear on the next `gc start` /
> rig boot — `install.sh` reports this as a soft note, not a failure. The
> config edits (import, fragment) are applied immediately regardless.

---

## Fully uninstalling

```bash
# Town:
packs/ast-lens/uninstall.sh --town            # keep the venv
packs/ast-lens/uninstall.sh --town --purge    # also delete packs/ast-lens/.venv

# Rig:
packs/ast-lens/uninstall.sh --rig whiskeyshop --purge
```

`uninstall.sh` reverses, in order: (1) removes the fragment from
`global_fragments` (town only), (2) `gc import remove` the import, (3) strips the
`PreToolUse` hook from every projected `settings.json`, (4) `gc reload` to
regenerate clean settings, (5) `--purge` deletes the `.venv`.

After uninstall:

```bash
gc import list | grep ast-lens                       # (no output)
grep ast-lens pack.toml                               # (no output, town)
grep read-with-outline city.toml                      # (no output, town)
grep -r outline-on-read.sh .gc/settings.json .gc/agents/*/.gc/settings.json   # (no output)
```

Backups (`*.ast-lens.bak.*`) are left next to each edited file; delete them once
you are satisfied.

---

## Flags

| Flag | Scripts | Meaning |
|---|---|---|
| `--town` | both | City-wide scope. |
| `--rig <name>` | both | Single-rig scope. The rig must already exist in `city.toml` (else the script aborts). |
| `--dry-run` | both | Print the plan; change nothing. |
| `--city <path>` | both | City root (default: two levels above the pack). |
| `--no-reload` | both | Skip `gc reload`; apply on the next `gc start`. |
| `--purge` | uninstall | Also delete `packs/ast-lens/.venv`. |

---

## Notes & caveats

- **`global_fragments` is deprecated** in gc (it warns:
  *“Use `[agent_defaults] append_fragments` or explicit `{{ template }}`”*). It
  still works, and the task contract specifies `global_fragments`, so that is
  what `--town` edits. If you later migrate to `append_fragments`, adjust the
  fragment step accordingly. This only affects the **town** prompt fragment; the
  skill and hook are unaffected.
- **`pack.toml` reformatting.** `gc import add/remove` rewrites the city-root
  `pack.toml` in gc's canonical style (2-space indent, an explicit
  `version = ""`). This is gc-native formatting, not the script's doing; the
  semantic content (your other imports) is preserved exactly. `city.toml`
  round-trips **byte-identical** through a town install+uninstall; rig scope
  round-trips `city.toml` byte-identical too.
- **Safe by design.** With no venv/deps the emitter and hook are silent
  (Algorithm 1 passthrough), so importing the pack can never break a `Read`.
- **`gc`, `jq`, and `python3`** must be on `PATH`. The scripts prepend the usual
  Homebrew / `~/go/bin` / `~/.local/bin` locations to guard against a stripped
  `PATH`.
