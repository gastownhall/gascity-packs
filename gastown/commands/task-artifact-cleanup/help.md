# gc gastown task-artifact-cleanup

Idempotently retire a Gastown task worktree after its work bead reaches a
verified terminal handoff.

Usage:

```bash
gc gastown task-artifact-cleanup [work-bead-id]
```

The command requires `GC_CITY_PATH`, `GC_RIG`, and `GC_RIG_ROOT`. It accepts
only the exact canonical artifact path for that city and rig, or the exact
historical polecat-provider layout for an intentionally adopted legacy
artifact. It never force-removes a worktree.

Before removal it requires a closed work bead, a clean worktree, and an exact
`artifact_source_sha` match. It then independently refreshes the recorded
target and proves the merged SHA is reachable there as corroboration of
terminal state; that target check does not prove a source-to-merge relation.
Direct merges must retain the exact artifact source SHA at
`origin/polecat/<bead>`, and that ref remains the durable recovery copy after
local cleanup.
Under the current PR-publication handoff, that source ref must instead equal
the rebased PR head GitHub reported to the refinery. Mutable bead metadata
alone is never sufficient deletion evidence.

Non-terminal MR handoffs are marked `artifact_cleanup_state=pending`;
verified-merge reconciliation calls the same command again. Successful or
already-completed cleanup records `artifact_cleanup_state=complete`.
With no bead ID, the command retries at most one closed artifact still marked
`pending`; the refinery runs that bounded sweep before looking for new work.
