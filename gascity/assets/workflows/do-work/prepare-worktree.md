
Resolve and publish the isolated worktree for this item. This is infrastructure
setup only. Do not edit source files in the launcher checkout.

1. Read current step bead metadata and get `gc.root_bead_id`; hard-fail if it is
   missing. Read that do-work root with `gc bd show <root-bead-id> --json`.
2. Resolve `<source-anchor-id>` from the do-work root:
   - read root metadata `gc.input_convoy_id`; hard-fail if it is missing
   - verify `gc.input_convoy_id` matches rendered runtime convoy `{{convoy_id}}`
   - read that input convoy with `gc bd show <input-convoy-id> --json`
   - if input convoy metadata has `gc.synthetic_kind=drain-unit-convoy`, use
     input convoy metadata `gc.drain_member_id`
   - do not use the synthetic drain-unit convoy id as `<source-anchor-id>`;
     hard-fail if the selected source anchor id equals the synthetic input convoy id
   - otherwise use `<input-convoy-id>` as the source anchor
   - if root metadata also has `gc.drain_member_id`, it must match the selected
     drain member
3. Validate context path {{context_path}}, files ownership, and verification
   policy for the resolved source anchor.
4. Create or reuse a deterministic git worktree at
   `$(pwd)/worktrees/<source-anchor-id>`. If the path is missing, fetch before
   cutting the worktree and fail closed on any default-resolution error:
   - run `git fetch origin`; hard-fail if it fails
   - run `git remote set-head origin --auto`; hard-fail if it fails
   - resolve `DEFAULT_REF` with
     `git symbolic-ref --quiet --short refs/remotes/origin/HEAD`; hard-fail if
     it is empty or does not resolve to an `origin/<default-branch>` ref
   - verify `git rev-parse --verify "$DEFAULT_REF^{commit}"`; hard-fail if it
     is not a commit
   - run `git worktree add "$WORKTREE" --detach "$DEFAULT_REF"` so the
     detached worktree starts at the fetched remote default commit
   If the path exists, never reset, remove, or overwrite it; validate that it
   is the worktree for this repository, and fail closed otherwise.
5. Persist the absolute path on the source anchor with
   `gc bd update <source-anchor-id> --set-metadata work_dir=<absolute worktree path>`.
   For synthetic drain-unit convoys, never persist `work_dir` on the synthetic drain-unit convoy; the original drain member/source anchor is authoritative.
   Verify the source anchor now has `work_dir` before closing this step with
   `gc.outcome=pass`.
