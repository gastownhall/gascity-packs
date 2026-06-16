Run Superpowers code review with the installed `requesting-code-review` skill.

Review the implementation against the requirements, plan, decomposition, and
test evidence. Write an implementation-review report with pass/fail verdict and
actionable findings. Required fixes must be specific enough for the processing
step to resolve them directly.

Read the code-review context from workflow root metadata
`gc.build.code_review_context_path`. Write the implementation review report to
workflow root metadata path `gc.build.code_review_report_path`, which should be
`<artifact_root>/implementation-review-report.md`.

The implementation review report is a Markdown build artifact, not a freeform
note. It must be valid for `gc.build.review.v1`: start with YAML front matter,
then include the required Markdown sections `## Verdict`, `## Findings`, and
`## Verification`. Use `status: approved` when closing with
`code_review.review_verdict=approve`; use `status: changes_required` when
closing with `code_review.review_verdict=iterate`.

The front matter must include this shape:

```yaml
---
schema: gc.build.review.v1
workflow:
  id: <workflow-root-id>
  formula: <workflow-formula>
methodology:
  pack: superpowers
  name: superpowers-code-review
producer:
  formula: superpowers-code-review
  stage: request-code-review
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: <review-subject-or-context-path>
      hash: sha256:<digest>
      ids: [SEC-001]
  coverage:
    - id: SEC-001
      status: covered
---
```

If an upstream entry lists `ids`, every id must appear exactly once in
`trace.coverage` and in a Markdown coverage table. The validator only
recognizes a Markdown table with an `ID` column and a `Status` column. Use this
shape and make the ID/status pairs exactly match `trace.coverage`:

| ID | Status |
| --- | --- |
| SEC-001 | covered |

Coverage statuses are not finding statuses or verdict statuses. Use only schema
allowed coverage statuses: `covered`, `blocked`, `deferred`, `not_applicable`,
`out_of_scope`, or `superseded`. For `status: changes_required`, use
`blocked` for the coverage rows that are not yet satisfied, and include
`rationale: <why this id is blocked>` on every non-`covered` coverage row. Do
not use `violated`, `resolved`, `approved`, or `changes_required` as
`trace.coverage[].status` or Markdown coverage table statuses. The Markdown
coverage table remains ID/status only; the rationale belongs in YAML front
matter.

Close with `gc.outcome=pass`,
`code_review.review_verdict=approve|iterate`,
`code_review.review_report_path=<implementation review report path>`, and
`code_review.output_path=<implementation review report path>`.

Use the exact claimed bead id when updating metadata. Do not pass freeform notes
or additional positional arguments to `bd update`; unquoted words can resolve to
unrelated beads. Use this command shape:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.review_verdict=approve' \
  --set-metadata 'code_review.review_report_path=<implementation review report path>' \
  --set-metadata 'code_review.output_path=<implementation review report path>'
bd close "$CLAIMED_BEAD_ID" --reason 'Implementation review approved with no required findings.'
```

Do not set `code_review.verdict` or `code_review.report_path`; the
process-code-review lane owns those approval-check fields.

Do not invoke provider-native subagents. You are the Gas City code review lane.
