Record the current gstack code-review findings in report mode.

This is the structurally read-only terminal for the current loop attempt. Read
the current synthesized report at workflow-root metadata
`gc.build.code_review_report_path`. Require that exact path to be a canonical
absolute existing regular file beneath the canonical artifact root. Preserve
its semantic `approved`, `changes_required`, or `blocked` status; successful
report delivery does not authorize fixes.

Never edit, stage, or commit product source. Never update implementation member
worktrees, commits, summaries, or canonical implementation provenance. Do not
reuse a report from an earlier attempt and do not enter the mutating
`apply-review-findings` lane.

Close only this claimed bead with `gc.outcome=pass`,
`code_review.verdict=reported`,
`code_review.report_path=<current gc.build.code_review_report_path>`, and
`code_review.output_path=<current gc.build.code_review_report_path>`.

Do not invoke provider-native subagents. This lane records current findings;
it does not implement them.
