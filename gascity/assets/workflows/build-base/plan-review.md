This is the `build-base` plan-review stage. Treat it as a virtual contract that concrete formulas may override.

Review the plan for traceability to requirements, feasibility, missing edge cases, and implementation readiness. If changes are required, update or route the plan before closing this stage.

Close this step only when the plan is approved or the blocking issues are recorded in the step summary.

Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.
