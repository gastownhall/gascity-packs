Run the starter factory test evidence review lane.

Check that each accepted task recorded an intended behavior, first verification
command, proof command, changed files, and remaining risks. Verify that the
commands actually cover the acceptance criteria claimed by the requirements and
plan.

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
`<artifact-root>/test-evidence-review-report.md`; never write review evidence
into the authoritative implementation worktree.
Run Python proof with `PYTHONDONTWRITEBYTECODE=1` and leave no `__pycache__` or
bytecode files.
Distinguish missing proof from product defects so the fix lane can act directly.

Close with `gc.outcome=pass`,
`code_review.test_evidence_verdict=approve|iterate`, and
`code_review.reviewed_attempt=<current gc.attempt>`,
`code_review.implementation_snapshot=<exact current snapshot>`, and
`code_review.review_input_snapshot=<exact current review-input snapshot>`, and
`code_review.output_path=<test evidence report path>`.

Use explicit close metadata so the review loop can detect the lane result:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.test_evidence_verdict=approve' \
  --set-metadata 'code_review.reviewed_attempt=<current gc.attempt>' \
  --set-metadata 'code_review.implementation_snapshot=<exact current snapshot>' \
  --set-metadata 'code_review.review_input_snapshot=<exact current review-input snapshot>' \
  --set-metadata 'code_review.output_path=<test evidence report path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Build-basic test evidence review approved.'
```

If proof is missing or insufficient, set
`code_review.test_evidence_verdict=iterate` instead of `approve` and explain
whether the fix lane should run missing proof commands or change code.

Do not set `code_review.verdict` or `code_review.report_path`; synthesis and
fix application own the final review verdict.

Do not invoke provider-native subagents. You are the starter factory test
evidence review lane.
