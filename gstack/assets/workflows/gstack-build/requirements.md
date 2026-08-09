Run garrytan/gstack office-hours intake for this build.

Use the gstack sprint model: Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect.
The upstream vocabulary is office-hours, plan-ceo-review,
plan-eng-review, plan-design-review, plan-devex-review, review, qa, cso, ship,
land-and-deploy, and document-release. In Gas City, those become graph lanes.

Current interaction_mode is {{interaction_mode}}. In interactive mode, ask one
focused question at a time when demand, status quo, user specificity, narrowest
wedge, observation, or future-fit is missing. In autonomous mode, write the
best requirements artifact from available context and record assumptions.

Write requirements to the requested requirements path when present. Include:
goal, demand evidence, current workaround, target user, narrowest wedge,
future-fit, constraints, acceptance criteria, non-goals, and open questions.

Close with `gc.outcome=pass` and the requirements artifact path.

Do not invoke provider-native subagents. This Gas City lane is the office-hours
worker for the build.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
