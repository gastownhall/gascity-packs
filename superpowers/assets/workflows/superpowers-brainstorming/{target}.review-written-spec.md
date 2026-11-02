Review the written requirements/spec artifact with the installed Superpowers
spec document reviewer guidance.

This lane represents the stock spec reviewer subagent as a Gas City graph lane.
Use the vendored `skills/brainstorming/spec-document-reviewer-prompt.md`
guidance as the source behavior for this lane.

Check completeness, internal consistency, clarity, scope, and YAGNI. Flag only
issues that would cause real planning or implementation mistakes. Minor wording
preferences and non-blocking polish suggestions are advisory.

Write the current attempt review artifact under the brainstorming artifact
directory. Required issues must be concrete and actionable.

Before closing, update the exact claimed bead id with the lane metadata:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.review_verdict=approve' \
  --set-metadata 'design_review.output_path=<spec review artifact path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers written spec review approved.'
```

If required issues remain, set `design_review.review_verdict=iterate` instead
of `approve` and name the smallest required correction in the report and close
reason. Do not pass `--metadata` or `--set-metadata` to `gc bd close`. Do not set
`design_review.verdict`; the feedback and approval lanes own the loop verdict.

Do not invoke provider-native subagents. You are the Gas City spec document
review lane.
