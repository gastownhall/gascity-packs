Finalize the build-basic starter factory review.

Verify the latest starter review loop approved the implementation and wrote a
starter review summary path. Record the approved review path on the workflow
root bead so the build-basic finalize stage can include it in `factory-run.md`.
Use `bd update "<workflow-root-id>" --set-metadata "gc.build.review_report_path=<absolute path>"`.
Do not use `bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.

Review approval is based on the implementation source anchor/worktree recorded
in the review context and canonical implementation summary. Do not downgrade the
review to `changes_required` because the launcher rig root has not been mutated;
root propagation is handled by publish. If the source anchor/worktree satisfies
the requirements and the remaining issue is only "not copied to root", write the
normalized `gc.build.review.v1` artifact with `status: approved`.

The approved review report must be a Markdown build artifact with YAML front
matter, not JSON. If the latest synthesis is not already valid for
`gc.build.review.v1`, write a normalized `review-report.md` under the build
artifact root and record that path. The front matter must include workflow
id/formula, methodology pack/name, producer formula/stage/attempt, `status`,
and `trace` with upstream and coverage entries. Include a Markdown coverage
table whose ID/status pairs exactly match `trace.coverage`, plus these required
sections:
The validator only recognizes a Markdown table with an `ID` column and a
`Status` column. Use this shape:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`. The top-level YAML shape must be:

- `schema: gc.build.review.v1`
- `workflow: {id: <workflow-root-id>, formula: build-basic}`
- `methodology: {pack: gascity, name: build-basic}`
- `producer: {formula: build-basic-review, stage: review, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `trace: {upstream: [...], coverage: [...]}`

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- For upstream build artifacts, use their recorded paths and scheme-qualified
  hashes such as `sha256:<digest>` or `git:<revision>`. For convoy or bead
  inputs, use `path: beads/<bead-id>` and `hash: bead:<bead-id>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for satisfied
  requirements; do not use `approved` in `trace.coverage[].status` or the
  Markdown coverage table.
- Do not create any additional Markdown table with both an `ID` column and a
  `Status` column unless it repeats the exact same coverage ID/status pairs.
  For requirement summaries, use different column names such as `Requirement`
  and `Result`, or use `covered` as the status for every covered requirement.

- Verdict
- Findings
- Verification

Before closing this expansion target, set the claimed step outcome with
`bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `bd close`.

Do not invoke provider-native subagents or provider-specific task tools.
