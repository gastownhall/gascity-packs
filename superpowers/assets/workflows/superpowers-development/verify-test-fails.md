Verify the selected existing or newly written test fails for the expected
reason.

Run the focused command recorded by the failing-test step from the task
worktree. Confirm the test fails because the required behavior is missing, not
because of syntax errors, missing imports, an invalid fixture, or a bad command.

If the failure is wrong and approved scope permits test changes, fix only the
test and run it again until it fails for the intended reason. If approved scope
forbids test changes, do not edit the test; record the mismatch as a blocker.
Record the command, relevant output, and corrected failure reason or blocker in
the task summary.

Do not invoke provider-native subagents or upstream plugin runtime commands.
