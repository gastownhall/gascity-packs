Apply Jev-gated review findings.

Use implementation target {implementation_target} for any code changes. Read
the synthesis if one was written in this iteration; otherwise read the report of
the single lane that ran (its path is `code_review.output_path` on that lane's
bead). Smells Jev confirmed are required fixes even when no lane mentions them:
{forwarded_smells}.

If every lane that ran approved and no smell was forwarded, write a no-op review
summary. Otherwise make the smallest focused changes, run the relevant proof
commands, and write the review-fix summary under the build artifact root.

Apply fixes to the implementation worktree named in the review context
(`gc.build.code_review_context_path` on the workflow root, section
`## Implementation Worktrees`), never to the launcher rig root. Run
`cd "$WORKTREE"` and verify `pwd -P` equals that worktree before making changes.
An unchanged launcher root is not a required fix; publish owns propagation.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

Set `code_review.verdict=done` only when every lane that ran approves after this
pass and every forwarded smell is fixed. Set `code_review.verdict=iterate` when
required fixes remain.

Always close with `gc.outcome=pass`, `code_review.verdict=done|iterate`,
`code_review.report_path=<review summary path>`, and
`code_review.output_path=<review summary path>`. Use the exact claimed bead id
and this command shape:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.verdict=done' \
  --set-metadata 'code_review.report_path=<review summary path>' \
  --set-metadata 'code_review.output_path=<review summary path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Jev-gated review approved.'
```

Do not invoke provider-native subagents.
