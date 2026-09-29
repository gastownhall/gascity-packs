
Read the current attempt synthesis and update `gc.github.implementation_plan_path` in place.

If the global verdict is `approve`:
- set implementation-plan front matter `status: approved`
- add or refresh a short accepted-risks note when relevant
- stamp root metadata `gc.github.design_review_status=approved`
- close this bead with `design_review.verdict=done`

If the global verdict is `iterate`:
- apply all required changes to `implementation-plan.md`
- keep front matter `status: draft`
- stamp root metadata `gc.github.design_review_status=iterating`
- close this bead with `design_review.verdict=iterate`

For every attempt, write:
- `implementation-plan-after.md`
- `implementation-plan.diff`
- `apply-summary.md`

Close with `gc.outcome=pass`, `design_review.verdict=done|iterate`,
`design_review.output_path=<apply-summary path>`, and
`gc.continuation_group=design-review-fixes`. Do not edit source files.
