Prepare the authoritative worktree for one gstack shared-drain item.

This is infrastructure setup only. Read the claimed step's workflow root bead
and require `gc.drain_member_id`, `gc.drain_index`,
`gc.drain_control_id`, and `gc.work_dir`. The drain member is the exact source
anchor, the item index must be a non-negative integer, and `gc.work_dir` must
resolve to the launcher rig repository root. Do not infer the source anchor
from a dependency or use the synthetic input convoy.

Do not read, edit, test, stage, or commit product source in this step. Its
machine check creates or reuses the deterministic shared git worktree for the
drain, verifies that it belongs to the launcher repository and differs from
the launcher checkout, and persists `work_dir` on the current source anchor.
Close with `gc.outcome=pass` only after the metadata is unambiguous; the check
will fail closed if setup or read-back verification does not succeed.

Do not invoke provider-native subagents. Gas City owns the shared-drain
lifecycle.
