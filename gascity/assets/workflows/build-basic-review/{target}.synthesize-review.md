Synthesize the build-basic starter factory review.

Read the acceptance, test evidence, and simplicity review reports. Deduplicate
findings, preserve the source review lane for each finding, and classify each
item as required fix, missing evidence, or residual risk.

Read `code_review.implementation_snapshot` from all three current-attempt lane
beads. All three values must match each other and the current
`gc.build.implementation_snapshot`; otherwise record missing evidence and do
not authorize `done`. Preserve that exact snapshot on the synthesis bead.
Also recompute `gc.build.review_input_snapshot` from the current canonical
summary/context paths and bytes. Require every lane value to equal the live root
value, then carry it as `code_review.review_input_snapshot`; any mismatch forces
iteration.

The three current-attempt lane verdicts are authoritative. An optional,
advisory, or non-blocking suggestion from a lane that approved is a residual
risk or observation, never a required fix or missing-evidence item. When all
three lanes approve, state explicitly that implementation changes are not
authorized and that the apply lane must produce a no-op result. Do not turn
wording such as "consider", "recommend", or "simpler alternative" into work.

Read `<artifact-root>` from root `gc.build.artifact_root`; require it to be
absolute and equal the parent of `gc.build.code_review_context_path`. Write exactly
`<artifact-root>/starter-review-synthesis.md`; never write review evidence into
the authoritative implementation worktree. Keep it short and actionable.

Close with `gc.outcome=pass`,
`code_review.reviewed_attempt=<current gc.attempt>`,
`code_review.implementation_snapshot=<exact current snapshot>`,
`code_review.review_input_snapshot=<exact current review-input snapshot>`,
`code_review.synthesis_path=<starter review synthesis path>`, and
`code_review.output_path=<starter review synthesis path>`.

Do not invoke provider-native subagents. Synthesis happens in this Gas City
fan-in lane.
