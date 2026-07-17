Run the gstack regression-test evidence lane.

For each QA defect or important acceptance criterion, verify there is a focused
regression test or a clear reason it cannot be automated yet. Check that the
proof commands are repeatable from the repository.

Current review_mode is {{review_mode}}. In report mode, do not edit, stage, or
commit product source or tests. Run only read-only or isolated proof commands;
record missing regression coverage as a finding instead of adding it.

Read the exact `gc.build.implementation_member_ids` scope from the QA context
and independently run or inspect each repeatable proof from that member's
authoritative implementation worktree. Verify `pwd -P` first and bind recorded
output to the member ID, worktree path, and commit. Tests run from the launcher checkout
are not implementation proof and require an `iterate` verdict.

Write findings under the artifact root.

Close with `gc.outcome=pass`,
`gstack.qa.regression_verdict=approve|iterate`, and
`gstack.qa.output_path=<regression report path>`.

Do not invoke provider-native subagents. You are the regression evidence lane.
