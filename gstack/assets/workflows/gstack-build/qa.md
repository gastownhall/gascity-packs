Prepare for gstack QA.

This stage adapts upstream qa into Gas City lanes for browser-oriented QA,
regression evidence, fix application, and synthesis. It runs after the
`review` anchor approves and before `release-readiness`; the check-gated QA
loop is the gate for release readiness, and the approved QA summary must be
recorded on the workflow root at `gc.build.qa_summary_path` before release
readiness begins. If the build has no browser surface, QA should still verify
runnable behavior through the closest available user workflow or command.

Current interaction_mode is {{interaction_mode}}. In interactive mode, use a
human gate only for environment credentials, staging URLs, or destructive test
choices. In autonomous mode, test what is available and record what could not
be reached.

Current review_mode is {{review_mode}}. In report mode, QA is read-only: record
behavior defects and missing evidence, but do not edit, stage, commit, or
publish implementation bytes. The report terminal records findings for blocked
finalization instead of routing them to the implementation target.

Close with `gc.outcome=pass` after QA context is ready.

Do not invoke provider-native subagents. Gas City fanouts own QA delegation.
