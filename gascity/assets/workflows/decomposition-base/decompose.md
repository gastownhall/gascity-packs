This is the `decomposition-base` methodology contract decomposition step.

Concrete methodology packs override this step to translate `{{plan_path}}` into
their native task shape, using optional context from `{{context_path}}`. Write
or record `{{decomposition_path}}` when the caller supplied an explicit
decomposition artifact path, and record the resolved path on workflow root
metadata as `gc.build.decomposition_path` before closing. The output must still
be an implementation convoy that downstream implementation formulas can drain
without knowing the planning methodology.

Create every work bead under the bead being decomposed (the source bead):

- Resolve the source bead from the launch convoy recorded on the workflow root
  as `gc.var.convoy_id`. Read it with `gc bd show <convoy-id> --json` (unwrap a
  one-element list). If it has `gc.synthetic=true` (the wrapper that
  `gc sling <bead>` makes), the source bead is its one tracked member from
  `gc convoy status <convoy-id> --json` `.children`. Never use the convoy ID
  itself as the parent.
- Pass `--parent <source-bead-id>` to every `gc bd create` for a runnable work
  bead, so the work stays grouped under the source bead in beads and in
  trackers that mirror them (for example, as Linear sub-issues).
- When the source bead is a `project` and the plan assigns a work bead to one
  of that project's milestones, use that milestone as the bead's parent
  instead.
- The implementation convoy keeps its `tracks` membership for dispatch;
  `--parent` only sets the parent-child hierarchy. Do not parent the
  implementation convoy bead itself.
- Before creating anything, check that each parent exists with
  `gc bd show <parent-id> --json`.
- If there is no single source bead (no launch convoy, or a non-synthetic
  convoy that groups several beads), create the work beads without a parent
  and record that reason in the decomposition artifact.

Artifact validation: this step is gated by the pack-owned `build-artifact-valid.sh` check, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
