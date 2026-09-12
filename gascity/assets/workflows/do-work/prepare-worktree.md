
Resolve and publish the isolated worktree for this item. This is infrastructure
setup only. Do not edit source files in the launcher checkout.

1. Read current step bead metadata and get `gc.root_bead_id`; hard-fail if it is
   missing. Read that do-work root with `gc bd show <root-bead-id> --json`. If
   `gc bd show --json` returns a one-element list, unwrap the first element before
   reading metadata.
2. Resolve `<source-anchor-id>` from the do-work root:
   - read root metadata `gc.input_convoy_id`; hard-fail if it is missing
   - verify `gc.input_convoy_id` matches rendered runtime convoy `{{convoy_id}}`
   - read that input convoy with `gc bd show <input-convoy-id> --json`; unwrap a
     one-element list response before reading metadata
   - if input convoy metadata has `gc.synthetic_kind=drain-unit-convoy`, use
     input convoy metadata `gc.drain_member_id`
   - do not use the synthetic drain-unit convoy id as `<source-anchor-id>`;
     hard-fail if the selected source anchor id equals the synthetic input convoy id
   - otherwise use `<input-convoy-id>` as the source anchor
   - if root metadata also has `gc.drain_member_id`, it must match the selected
     drain member
3. Validate context path {{context_path}}, files ownership, and verification
   policy for the resolved source anchor.
