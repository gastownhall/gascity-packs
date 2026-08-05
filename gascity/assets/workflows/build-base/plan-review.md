This is the `build-base` plan-review stage. Treat it as a virtual contract that concrete formulas may override.

Review the plan for traceability to requirements, feasibility, missing edge cases, and implementation readiness. If changes are required, update or route the plan before closing this stage.

Close this step only when the plan is approved or the blocking issues are recorded in the step summary.

On approval, PROMOTE the plan-review artifact path to the workflow root so the
downstream decompose stage can read it at runtime (symmetric with
`gc.build.plan_path`; dip-5hkepo). Record the absolute path of the plan-review
artifact you produced:
`bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_path=<absolute path>" --set-metadata "gc.var.plan_review_path=<absolute path>"`.
Do not use `bd update --metadata 'key=value'`; `--metadata` only accepts a JSON object.
