Use the built-in Gas City `design-review` flow.

Run a plan review against the implementation plan. Treat required changes as blockers for decomposition; update the plan or capture the unresolved findings before closing this step.

Include a lightweight implementation readiness pass before decomposition:

- requirements traceability: every major plan task maps to acceptance criteria
- task boundaries: each task can become a clear implementation bead
- test commands: the plan names the focused proof commands or test strategy
- risk: risky files, migrations, public interfaces, and rollback concerns are
  explicit enough for an implementer

Write the plan-review artifact as Markdown with YAML front matter valid for
`gc.build.plan-review.v1` (`gascity/schemas/build/plan-review.v1.yaml`),
including a single `verdict` token from its closed vocabulary (`approved` or
`proceed` release decomposition; every other listed verdict blocks it), and
record it on the workflow root as
`gc.build.plan_review_report_path=<path>`. Do not write or overwrite
`gc.build.review_report_path`; that key is reserved for the later
build-basic implementation review artifact.

Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.
