Synthesize the Compound Engineering plan-review lanes.

Merge coherence, feasibility, scope, and architecture findings into one plan-review report. Deduplicate overlapping findings, classify each as required change or residual risk, and write the approval verdict used by `../assets/scripts/checks/design-review-approved.sh`.

Read the review context from `gc.build.plan_review_context_path` and write the
synthesized report to `gc.build.plan_review_report_path`, which should be
`<artifact_root>/plan-review/report.md`.

Close with `gc.outcome=pass`,
`design_review.review_verdict=approve|iterate`, and
`design_review.review_report_path=<synthesized report path>`. Do not set
`design_review.verdict`; the apply-plan-findings lane owns the final loop
verdict consumed by the approval check.

Do not invoke provider-native subagents. Synthesis happens in this Gas City lane.
