
Write the review verdict report to {{report_path}} with pass/fail, findings,
missing evidence, and recommended fixes for subject {{subject_path}}.

The requested review authority is `{{review_mode}}`: in `report` mode, write
findings and verdicts without mutating code; in `agent` mode, also include a
structured fix handoff for the caller's review-fix formula to apply; in
`interactive` mode, safe fixes may be negotiated or applied with every change
and reason recorded in the report. The interaction posture is
`{{interaction_mode}}`.

Under the `## Findings` heading, list every finding as one item in a YAML
sequence of mappings, each with exactly the keys `id`, `severity` (`minor`,
`major`, or `blocker`), `title`, `evidence`, and `required_fix`:

```yaml
- id: REVIEW-001
  severity: major
  title: SQL injection in query builder
  evidence: apps/foo/src/db.ts:42 concatenates user input into SQL
  required_fix: Use parameterized queries via the existing sql tag helper
```

If there are no findings, write the single line `None` under the heading
instead. Callers that translate this report into a `gc.verdict-report.v1`
verdict (for example the github-pr-review adapter) parse this exact shape.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the report recorded at `gc.build.review_report_path` (fallback `gc.var.report_path`) against schema `gc.build.review.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the report in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the report.
