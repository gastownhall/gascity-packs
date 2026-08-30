Use the built-in Gas City `design-review` flow.

Run a plan review against the implementation plan. Treat required changes as blockers for decomposition; update the plan or capture the unresolved findings before closing this step.

Include a lightweight implementation readiness pass before decomposition:

- requirements traceability: every major plan task maps to acceptance criteria
- task boundaries: each task can become a clear implementation bead
- test commands: the plan names the focused proof commands or test strategy
- risk: risky files, migrations, public interfaces, and rollback concerns are
  explicit enough for an implementer

If you write a plan-readiness note, record it on the workflow root as
`gc.build.plan_review_report_path=<path>`. Do not write or overwrite
`gc.build.review_report_path`; that key is reserved for the later
build-basic implementation review artifact.

Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.
