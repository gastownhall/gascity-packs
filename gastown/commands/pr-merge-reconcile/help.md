# gastown pr-merge-reconcile

Keep `merge_strategy=mr` work blocked until its pull request is actually
merged.

```text
gc gastown pr-merge-reconcile
gc gastown pr-merge-reconcile record WORK PR_URL PR_NUMBER TARGET HEAD_SHA
```

`record` stores the verified pull-request handoff on `WORK` and moves the bead
to `blocked` without closing it; the complete record, the `blocked` status and
the re-armed marker land in one update. The PR repository is bound to the rig's
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
merge commit is reachable from the freshly fetched, fully-qualified
`refs/remotes/origin/<target>` (a same-named local tag or branch cannot stand
in for it), with local replacement refs and grafts disabled. Merge, squash and
rebase merges all qualify because GitHub's merge commit, not the PR head, is
checked. A merge commit that is not on the target stays retryable and is
escalated once per episode; a previously verified merge commit that later
disappears from the target is treated as contradictory evidence.
It records the distinct `merge_result=mr_merged` result, closes the bead, and
freshly confirms that the closed record still retains the validated
`pr_head_sha` and exact `polecat/<work>` branch. Only then does it invoke the
idempotent task-artifact cleanup command. It clears the PR reconciliation
marker only after another fresh read proves cleanup durably complete without
losing that MR identity.
Cleanup failures remain marked on the closed bead for a later patrol retry.
If cleanup reports `artifact_cleanup_state=blocked` (an unsafe artifact that
will not self-heal), the marker is released and mayor is asked to review the
preserved artifact, so it cannot occupy the one-per-patrol slot forever.

Blocked beads are not session demand, so the witness patrol wakes the refinery
whenever a pending check is due; otherwise an idled-out refinery would never
release a merged PR's dependents.

An open PR whose head changes is returned to the refinery for quality-gate
revalidation. Stored `mr_merged` evidence that GitHub reports as open, a
closed-unmerged PR, a merged PR whose head changed after validation, an
ambiguous legacy closed record, or contradictory metadata remains blocked and
is escalated.

## Publish-order locks and auto-merge arming

An unchanged open PR whose bead carries `metadata.publish_after=<bead-id>` is
a publish-order lock: while the blocker bead is not `closed`, the record stays
pending, the run stamps `publish_order_hold=true` and
`publish_order_blocker_state=<status>`, and auto-merge is never armed. A
blocker that cannot be read (missing bead, malformed id, or a self-reference)
also holds, is stamped `pr_reconcile_error`, and is escalated to mayor once
per hold state. When the blocker closes, the next run releases the hold
(unsetting both stamps) and the PR becomes armable again.

For an unchanged open PR with no active lock, the reconciler makes the
remote auto-merge state match the record, and every decision leaves a bead
record:

- `mergeable` and not already armed: the reconciler arms auto-merge
  (`gh pr merge --auto`, or the `enablePullRequestAutoMerge` GraphQL mutation
  when only a token is available; method from `GASTOWN_PR_AUTO_MERGE_METHOD`,
  default `squash`) and stamps `auto_merge_armed=by_reconcile`,
  `auto_merge_armed_by=<session>`, `auto_merge_armed_at`.
- already armed remotely with no record: it stamps
  `auto_merge_armed=observed_external` with the observing session, so a hand
  re-arm by any actor is attributed within one patrol pass.
- `mergeable=false` (conflicting, e.g. behind main): it stamps
  `pr_state=merge_conflicting` with `pr_reconcile_error` and escalates to
  mayor once per transition; the branch owner must re-publish and revalidate.
- mergeability not yet computed: it keeps the record pending quietly.

Arming failures (`arm_failed`, invalid method) are retryable errors on the
bead; the pending marker survives. Manual re-arms remain possible but leave
no GitHub-side attribution beyond the shared token, so actors re-arming by
hand are expected to record it on the bead or in mail; the reconciler closes
the attribution gap for anything it observes.
