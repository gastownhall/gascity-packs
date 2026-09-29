
Read workflow root metadata, the current `gc.github.implementation_plan_path`,
requirements, triage report, and relevant tests. Derive the current attempt
from this bead metadata (`gc.attempt`) and write artifacts under
`<gc.github.design_review_dir>/attempt-<attempt>/`.

Review only testing and risk:

- Would the tests catch the reported regression?
- Are fake/stub boundaries explicit enough?
- Are edge cases and negative paths represented?
- Are rollout and observability notes sufficient for this change?

Write `testing-risk-review.md` with:
- `## Verdict` containing `approve` or `iterate`
- `## Findings`
- `## Required Changes`

Close with `gc.outcome=pass` and `design_review.output_path` pointing at the
Markdown artifact. `iterate` requires concrete findings.
