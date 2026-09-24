This is the `build-base` decompose stage. Treat it as a virtual contract that concrete formulas may override.

Convert the approved requirements and plan into executable work units. The
decomposition must preserve traceability back to the plan, create or identify
the implementation beads that will form the implementation convoy, and avoid
implementation choices not already supported by the approved artifacts.

Create a new implementation convoy for the work units. Do not reuse the source
or launch convoy from `gc.var.convoy_id`; that convoy only carried the original
workflow request. The implementation convoy must contain only the runnable work
unit beads that the drain stage should execute.

Record the implementation convoy ID on the workflow root bead as both:

- `gc.input_convoy_id=<implementation-convoy-id>` for the drain contract.
- `gc.build.implementation_convoy_id=<implementation-convoy-id>` for build
  reporting and downstream methodology-specific stages.

Use one quoted `gc bd update` command against the workflow root bead, for example:

`gc bd update "<workflow-root-id>" --set-metadata "gc.input_convoy_id=<implementation-convoy-id>" --set-metadata "gc.build.implementation_convoy_id=<implementation-convoy-id>"`

Close this step only after the decomposition artifact or task beads are
recorded on the workflow root bead and both convoy metadata fields are set
before closing. Verify the recorded implementation convoy is not the original
launch/source convoy.

Write the decomposition artifact to the resolved decomposition path and ensure
that path is recorded on the workflow root bead as `gc.build.decomposition_path`.
Use `gc bd update "<workflow-root-id>" --set-metadata "gc.build.decomposition_path=<absolute path>"`.
Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.
Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
