Run the starter factory test evidence review lane.

Check that each accepted task recorded an intended behavior, first verification
command, proof command, changed files, and remaining risks. Verify that the
commands actually cover the acceptance criteria claimed by the requirements and
plan.

Before evaluating proof, read `gc.build.code_review_context_path` from the
workflow root bead and use its `## Implementation Worktrees` section as the
authority for where commands must run. `gc.work_dir` is the launcher rig root,
not the implementation worktree. Do not run evidence commands from the launcher
checkout. Resolve relative command paths against the listed implementation
worktree, run `cd "$WORKTREE"`, and verify `pwd -P` equals that worktree before
executing proof commands. If the context is missing a usable implementation
worktree, write an iterate finding against review setup.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

Write concrete findings under the build artifact root. Distinguish missing
proof from real product defects so the fix lane can either run the missing
command or change code.

Close with `gc.outcome=pass`,
`code_review.test_evidence_verdict=approve|iterate`, and
`code_review.output_path=<test evidence report path>`.

Use explicit close metadata so the review loop can detect the lane result:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.test_evidence_verdict=approve' \
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
