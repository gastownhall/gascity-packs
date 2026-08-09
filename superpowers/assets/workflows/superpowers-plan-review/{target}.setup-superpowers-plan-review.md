Prepare the Superpowers plan-review context.

Resolve the requirements artifact, plan artifact, artifact root, and optional
context bundle from workflow root metadata. Use these exact handoff paths:

- plan-review context: `<artifact_root>/plan-review-context.md`
- plan-review report: `<artifact_root>/plan-review-report.md`
- plan-review apply summary: `<artifact_root>/plan-review-apply-summary.md`

Write the compact context file to the plan-review context path. The context
file must include the requirements path, plan path, optional context bundle
path/status, source bead id, workflow root id, and the exact report/apply
summary paths above.

Update workflow root metadata before closing:

- `gc.build.plan_review_context_path=<context path>`
- `gc.build.plan_review_report_path=<report path>`
- `gc.build.plan_review_apply_summary_path=<apply summary path>`
- `gc.build.plan_review_status=ready`

The context file must state the loop contract: the plan-document-review lane
writes `design_review.review_verdict=approve|iterate`; the apply-plan-feedback
lane owns `design_review.verdict=done|iterate` for
`../assets/scripts/checks/design-review-approved.sh`.

Close this setup bead with `gc.outcome=pass` and
`design_review.output_path=<context path>`.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This graph stage is the delegation mechanism.
