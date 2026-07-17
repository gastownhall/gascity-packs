Finalize the gstack QA review.

In agent or interactive mode, verify the latest QA loop ended with
`code_review.verdict=done`, then record the approved QA summary on the workflow
root at `gc.build.qa_summary_path` for release readiness and the final sprint
report. Require its YAML front matter to have `status: approved` and record
`gc.build.qa_status=approved`.

In report mode, require the selected non-mutating terminal to have
`code_review.verdict=reported`. Record its exact report path at
`gc.build.qa_summary_path`, require its YAML front matter to preserve the
synthesis status as `approved`, `changes_required`, or `blocked`, and set
`gc.build.qa_status=reported`. Report delivery may pass this expansion, but
unresolved findings must remain visible to build finalization and must not
authorize product mutation or an approved final artifact.

The finalizer check binds `gc.build.qa_summary_path` to the one closed/pass
`gc.review.report_terminal=true` bead from the current QA loop attempt. A
missing, duplicate, stale-attempt, non-canonical, or outside-artifact-root path
must fail the check; do not reuse an earlier QA summary to repair it.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents.
