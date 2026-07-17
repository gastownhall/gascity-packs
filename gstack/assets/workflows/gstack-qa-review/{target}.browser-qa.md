Run the gstack browser QA lane.

Exercise the most important user workflows with the available browser or
command-line testing surface. Capture screenshots, logs, command output, or
other evidence. If browser testing is unavailable, record the fallback proof
used and what remains untested.

Current review_mode is {{review_mode}}. In report mode, use non-destructive or
isolated flows and do not edit, stage, or commit product source. Record a flow
that cannot be exercised safely as missing evidence rather than changing the
implementation or persistent environment to make the test pass.

Read the exact `gc.build.implementation_member_ids` scope from the QA context.
For every member, enter its recorded authoritative implementation worktree and
verify `pwd -P` before running the user workflow or command-line fallback. Do
not read, test, or fix product source in the launcher checkout. Evidence from a
different directory does not prove the implementation member and must produce
an `iterate` verdict.

Write findings under the artifact root.

Close with `gc.outcome=pass`,
`gstack.qa.browser_verdict=approve|iterate`, and
`gstack.qa.output_path=<browser QA report path>`.

Do not invoke provider-native subagents. You are the QA lane.
