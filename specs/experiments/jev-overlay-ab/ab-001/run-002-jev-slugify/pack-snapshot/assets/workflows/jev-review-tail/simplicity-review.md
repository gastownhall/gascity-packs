Run the Jev-gated simplicity review lane. Scope: **{simplicity_scope}**.

- `design`: Jev's smell screen found no mechanical code smell in any diff hunk
  (debug output, dead or commented-out code, swallowed errors, unused imports,
  duplicated logic). Skip those checks and review design only: readable
  boundaries, naming, unnecessary abstractions, accidental broad changes, fit
  with the codebase, and obvious future maintenance risk.
- `full`: review design and check the diff for those smells too.

Smells Jev already confirmed go straight to the fix lane and need no review:
{forwarded_smells}.

Flag only concrete issues a new factory user can understand and act on.

Before inspecting files, read `gc.build.code_review_context_path` from the
workflow root bead and use its `## Implementation Worktrees` section as the
authority for code under review. `gc.work_dir` is the launcher rig root, not the
implementation worktree. Resolve relative file paths against the listed
implementation worktree, run `cd "$WORKTREE"`, and verify `pwd -P` equals that
worktree before running any command.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

Write findings under the build artifact root, tied to specific changed files,
with the smallest useful fix.

When the scope is `full`, record whether you found any of the five smells as
compact JSON in `jev.smell_verdicts`: `{"screen":"present"}` or
`{"screen":"clean"}`. Then close with `gc.outcome=pass`,
`code_review.simplicity_verdict=approve|iterate`, and
`code_review.output_path=<simplicity review report path>`:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.simplicity_verdict=approve' \
  --set-metadata 'jev.smell_verdicts={"screen":"clean"}' \
  --set-metadata 'code_review.output_path=<simplicity review report path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Jev-gated simplicity review approved.'
```

Use `iterate` instead of `approve` for required fixes. Do not set
`code_review.verdict` or `code_review.report_path`. Do not invoke
provider-native subagents.
