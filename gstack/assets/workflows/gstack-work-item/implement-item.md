Implement the assigned gstack shared-drain item.

Gas City owns the shared drain and source-anchor lifecycle. Read the claimed
step's workflow root bead, then require its `gc.drain_member_id`,
`gc.drain_index`, and `gc.drain_control_id`. The drain member is the exact
source anchor; do not infer one from a dependency or use the synthetic input
convoy. The item index must be a non-negative integer.

The required `prepare-shared-worktree` step must already have created or reused
one deterministic shared worktree and persisted `work_dir` on the current
source anchor. Read the source anchor back and require that path to be
absolute, existing, linked to the launcher repository, and distinct from the
launcher checkout. Set `WORKTREE` to that path, run `cd "$WORKTREE"`, and
verify `pwd -P` equals `$WORKTREE` before any source read, edit, test, hash,
commit, or proof command. The workflow root bead's `gc.work_dir` remains the
launcher rig root for validation, not the implementation worktree.

Read only the assigned item scope, implement the smallest complete change, and
run focused proof. Write the item summary as Markdown with YAML front matter
valid for `gc.build.implementation-summary.v1`, not a freeform note or JSON.
Read its path from workflow root metadata `gc.implementation.summary_path`
(fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`).
If all are blank, derive an absolute per-item path for the source anchor and
record it on the workflow root bead as `gc.implementation.summary_path`.

Use nested mappings with this top-level shape:

```yaml
---
schema: gc.build.implementation-summary.v1
workflow:
  id: <gstack-work-item-workflow-root-id>
  formula: gstack-work-item
methodology:
  pack: gstack
  name: gstack-work-item
producer:
  formula: gstack-work-item
  stage: implement-item
  attempt: <positive integer>
status: approved
trace: {upstream: [...], coverage: [...]}
---
```

The artifact's first line must be `---`. Every `trace.upstream` entry must have
`path` and a scheme-qualified `hash`. Represent the source anchor as
`path: beads/<source-anchor-id>` and `hash: bead:<source-anchor-id>`. Preserve
actual source IDs verbatim; never invent, substitute, or renumber them. Every
upstream ID must appear exactly once in `trace.coverage`; when the source
declares no IDs, omit `ids` and use `coverage: []`. Every non-`covered` entry
must include a rationale. Include one Markdown table whose `ID` and `Status`
pairs exactly match the YAML coverage:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, and replace the
placeholder with an actual ID. When coverage is empty, do not add a data row;
omit the table or use only its header and separator.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

Record intended behavior, the first verification command and observed result,
changed files, the final proof command and observed result, and remaining
risks. Bind those claims to the source anchor bead and authoritative
implementation worktree: make a focused commit, read its full commit SHA with
`git rev-parse HEAD` from `$WORKTREE`, and include the exact
`beads/<source-anchor-id>` reference, canonical worktree path, commit SHA,
changed files, and observed passing result in the summary. Record
`gc.implementation.worktree_path`, `gc.implementation.commit`, and
`gc.implementation.summary_path` on the source anchor bead; the summary path
must be inside that worktree. Read the source anchor back and require those
values to match `work_dir`, worktree `HEAD`, and the existing summary. Never
record or accept launcher-checkout proof.

From `$WORKTREE`, run `git status --porcelain --untracked-files=all` after
writing the post-commit summary. Each recorded per-item summary is the only
permitted uncommitted path for its member; other already-recorded member
summaries in the shared worktree are also evidence-only exceptions. Fail
instead of closing if status reports any other staged, unstaged, or untracked
path. An untracked product file is incomplete implementation, not evidence.

Before closing, resolve the launcher rig root from the workflow root
bead's `gc.work_dir`. If that root does not contain the validator, use the
nearest ancestor containing `.gc/scripts/checks/build-artifact-valid.sh`.
Read the exact current bead ID from the startup claim output and substitute it
literally below; shell variables from earlier tool calls do not persist. Then
run:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in the recorded summary before setting
`gc.outcome=pass`.

Close with `gc.outcome=pass` only after verification.

Do not invoke provider-native subagents. You are the single item lane.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
