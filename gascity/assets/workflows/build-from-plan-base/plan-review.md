This is the `build-from-plan-base` plan-review stage.

Review the implementation plan before decomposition. The verdict must map to
approved, questions, changes_required, or blocked, and it must honor
interaction_mode {{interaction_mode}}.

Write the plan-review artifact to `{{plan_review_path}}` when supplied;
otherwise write it under `{{artifact_root}}`. Record the verdict on the
workflow root bead as `gc.build.plan_review_status=<verdict>` with
`gc bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_status=<verdict>"`.
Close only after `approved` is recorded on the workflow root. A blocked,
changes-required, or questions verdict must still be recorded with a concrete
reason, but it does not complete this stage: this step stays open and iterates
until the plan is approved, so resolve the findings within this stage,
re-review, and record `approved` before closing.

Approval gate: this stage is gated by `.gc/scripts/checks/plan-review-approved.sh`, which passes only when the workflow root records `gc.build.plan_review_status=approved`. Any other value, or a missing value, fails the check and re-dispatches this step. On a later attempt (`gc.attempt` greater than 1), read the previous verdict from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and continue from it instead of starting over. Two bounded attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and a machine-readable reason that blocks downstream stages. Never ask questions in headless mode; record unresolved blockers in the verdict and the artifact.
