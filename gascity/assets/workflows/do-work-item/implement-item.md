
Run inside an existing shared worktree lifecycle. Resolve reserved `convoy_id`,
read `gc.drain_member_id` and `gc.drain_item_index`, validate ownership and
verification policy, validate context path {{context_path}} when set, implement
the item, write an item summary, and close only the source anchor on success.

Do not infer the source anchor from dependency ids. Read the reserved convoy and
source anchor metadata directly; when `gc bd show --json` returns a one-element
list, unwrap the first element before reading metadata. `gc.work_dir` is the
launcher rig root, not the implementation location. Read `work_dir` from the
source anchor (the authoritative worktree recorded there), set `WORKTREE` to
it, run `cd "$WORKTREE"`, and verify `pwd -P` equals `$WORKTREE` before any
source read, source edit, test, file hash, `git add`, or `git commit`.

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
that commit detached (`git log -1 "refs/heads/<gc.work_branch>"`, the full
ref, since a bare name resolves tag-first; `git show`), never on the
branch, so the release loses nothing.

Write or update the item summary with these schema-required body sections,
using the exact `##` headings below in this order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

The `## Verification` section must include both the first verification command
and the final proof command, with the observed pass/fail result.

Write the summary as a `gc.build.implementation-summary.v1` artifact and record
its absolute path on the workflow root bead as `gc.implementation.summary_path`
before closing.
Include a Markdown coverage table. The validator only recognizes a table with
an `ID` column and a `Status` column. Use this shape:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`. The top-level YAML shape must be:

- `schema: gc.build.implementation-summary.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: gascity, name: build-basic}`
- `producer: {formula: do-work-item, stage: implement-item, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `trace: {upstream: [...], coverage: [...]}`

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- For the source anchor bead, use `path: beads/<source-anchor-id>` and
  `hash: bead:<source-anchor-id>`. For changed files or upstream build
  artifacts, use repo-relative paths and scheme-qualified hashes such as
  `sha256:<digest>` or `git:<revision>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for satisfied
  requirements; do not use `approved` in `trace.coverage[].status` or the
  Markdown coverage table.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. Before closing this step, read the launcher rig root from the workflow root bead's `gc.work_dir`, then run the same validator locally from that rig root with `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`; fix every reported validation error before setting `gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
