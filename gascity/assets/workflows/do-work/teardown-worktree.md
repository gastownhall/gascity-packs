
Resolve `<source-anchor-id>` using the same rules as `prepare-worktree`. Read
`work_dir` from the source anchor.

This step owns worktree teardown and runs whether `implement` and
`close-source-anchor` passed or failed, so a worktree never outlives this
workflow.

1. If `work_dir` is empty or unset on the source anchor, there is nothing to
   tear down; close this step with `gc.outcome=pass`.
2. If `work_dir` is set but the path does not exist, a previous attempt (or a
   crash) already removed it; clear `work_dir` from the source anchor with
   `gc bd update <source-anchor-id> --unset-metadata work_dir` and close this
   step with `gc.outcome=pass`.
3. Otherwise set `WORKTREE` to that path. Confirm `git worktree list` in the
   launcher checkout includes `$WORKTREE` and that it is not the launcher
   checkout itself; fail closed if either check does not hold.
4. Safety gate. `prepare-worktree` creates a `--detach HEAD` checkout: any
   commit made inside it is reachable only through that worktree until
   something else — a branch, a push, a merge back into the launcher
   checkout — makes it durable elsewhere. Never remove the worktree while
   that is still the only copy:
   - Run `git -C "$WORKTREE" status --porcelain`. Any output means
     uncommitted work is present — leave the worktree in place and close this
     step with `gc.outcome=fail`.
   - Run `git -C "$WORKTREE" rev-parse HEAD` for the worktree's current
     commit, then confirm it is reachable from some ref other than the
     worktree's own private HEAD, for example
     `git for-each-ref --contains <sha> refs/heads refs/remotes`. An empty
     result means the commit exists nowhere but this detached worktree, and
     removing it would orphan that commit — leave the worktree in place and
     close this step with `gc.outcome=fail`.
5. When the safety gate passes, remove the worktree without `--force`:
   `git worktree remove "$WORKTREE"`, then `git worktree prune`. A clean,
   ref-confirmed worktree removes cleanly; if `git worktree remove` still
   refuses, do not force it — leave the worktree and fail this step so the
   refusal gets investigated instead of silently discarding whatever it is
   protecting.
6. Clear `work_dir` from the source anchor with
   `gc bd update <source-anchor-id> --unset-metadata work_dir`, verify the
   worktree directory no longer exists, and close this step with
   `gc.outcome=pass`.

A `gc.outcome=fail` close from step 4 or step 5 is an expected outcome, not a
bug report: it means real work still lives only in this worktree, and
removing it would be unsafe. Leave it for a later pass or a human once the
work is confirmed durable elsewhere.
