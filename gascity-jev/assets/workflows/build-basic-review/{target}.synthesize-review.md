Synthesize the build-basic starter factory review.

Read the acceptance, test evidence, and simplicity review reports. Deduplicate
findings, preserve the source review lane for each finding, and classify each
item as required fix, missing evidence, or residual risk.

For `jev_findings_mode={{jev_findings_mode}}` in `auto` or `assist`, follow
`{{pack_root}}/assets/jev-decisions.md` for the `findings` task. Use model
`{{jev_decision_model}}`, threshold `{{jev_decision_threshold}}`, and a new
attempt directory under the build artifact root. Pass every original finding
with its lane and source anchor. Use confident categories and proposed pairs
to focus synthesis; resolve fallback questions and verify combined remedies.
Preserve all finding IDs/sources and every original lane verdict. With `off`,
perform ordinary synthesis. In auto mode without a key, avoid preparing a
separate Jev bundle and record `missing_credential` in the synthesis.

Also read `gc.build.code_review_context_path` from the workflow root bead. When
you carry a finding forward, include the source anchor and implementation
worktree from the context's `## Implementation Worktrees` section. If a finding
cites only a relative filename, resolve that filename relative to the
implementation worktree, never the launcher checkout. Required fixes must be
specific enough for the fix lane to act without guessing which worktree owns the
file.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

Write one starter review synthesis under the build artifact root. The synthesis
must be short enough for a first-time factory user to scan, but concrete enough
for the fix lane to act without another planning pass.

Close with `gc.outcome=pass`,
`code_review.synthesis_path=<starter review synthesis path>`, and
`code_review.output_path=<starter review synthesis path>`.

Do not invoke provider-native subagents. Synthesis happens in this Gas City
fan-in lane.
