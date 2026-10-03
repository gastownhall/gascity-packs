Run the Superpowers gap-analysis review lane.

Use the installed verification guidance to check whether the implementation
actually satisfies the approved requirements, plan, decomposition, and claimed
test evidence. Flag missing behavior, unverified acceptance criteria, drift from
the plan, and test claims that were not proven by commands or artifacts.

Write concrete findings that the feedback-processing lane can resolve in one
pass with file, artifact, command, or requirement references.

## Retry-aware evidence

The subject diff and implementation summary describe the **Initial-review
baseline**. They preserve the original change for traceability, so they may
continue to show a defect after a repair pass. Before issuing a verdict, inspect
the current attempt and its repair evidence:

1. List closed lanes for this workflow root with `gc.step_id=write-report.process-code-review`, then select the highest numeric `gc.attempt` that is lower than this lane's attempt.
2. If that prior process lane has `code_review.verdict=iterate`, read the
   review-fix summary at workflow-root metadata
   `gc.build.review_fix_summary_path`.
3. Verify the claimed resolution against the fixed implementation worktree or
   commit recorded in that summary, including its relevant test evidence.

The static initial subject alone is not evidence that a finding remains open.
On a retry, you must not issue an `iterate` verdict merely because the
Initial-review baseline still contains the original vulnerable code. Return
`iterate` only for a finding that remains in the fixed implementation or whose
claimed resolution cannot be verified.

## Standalone-review scope

This review workflow may be invoked directly against a diff rather than from a
full build workflow. In that case the requirements, plan, and decomposition
paths may be intentionally absent. Apply this rule only when the context says
`implementation_convoy_id: not provided` as well as marking the three upstream
paths not provided. Their absence must not by itself cause `iterate`: record it
as unavailable context, not as a required implementation finding. When a
convoy or any upstream input is declared, return `iterate` for a missing
required artifact or evidence of a concrete failure or mismatch.

Read the code-review context from workflow root metadata
`gc.build.code_review_context_path`. Write the gap-analysis report to workflow
root metadata path `gc.build.gap_analysis_report_path`, which should be
`<artifact_root>/gap-analysis-report.md`.

The gap-analysis report is a Markdown build artifact, not a freeform note. It
must be valid for `gc.build.review.v1`: start with YAML front matter, then
include the required Markdown sections `## Verdict`, `## Findings`, and
`## Verification`. Use `status: approved` when closing with
`code_review.gap_verdict=approve`; use `status: changes_required` when closing
with `code_review.gap_verdict=iterate`.

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
  stage: gap-analysis-review
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: <review-context-or-implementation-review-path>
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

Close with `gc.outcome=pass`, `code_review.gap_verdict=approve|iterate`,
`code_review.gap_report_path=<gap-analysis report path>`, and
`code_review.output_path=<gap-analysis report path>`.

Use the exact claimed bead id when updating metadata. Do not pass freeform notes
or additional positional arguments to `gc bd update`; unquoted words can resolve to
unrelated beads. Use this command shape:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.gap_verdict=approve' \
  --set-metadata 'code_review.gap_report_path=<gap-analysis report path>' \
  --set-metadata 'code_review.output_path=<gap-analysis report path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Gap-analysis review approved with no required findings.'
```

Do not set `code_review.verdict` or `code_review.report_path`; the
process-code-review lane owns those approval-check fields.

Do not invoke provider-native subagents or upstream plugin runtime commands.
