This is the `implementation-base` methodology contract worktree scope step.

This step is a durable scope latch, not agent-facing work: the orchestrator
manages it structurally once `prepare-worktree`, `implement`, and
`close-source-anchor` all reach a terminal state, and its outcome mirrors
whether any of those scoped members failed. Concrete methodology packs should
generally leave this step alone; override it only if a different scope name
or member set is required, and preserve the scope contract that
`teardown-worktree` depends on.
