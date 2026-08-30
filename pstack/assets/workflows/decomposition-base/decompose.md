This is the `decomposition-base` methodology contract decomposition step.

Concrete methodology packs override this step to translate `{{plan_path}}` into
their native task shape, using optional context from `{{context_path}}`. Write
or record `{{decomposition_path}}` when the caller supplied an explicit
decomposition artifact path, and record the resolved path on workflow root
metadata as `gc.build.decomposition_path` before closing. The output must still
be an implementation convoy that downstream implementation formulas can drain
without knowing the planning methodology.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
