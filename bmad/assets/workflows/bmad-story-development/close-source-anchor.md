Close the validated BMAD shared-drain source anchor.

This step runs only after the `implement-item` methodology-review and artifact
machine gate succeeds. Read the current step's `gc.root_bead_id`, then read the
inner workflow root's `gc.input_convoy_id`, `gc.drain_member_id`, and
`gc.drain_item_index`. Require the member and index to be non-empty. Read the
reserved input convoy; if it also records a member or index, require exact
equality with the root values. Require
`gc.build.implementation_source_anchor_id` to equal the root
`gc.drain_member_id`. Close only that actual source anchor, never the reserved
or synthetic convoy.

Read `gc.implementation.summary_path` from the inner workflow root, preceding
`implement-item` control bead, and source anchor. Require all three values to be
the same absolute path and require the validated summary to exist. Re-read the
source anchor's `work_dir`, require it to equal the recorded authoritative
worktree, and verify the expected implementation commit or clean working-tree
evidence is present there.

Update the source anchor with `gc.outcome=pass`, close it with a concise reason
naming the verified commit and summary, and read it back. Require
`status=closed` and `gc.outcome=pass` before closing this step. If identity,
summary, worktree, or close verification fails, leave the source anchor open
and close this step with `gc.outcome=fail`.

Do not invoke provider-native subagents. This post-gate lane owns only source
anchor closure.
