Use the built-in Gas City `design-review` flow.

Run a plan review against the implementation plan. Treat required changes as blockers for decomposition: update the plan or route the fixes, then re-review within this stage. Capturing unresolved findings does not complete this step; it stays open and iterates until the plan is approved.

Include a lightweight implementation readiness pass before decomposition:

- requirements traceability: every major plan task maps to acceptance criteria
- task boundaries: each task can become a clear implementation bead
- test commands: the plan names the focused proof commands or test strategy
- risk: risky files, migrations, public interfaces, and rollback concerns are
  explicit enough for an implementer

Record the verdict on the workflow root as
`gc.build.plan_review_status=<approved|questions|changes_required|blocked>`
with `gc bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_status=<verdict>"`.
If you write a plan-readiness note, record it on the workflow root as
`gc.build.plan_review_report_path=<path>`. Do not write or overwrite
`gc.build.review_report_path`; that key is reserved for the later
build-basic implementation review artifact.

Approval gate: this stage is gated by `.gc/scripts/checks/plan-review-approved.sh`, which passes only when the workflow root records `gc.build.plan_review_status=approved`. Any other value, or a missing value, fails the check and re-dispatches this step. On a later attempt (`gc.attempt` greater than 1), read the previous verdict from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and continue from it instead of starting over. Two bounded attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and a machine-readable reason that blocks downstream stages. Never ask questions in headless mode; record unresolved blockers in the verdict and the step summary.

Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.
