Resolve the workflow root from the claimed step metadata. Read its record:
`gc gc source-delivery show --root <root-id>`.
Read the source task named in the record. Work only in its absolute `worktree`
path; never edit the launcher checkout. Keep the input commit and ownership
record intact. Implement the task, run the recorded verify_command, and commit
focused changes on the attached branch. Preserve unrelated files.

Leave the source task open. Close only this step with gc.outcome=pass once the
implementation is committed and the worktree is clean. Report blockers instead
of inventing verification evidence. Drain after closing the step.
