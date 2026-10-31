Resolve the workflow root from the claimed step metadata. Read its record with
`gc gc source-delivery show --root <root-id>`.
On the initial iteration there is no prior review: make no changes and pass
this step. On later iterations read `findings`, fix only the requested issues
in the recorded owned worktree, run verify_command and commit the repair. Do
not alter the fixed input, verification command or review evidence yourself.
If verification failed after an approved review, rerun the recorded command,
diagnose and repair that failure in the same worktree before re-review.

Never approve your own changes, integrate, push or close source work. Close only
this step with gc.outcome=pass after repairs are committed and the worktree is
clean. The native review loop permits at most two repair rounds after initial
review. Retain work and explain blockers when repair is impossible. Drain.

When a build, test or commit runs asynchronously, track its exact job handle and
wait within a stated time bound. If that bound expires, inspect that job and
the recorded worktree's Git status and commit before deciding to retry. A
process-name search can match the waiting shell itself; it does not prove a
specific job is still running. Preserve successful commits across recovery.
