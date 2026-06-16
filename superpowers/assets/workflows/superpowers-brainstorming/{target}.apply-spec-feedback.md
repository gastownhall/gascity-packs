Apply required Superpowers spec-review feedback to the requirements artifact.

If the review approved the artifact, perform a no-op pass and record that no
changes were needed. If the review found required issues, update only the
requirements/spec artifact and any companion brainstorming notes needed to
resolve them. Preserve traceability to the original target and do not add
unrequested scope.

For every attempt, write an apply summary and, when the artifact changed, a
diff. Before closing, update the exact claimed bead id with the lane metadata:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.output_path=<apply-summary path>' \
  --set-metadata 'design_review.required_changes_applied=false'
bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers spec feedback pass completed.'
```

If required changes were applied, set
`design_review.required_changes_applied=true` instead. Do not pass `--metadata` or `--set-metadata` to `bd close`. Do not set `design_review.verdict`; the approval lane owns the loop verdict.

Do not invoke provider-native subagents. This Gas City lane owns the spec
feedback pass.
