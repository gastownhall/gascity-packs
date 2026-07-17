Finalize the gstack release readiness review.

Verify the latest release readiness loop approved the sprint or recorded
blocking release issues. Record the exact readiness summary on the workflow
root at `gc.build.release_readiness_summary_path` for finalization and require
its YAML front matter status to be one of `approved`, `changes_required`, or
`blocked`.

In agent or interactive mode, require `code_review.verdict=done`, require
`status: approved`, and record `gc.build.release_readiness_status=approved`. In
report mode, report delivery may close this expansion with
`code_review.verdict=reported` and
`gc.build.release_readiness_status=reported`, but preserve
`changes_required` or `blocked` in the summary so the executable final gate
requires a blocked final artifact.

The finalizer check binds `gc.build.release_readiness_summary_path` to the one
closed/pass `gc.review.report_terminal=true` bead from the current readiness
loop attempt. Missing, duplicate, stale-attempt, non-canonical, or
outside-artifact-root evidence must fail instead of reusing an earlier report.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents.
