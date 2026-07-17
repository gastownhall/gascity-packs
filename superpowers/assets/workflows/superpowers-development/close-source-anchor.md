Close the Superpowers implementation source anchor.

Resolve the source anchor using the same rules as the inherited worktree setup.
Read `work_dir`, `gc.implementation.worktree_path`,
`gc.implementation.commit`, and `gc.implementation.summary_path` from that
exact source anchor. Require both worktree paths to resolve to the same
worktree, the commit to equal that worktree's `HEAD`, and the summary to exist
inside that worktree. Confirm the source anchor still matches the current
drained item. Missing, ambiguous, or cross-worktree proof must leave the source
anchor open and fail this step.

On success, close only the source anchor with `gc.outcome=pass`. Read the
source anchor back and verify it is closed before closing this step. Do not close
the drain-unit convoy, parent convoy, workflow root, or post-implementation
review steps.

Do not invoke provider-native subagents or upstream plugin runtime commands.
