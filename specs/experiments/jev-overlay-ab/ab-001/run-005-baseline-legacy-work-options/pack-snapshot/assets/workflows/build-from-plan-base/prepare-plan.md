This is the `build-from-plan-base` planning handoff step.

Validate that the approved requirements artifact exists at
`{{requirements_path}}` and that artifact_root {{artifact_root}},
context_path {{context_path}}, plan_path {{plan_path}}, and
plan_review_path {{plan_review_path}} are safe plain paths. Record the selected
planning_formula {{planning_formula}} for downstream traceability.

Do not run decomposition or implementation from this step. Record
`gc.build.continuation_entrypoint=plan` when this suffix is launched directly.
Close only after the plan stage can write or reuse the selected plan artifact.
