# Gastown Pack

Gastown is the domain-specific coding workflow pack. It provides the city
coordinator roles, rig worker roles, patrol formulas, and the pack-local dog
pool used for stuck-agent shutdown warrants.

## Import

```toml
[imports.gastown]
source = "../packs/gastown"
```

Use the pack as the workspace pack for city-scoped agents and as a rig pack for
rig-scoped agents.

## Composition

Gas City composes the builtin core pack (mechanical housekeeping orders)
through the explicit `includes` entries that `gc init` writes into
city.toml; this pack composes alongside it via `[imports.gastown]`. The
retired maintenance pack no longer exists: gastown's `mol-shutdown-dance`
and dog prompt fragments (`propulsion-dog`, `architecture`,
`following-mol`) are the only copies in play, and cross-pack agent name
collisions are hard errors rather than fallback resolutions.

Verify the composed recipe after changing imports:

```bash
gc formula show mol-shutdown-dance
```

The recipe must read warrant metadata from the claimed bead via
`$GC_BEAD_ID` and must not declare a required `warrant_id` var.

## Merge strategies

Work beads default to `metadata.merge_strategy=direct`: refinery lands the
branch on the target and closes the bead after verifying the remote target.
With `mr` / `pr`, refinery publishes a GitHub pull request and records a
pending handoff. The source bead stays `blocked` until
`gc gastown pr-merge-reconcile` verifies the validated PR head was merged and
its merge commit is reachable from the recorded target branch. Keeping the
source bead non-closed also keeps its dependency children non-ready.

The reconciler checks at most one pending PR per refinery patrol. Open PRs
remain pending, changed open heads return to refinery quality gates, and
closed-unmerged or merged-unvalidated PRs remain blocked for operator review.

This contract applies to new handoffs. An upgrade does not reopen legacy beads
that an older pack already closed at PR publication; operators should audit
those closed `merge_result=pull_request` records against their PR state before
relying on their dependency edges.

## Dog Pool

Gastown owns `mol-shutdown-dance` and the dog agent that runs stuck-agent
warrants, including the dog's `wake_mode` and `work_dir` settings. In import
composition gastown's dog expands as the distinct `gastown.dog` agent; the
dolt pack ships its own separate dog for Dolt maintenance formulas, and the
two coexist under their binding-qualified names.

Gastown deliberately does not ship retired dog formulas for JSONL export or
stale-session reaping. The Gas City builtin core pack provides JSONL export,
stale-session and stale-data cleanup, and Dolt housekeeping as deterministic
exec orders.
