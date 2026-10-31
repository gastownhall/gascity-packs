Resolve the workflow root from the claimed step metadata, then run
`gc gc source-delivery cleanup --root <root-id>`.
Native cleanup checks exact provisioning attempt, ownership, cleanliness,
reachability and integration before removing the worktree. Never force removal,
delete the implementation branch, or recursively remove a refused workspace.
Report cleanup_pending with its concrete reason and retain recoverable work.

The native workflow finalizer closes the source task after this and all other
required stages pass. Keep the source task open while cleanup is pending.

On success, close only this step with gc.outcome=pass and drain the worker. The
workflow record retains fixed input, predecessor, review, test and integrated
commit identities after cleanup. No GitHub publication is part of this journey.
