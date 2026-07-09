Draft the gstack implementation plan.

Use the requirements artifact, context bundle, and existing repo patterns to
produce a plan that is ready for the gstack plan-review fanout. Preserve the raw
gstack posture: founder-level scope challenge first, then design, engineering,
and developer-experience readiness.

The plan must include at least two implementation approaches, the recommended
approach, task boundaries, test commands, release risks, and what work is not in
scope. Keep it approachable for first-time factory users: concrete files and
commands beat abstract strategy.

Close with `gc.outcome=pass` and the plan artifact path.

Do not invoke provider-native subagents. Gas City fanouts handle downstream
review.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
