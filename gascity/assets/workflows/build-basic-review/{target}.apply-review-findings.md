Apply build-basic starter review findings.

First recompute the current implementation snapshot and review-input snapshot from
exact member/commit tuples and canonical summary/context bytes; require every
lane, synthesis, and root value to match.

If all three review lanes approve those exact snapshots, this is a mandatory
no-op. Optional or non-blocking suggestions must not authorize edits.

Use the authoritative context worktree and retain
`gc.implementation.worktree_path`, `gc.implementation.commit`, and
`gc.implementation.summary_path`. No-op `done` requires matching `HEAD` and a
clean tree. Restored bytes still mean `iterate`.

If required fixes or missing evidence remain, act only on a concrete `iterate`
item in the authoritative implementation worktree at
`gc.implementation.worktree_path`. Resolve its implementation convoy member id,
make the smallest change, and run proof. Rewrite and validate
that member summary at `gc.implementation.summary_path`, then commit all tracked
source-worktree bytes, including that member summary. Only with a clean tree may
you capture terminal full `HEAD`, the current full commit. Atomically
update that member, never the root or claimed apply bead:
`gc bd update "<implementation-member-id>" --set-metadata 'gc.implementation.commit=<current full HEAD>' --set-metadata 'gc.implementation.summary_path=<current absolute member summary>'`.
Next refresh canonical `gc.build.implementation_summary_path` and
`gc.build.code_review_context_path` with current `sha256` traces. Run the
installed provenance verifier with `--emit-current`; never hand-hash. Then,
before closing the current Ralph iteration, publish its exact values:
`gc bd update "<workflow-root-id>" --set-metadata 'gc.build.implementation_snapshot=<new snapshot>' --set-metadata 'gc.build.review_input_snapshot=<new review-input snapshot>'`.
Make no later source edit or commit. Read both beads back; require commit,
`HEAD`, summaries, context, and snapshots to agree. You must set `code_review.verdict=iterate`; only a subsequent unchanged, all-approved pass
may set `done`.

Require `gc.build.artifact_root` to be absolute and equal the parent of
`gc.build.code_review_context_path`. Write `<artifact-root>/apply-review-findings-report.md`,
never review evidence in the implementation worktree. Use
`PYTHONDONTWRITEBYTECODE=1`; leave no bytecode. Apply fixes to the source
worktree, not to the launcher rig root; a root-checkout observation cannot override
`iterate`.

Set `code_review.verdict=done` only when unchanged and all-approved. Close with
`gc.outcome=pass`, `code_review.verdict=done|iterate`,
`code_review.reviewed_attempt=<current gc.attempt>`,
`code_review.implementation_snapshot=<current snapshot>`,
`code_review.review_input_snapshot=<current review-input snapshot>`, and both
report/output paths equal to `<apply-report>`.

Unchanged/no-op `done` example:

```bash
gc bd update "$CLAIMED_BEAD_ID" --set-metadata 'gc.outcome=pass' --set-metadata 'code_review.verdict=done' --set-metadata 'code_review.reviewed_attempt=<current gc.attempt>' --set-metadata 'code_review.implementation_snapshot=<current snapshot>' --set-metadata 'code_review.review_input_snapshot=<current review-input snapshot>' --set-metadata 'code_review.report_path=<apply-report>' --set-metadata 'code_review.output_path=<apply-report>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Build-basic starter review approved.'
```

Changed/restored-bytes `iterate` example:

Use the same update and paths, but set `code_review.verdict=iterate`, the new
snapshot values, and close with reason `Inputs changed; fresh review required.`
