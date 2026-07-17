Apply required Compound Engineering code-review findings.

Read the synthesized review report and resolve required findings in this single
lane. Preserve traceability to the reviewer, finding id, severity, file anchors,
and acceptance criteria.

Read the canonical absolute review directory from workflow root metadata
`gc.build.code_review_artifact_root` and the synthesized report from the exact
recorded `gc.build.code_review_report_path`. Require the report to be contained
by that root. Write the review-fix summary to the exact path already recorded
in `gc.build.review_fix_summary_path`; if it is blank, derive
`<code-review-artifact-root>/apply-summary.md` and record that absolute path on
the workflow root before writing. Reject any input or output path outside the
recorded root.

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

Close this lane only after the review-fix artifact records changed files, tests
run, resolved findings, and blockers. If the synthesized report approves the
implementation with no required fixes and this lane made no mutation, record a
no-op review-fix artifact, update workflow root metadata with
`gc.build.code_review_status=approved`, and close with
`code_review.verdict=done`.

Always close with `gc.outcome=pass`,
`code_review.verdict=done|iterate`,
`code_review.report_path=<review fix summary path>`, and
`code_review.output_path=<review fix summary path>`.

Do not invoke provider-native subagents. This graph lane is the delegation
mechanism.
