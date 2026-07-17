Apply gstack code-review findings.

Use implementation target {{implementation_target}} for any code changes. Read
the review synthesis from workflow root `gc.build.code_review_report_path`. If
all required review lanes approve, write a no-op review-fix artifact. If
required fixes or missing evidence remain, make the smallest focused changes
and run proof commands. Write the review-fix artifact under the artifact root
and record it on the workflow root as `gc.build.review_fix_summary_path`.

Read `gc.build.implementation_member_ids` and the exact member-to-worktree map
from the review context. Apply each required fix only inside the affected
member's authoritative implementation worktree after verifying `pwd -P`;
never edit, test, or commit product source in the launcher checkout. Commit the
fix in that worktree, rerun the relevant proof there, and update the source
member's `gc.implementation.worktree_path`, `gc.implementation.commit`, and
`gc.implementation.summary_path`. Refresh the implementation summary with the
new full commit SHA and observed proof result. Missing or ambiguous member
ownership is a blocking finding and must produce `code_review.verdict=iterate`.

After all member updates, regenerate the canonical root summary at the exact
workflow-root path in `gc.build.implementation_summary_path`. Its body must
name every exact member, authoritative worktree, current full commit, and
per-item summary. Its `trace.upstream` must contain each current absolute
per-item summary path exactly once with the `sha256` digest of its current
bytes. A pre-review commit or digest is stale evidence and must not receive a
`done` verdict.

Set `code_review.verdict=done` only when staff, QA evidence, security, and gap
analysis approve, and update workflow root metadata with
`gc.build.code_review_status=approved`. Set `code_review.verdict=iterate` when
required fixes remain, and update workflow root metadata with
`gc.build.code_review_status=draft`.

Always close with `gc.outcome=pass`,
`code_review.verdict=done|iterate`,
`code_review.report_path=<review-fix artifact path>`, and
`code_review.output_path=<review-fix artifact path>`.

Do not invoke provider-native subagents. This Gas City graph lane is the delegation
mechanism for fixes.
