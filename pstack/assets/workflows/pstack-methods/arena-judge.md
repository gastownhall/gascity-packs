Cross-judge candidates, synthesize the decision, and preserve dissent.

Write a Gas City `pstack.arena-synthesis.v1` artifact to
`.gc/pstack/arena-synthesis.md`. Do not invoke provider-native subagents.

The report must be Markdown with YAML front matter. Use mapping objects:

- `schema: pstack.arena-synthesis.v1`
- `workflow: {id: <workflow-root-id>, formula: pstack-arena}`
- `producer: {formula: pstack-arena, stage: judge, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `candidates: [...]`
- `cross_judge: {...}`
- `synthesis: {...}`
- `decision: {...}`
- `dissent: [...]`
- `trace: {upstream: [...], coverage: [...]}`

`trace.upstream[]` entries must include `path` and `hash`. Include a Markdown
coverage table with `ID` and `Status` columns whose pairs match
`trace.coverage`.

Artifact validation: this step is gated by
`.gc/scripts/checks/build-artifact-valid.sh`, which validates the report
recorded at `pstack.artifact_path` against schema `pstack.arena-synthesis.v1`.
