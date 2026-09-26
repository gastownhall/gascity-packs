Run the Jev-gated test evidence review lane.

This lane runs because the gate's receipts did not clear it (tests failed, a
pre-existing test file changed, no test runner was found, Jev was unavailable),
or because it was sampled for an audit of the receipts. The receipts are in the
review context under `## Implementation Worktrees`.

Check that each accepted task recorded an intended behavior, first verification
command, proof command, changed files, and remaining risks. Verify that the
commands actually cover the acceptance criteria claimed by the requirements and
plan, and that pre-existing tests were not weakened.

Before evaluating proof, read `gc.build.code_review_context_path` from the
workflow root bead and use its `## Implementation Worktrees` section as the
authority for where commands must run. `gc.work_dir` is the launcher rig root,
not the implementation worktree. Resolve relative command paths against the
listed implementation worktree, run `cd "$WORKTREE"`, and verify `pwd -P` equals
that worktree before executing proof commands.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

Write concrete findings under the build artifact root. Distinguish missing proof
from real product defects so the fix lane can either run the missing command or
change code.

Close with `gc.outcome=pass`, `code_review.test_evidence_verdict=approve|iterate`,
and `code_review.output_path=<test evidence report path>`:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.test_evidence_verdict=approve' \
  --set-metadata 'code_review.output_path=<test evidence report path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Jev-gated test evidence review approved.'
```

Use `iterate` instead of `approve` when proof is missing or insufficient. Do not
set `code_review.verdict` or `code_review.report_path`. Do not invoke
provider-native subagents.
