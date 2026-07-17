Implement this Compound Engineering shared-drain item with
{{implementation_target}}.

Gas City owns the shared drain and source-anchor lifecycle. Read the claimed
step bead's `gc.root_bead_id`, then read that inner `compound-work-item`
workflow root bead. Resolve its reserved `gc.input_convoy_id`, read the input
convoy, and read `gc.drain_member_id` and `gc.drain_item_index` from the inner
workflow root metadata. Use that drain member as the source anchor. If the
reserved convoy also records `gc.drain_member_id`, require it to match the root
value. Validate the drain item index, ownership, and context path
{{context_path}} when set. Never infer the source anchor from a dependency bead
or use the reserved convoy itself as the source anchor.

Read `work_dir` only from the source anchor and require it to identify the
absolute, existing authoritative shared git worktree. Set `WORKTREE` to that
path, run `cd "$WORKTREE"`, and verify `pwd -P` equals `$WORKTREE` before any
source read, edit, test, hash, `git add`, or commit. The workflow root bead's
`gc.work_dir` identifies the launcher rig root used for artifact validation;
it is not the implementation worktree.

Use the installed ce-work guidance as the implementation discipline. Apply the
smallest complete change for this source anchor, run focused verification
inside the authoritative worktree, and review the scoped diff.

Write the per-item implementation summary as Markdown with YAML front matter
valid for `gc.build.implementation-summary.v1`, not as a freeform note or JSON.
Read its path from the inner workflow root bead metadata
`gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`). If a path
is already recorded, require and use that exact absolute path.

If all summary path keys are blank, resolve the artifact root from the inner
workflow root metadata `gc.var.artifact_root` (fallback
`gc.build.artifact_root`, then rendered `{{artifact_root}}`). Resolve the
launcher rig root from that same workflow root bead's `gc.work_dir`; when it
names an attempt worktree, walk to the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. Resolve a relative artifact root
against that launcher rig root, derive the absolute path
`<artifact-root>/task-<source-anchor-id>-summary.md`, and record it on the inner
workflow root bead as `gc.implementation.summary_path` before writing. Always
record the final absolute path on the workflow root bead, implement step, and
source anchor. In particular, never interpret `{{artifact_root}}` relative to the implementation worktree.

The artifact's first line must be `---`. Use nested mappings with this shape:

```yaml
---
schema: gc.build.implementation-summary.v1
workflow:
  id: <compound-work-item-workflow-root-id>
  formula: compound-work-item
methodology:
  pack: compound-engineering
  name: ce-work
producer:
  formula: compound-work-item
  stage: implement-item
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

Record the intended behavior, changed files, commit hash when applicable, the
first verification command and observed result, the final proof command and
observed result, and remaining risks.

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
`gc.outcome=pass`, then close only the source anchor on success.
Do not invoke provider-native subagents. This Gas City lane is the work
delegation mechanism for ce-work.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
