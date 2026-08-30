This is the `planning-base` methodology contract requirements step.

Concrete methodology packs override this step to produce their native
requirements artifact. Write the approved requirements to `{{requirements_path}}`
when it is provided, or record the resolved requirements path on workflow root
metadata as `gc.build.requirements_path` before closing.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
