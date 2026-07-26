# gastown pr-merge-reconcile

Keep `merge_strategy=mr` work blocked until its pull request is actually
merged.

```text
gc gastown pr-merge-reconcile
gc gastown pr-merge-reconcile record WORK PR_URL PR_NUMBER TARGET HEAD_SHA
```

`record` stores the verified pull-request handoff on `WORK` and moves the bead
to `blocked` without closing it. With no arguments, the command checks the
least-recently-checked pending PR in the current rig and adopts it to the
current refinery instance when needed. It closes the bead only after GitHub
reports the PR merged and the merge commit is reachable from the recorded
target branch on `origin`.

An open PR whose head changes is returned to the refinery for quality-gate
revalidation. A closed-unmerged PR, a merged PR whose head changed after
validation, or contradictory metadata remains blocked and is escalated.
