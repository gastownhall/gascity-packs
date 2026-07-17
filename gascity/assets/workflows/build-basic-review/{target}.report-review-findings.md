Record build-basic starter review findings in report mode.

This is the structurally read-only terminal review lane. Read the three current
review lanes, synthesis, live root snapshots, canonical summary, and review
context. Never edit or commit implementation bytes, update implementation
members, rewrite canonical summary/context, or change workflow-root provenance.
The preceding refresh child owns deterministic provenance publication.

Require every current-attempt row to carry the same live
`code_review.implementation_snapshot` and
`code_review.review_input_snapshot`. Record lane verdicts and required findings
without applying them. An `iterate` finding is a completed report, not a request
to rerun this read-only loop. Write exactly
`<artifact-root>/apply-review-findings-report.md`; require
`gc.build.artifact_root` to be absolute and equal the parent of
`gc.build.code_review_context_path`. Never write review evidence in the
implementation worktree.

Close only this claimed bead with `gc.outcome=pass`,
`code_review.verdict=reported`,
`code_review.reviewed_attempt=<current gc.attempt>`, both exact snapshot values,
and `code_review.report_path` plus `code_review.output_path` equal to the report:

```bash
gc bd update "$CLAIMED_BEAD_ID" --set-metadata 'gc.outcome=pass' --set-metadata 'code_review.verdict=reported' --set-metadata 'code_review.reviewed_attempt=<current gc.attempt>' --set-metadata 'code_review.implementation_snapshot=<current snapshot>' --set-metadata 'code_review.review_input_snapshot=<current review-input snapshot>' --set-metadata 'code_review.report_path=<artifact-root>/apply-review-findings-report.md' --set-metadata 'code_review.output_path=<artifact-root>/apply-review-findings-report.md'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Starter review recorded without mutation.'
```

Do not invoke provider-native subagents.
