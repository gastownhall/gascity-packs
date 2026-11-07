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

Before removal it requires a closed work bead, a terminal handoff, a clean
worktree, and an exact match between the worktree HEAD and the recorded
recovery source SHA. It then applies the evidence matrix for that handoff:

- `merged` / `already_merged` requires the exact artifact source SHA at
  `origin/polecat/<bead>` and independently refreshes the recorded target to
  prove `merged_sha` is reachable there as terminal-state corroboration;
- `mr_merged` requires the source ref to equal the validated `pr_head_sha`
  GitHub reported to the refinery, plus refreshed target reachability for
  `merged_sha`. When GitHub deleted the head branch on merge (the branch is
  absent, not moved), GitHub's immutable `refs/pull/<pr_number>/head` at that
  exact SHA stands in as the retained source ref; and
- a no-merge deliverable (`metadata.deliverable` of `comment`, `verdict`,
  `config`, `artifact`, or `none`, with no `merge_result`) requires the same
  proof the polecat submit gate enforced before closing: a recorded comment
  for `comment` / `verdict`, or a non-empty `metadata.deliverable_evidence`
  stamp for `config` / `artifact` / `none`. The deliverable lives on the bead
  in the ledger, never in the worktree, so the retired checkout is the
  untouched fork point: its HEAD must equal the recorded `fork_sha`, and that
  SHA must still be reachable from the recorded base (`metadata.base_ref`, a
  `refs/remotes/origin/*` ref) on origin.

The target checks do not prove a source-to-merge relation. In every accepted
case the exact source ref remains independent recovery evidence after local
cleanup. Mutable bead metadata alone is never sufficient deletion evidence.

The historical `merge_result=pull_request`, current
`merge_result=pull_request_pending`, obsolete
`merge_result=pull_request_merged`, and unknown result values are not terminal,
even on a closed bead. They remain pending until operator review and
verified-merge reconciliation establish explicit `mr_merged` evidence.
Non-terminal MR handoffs are marked `artifact_cleanup_state=pending`;
verified-merge reconciliation calls the same command again. A recognized
no-merge deliverable without its proof also stays `pending`: the proof can
still arrive after the close (a comment is posted, evidence is stamped), so
the record defers with the missing proof named rather than blocking.
Successful or already-completed cleanup records
`artifact_cleanup_state=complete`. With no bead ID, the command retries at
most one closed artifact still marked `pending` that is actionable: its
result is exactly `merged`, `already_merged`, or `mr_merged`, or it is a
proven no-merge deliverable as above. Filtering actionable records before
ordering the sweep prevents an older non-terminal record from starving a
newer actionable cleanup. The refinery runs that bounded sweep before
looking for new work.
