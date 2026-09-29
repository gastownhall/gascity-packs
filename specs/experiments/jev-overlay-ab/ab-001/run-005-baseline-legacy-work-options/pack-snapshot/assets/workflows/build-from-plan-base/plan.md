This is the `build-from-plan-base` plan stage.

Produce or reuse the implementation plan using approved requirements from
`{{requirements_path}}`. Write the plan to `{{plan_path}}` when provided;
otherwise write the default implementation-plan artifact under
`{{artifact_root}}`.

The plan must preserve requirement traceability, upstream hashes, assumptions,
risks, out-of-scope work, and verification strategy. Close only after the plan
path and content hash are recorded for the inherited decompose suffix.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
