# gc gastown task-artifact-cleanup

Idempotently retire a Gastown task worktree after its work bead reaches a
verified terminal handoff.

Usage:

```bash
gc gastown task-artifact-cleanup <work-bead-id>
```

The command requires `GC_CITY_PATH`, `GC_RIG`, and `GC_RIG_ROOT`. It accepts
only the exact canonical artifact path for that city and rig, or the exact
historical polecat-provider layout for an intentionally adopted legacy
artifact. It never force-removes a worktree.

Before removal it requires a closed work bead, terminal merge/PR evidence, a
clean worktree, and an exact `artifact_source_sha` match. Non-terminal MR
handoffs are marked `artifact_cleanup_state=pending`; verified-merge
reconciliation calls the same command again. Successful or already-completed
cleanup records `artifact_cleanup_state=complete`.
