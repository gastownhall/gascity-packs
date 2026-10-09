Finalize the Compound Engineering build.

Record the final resolution summary path, final verdict, and artifact paths on the build-base workflow root bead. Close the expansion target with pass or fail according to the synthesized resolution.

Final report: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`,
which validates the artifact recorded at workflow root metadata
`gc.build.final_report_path` against schema `gc.build.final-report.v1`, and the
build gate checks the same key. Write the final report from the synthesized
resolution before closing:

- Resolve the final report path: use workflow root metadata
  `gc.build.final_report_path` when it is set (the build prepare stage
  pre-declares `<artifact_root>/factory-run.md`); otherwise use
  `<artifact_root>/factory-run.md`. If the path is relative, resolve it against
  `$GC_RIG_ROOT`.
- Write the final report there as Markdown with YAML front matter starting on
  its first line, not JSON. Use mapping objects, not dotted keys or scalar
  shortcuts:

```yaml
---
schema: gc.build.final-report.v1
workflow:
  id: <workflow-root-id>
  formula: <workflow-root-formula>
methodology:
  pack: compound-engineering
  name: compound-resolution
producer:
  formula: compound-resolution
  stage: finalize
  attempt: 1
status: approved
trace:
  upstream:
    - path: <resolution summary path>
      hash: sha256:<digest>
      ids: [REQ-001]
  coverage:
    - id: REQ-001
      status: covered
---
```

- Use `status: approved` when the synthesized resolution passes and
  `status: blocked` when unresolved blockers remain. Set `producer.attempt` to
  the current `gc.attempt` (a positive integer).
- `trace.upstream[]` entries must include `path` and `hash`. If an upstream
  entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in a Markdown coverage table with an `ID` column and a
  `Status` column whose ID/status pairs exactly match `trace.coverage`.
  Coverage statuses are `covered`, `not_applicable`, `deferred`, `blocked`,
  `out_of_scope`, or `superseded`, never `approved`.
- Include these required sections as `##` headings, in this order: Summary, Outcome,
  Artifacts, and Remaining Risks.
- Record the absolute final report path on the workflow root bead, not on the
  claimed step bead:
  `gc bd update "<workflow-root-id>" --set-metadata "gc.build.final_report_path=<absolute path>"`.
  Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts
  a JSON object.
- From `$GC_RIG_ROOT`, run the artifact validator with the claimed bead id and
  fix any error before setting `gc.outcome=pass`:
  `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`.
- On repair attempts (`gc.attempt` greater than 1), first read the validator
  errors from `gc.attempt_log` on the validation loop control bead (the
  dependent of this step bead) and fix every listed error in place.

Before closing, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"` (or
`gc.outcome=fail` with a concise `gc.failure_reason`), then close with
`gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.
