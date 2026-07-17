Apply gstack QA findings.

This lane is valid only when `gc.var.review_mode` is `agent` or `interactive`.
If it is `report`, stop without reading, testing, or changing product source;
the graph must select `qa-report-findings` instead.

Use implementation target {{implementation_target}} for fixes. Fix behavior
defects first, then add or update regression tests. If the QA lane found only
missing evidence, run and record the missing proof instead of changing code.
Read the current synthesis result first. When it is `approve`, write a no-op QA
fix artifact and set the terminal verdict to `done`. When it is `iterate`, apply
the focused fixes below and set the terminal verdict to `iterate` so the browser
and regression lanes rerun against the new commit; a same-iteration fix claim
must not erase the reviewers' finding.

Read `gc.build.implementation_member_ids` and the exact member-to-worktree map
from the QA context. Apply each fix only inside the affected member's
authoritative implementation worktree after verifying `pwd -P`; never edit or
test product source in the launcher checkout. Commit the fix in that worktree,
rerun the proof there, update the source member's
`gc.implementation.worktree_path`, `gc.implementation.commit`, and
`gc.implementation.summary_path`, and update the summary with the new full
commit SHA and observed passing result. Missing member ownership is a blocking
finding, not permission to patch the launcher.

After all member updates, regenerate the canonical root summary at the exact
workflow-root path in `gc.build.implementation_summary_path`. Its body must
name every exact member, authoritative worktree, current full commit, and
per-item summary. Its `trace.upstream` must contain each current absolute
per-item summary path exactly once with the `sha256` digest of its current
bytes. A pre-QA commit or digest is stale evidence and requires another
iteration.

Write a QA fix artifact under the artifact root.

Close with `gc.outcome=pass`,
`code_review.verdict=done|iterate`,
`code_review.report_path=<QA fix artifact path>`,
`code_review.output_path=<QA fix artifact path>`, and
`gstack.qa.fix_output_path=<QA fix artifact path>`.

Do not invoke provider-native subagents. This Gas City graph lane is the QA fix
delegation mechanism.
