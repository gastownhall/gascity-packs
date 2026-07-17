Finalize the build-basic review.

From the highest numeric `gc.attempt`, select exactly one current lane/synthesis/
terminal group. Report mode requires `report-review-findings`, terminal verdict
`reported`, and lane verdicts `approve|iterate`. Other modes require
`apply-review-findings`, terminal verdict `done`, and all lanes `approve`. The
terminal's `code_review.reviewed_attempt` must equal its `gc.attempt`; do not use
this finalizer step's own `gc.attempt`. All rows must share the live snapshots.
Recompute the combined value from implementation snapshot and canonical
summary/context paths and bytes; mismatch requires iteration.

In report mode preserve the semantic result: use `status: approved` only when
all lanes approve, otherwise `status: changes_required`. A valid report succeeds
even when findings require changes. Other modes require `status: approved`.

Read `<artifact-root>` from root `gc.build.artifact_root`; require it to be
absolute and equal the parent of `gc.build.code_review_context_path`. Write
exactly `<artifact-root>/review-report.md`; never write review evidence into an
implementation worktree. Record it with:
`gc bd update "<workflow-root-id>" --set-metadata "gc.build.review_report_path=<absolute path>"`.
Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.

Write a normalized `gc.build.review.v1` Markdown artifact from the synthesis;
never mutate or repoint summary or context. Include one coverage table whose
ID/status pairs exactly match `trace.coverage`. The validator only recognizes a
Markdown coverage table with the same status when
it has `ID` and `Status` columns:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`:

- `schema: gc.build.review.v1`
- `workflow: {id: <workflow-root-id>, formula: build-basic}`
- `methodology: {pack: gascity, name: build-basic}`
- `producer: {formula: build-basic-review, stage: review, attempt: <positive integer>}`
- `status: approved|changes_required` under the mode rule above
- `implementation_snapshot: <exact current snapshot>`
- `review_input_snapshot: <exact current review-input snapshot>`
- `reviewed_attempt: <exact positive loop attempt>`
- `trace: {upstream: [...], coverage: [...]}`

Trace the exact canonical implementation summary once at the absolute `gc.build.implementation_summary_path`
with its freshly computed `sha256:<digest>`. Trace
`gc.build.code_review_context_path` once with its current
digest. The `implementation_snapshot: <exact current snapshot>` and review-input
snapshot must equal the root and every row; repeat both in Verification.

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- Use scheme-qualified hashes. If an entry lists `ids`, every ID must appear
  exactly once in `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for approved
  coverage; for `status: changes_required`, include at least one `blocked` row
  with rationale; do not use `approved` in `trace.coverage[].status`.
- Do not create any additional Markdown table with both an `ID` column and a
  `Status` column unless it repeats the exact matrix.

Required body sections: Verdict, Findings, and Verification.

Before closing this expansion target, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.

Do not invoke provider-native subagents or provider-specific task tools.
