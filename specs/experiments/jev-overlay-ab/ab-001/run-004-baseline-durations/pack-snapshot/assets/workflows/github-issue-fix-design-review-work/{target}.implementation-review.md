
Read workflow root metadata, the current `gc.github.implementation_plan_path`,
requirements, triage report, and relevant code. Derive the current attempt from
this bead metadata (`gc.attempt`) and write artifacts under
`<gc.github.design_review_dir>/attempt-<attempt>/`.

Review only implementation realism:

- Does the proposed change touch the right modules?
- Are APIs, state, and side effects clear enough for build agents?
- Are hidden compatibility or layering issues missing?
- Is the plan smaller than necessary or broader than approved requirements?

Write `implementation-review.md` with:
- `## Verdict` containing `approve` or `iterate`
- `## Findings`
- `## Required Changes`

Close with `gc.outcome=pass` and `design_review.output_path` pointing at the
Markdown artifact. `iterate` requires concrete findings.
