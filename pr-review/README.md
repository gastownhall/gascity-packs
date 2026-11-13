# PR Review Pack

Formula-driven adopt-PR workflow for Gas City. Reviews contributor
PRs using a multi-model review engine (Claude + Codex + Gemini), with a human
gate before finalize and a publish/merge handoff to mayor.

## What's Included

- **`mol-adopt-pr` formula** — 5-step molecule: intake, rebase-check, review,
  human-gate, finalize
- **`/review-pr` skill** — multi-model code review engine (overlay), including
  explicit doc-contract, error-path parity, lock-contract, and Gas City
  mechanical-sync checks

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
   gc bd close <human-gate-step-id>
   ```
5. **Finalize** — Resolve merge path, prepare local artifacts (squash/rebase/branch/synthesis), hand publish + merge to mayor, then clean up refs and update the root bead

## Merge Paths

| Path | Condition | Strategy |
|------|-----------|----------|
| A | No maintainer changes | Squash merge |
| B | Maintainer changes + edits enabled | Merge commit (preserves dual authorship) |
| C | Maintainer changes + edits disabled | New PR from maintainer's fork |
| D | Original PR already merged | Follow-up PR for fixups |

## Publication hand-off

`mol-pr-from-issue`, `mol-pr-revert` and `mol-pr-merge-only` perform no GitHub
write and no push. Each run ends at `branch-ready` with the finished work local and the exact publish
commands recorded on the molecule root bead:

| Formula | Recorded command keys |
|---------|-----------------------|
| `mol-pr-from-issue` | `evidence.publish_push_cmd`, `evidence.publish_create_cmd` |
| `mol-pr-revert` | `evidence.publish_push_cmd`, `evidence.publish_create_cmd`, `evidence.publish_comment_cmd` |
| `mol-pr-merge-only` | `evidence.publish_ack_cmd`, `evidence.publish_push_cmd`, `evidence.publish_merge_cmd` |

The publisher (the `publish_owner` var, default `maintainer`, recorded as
`evidence.publish_owner`) runs them in that order from its own login and its
own checkout, after human approval of the artifact. Every command is fully resolved and shell-quoted: it
names the repository, pushes an exact SHA by URL from the recorded git
directory (pinned by a `refs/staged-gh/<root>` ref), and needs no hand edits.
Comment and label writes the pool used to post are staged under
`.gc/staged-gh/<root>-pr-<n>/` with their commands in the root bead notes.
`pr-review/tests/test_handoff_publish_commands.py` replays the recorded
commands through bash to hold that contract.

Recommended deployment: give unattended pool seats a read-only `GH_TOKEN`.
Without it the pool itself can publish, and only this prose stands between
an unreviewed branch and the forge.

## Importing into pack.toml

```toml
[imports.pr-review]
source = "../packs/pr-review"
```
