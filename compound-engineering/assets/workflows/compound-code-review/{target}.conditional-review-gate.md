Gate one Compound Engineering conditional code-review lane.

Read the claimed bead metadata `ce.review_key`, `ce.review_step_suffix`, and
`ce.review_artifact_name`. Read the reviewer manifest from workflow root
metadata `gc.build.reviewer_selection_path`.

If the manifest selects `ce.review_key`, close only this gate bead with
`gc.outcome=pass`, `code_review.gate_decision=selected`, and
`code_review.review_key=<ce.review_key>`. The paired reviewer bead becomes
ready after this gate closes.

If the manifest skips `ce.review_key`, find the paired reviewer bead with
`gc bd list --all --metadata-field "gc.root_bead_id=$CLAIMED_ROOT_BEAD_ID"
--metadata-field "gc.step_ref=<paired step ref>" --json --limit 0`, where the
paired step ref is this gate's `gc.step_ref` without the trailing `-gate`. If
the current bead does not expose `gc.step_ref`, derive the paired step ref from
`ce.review_step_suffix` and verify the candidate title and route before updating
it. Write a no-op lane artifact to
`{{artifact_root}}/code-review/<ce.review_artifact_name>`, update the paired
reviewer bead with `gc.outcome=pass`,
`code_review.review_verdict=approve`,
`code_review.lane_report_path=<no-op artifact path>`,
`code_review.gate_decision=skipped`, `code_review.review_key=<ce.review_key>`,
and `code_review.skip_reason=<manifest reason>`, then close that paired
reviewer bead. After that, close this gate bead with `gc.outcome=pass`,
`code_review.gate_decision=skipped`, `code_review.review_key=<ce.review_key>`,
and `code_review.skip_reason=<manifest reason>`.

Use exact bead ids from filtered `gc bd list --json` results. Do not update a
template name, do not fuzzy-match, and do not close a bead without reading it
back afterward.

Do not invoke provider-native subagents. This Gas City gate prevents skipped CE
conditional reviewers from being routed to real reviewer sessions.
