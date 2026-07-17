Synthesize the gstack release readiness result.

Read the document-release, ship-readiness, and deployment-readiness reports.
Set `code_review.verdict=done` only when release readiness is approved or every
remaining concern is explicitly non-blocking. Set `code_review.verdict=iterate`
when release-blocking issues remain.

Write one release readiness summary under the artifact root. Begin it with YAML
front matter whose `status` is `approved` only when the semantic verdict is
`done`, `changes_required` when release-blocking findings remain, or `blocked`
when required readiness evidence cannot be obtained safely.

Bind the summary to this exact producer attempt. Read the claimed synthesis
bead's literal ID and positive `gc.attempt`; do not copy either from an earlier
readiness attempt. The summary must use this front-matter contract:

```yaml
---
schema: gc.gstack.release-readiness-summary.v1
producer:
  bead_id: <exact-current-synthesis-bead-id>
  stage: synthesize-release-readiness
  attempt: <current-positive-gc.attempt>
status: approved|changes_required|blocked
semantic_verdict: done|iterate
---
```

After the front matter, write exactly these non-empty second-level sections in
order: `## Summary`, `## Findings`, and `## Evidence`. Compute the SHA-256 of
the final summary bytes only after the file is complete. Do not edit the file
after recording that digest.

Close with `gc.outcome=pass`,
`code_review.reviewed_attempt=<current gc.attempt>`,
`code_review.verdict=done|iterate`,
`code_review.report_path=<release readiness summary path>`,
`code_review.output_path=<release readiness summary path>`,
`gstack.release.summary_path=<release readiness summary path>`, and
`gstack.synthesis.sha256=sha256:<digest-of-final-readiness-summary-bytes>`.

Do not invoke provider-native subagents. Synthesis happens in this Gas City
fan-in lane.
