Apply Superpowers code-quality findings.

Use implementation target {{implementation_target}} for any code changes. Read
the spec compliance report, spec-fix summary, and code quality report. If both
review lanes approve, write a no-op final task-review summary. If required
quality fixes remain, make the smallest focused updates, rerun the relevant
verification, and write the fix summary.

Set `code_review.verdict=done` only when spec compliance and code quality both
approve after this pass. Set `code_review.verdict=iterate` when required
findings remain or when quality was deferred because spec compliance still
needed another pass.

Always close with `gc.outcome=pass`,
`code_review.verdict=done|iterate`,
`code_review.report_path=<task review summary path>`, and
`code_review.output_path=<task review summary path>`.

Use the exact claimed bead id when updating metadata. Do not pass freeform notes
or additional positional arguments to `gc bd update`; unquoted words can resolve to
unrelated beads. Use this command shape:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.verdict=done' \
  --set-metadata 'code_review.report_path=<task review summary path>' \
  --set-metadata 'code_review.output_path=<task review summary path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers task review approved.'
```

Do not invoke provider-native subagents. This Gas City fanout lane is the
delegation mechanism.

