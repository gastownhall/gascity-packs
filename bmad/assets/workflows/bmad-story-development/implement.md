Coordinate the BMAD story-development loop for one separately drained source
anchor.

The inherited `prepare-worktree` lane owns worktree creation. Resolve the
source anchor from the workflow root's `gc.input_convoy_id`; if that convoy has
`gc.synthetic_kind=drain-unit-convoy`, use its `gc.drain_member_id`, never the
synthetic convoy or a dependency bead. Require the source anchor's `work_dir`
to name an absolute existing git worktree distinct from the launcher rig root.

The child lanes perform setup, story implementation, self-check, acceptance
audit, and fixes. They must use that authoritative source-anchor worktree and
write the canonical item artifact recorded on this workflow root as
`gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`). The final
item summary must validate as `gc.build.implementation-summary.v1` before the
loop can approve. Do not accept a freeform child note as the summary.

Use `.gc/scripts/checks/implementation-review-approved.sh` only to decide
whether the current BMAD review iteration is clean. Another iteration must
reuse the same source anchor, worktree, and summary path.

Do not edit source in the launcher checkout. Do not invoke provider-native
subagents. Re-run or continue only through this Gas City graph stage's child
steps.