4. Check the workspace gc gave this session before creating anything. When
   `$GC_DIR` is already a git worktree of the rig on a branch (the agent's
   lane, prepared by its `pre_start`: `git -C "$GC_DIR" rev-parse
   --is-inside-work-tree` prints `true` and `git -C "$GC_DIR" branch
   --show-current` prints a branch name, or the `pre_start` log says so, and
   `$GC_DIR` is not the rig root), this MAY be the lane case. Prove it with
   the boundary test below before recording a branch or detaching anything:
   those two probes also succeed from any SUBDIRECTORY of a checkout, and a
   subdirectory of a human checkout must never be detached. In the lane case
   this step creates nothing and hands no directory to anyone: a lane is per
   agent (this one is the run operator's), and the item's BRANCH is the
   handoff. Every worktree of the rig shares its refs, so a branch made
   visible here is reachable from the implementation worker's own lane.
   - Boundary test. Resolve every path through symlinks before comparing
     (`cd <path> && pwd -P`, or `realpath`; on macOS `/tmp` resolves to
     `/private/tmp`). ALL three must hold:
     1. The canonical git top-level of `$GC_DIR` IS `$GC_DIR`: `git -C
        "$GC_DIR" rev-parse --show-toplevel`, resolved, equals `$GC_DIR`,
        resolved. A subdirectory of any checkout fails this.
     2. That top-level is NOT the rig root and is NOT inside the rig root
        (the launcher checkout: `gc.work_dir` on the workflow root bead read
        in step 1, resolved). Equality fails, and so does a prefix match of
        the resolved rig root path plus a path separator.
     3. `$GC_DIR` belongs to the rig's repository: `git -C "$GC_DIR"
        rev-parse --git-common-dir`, resolved, is the same directory as the
        rig root's `.git` (`git -C <rig root> rev-parse --git-common-dir`,
        resolved). A worktree of another repository fails this.
     When any part fails, this is NOT the lane case: record no branch, run
     no `switch` in `$GC_DIR`, detach nothing (a `switch --detach` in a
     subdirectory of the rig checkout would detach the human checkout's
     HEAD), and continue with step 5 exactly as before (the per-item
     worktree under `$(pwd)/worktrees/<source-anchor-id>`, then step 6
     persists `work_dir`).
   - Resolve the item's branch by NAME, before recording anything: the
     item's branch is the one branch whose name contains `<source-anchor-id>`
     as a whole token (`<source-anchor-id>`, `fix/<source-anchor-id>-x`,
     never `<source-anchor-id>0`), local or on `origin` (the remote
     `pre_start` fetches), using the same whole-token matching as `pre_start`
     (worker-worktree.sh, "Bead branch"). Nothing else identifies it. Not the
     branch `pre_start` put THIS lane on: it is named for the trigger STEP
     bead, so a re-launched item (a new do-work run after a crash, a stopped
     run, or a review that sent it back) puts this lane on a fresh step
     branch, cut from the base and knowing nothing of the item's committed
     work; that branch is left where it is, unused and recorded nowhere. Not
     the recorded `gc.work_branch` on its own: a claim-time stamp (older `gc`
     builds, and any session started in the rig root, stamp the rig root's
     branch on the bead they claim) overwrites it with a name no checkout
     state can tell from an item branch, because a human checkout moves
     between branches, and a stamp can even contain the id
     (`human/<source-anchor-id>-notes`), so the record decides nothing on
     its own. Read the record FIRST (`gc bd show <source-anchor-id> --json`,
     metadata `gc.work_branch`; it is checked against the resolution below
     and re-aligned when stale), then decide once, by name:
     1. List every branch naming the item, the way `pre_start` does, by FULL
        ref name with exactly one namespace prefix removed, so that neither a
        tag of the same name (`%(refname:short)` would then print `heads/x`)
        nor a local branch literally named `origin/x` can change a name:
        `git -C "$GC_DIR" for-each-ref --format='%(refname)' refs/heads`,
        with the leading `refs/heads/` removed; and `git -C "$GC_DIR"
        for-each-ref --format='%(refname)' refs/remotes/origin`, with the
        leading `refs/remotes/origin/` removed and `HEAD` dropped. Keep the
        names matching `(^|[^A-Za-z0-9])<source-anchor-id>([^A-Za-z0-9]|$)`,
        de-duplicate. Exactly one: `BRANCH=` that name, whether or not the
        record agrees; a listed name that no longer resolves when taken below
        fails this step closed (it vanished under you), never falls through
        to a new branch. None: `BRANCH=<source-anchor-id>`, a new branch.
        Several: fail this step closed listing them,
        even when one of them is the record; take nothing, record nothing.
        The run operator reconciles them with each branch's owner before the
        item is re-launched: every branch that is not the item's is renamed
        to a name without the id, its commits preserved, on `origin` as well
        as locally (a local rename leaves `origin/<old name>` behind and the
        next fetch brings the candidate back); then a fetch and this listing
        show exactly one candidate.
     2. Take the branch in this lane, `--no-overwrite-ignore` always: a
        local branch, `git -C "$GC_DIR" switch --no-overwrite-ignore
        "$BRANCH"` (this lane already on it, a retry of this step after the
        record and before the detach, is a no-op and counts as taken); a
        branch only on `origin`, `git -C "$GC_DIR" switch
        --no-overwrite-ignore -c "$BRANCH" --track
        "refs/remotes/origin/$BRANCH"`; a new
        branch, `git -C "$GC_DIR" switch --no-overwrite-ignore -c "$BRANCH"`
        from HEAD (the base this lane's `pre_start` branch was cut from).
        Any refusal fails this step closed, creates nothing and records
        nothing: another worktree holds the branch (git: "already checked
        out at <path>", or "already used by worktree at <path>" in newer
        git; a writer crashed before releasing, or a human checkout took the
        branch), so the holder's path from `git worktree list` goes in the
        close reason and the run operator releases it from that checkout,
        never this step and never `--force`; or an ignored file is in the
        way (never removed; the close reason quotes git's refusal, and names
        no holder because there is none). The committed work stays where it
        is.
   - Record the branch on the source anchor with
     `gc bd update <source-anchor-id> --set-metadata gc.work_branch=<branch>`
     only when the record differs from `$BRANCH` (no record, a claim-time
     stamp, a record of a gone or renamed branch); an equal record is left
     as it is. This never records a fresh base branch over a recorded item
     branch: a new branch is created only when no branch names the item. A
     branch recorded before this rule under a name that does not contain
     `<source-anchor-id>` is not found by it and would be left behind: before
     rolling this rule out on a city, the operator audits open items'
     `gc.work_branch` values and renames such branches to contain the id as a
     whole token (this pack's own cities import the upstream pack, which has
     no lane case, so none exist there). For synthetic drain-unit convoys,
     stamp the original drain member/source anchor, never the synthetic
     drain-unit convoy.
   - Detach this lane from the branch with `git -C "$GC_DIR" switch --detach`.
     git allows one worktree per branch, so detaching frees the branch for
     the next role's lane; HEAD stays at the same commit and untracked files
     (staged skills, hooks) stay in place.
   - Verify before closing this step with `gc.outcome=pass`: the source
     anchor's `gc.work_branch` equals `$BRANCH`, `git -C "$GC_DIR" rev-parse
     --verify "refs/heads/$BRANCH"` succeeds, and `git -C "$GC_DIR" branch
     --show-current` prints nothing.
   Do NOT persist `work_dir` in the lane case: step 6 is skipped. A directory
   is per agent and is never handed to another agent; the next role works in
   its own lane on the recorded branch. The source anchor then has no
   `work_dir` and records `gc.work_branch`, and every later step that reads
   `work_dir` (implement, close-source-anchor, the review setup and its review
   and fix lanes) resolves that case in its OWN lane under one lifecycle,
   because git allows one worktree per branch: a lane HOLDS the item's branch
   only while it is writing to it and RELEASES it when it hands off; every
   reader INSPECTS the recorded commit detached, never on the branch.
   - A writer (implement, then the review fix lane) switches its own lane
     onto the branch with `git switch --no-overwrite-ignore "<gc.work_branch>"`,
     commits there, and releases the branch the same way this step does,
     `git -C "$GC_DIR" switch --detach`, after its final commit and before it
     closes its step; every writer releases the branch the same way when it
     hands off. HEAD stays at the commit, so nothing is lost: the next step
     reads the commit by the branch's full ref.
   - A reader (close-source-anchor, the review setup, the acceptance,
     simplicity and test-evidence lanes) never takes the branch: it reads the
     branch's commit with `git log -1 "refs/heads/<branch>"` / `git show`, or
     detaches its own lane at that commit (`git switch --detach
     --no-overwrite-ignore <commit>`) to run commands there, after the same
     boundary test above that every writer applies. A reader whose `$GC_DIR`
     fails it (a role with no `work_dir` starts in the rig root, the human
     checkout) detaches nothing and reads by `git show` and `git log` only.
     Readers detached at one commit never contend, however many run in
     parallel, and never block the next writer.
   - Every read that resolves the branch NAME to a commit (`git log -1`,
     `git rev-parse`, `git show`: close-source-anchor's verification, the
     commit the review setup records, a review lane resolving a branch the
     context carries, the fix lane's refresh) names the FULL ref,
     `refs/heads/<branch>` (`refs/remotes/origin/<branch>` for a branch that
     is only on `origin`), never the bare name: git resolves a bare name
     tag-first (`refs/tags/<name>` before `refs/heads/<name>`), so a tag with
     the branch's name, at the base, would send every reader to the base and
     review would inspect and record the base instead of the implementation,
     while the listing above still finds the branch. Only the branch operand
     of `git switch`, which resolves branches alone, stays bare; a tracked
     take's start point is `refs/remotes/origin/<branch>`, because a
     `--track` start point is a commit-ish, not a branch lookup, and a tag
     named `origin/<branch>` makes the bare form fail "ambiguous object
     name" (a spurious failure of a resumable item).
   - A writer that commits after a commit was recorded for readers (the
     review fix lane, after the review setup recorded the commit it reviews)
     refreshes the recorded commit before it releases the branch: this
     source anchor's record in the review context file and `gc.review_commit`
     on this source anchor (per item, never a workflow-wide key: separate
     drains put several items on independent branches, each inspected at its
     own commit), so the next attempt's readers inspect the new commit, never
     the one the setup saw, and no other item's recorded commit moves.
   - A writer that crashed before releasing leaves the branch held. The next
     writer's switch then fails (git: "already checked out at <path>", or
     "already used by worktree at <path>" in newer git); that step fails
     closed with the holder's path (from `git worktree list`) in its close
     reason, and the run operator (a human or the mayor) releases the branch
     with `git -C <holder lane> switch --detach`. A step never enters another
     agent's lane and never releases it, and no step `--force`s past a
     holder.
   Otherwise (the session started in the rig root; the role has no lane),
   continue with step 5.
5. Create or reuse a deterministic git worktree at
   `$(pwd)/worktrees/<source-anchor-id>`, based on the up-to-date remote
   default branch — never the launcher's local `HEAD`, which may be behind
   `origin`. If the path is missing:
   - Resolve the remote default branch (do not hardcode `main`). Read the
     local ref first, and only touch the network if it is missing:

     ```sh
     DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
     if [ -z "$DEFAULT_BRANCH" ]; then
       git remote set-head origin --auto >/dev/null 2>&1 || true
       DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
     fi
     ```

     `refs/remotes/origin/HEAD` is written by `git clone` and refreshed by
     `git remote set-head origin --auto`. It is NOT written by `git init` plus
     `git fetch`, which is how `actions/checkout` and several of our own
     checkouts are built, so the refresh branch is load-bearing rather than
     defensive. The fetch on the next line still guarantees the base is
     current, so a stale ref costs nothing.

     If it is still empty, fail closed — do not fall back to local `HEAD`.
   - Fetch it so the base is current:
     `git fetch --prune origin "$DEFAULT_BRANCH"`.
   - Create the worktree detached at the freshly fetched tip:
     `git worktree add "$WORKTREE" --detach "origin/$DEFAULT_BRANCH"`.
   If the path exists but is not the worktree for this repository, fail closed.
6. Persist the absolute path on the source anchor with
   `gc bd update <source-anchor-id> --set-metadata work_dir=<absolute worktree path>`.
   For synthetic drain-unit convoys, never persist `work_dir` on the synthetic drain-unit convoy; the original drain member/source anchor is authoritative.
   Verify the source anchor now has `work_dir` before closing this step with
   `gc.outcome=pass`.
