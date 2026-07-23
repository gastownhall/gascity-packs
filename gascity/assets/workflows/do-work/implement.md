
Before any source read, edit, test, hash, `git add`, or `git commit`, obtain and
verify the authoritative convoy- or epic-owned workspace for this claimed item:

```sh
gc gc workspace path --step-id "<claimed-step-id>"
gc gc workspace verify-entry --step-id "<claimed-step-id>"
```

Work only in the returned workspace. Treat a missing or invalid workspace as
fatal. Do not infer or reconstruct its location and do not repair workspace
state.

Implement only the owned source-anchor boundary, run sandboxed verification
inside the workspace, and make a focused commit there. Leave the source anchor
open for `close-source-anchor`; close only this implementation step when done.

After implementation, tests, and the focused commit are complete, require a
clean workspace and run:

```sh
gc gc workspace record-result --step-id "<claimed-step-id>"
```

No-change results are valid; do not close this step with pass until that command
succeeds.

For artifact validation, read the launcher rig root from the workflow root bead's `gc.work_dir`, then run:

```sh
GC_BEAD_ID="$CLAIMED_STEP_ID" .gc/scripts/checks/build-artifact-valid.sh
```

fix every reported validation error before setting `gc.outcome=pass`.

Write or update the task summary with these schema-required body sections,
using the exact `##` headings below in this order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

The `## Verification` section must include both the first verification command
and the final proof command, with the observed pass/fail result.

Write the summary as a `gc.build.implementation-summary.v1` artifact and record
its absolute path on the workflow root bead as `gc.implementation.summary_path`
before closing.
Include a Markdown coverage table. The validator only recognizes a table with
an `ID` column and a `Status` column. Use this shape:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`. The top-level YAML shape must be:

- `schema: gc.build.implementation-summary.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: gascity, name: build-basic}`
- `producer: {formula: do-work, stage: implement, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `trace: {upstream: [...], coverage: [...]}`

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- For the source anchor bead, use `path: beads/<source-anchor-id>` and
  `hash: bead:<source-anchor-id>`. For changed files or upstream build
  artifacts, use repo-relative paths and scheme-qualified hashes such as
  `sha256:<digest>` or `git:<revision>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for satisfied
  requirements; do not use `approved` in `trace.coverage[].status` or the
  Markdown coverage table.

Artifact validation gates this step and validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. Fix every reported validation error before setting `gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
