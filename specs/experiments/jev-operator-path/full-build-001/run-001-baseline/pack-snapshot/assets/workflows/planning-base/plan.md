This is the `planning-base` methodology contract plan step.

Concrete methodology packs override this step to produce their native
implementation plan or design artifact. Write the plan to `{{plan_path}}` when
it is provided, and keep serialization at the artifact boundary. Record the
resolved plan path on workflow root metadata as `gc.build.plan_path` before
closing.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
