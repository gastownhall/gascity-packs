This is the `build-from-decompose-base` decomposition stage.

Read the approved requirements from `{{requirements_path}}` (provided at launch, so its interpolation is stable).

Resolve the approved implementation plan and the plan-review artifact at RUNTIME from the workflow ROOT var store — do NOT rely on the instantiation-frozen `{{plan_path}}`/`{{plan_review_path}}`. Those render at instantiation, before the plan and plan-review stages produce their paths, so when the paths are produced mid-flow they freeze EMPTY (dip-5hkepo). By the time this step is claimable the producing stages have promoted the real paths to the workflow root (plan via the plan stage, plan-review via the plan-review stage). Run `bd show "<workflow-root-id>" --json` and read `gc.build.plan_path` (fallback `gc.var.plan_path`) for the approved implementation plan and `gc.build.plan_review_path` (fallback `gc.var.plan_review_path`) for the plan-review verdict. Resolve `<workflow-root-id>` via `gc.root_bead_id` on this step bead (a bead with no `gc.root_bead_id` is its own workflow root).

Use the selected decomposition methodology `{{decomposition_formula}}` when translating the plan into durable work items.

Create or adopt an implementation convoy for the work units. The convoy must contain only runnable implementation beads for this continuation; do not reuse any original request, planning, or workflow-control convoy.

Write the decomposition artifact to `{{decomposition_path}}` when supplied; otherwise write it under `{{artifact_root}}` as the default decomposition artifact. The decomposition must include work item IDs, requirement and plan traceability, expected files or formula assets, verification expectations, dependencies, skipped work, and blocked work with rationale.

Record the implementation convoy ID on the workflow root bead as both:

- `gc.input_convoy_id=<implementation-convoy-id>` for the drain contract.
- `gc.build.implementation_convoy_id=<implementation-convoy-id>` for continuation reporting.

Close this step only after the decomposition artifact is recorded and both convoy metadata fields are set. Verify the recorded implementation convoy is not the original launch or workflow-control convoy.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
