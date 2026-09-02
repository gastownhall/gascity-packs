Implement the owned source anchor inside the Gas City worktree that
`prepare-worktree` published.

Resolve `<source-anchor-id>` using the same rules as `prepare-worktree`. For a
synthetic drain-unit convoy, the source anchor is the original drain member in
`gc.drain_member_id`, not the synthetic convoy id. Read `work_dir` from the
source anchor, never from the synthetic drain-unit convoy. Validate that it is
an absolute existing git worktree, set `WORKTREE` to that path, then
`cd "$WORKTREE"` before reading or editing source files.

Do not edit files in the launcher checkout. Do not invoke provider-native subagents.

Write `gc.build.implementation-summary.v1` and record its absolute path on the
workflow root bead as `gc.implementation.summary_path` before closing.

Use mapping objects for front matter:

- `schema: gc.build.implementation-summary.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: pstack, name: pstack-build}`
- `producer: {formula: pstack-work, stage: implement, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `trace: {upstream: [...], coverage: [...]}`

Required body sections in this order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

Include a Markdown coverage table with `ID` and `Status` columns.

Artifact validation: this step is gated by
`.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary
recorded at `gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`) against
schema `gc.build.implementation-summary.v1`.
