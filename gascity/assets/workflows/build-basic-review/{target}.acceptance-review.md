Run the starter factory acceptance review lane.

Review the implementation against the requirements, acceptance criteria,
implementation plan, decomposition, and task summaries. Focus on correctness:
did the factory build the requested behavior, and did it avoid out-of-scope
changes?

Read the review context first and evaluate the implementation source
anchor/worktree recorded there. The launcher rig root is not the review target
for build-basic; it may still contain the original fixture until publish. Do not
mark acceptance as `iterate` merely because the root checkout is unchanged when
the recorded source anchor/worktree implements the requested behavior and its
proof commands pass.

Read `gc.build.implementation_snapshot` from the workflow root and the review
context. Recompute it from the current member-id/commit tuples before reviewing
and require both values to match. Review the exact current implementation snapshot.
Carry the matching value on this lane as
`code_review.implementation_snapshot`; a missing or changed snapshot requires
`iterate` and a fresh review.
Recompute the root `gc.build.review_input_snapshot` from the canonical absolute
summary/context paths, their current raw-byte SHA-256 digests, and that
implementation snapshot. Require an exact root match and carry it as
`code_review.review_input_snapshot`; otherwise use `iterate`.

Read `<artifact-root>` from root `gc.build.artifact_root`; require it to be
absolute and equal the parent of `gc.build.code_review_context_path`. Write exactly
`<artifact-root>/acceptance-review-report.md`; never write review evidence into
the authoritative implementation worktree.
Run Python proof with `PYTHONDONTWRITEBYTECODE=1` and leave no `__pycache__` or
bytecode files.
Required findings must include the relevant requirement or task reference plus
the file, command, or artifact that proves the issue.

Close with `gc.outcome=pass`,
`code_review.acceptance_verdict=approve|iterate`, and
`code_review.reviewed_attempt=<current gc.attempt>`,
`code_review.implementation_snapshot=<exact current snapshot>`, and
`code_review.review_input_snapshot=<exact current review-input snapshot>`, and
`code_review.output_path=<acceptance review report path>`.

Use explicit close metadata so the review loop can detect the lane result:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.acceptance_verdict=approve' \
  --set-metadata 'code_review.reviewed_attempt=<current gc.attempt>' \
  --set-metadata 'code_review.implementation_snapshot=<exact current snapshot>' \
  --set-metadata 'code_review.review_input_snapshot=<exact current review-input snapshot>' \
  --set-metadata 'code_review.output_path=<acceptance review report path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Build-basic acceptance review approved.'
```

If you find required fixes, set
`code_review.acceptance_verdict=iterate` instead of `approve` and explain the
smallest required fix in the report and close reason.

Do not set `code_review.verdict` or `code_review.report_path`; synthesis and
fix application own the final review verdict.

Do not invoke provider-native subagents. You are the starter factory acceptance
review lane.
