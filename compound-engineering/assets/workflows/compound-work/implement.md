Implement this Compound Engineering item with {{implementation_target}}.

Gas City owns the worktree, bead, and convoy plumbing. Resolve the source anchor
before reading or editing source. Read the claimed step bead's
`gc.root_bead_id`, then read that inner `compound-work` workflow root bead and
its `gc.input_convoy_id`. Read the input convoy. If it has
`gc.synthetic_kind=drain-unit-convoy`, use its `gc.drain_member_id` as the
source anchor; otherwise use the input convoy ID. Never use a dependency bead
or the synthetic drain-unit convoy itself as the source anchor.

Read `work_dir` only from the source anchor. Require it to be an absolute,
existing git worktree distinct from the launcher checkout. Set `WORKTREE` to
that path, run `cd "$WORKTREE"`, and verify `pwd -P` equals `$WORKTREE` before
any source read, edit, test, hash, `git add`, or commit. If `work_dir` is
missing or invalid, fail before editing. The workflow root bead's `gc.work_dir`
identifies the launcher rig root used for artifact validation; it is not the
implementation worktree.

Use the installed ce-work guidance as the implementation discipline for this
Gas City lane. Implement only the owned source anchor boundary, run focused
verification inside the authoritative worktree, review the scoped diff, and
make a focused commit there when the item requires source changes.

Write the per-item implementation summary as Markdown with YAML front matter
valid for `gc.build.implementation-summary.v1`, not as a freeform note or JSON.
Read its path from the inner workflow root bead metadata
`gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`). If a path
is already recorded, require and use that exact absolute path.

If all summary path keys are blank, derive the absolute summary path as
`<WORKTREE>/implementation-summary.md`. If a summary path is already recorded,
resolve it and require it to be inside `WORKTREE`; never accept a launcher or
attempt-local artifact as the per-item summary. The launcher artifact root
still owns aggregate build artifacts; never interpret `{{artifact_root}}` relative to the implementation worktree.
Record the final absolute path on the
workflow root bead, implement step, and source anchor before writing.

The artifact's first line must be `---`. Use nested mappings with this shape:

```yaml
---
schema: gc.build.implementation-summary.v1
workflow:
  id: <compound-work-workflow-root-id>
  formula: compound-work
methodology:
  pack: compound-engineering
  name: ce-work
producer:
  formula: compound-work
  stage: implement
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: beads/<source-anchor-id>
      hash: bead:<source-anchor-id>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

The required logical trace shape is
`trace: {upstream: [...], coverage: [...]}`. Every upstream entry must contain
a non-empty `path` and scheme-qualified `hash`. Preserve actual source IDs
verbatim; never invent, substitute, or renumber them. Every declared upstream
ID must occur exactly once in coverage. If no source declares IDs, omit `ids`
and use `coverage: []`. Use only schema coverage statuses, and add a non-empty
`rationale` to every non-`covered` entry.

When coverage is non-empty, include one Markdown coverage table whose `ID` and `Status`
pairs exactly match the YAML coverage:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Replace the illustrative data row with actual IDs. When coverage is empty,
omit the table or include only its header and separator; never emit a
placeholder data row.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

Record the intended behavior, changed files, commit hash, the first
verification command and observed result, the final proof command and observed
result, and remaining risks.

Before closing, return only as needed to the launcher rig root. If the root's
`gc.work_dir` does not itself contain the validator, use the nearest ancestor
that does. From that launcher rig root run:

Read the exact current bead ID from the startup claim output. In the same shell
invocation, substitute it literally for the placeholder below; variables from
earlier tool calls do not persist.

```bash
export CLAIMED_BEAD_ID='<exact-current-bead-id>'
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in the exact recorded summary before setting
`gc.outcome=pass`. Leave the source anchor open for the close-source-anchor
step. Do not invoke provider-native subagents.

After the final product verification and focused commit, read the full commit
from the authoritative worktree with `git rev-parse HEAD`. Persist the exact
proof tuple on the source anchor bead itself in one update:

```bash
gc bd update <source-anchor-id> \
  --set-metadata "gc.implementation.worktree_path=$WORKTREE" \
  --set-metadata "gc.implementation.commit=<full-HEAD-from-WORKTREE>" \
  --set-metadata "gc.implementation.summary_path=<absolute-summary-inside-WORKTREE>"
```

Read the source anchor bead back. Require its `work_dir` and recorded worktree
path to resolve to the same worktree, its commit to equal that worktree's
`HEAD` (the recorded commit must equal the worktree's `HEAD`), and its summary
to exist inside that worktree. Do not report pass until
all three checks succeed.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
