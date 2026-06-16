Use the assigned Superpowers writing-plans skill materialized for this agent.

Write a plan artifact from the requirements output. Include enough implementation sequencing for build-base plan-review and decompose to proceed.

Scoping invariant: the Superpowers build lifecycle phases are already being
executed by this formula. Do not write `prepare`, `requirements`, `plan`,
`plan-review`, `decompose`, `implement`, `summarize-implementation`, `review`,
`finalize`, or `publish` as `### Task N` implementation sections. Describe the
lifecycle in prose or traceability tables only.

Only `### Task N` sections are decomposed into implementation beads. Each
`### Task N` section must describe downstream source work for the original
input task or convoy member: files to modify, behavior to implement, tests to
write or run, and acceptance criteria. For the build fixture, the plan should
produce a single implementation task for `slugger.py` / `slugify()` unless the
approved requirements identify additional source-code work.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
