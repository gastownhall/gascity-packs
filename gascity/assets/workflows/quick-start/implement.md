Resolve the workflow root from the claimed step metadata. Read its record:
`gc gc source-delivery show --root <root-id>`.
Read the source task named in the record. Work only in its absolute `worktree`
path; keep the input commit and ownership record intact.

On the initial iteration, implement the task, run the recorded verify_command
and commit focused changes on the attached branch. Preserve unrelated files.
On later iterations, read `findings` and repair the requested issues in that
same worktree. If verification failed after an approved review, rerun the
recorded command, diagnose and repair that failure before re-review. Keep the
fixed input, verification command and independent review evidence intact.

Never approve your own changes, integrate, push or close source work. Close only
this step with gc.outcome=pass after implementation or repairs are committed and
the worktree is clean. The native loop permits initial implementation and review
plus at most two repair rounds. Retain work and explain blockers when repair is
impossible. Drain after closing the step.

When a build, test or commit runs asynchronously, track its exact job handle and
wait within a stated time bound. If that bound expires, inspect that job and
the recorded worktree's Git status and commit before deciding to retry. A
process-name search can match the waiting shell itself; it does not prove a
specific job is still running. Preserve successful commits across recovery.
