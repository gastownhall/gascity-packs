Stage one exact lease-owned rejection-rebase conflict generation.

Usage:

    gc gastown polecat-conflict stage

Invoke this command only through the exact current workspace step:

    gc gastown polecat-step exec \
      --convoy <input-convoy-id> \
      --step-ref mol-polecat-work.workspace-setup \
      -- gc gastown polecat-conflict stage

The command independently revalidates the active Graph step and root, sole
convoy source, canonical artifact registration, source branch, captured lease,
frozen remote, lease-owned temporary rebase branch, and Git rebase generation.
It rejects untracked files and unstaged tracked changes outside the complete
set of currently unmerged paths.

Before changing the real index it copies the index, stages exactly the
NUL-enumerated unmerged paths in that copy, checks the exact conflict result,
and records an immutable intent binding the lease context, stopped commit,
`REBASE_HEAD`, onto commit, pre-continuation parent, complete unmerged-index
tuple digest, and expected post-stage tree. It then revalidates all authority,
stages exactly the same paths in the real index, proves the exact expected tree
and clean working state, and creates a matching done proof. Identical retries
converge after lost responses; a different generation or resolution never
overwrites an existing proof. If the reviewed resolution makes the stopped
commit empty, the lease materializes one proof-bound empty commit before
continuing so the source commit count is still preserved.

After `POLECAT_CONFLICT_STAGE_COMPLETE`, rerun only
`gc gastown polecat-workspace execute`. The lease command verifies the matching
done proof before every rebase continuation.
