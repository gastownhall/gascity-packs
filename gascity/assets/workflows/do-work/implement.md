
Resolve `<source-anchor-id>` using the same rules as `prepare-worktree`. For a
synthetic drain-unit convoy, the source anchor is the original drain member in
`gc.drain_member_id`, not the synthetic convoy id. Read `work_dir` from the source anchor, never read `work_dir` from the synthetic drain-unit convoy,
validate that it is an absolute existing git worktree, set `WORKTREE` to that
path, then `cd "$WORKTREE"` before reading or editing source files. If
`work_dir` is missing, invalid, or points at the launcher checkout, fail this step before editing;
the lane case in the next paragraph is the one exception to a missing `work_dir`.

When the source anchor has no `work_dir` and records `gc.work_branch`
(`prepare-worktree` ran in the run operator's lane and recorded the item's
branch instead of a directory), your own `$GC_DIR` is the worktree: it is a
lane your `pre_start` put on the item's branch (the branch recorded by
`prepare-worktree`); work there. Prove it before editing, and before any
`switch`, with the boundary test `prepare-worktree` step 4 applies (every
path resolved through symlinks, `pwd -P`): `git -C "$GC_DIR" rev-parse
--show-toplevel` equals `$GC_DIR` itself, that top-level is neither the rig
root (`gc.work_dir` on the workflow root bead) nor inside the rig root, and
`git -C "$GC_DIR" rev-parse --git-common-dir` is the rig root's `.git`. When
any part fails, `$GC_DIR` is not a lane (a subdirectory of the human
checkout, or a worktree of another repository): fail this step before
editing and never run `switch` there, because switching a subdirectory of
the rig checkout would switch the human checkout's branch. Then `git -C
"$GC_DIR" rev-parse --verify "refs/heads/<gc.work_branch>"` must succeed, and
`git -C "$GC_DIR" branch --show-current` must print that branch. If it prints
another branch or nothing, switch your own lane onto the recorded branch with
`git -C "$GC_DIR" switch --no-overwrite-ignore "<gc.work_branch>"` (refs are
shared by every worktree of the rig, and `prepare-worktree` detached its lane
from the branch so it is free). `--no-overwrite-ignore` makes git refuse when
an ignored file in your lane (a build output, say) collides with a path the
branch tracks; a plain `switch` would overwrite that file silently, and the
lane helper `worker-worktree.sh` protects the same case. If git refuses, for
that or any other reason, or the branch is missing from the repository, fail
this step before editing: never `--force`, never a stash (the stash stack is
shared by every worktree of the rig), and never remove the colliding file.
Then set `WORKTREE="$GC_DIR"`; `cd "$WORKTREE"` and the `pwd -P` check below
hold trivially. Never enter another
agent's lane, and never treat a persisted `work_dir` that points into
`.worktrees/<rig>/lane-*` of another agent as yours: a `work_dir` naming a
lane other than `$GC_DIR` is invalid, fail this step before editing.
Otherwise the steps below apply unchanged.

Do not infer the source anchor from dependency ids such as the
`prepare-worktree` step. Read the claimed step bead's `gc.root_bead_id`, read
that do-work root with `gc bd show <root-bead-id> --json`, then read the root
metadata `gc.input_convoy_id`. Read that input convoy with `gc bd show
<input-convoy-id> --json`; if the JSON output is a one-element list, unwrap the
first element before reading metadata. If the input convoy has
`gc.synthetic_kind=drain-unit-convoy`, use its `gc.drain_member_id` as the
source anchor. Otherwise use the input convoy id as the source anchor. Then
read the source anchor and use only its `work_dir` metadata as `WORKTREE`,
or, when it has no `work_dir` and records `gc.work_branch`, your own lane
`$GC_DIR` on that branch, resolved as the lane paragraph above says; never any
other directory.

`gc.work_dir` is the launcher rig root, not the implementation worktree. Use
`gc.work_dir` only later to run `.gc/scripts/checks/build-artifact-valid.sh`.
After resolving `WORKTREE`, run `cd "$WORKTREE"` and verify `pwd -P` equals
`$WORKTREE` before any source read, source edit, test, file hash, `git add`, or
`git commit`. If a command uses the launcher checkout path for source edits,
verification, hashes, or commits, the step is invalid and must fail.

Do not edit files in the launcher checkout. Implement only the owned source
anchor boundary, run sandboxed verification from inside the worktree, and make a
focused commit in the worktree. Leave the source anchor open for
`close-source-anchor`; close only this implementation step when done.

Release the branch when you hand off (the lane case). A lane HOLDS the item's
branch only while it is writing to it: git allows one worktree per branch, so
a branch left checked out in your lane blocks the review fix lane's switch
(git: "already checked out at <your lane>", or "already used by worktree at
<your lane>" in newer git) and forces every later writer to fail closed.
After the final commit and BEFORE closing this step with `gc.outcome=pass`,
release the branch from your lane: `git -C "$GC_DIR" switch --detach` (HEAD
stays at your commit; untracked files stay), then verify
`git -C "$GC_DIR" branch --show-current` prints nothing, and name the commit
id in this step's close reason. Nothing is lost: `close-source-anchor` reads
the commit by branch (`git log -1 <gc.work_branch>`), the review lanes inspect
it detached at that commit, and the fix lane takes the branch, commits, and
releases it the same way. This release is the lane case only; the per-item
`work_dir` worktree of the rig-root path is already detached and is shared
with no one.

Write or update the task summary with these schema-required body sections,
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
- `producer: {formula: do-work, stage: implement, attempt: <positive integer>}`
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
