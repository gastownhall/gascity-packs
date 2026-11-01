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

Before removal it requires a closed work bead, an explicitly merged
`merge_result`, a clean worktree, and an exact `artifact_source_sha` match. It
then applies the evidence matrix for that exact result:

- `merged` / `already_merged` requires the exact artifact source SHA at
  `origin/polecat/<bead>`. It uses `merged_target`, falling back to `target`
  only when `merged_target` is absent, null, or empty. An invalid populated
  `merged_target` blocks cleanup. It fetches the target and pins one commit
  for both `merged_sha` ancestry and the source-patch check described below.
- `mr_merged` requires the source ref to equal the validated `pr_head_sha`
  GitHub reported to the refinery, plus refreshed target reachability for
  `merged_sha`. When GitHub deleted the head branch on merge (the branch is
  absent, not moved), GitHub's immutable `refs/pull/<pr_number>/head` at that
  exact SHA stands in as the retained source ref.

For a direct handoff, complete history must show that the source is an
ancestor of the pinned target, or that every source-only non-merge commit has
an equivalent patch in the target history. The latter requires no source-only
merge commits and a successful, nonempty `git cherry <target> <source>` result
containing only negative object-ID records. Shallow or incomplete history,
failed queries, positive or malformed records, and unexplained empty output
block cleanup. History queries disable Git replacements and grafts.

The source-patch proof also tightens existing direct refinery landings with a
populated `merged_target`; it is not limited to the `target` fallback. A
conflict-free rebase with changed diff context, or a differently resolved
patch, can fail normalized patch equivalence even when the resulting change
is present in target history. Such proof failures record
`artifact_cleanup_state=blocked`. The current pending-only retry selector
does not automatically retry that blocked record; operator resolution is
needed.

This proves historical normalized patch equivalence. It does not prove
semantic equality, current-tree equality, or the absence of later reverts.
The integration commit need not itself introduce every source patch. The
verified-PR path retains its separate validated-head checks. In every accepted
case the exact remote source ref preserves the original bytes as independent
recovery evidence after local cleanup. Mutable bead metadata alone is never
sufficient deletion evidence.

The historical `merge_result=pull_request`, current
`merge_result=pull_request_pending`, obsolete
`merge_result=pull_request_merged`, and unknown result values are not terminal,
even on a closed bead. They remain pending until operator review and
verified-merge reconciliation establish explicit `mr_merged` evidence.
Non-terminal MR handoffs are marked `artifact_cleanup_state=pending`;
verified-merge reconciliation calls the same command again. Successful or
already-completed cleanup records `artifact_cleanup_state=complete`.
With no bead ID, the command retries at most one closed artifact still marked
`pending` whose result is exactly `merged`, `already_merged`, or `mr_merged`.
Filtering terminal results before ordering the sweep prevents an older
non-terminal record from starving a newer actionable cleanup. The refinery
runs that bounded sweep before looking for new work.
