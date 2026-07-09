Decompose the approved gstack plan at `{{plan_path}}` into implementation work
and write the decomposition artifact to `{{decomposition_path}}` when supplied.

Create one implementation convoy and record `gc.input_convoy_id` so downstream
Gas City drains can find the workflow root bead and implementation convoy
before closing.

Do not invoke provider-native subagents.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
