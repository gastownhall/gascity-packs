Coordinate the BMAD story-development loop for one shared-drain item.

Read the inner workflow root's `gc.input_convoy_id`, `gc.drain_member_id`, and
`gc.drain_item_index`. Require the member and index to be non-empty. Read the
reserved input convoy; when it also records a member or index, require exact
equality with the root values. Use only the root `gc.drain_member_id` as the
source anchor, never a dependency bead, reserved convoy, or synthetic convoy.
Require the source anchor's `work_dir` to name the existing authoritative
shared git worktree. The workflow root's `gc.work_dir` is the launcher rig root
used for validation, not the implementation worktree.

The child lanes perform setup, story implementation, self-check, acceptance
audit, and fixes. They must enter the authoritative source-anchor worktree and
write the canonical item artifact recorded on this workflow root as
`gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`). The final
item summary must validate as `gc.build.implementation-summary.v1` before the
loop can approve. Do not accept a freeform child note as the summary.

The apply-findings child must leave the actual source anchor open. The explicit
`close-source-anchor` step runs only after the outer methodology-review and
artifact machine gate succeeds. Every iteration or failure keeps the anchor
open.

Use `.gc/scripts/checks/implementation-review-approved.sh` only to decide
whether the current BMAD review iteration is clean. Another iteration must
reuse the same source anchor, shared worktree, and summary path.

Do not edit source in the launcher checkout. Do not invoke provider-native
subagents. Re-run or continue only through this Gas City graph stage's child
steps.
