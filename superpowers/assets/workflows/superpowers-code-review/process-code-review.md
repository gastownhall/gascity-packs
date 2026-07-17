Process Superpowers code-review feedback.

Use the installed `receiving-code-review` skill as guidance for triaging review
and gap-analysis findings. Resolve required findings in this single lane and
preserve traceability to the reviewer, finding id, file anchors, and acceptance
criteria.

Read the code-review context from workflow root metadata
`gc.build.code_review_context_path`, the implementation review report from
`gc.build.code_review_report_path`, and the gap-analysis report from
`gc.build.gap_analysis_report_path`. Write the review fix summary to workflow
root metadata path `gc.build.review_fix_summary_path`, which should be
`<artifact_root>/review-fix-summary.md`.

Use implementation target {{implementation_target}} for any code changes.
Before any mutation, read workflow root metadata
`gc.build.implementation_convoy_id` and enumerate the exact closed convoy
members. Resolve the exact implementation convoy member that owns each required
finding from the review context, changed-file evidence, and per-member summary.
Read that member bead's absolute `gc.implementation.worktree_path` and
`gc.implementation.summary_path`. Missing or ambiguous ownership is blocking:
do not edit product source, record the blocker, and use
`code_review.verdict=iterate`.

For each affected member, use this order:

1. Canonicalize the member's authoritative implementation worktree and require
   the per-member summary to be inside it. Enter that worktree and Verify
   `pwd -P` exactly equals `gc.implementation.worktree_path` before any source
   read, edit, test, stage, summary rewrite, or commit.
2. Apply only that member's required fixes and run the relevant proof there.
   Never edit, test, stage, or commit product source in the launcher rig root,
   the current review-fix bead's worktree, or the artifact directory.
3. Rewrite and validate the per-member summary at
   `gc.implementation.summary_path` with the changed files, proof commands,
   observed results, and remaining risks.
4. Stage the source changes and summary, then commit all tracked source-worktree
   bytes, including the per-member summary. Require a clean tracked tree, then
   capture the current full `HEAD` with `git rev-parse HEAD`.
5. Atomically publish the terminal commit and summary on the exact member:
   `gc bd update "<implementation-member-id>" --set-metadata 'gc.implementation.commit=<current full HEAD>' --set-metadata 'gc.implementation.summary_path=<current absolute member summary>'`.
   Read the member back and require its commit, worktree `HEAD`, and summary path
   to agree. These implementation fields belong on the member, never the
   workflow root or current review-fix bead.

After all member updates, Regenerate the canonical root summary at the exact
workflow-root path `gc.build.implementation_summary_path`. Resolve every exact
implementation convoy member again; name each member, authoritative worktree,
current full commit, and per-member summary. Its `trace.upstream` must include
each current absolute per-member summary path exactly once with the `sha256`
digest of its current bytes. Validate the regenerated root summary, then refresh
`gc.build.code_review_context_path` with the current member, commit, worktree,
and summary mapping so the next review does not consume stale evidence.

Any product or per-member-summary mutation invalidates the current review,
including a mutation whose source bytes are later restored. Force
`code_review.verdict=iterate`, set workflow root
`gc.build.code_review_status=draft`, and close this iteration only after the
member and root evidence above is current. Only a subsequent unchanged review
iteration may set `done`.

Close this lane only after the review-fix artifact records resolved findings,
changed files, tests run, and blockers. If there are no required fixes, record a
no-op review-fix artifact instead of editing code.

If the review-fix artifact includes `gc.build.review.v1` front matter, its
`trace.coverage[].status` values and Markdown coverage table statuses must use
only schema allowed coverage statuses: `covered`, `blocked`, `deferred`,
`not_applicable`, `out_of_scope`, or `superseded`. Use `covered` for resolved
findings; do not use `resolved`, `violated`, `approved`, or `changes_required`
as coverage statuses. Include `rationale: <why this id is not covered>` on
every non-`covered` coverage row. The Markdown coverage table remains ID/status
only; the rationale belongs in YAML front matter.

If both review lanes approve and this lane made no mutation, perform a no-op
pass, update workflow root metadata with
`gc.build.code_review_status=approved`, and close with
`code_review.verdict=done`. A mutating iteration must retain the draft/iterate
outcome above even when it resolved every reported finding.

Always close with `gc.outcome=pass`, `code_review.verdict=done|iterate`,
`code_review.report_path=<review fix summary path>`, and
`code_review.output_path=<review fix summary path>`.

Use the exact claimed bead id when updating review-lane metadata. Do not pass
freeform notes or additional positional arguments to `gc bd update`; unquoted
words can resolve to unrelated beads. This unchanged/no-op approval example is
the only path that may publish `done`:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.verdict=done' \
  --set-metadata 'code_review.report_path=<review fix summary path>' \
  --set-metadata 'code_review.output_path=<review fix summary path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Code-review feedback processed and approved.'
```

After a mutation, use the same claimed-bead update shape with
`code_review.verdict=iterate` and close with a reason that a fresh review is
required. Never place `gc.implementation.commit` or
`gc.implementation.summary_path` on `$CLAIMED_BEAD_ID`.

Do not invoke provider-native subagents. This graph lane is the delegation
mechanism.
