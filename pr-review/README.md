# PR Review Pack

Formula-driven adopt-PR workflow for Gas City. Reviews and merges contributor
PRs using a multi-model review engine (Claude + Codex + Gemini), with a human
gate between review and merge.

## What's Included

- **`mol-adopt-pr` formula** — 6-step molecule: intake, rebase-check, review,
  human-gate, finalize, complete
- **`/review-pr` skill** — multi-model code review engine (overlay)

## Prerequisites

- `gh` CLI authenticated with repo access
- Polecat agent (from consuming pack) with worktree support
- `bd` CLI for bead operations

## Usage

Sling a PR review to a polecat:

```bash
gc sling <rig>/polecat mol-adopt-pr --formula \
  --var pr=https://github.com/org/repo/pull/42
```

With bare integer (uses current repo):

```bash
gc sling <rig>/polecat mol-adopt-pr --formula --var pr=42
```

Skip Gemini (dual-model mode — Claude + Codex only):

```bash
gc sling <rig>/polecat mol-adopt-pr --formula \
  --var pr=42 --var skip_gemini=true
```

## Workflow

1. **Intake** — Parse PR, fetch metadata, validate scope, checkout branch
2. **Rebase check** — Auto-rebase straightforward conflicts, reject complex ones
3. **Review** — Run `/review-pr` (parallel Claude + Codex + Gemini)
4. **Human gate** — Blocks until maintainer closes the step manually:
   ```bash
   bd close <human-gate-step-id>
   ```
5. **Finalize** — Determine merge path, push, post synthesis comment, wait for CI, merge
6. **Complete** — Clean up refs, update root bead

## Merge Paths

| Path | Condition | Strategy |
|------|-----------|----------|
| A | No maintainer changes | Squash merge |
| B | Maintainer changes + edits enabled | Merge commit (preserves dual authorship) |
| C | Maintainer changes + edits disabled | New PR from maintainer's fork |
| D | Original PR already merged | Follow-up PR for fixups |

## Including in city.toml

```toml
[workspace]
includes = [
    "https://github.com/julianknutsen/packs/tree/main/pr-review",
]
```
