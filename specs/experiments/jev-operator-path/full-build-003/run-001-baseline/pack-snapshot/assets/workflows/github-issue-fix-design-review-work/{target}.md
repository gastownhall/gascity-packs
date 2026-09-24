
Validate that `gc.github.implementation_plan_path` exists and its front matter has
`status: approved`. If not, fail this step with `gc.outcome=fail` and
`gc.failure_class=hard`.

On success, update this step and the workflow root with:
- `gc.github.implementation_plan_path=<absolute implementation-plan.md path>`
- `gc.github.implementation_plan_status=approved`
- `gc.github.design_review_status=approved`
- `gc.github.design_review_dir=<absolute review dir>`
- `gc.outcome=pass`

Close this sink step with `gc.outcome=pass`. Downstream `create-beads` must not
need to know whether the review came from the base two-lane loop or a local
override.
