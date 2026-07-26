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
least-recently-checked pending PR in the current rig and adopts it to the
current refinery instance when needed. The scan includes closed beads whose
artifact cleanup was interrupted. It closes the bead only after GitHub
reports the PR merged and the merge commit is reachable from the recorded
target branch on `origin`, with local replacement refs and grafts disabled.
It records the distinct `merge_result=mr_merged` result, closes the bead, and
freshly confirms that the closed record still retains the validated
`pr_head_sha` and exact `polecat/<work>` branch. Only then does it invoke the
idempotent task-artifact cleanup command. It clears the PR reconciliation
marker only after another fresh read proves cleanup durably complete without
losing that MR identity.
Cleanup failures remain marked on the closed bead for a later patrol retry.

An open PR whose head changes is returned to the refinery for quality-gate
revalidation. A closed-unmerged PR, a merged PR whose head changed after
validation, an ambiguous legacy closed record, or contradictory metadata
remains blocked and is escalated.
