This is the `build-from-requirements-base` requirements stage.

Produce or reuse the requirements artifact at `{{requirements_path}}` when
provided; otherwise write the default requirements artifact under
`{{artifact_root}}`.

The requirements artifact must use the base requirements contract, stable IDs,
example mapping, acceptance criteria, open questions, out-of-scope notes, and
approval state. Close only after the requirements path and content hash are
recorded for the inherited plan suffix.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
