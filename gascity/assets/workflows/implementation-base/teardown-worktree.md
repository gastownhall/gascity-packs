This is the `implementation-base` methodology contract worktree teardown
step.

Concrete methodology packs override this step only when their implementation
items need different teardown. Preserve the safety gates below so a worktree
never outlives this workflow and a commit that exists nowhere else is never
discarded.

Default fallback behavior: resolve `<source-anchor-id>` using the same rules
as `prepare-worktree`, then read `work_dir` from that source anchor.

- If `work_dir` is empty, unset, or the path no longer exists, there is
  nothing to tear down: clear `work_dir` if it is still set and close this
  step with `gc.outcome=pass`.
- Otherwise, before removing anything, gate on safety: `git -C "$WORKTREE"
  status --porcelain` must be empty, and `git -C "$WORKTREE" rev-parse HEAD`
  must be reachable from some ref other than the worktree's own HEAD (for
  example `git for-each-ref --contains <sha> refs/heads refs/remotes`). If
  either check fails, leave the worktree in place and close this step with
  `gc.outcome=fail` so the unfinished or undurable work gets a later pass or a
  human instead of being silently discarded.
- When the safety gate passes, remove the worktree without `--force`
  (`git worktree remove "$WORKTREE"`, then `git worktree prune`), clear
  `work_dir` from the source anchor, and close this step with
  `gc.outcome=pass`.
