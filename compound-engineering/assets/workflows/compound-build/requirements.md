Use the assigned Compound Engineering brainstorm skill materialized for this agent.

Run the brainstorm discipline against the build target and optional context path. Produce a requirements artifact in the build artifact root that preserves Compound Engineering requirement and assumption identifiers while satisfying the build-base requirements contract.

Read the requirements path from workflow root metadata
`gc.build.requirements_path`. After writing the artifact, update the workflow
root bead with:

- `gc.build.requirements_path=<requirements artifact path>`
- `gc.build.requirements_status=approved|draft|failed`
- `gc.build.requirements_summary=<one-sentence summary>`

Close this step only after the workflow root metadata and this step metadata
record the same requirements outcome.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
