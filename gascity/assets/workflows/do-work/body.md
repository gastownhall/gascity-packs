
This step is a durable scope latch, not agent-facing work. The orchestrator
manages it: it becomes Ready only once `prepare-worktree`, `implement`, and
`close-source-anchor` all reach a terminal state, and its own outcome mirrors
whether any of those scoped members failed. Do not claim, edit, or hand-write
a close reason for this step; leave it for the control dispatcher.

`teardown-worktree` needs this step so worktree cleanup runs exactly once,
after the worktree body is done with the item worktree, regardless of
whether implementation passed or failed.
