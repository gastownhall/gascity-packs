Synthesize the build-basic starter factory review.

Read the acceptance, test evidence, and simplicity review reports. If the
workflow root records `gc.build.human_findings_path` (a human requested
changes at the interactive gate in an earlier attempt), read that file too
and carry every item in it as a REQUIRED FIX — human findings are
authoritative and must not be dropped even when no automated lane
independently reports them. Deduplicate findings, preserve the source
review lane (or "human gate") for each finding, and classify each item as
required fix, missing evidence, or residual risk.

Write one starter review synthesis under the build artifact root. The synthesis
must be short enough for a first-time factory user to scan, but concrete enough
for the fix lane to act without another planning pass.

Close with `gc.outcome=pass`,
`code_review.synthesis_path=<starter review synthesis path>`, and
`code_review.output_path=<starter review synthesis path>`.

Do not invoke provider-native subagents. Synthesis happens in this Gas City
fan-in lane.

