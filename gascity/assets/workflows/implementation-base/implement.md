This is the `implementation-base` methodology contract implementation step.

Concrete methodology packs override this step to apply their native
implementation discipline. Work only inside the prepared worktree and preserve
the source anchor for the close step.

Default fallback behavior must still enforce the worktree contract: resolve the
source anchor from workflow metadata, read `work_dir` from that source anchor,
and `cd "$WORKTREE"` before source reads, edits, tests, hashes, or commits.
When the source anchor has no `work_dir` and records `gc.work_branch`
(`prepare-worktree` ran in a lane and handed the item over by branch; a
directory is per agent and is never handed to another agent), the worktree is
your OWN lane, `$GC_DIR`, on the recorded branch: prove the lane with the
boundary test `do-work/prepare-worktree` step 4 applies (resolved `git -C
"$GC_DIR" rev-parse --show-toplevel` equals `$GC_DIR`; neither the rig root
nor inside it; `rev-parse --git-common-dir` is the rig root's `.git`), then,
unless `git -C "$GC_DIR" branch --show-current` already prints that branch,
`git -C "$GC_DIR" switch --no-overwrite-ignore "<gc.work_branch>"`; when any
part fails or git refuses (an ignored file in your lane colliding with a path
the branch tracks), fail this step before editing: never `--force`, never a
stash, never remove the colliding file. Then `WORKTREE="$GC_DIR"`. Never enter
another agent's lane: a persisted `work_dir` naming a lane other than
`$GC_DIR` is invalid, fail closed.

Release the branch when you hand off (the lane case): a lane HOLDS the item's
branch only while it is writing to it, because git allows one worktree per
branch and a branch left checked out in your lane blocks the next writer's
switch (git: "already checked out at <your lane>", or "already used by
worktree at <your lane>" in newer git). After the final commit and
BEFORE closing this step with `gc.outcome=pass`, release the branch from your
lane: `git -C "$GC_DIR" switch --detach` (HEAD stays at your commit; untracked
files stay), then verify `git -C "$GC_DIR" branch --show-current` prints
nothing, and name the commit id in this step's close reason. Readers inspect
that commit detached (`git log -1 <gc.work_branch>`, `git show`), never on the
branch, so the release loses nothing.

`gc.work_dir` is the launcher rig root, not the implementation worktree. When
reading beads with `gc bd show --json`, handle both an object and a one-element
list before reading metadata.

Write the per-item implementation summary as a `gc.build.implementation-summary.v1`
artifact and record its absolute path on the workflow root bead as
`gc.implementation.summary_path` before closing.

The summary body must contain these exact schema-required `##` headings in this
order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. Before closing this step, read the launcher rig root from the workflow root bead's `gc.work_dir`, then run the same validator locally from that rig root with `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`; fix every reported validation error before setting `gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
