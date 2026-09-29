Run the Jev-gated acceptance review lane.

The Jev review gate already judged every acceptance criterion from receipts.
Review only these criteria: **{acceptance_scope}** (`all` means every
criterion). The gate's criterion list, with ids, is in the review context under
`## Acceptance Criteria (as parsed by the gate)`. Criteria outside this scope
were cleared by the gate; do not re-review them. If the scope names a criterion
marked as an audit, review it exactly like the others.

For each criterion in scope, decide whether any input makes the implementation
violate it, and whether the build stayed in scope. Focus on correctness: did the
factory build the requested behavior?

Before inspecting files or running tests, read `gc.build.code_review_context_path`
from the workflow root bead and use its `## Implementation Worktrees` section as
the authority for code under review. `gc.work_dir` is the launcher rig root, not
the implementation worktree. Do not inspect or edit the launcher checkout.
Resolve every relative source path and proof command against the listed
implementation worktree, run `cd "$WORKTREE"`, and verify `pwd -P` equals that
worktree before executing commands. An unchanged launcher root is not a finding;
publish owns propagation.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

Write findings under the build artifact root. Required findings must name the
criterion id and the file, command, or artifact that proves the issue.

Record one verdict per criterion in scope as compact JSON in
`jev.criteria_verdicts`, using exactly `holds` or `violated`, for example
`{"AC-1":"holds","AC-3":"violated"}`. The gate's audit depends on it. Then close
with `gc.outcome=pass`, `code_review.acceptance_verdict=approve|iterate`, and
`code_review.output_path=<acceptance review report path>`:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.acceptance_verdict=approve' \
  --set-metadata 'jev.criteria_verdicts={"AC-1":"holds"}' \
  --set-metadata 'code_review.output_path=<acceptance review report path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Jev-gated acceptance review approved.'
```

Use `iterate` instead of `approve` when any criterion is violated, and explain
the smallest required fix in the report and close reason.

Do not set `code_review.verdict` or `code_review.report_path`; synthesis and fix
application own the final review verdict. Do not invoke provider-native
subagents.
