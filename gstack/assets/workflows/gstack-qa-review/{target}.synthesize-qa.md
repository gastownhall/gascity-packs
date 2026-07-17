Synthesize the gstack QA result.

Read the browser QA and regression evidence. Set the semantic
`code_review.review_verdict=approve` only when QA behavior and regression
evidence are approved. Set `code_review.review_verdict=iterate` when defects or
missing evidence remain. This synthesis does not apply fixes and does not own
the loop-terminal `code_review.verdict`.

Before choosing `approve`, read `gc.build.implementation_member_ids` from the
workflow root and require evidence for every exact member from its
authoritative implementation worktree. The evidence must name the member,
canonical worktree path, current full commit SHA, proof command, and observed
passing result. Reject evidence or fixes from the launcher checkout, any
unrecorded worktree, or only a subset of members. Do not turn an upstream
`iterate` into `done` merely because a fix report claims success.

Write one QA summary under the artifact root. Begin it with YAML front matter
whose `status` is `approved` when the semantic verdict is `approve`,
`changes_required` when it is `iterate`, or `blocked` when QA could not obtain
the required evidence safely. Do not claim `approved` while either input lane
still reports a defect or evidence gap.

Bind the summary to this exact producer attempt. Read the claimed synthesis
bead's literal ID and positive `gc.attempt`; do not copy either from an earlier
QA attempt. The summary must use this front-matter contract:

```yaml
---
schema: gc.gstack.qa-summary.v1
producer:
  bead_id: <exact-current-synthesis-bead-id>
  stage: synthesize-qa
  attempt: <current-positive-gc.attempt>
status: approved|changes_required|blocked
semantic_verdict: approve|iterate
---
```

After the front matter, write exactly these non-empty second-level sections in
order: `## Summary`, `## Findings`, and `## Evidence`. Compute the SHA-256 of
the final summary bytes only after the file is complete. Do not edit the file
after recording that digest.

Close with `gc.outcome=pass`,
`code_review.reviewed_attempt=<current gc.attempt>`,
`code_review.review_verdict=approve|iterate`,
`code_review.report_path=<QA summary path>`,
`code_review.output_path=<QA summary path>`,
`gstack.qa.summary_path=<QA summary path>`, and
`gstack.synthesis.sha256=sha256:<digest-of-final-QA-summary-bytes>`.

Do not invoke provider-native subagents. Synthesis happens in this Gas City
fan-in lane.
