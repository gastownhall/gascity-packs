Record gstack QA findings in report mode.

This is the structurally read-only QA terminal. Read the browser QA, regression
evidence, and synthesized QA summary. Preserve the synthesis's semantic
`code_review.review_verdict=approve|iterate` and record every defect or missing
piece of evidence without applying it.

Never edit, stage, or commit product source. Never update implementation member
worktree, commit, or summary metadata; never regenerate the canonical
implementation summary. You may run additional read-only proof commands when
needed, but run them only in the affected member's authoritative implementation
worktree and do not turn evidence collection into a source mutation.

Write a report-only QA artifact beneath the canonical absolute artifact root and
record its canonical absolute path as `gstack.qa.report_path`. Begin it with
YAML front matter and preserve the synthesis status exactly: `approved`,
`changes_required`, or `blocked`. An `iterate` semantic result is successful
report delivery, not permission to enter the mutating fix lane or repeat this
read-only loop. `code_review.report_path` and `code_review.output_path` must be
the same existing regular file under that artifact root; do not point either at
an earlier code-review or QA attempt.

Treat the closed synthesis bead, its output path, and its recorded
`gstack.synthesis.sha256` as immutable input. Recompute the digest and fail
closed if it differs; never edit the synthesis to make it match. Read the
literal synthesis bead ID and current positive `gc.attempt`. The report must
use this front-matter contract, with exactly one synthesis trace:

```yaml
---
schema: gc.gstack.qa-report.v1
producer:
  bead_id: <exact-current-report-terminal-bead-id>
  stage: qa-report-findings
  attempt: <current-positive-gc.attempt>
status: <exact-synthesis-status>
semantic_verdict: <exact-synthesis-approve-or-iterate-verdict>
trace:
  upstream:
    - path: <canonical-current-synthesis-output-path>
      hash: sha256:<digest-of-current-synthesis-bytes>
      ids: [<exact-current-synthesis-bead-id>]
---
```

After the front matter, write exactly these non-empty second-level sections in
order: `## Summary`, `## Findings`, `## Evidence`, and `## Next Action`.

Close only this claimed bead with `gc.outcome=pass`,
`code_review.verdict=reported`,
`code_review.reviewed_attempt=<current gc.attempt>`,
`code_review.report_path=<QA report path>`,
`code_review.output_path=<QA report path>`,
`gstack.qa.report_path=<QA report path>`,
`gstack.report.synthesis_bead_id=<exact-current-synthesis-bead-id>`,
`gstack.report.synthesis_path=<canonical-current-synthesis-output-path>`,
`gstack.report.synthesis_sha256=sha256:<current-synthesis-digest>`,
`gstack.report.semantic_verdict=<exact-synthesis-verdict>`, and
`gstack.report.semantic_status=<exact-synthesis-status>`.

Do not invoke provider-native subagents. This Gas City lane records findings;
it does not implement them.
