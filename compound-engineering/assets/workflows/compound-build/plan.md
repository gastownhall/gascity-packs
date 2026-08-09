Use the assigned Compound Engineering planning skill materialized for this agent.

Create a plan artifact from the requirements output. Preserve Compound Engineering traceability identifiers and include the stage handoff details needed by the build-base plan, plan-review, and decompose stages.

Read the requirements artifact from workflow root metadata
`gc.build.requirements_path` and write the plan artifact to
`gc.build.plan_path`. After writing the artifact, update the workflow root bead
with:

- `gc.build.plan_path=<plan artifact path>`
- `gc.build.plan_status=approved|draft|failed`
- `gc.build.plan_summary=<one-sentence summary>`

Close this step only after the workflow root metadata and this step metadata
record the same plan outcome.

Do not invoke provider-native subagents or upstream plugin runtime commands. If
upstream methodology would require document-review or research subagents, record
the needed graph lanes as required follow-up.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
