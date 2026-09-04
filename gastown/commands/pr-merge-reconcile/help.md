# gastown pr-merge-reconcile

Keep `merge_strategy=mr` work blocked until its pull request is actually
merged.

```text
gc gastown pr-merge-reconcile
gc gastown pr-merge-reconcile record WORK PR_URL PR_NUMBER TARGET HEAD_SHA
```

`record` stores the verified pull-request handoff on `WORK` and moves the bead
to `blocked` without closing it. The PR repository is bound to the rig's
standard github.com `origin`. With no arguments, the command checks the
least-recently-checked reconciliation marker in the current rig and adopts it
to the current refinery instance when needed. The scan includes interrupted
open records and closed beads whose artifact cleanup was interrupted. A
complete open `pull_request_pending` record finishes its transition to
`blocked` before lookup. An incomplete open record is reopened for full
quality-gate validation after stale partial PR evidence and its marker are
cleared; the independently validated `existing_pr` reuse hint armed with the
marker is retained to avoid creating a duplicate PR. An interrupted
changed-head requeue is likewise adopted and released for revalidation. Work
and artifact metadata are preserved.

Before any GitHub lookup, blocked records must be exactly
`pull_request_pending`, or exactly `mr_merged` with the complete stored merge
SHA, `pr_state=merged`, and merge timestamp produced before a verified close
failed. Closed retries require that same complete `mr_merged` evidence.
Unknown, incomplete, obsolete, or otherwise contradictory blocked/closed
states are quarantined and escalated.

The command closes the bead only after GitHub reports the PR merged and the
merge commit is reachable from the recorded target branch on `origin`, with
local replacement refs and grafts disabled.
It records the distinct `merge_result=mr_merged` result, closes the bead, and
freshly confirms that the closed record still retains the validated
`pr_head_sha` and exact `polecat/<work>` branch. Only then does it invoke the
idempotent task-artifact cleanup command. It clears the PR reconciliation
marker only after another fresh read proves cleanup durably complete without
losing that MR identity.
Cleanup failures remain marked on the closed bead for a later patrol retry.

An open PR whose head changes is returned to the refinery for quality-gate
revalidation. Stored `mr_merged` evidence that GitHub reports as open, a
closed-unmerged PR, a merged PR whose head changed after validation, an
ambiguous legacy closed record, or contradictory metadata remains blocked and
is escalated.
