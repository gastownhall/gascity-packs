Manage deterministic host-local worktrees shared by the convoy or epic that
owns each separately drained implementation item.

Usage:

```sh
gc gc workspace prepare --step-id <claimed-step-id> --input-ref <git-revision>
gc gc workspace path --step-id <claimed-step-id>
gc gc workspace verify-entry --step-id <claimed-step-id>
gc gc workspace record-result --step-id <claimed-step-id>
gc gc workspace result --step-id <claimed-step-id>
gc gc workspace cleanup --step-id <claimed-step-id>
gc gc workspace cleanup-if-complete --step-id <claimed-step-id>
```

`prepare` creates, exactly replays, or safely advances the detached workspace
for the claimed item's graph-derived owner. Items owned by the same convoy or
epic reuse one clean linear worktree. `path` returns the recorded workspace.
`verify-entry` requires a clean detached workspace at the recorded input.
`record-result` records the clean output revision; `result` returns that exact
current-item result for source-anchor close. `cleanup-if-complete` queries the
existing bead graph after that exact anchor closes. It retains the workspace
until every direct member of the derived owner is closed with `gc.outcome=pass`;
the last successful item removes the clean result worktree without force and
deletes transient state. Prompts invoke this conditional action; `cleanup`
remains the strict unconditional operation for validated orchestration.

`prepare` optionally accepts `--workspace-parent <path>`; otherwise it creates
worktrees beneath the rig root. The command requires `GC_WORK_DIR` (or the
legacy `GC_RIG_ROOT`) to identify that root. It rejects unsupported lifecycle
actions, destructive repair, and cross-host reuse.
