This is the `build-base` plan-review stage. Treat it as a virtual contract that concrete formulas may override.

Review the plan for traceability to requirements, feasibility, missing edge cases, and implementation readiness. If changes are required, update or route the plan before closing this stage.

Record the verdict on the workflow root bead as
`gc.build.plan_review_status=<approved|questions|changes_required|blocked>`
with `gc bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_status=<verdict>"`.
Still record blocking issues in the step summary, but recording them does not
complete this stage: a `changes_required`, `questions`, or `blocked` verdict
keeps this step open, and it iterates until the plan is approved. Resolve the
findings within this stage (apply or route the plan changes, or in
`interactive` mode obtain the answers), re-review, and record `approved`
before closing.

Approval gate: this stage is gated by `.gc/scripts/checks/plan-review-approved.sh`, which passes only when the workflow root records `gc.build.plan_review_status=approved`. Any other value, or a missing value, fails the check and re-dispatches this step. On a later attempt (`gc.attempt` greater than 1), read the previous verdict from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and continue from it instead of starting over. Two bounded attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and a machine-readable reason that blocks downstream stages. Never ask questions in headless mode; record unresolved blockers in the verdict and the step summary.

Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.
