Use the assigned BMAD architecture skill materialized for this agent.

Create the architecture or implementation plan artifact from the PRD. Preserve BMAD decisions and architecture output, then record the build-base plan path on the workflow root bead.

Do not invoke provider-native subagents or upstream BMAD runtime commands.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
