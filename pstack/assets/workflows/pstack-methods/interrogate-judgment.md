Deduplicate findings, map agreement, and write one lead judgment.

Write a Gas City `gc.build.review.v1` artifact to `.gc/pstack/interrogate-judgment.md`.
Do not invoke provider-native subagents.

The report must be Markdown with YAML front matter. Use mapping objects:

- `schema: gc.build.review.v1`
- `workflow: {id: <workflow-root-id>, formula: pstack-interrogate}`
- `methodology: {pack: pstack, name: pstack-interrogate}`
- `producer: {formula: pstack-interrogate, stage: judgment, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `trace: {upstream: [...], coverage: [...]}`

`trace.upstream[]` entries must include `path` and `hash`. Include a Markdown
coverage table with `ID` and `Status` columns whose pairs match
`trace.coverage`.

Required body sections:

- Verdict
- Findings
- Verification

Artifact validation: this step is gated by
`.gc/scripts/checks/build-artifact-valid.sh`, which validates the report
recorded at `pstack.artifact_path` against schema `gc.build.review.v1`.
