Review the plan with the installed Superpowers planning-review guidance.

Check whether the plan is implementable, traceable to the requirements, testable, and scoped to the requested outcome. Return findings in the design-review artifact format consumed by the approval check.

Reject with `design_review.review_verdict=iterate` if any `### Task N` section
represents Superpowers build lifecycle work such as prepare, requirements,
plan, plan-review, decompose, review, finalize, or publish. Those phases are
already being executed by the formula and must not become implementation beads.
Approved `### Task N` sections must be only downstream source-code work for the
original input task or convoy member.

Read the plan-review context from workflow root metadata
`gc.build.plan_review_context_path`. Write the plan-review report to workflow
root metadata path `gc.build.plan_review_report_path`, which should be
`<artifact_root>/plan-review-report.md`.

Close with `gc.outcome=pass`,
`design_review.review_verdict=approve|iterate`, and
`design_review.output_path=<report path>`. Do not set
`design_review.verdict`; the feedback lane owns the loop verdict consumed by
the approval check.

Do not invoke provider-native subagents. You are the Gas City lane for this prompt.
