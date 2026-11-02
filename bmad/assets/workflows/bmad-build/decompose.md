Use the assigned BMAD epic/story decomposition skill materialized for this agent.

Create epics and stories from the approved PRD and architecture. Preserve
traceability to BMAD artifacts, create story beads for implementation, and
translate the resulting story set into the build-base decomposition output and
implementation convoy.

Record the implementation convoy ID on the workflow root bead as
`gc.input_convoy_id=<implementation-convoy-id>` with
`gc bd update <workflow-root-id> --set-metadata gc.input_convoy_id=<implementation-convoy-id>`
before closing.

Do not invoke provider-native subagents or upstream BMAD runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
