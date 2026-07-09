Create the gstack implementation convoy.

Read the approved plan and decompose it into implementation beads under the
workflow root bead. Each bead must map to one vertical slice and include
acceptance criteria, files or modules likely affected, first verification
command, and expected proof command.

Record `gc.input_convoy_id` on the current step, create the implementation
convoy, and link source-anchor beads back to the workflow root bead. Before
closing, ensure the implementation convoy is discoverable from the workflow
root bead.

Do not copy review-lane procedure into implementation beads. The convoy should
describe product work; `gstack-work` carries the execution process.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents. Gas City graph lanes own fanout.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
