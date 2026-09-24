
Read workflow root metadata from `gc bd show <root-bead-id> --json`. Validate the
generic review verdict report at `gc.github.review_report_path` and map it with
`{{pack_root}}/assets/scripts/github_reports.py review-outcome`:
`pass/none -> approve`, `fail/minor -> comment`, `fail/major -> request_changes`,
and `fail/blocker -> block`.

If workflow root metadata has `gc.github.reused_current_output=true`, validate
that `gc.github.comment_path` points to an existing `comment.md` under
`gc.github.review_dir`, verify the review report still maps to the stored
`gc.github.review_outcome`, close this step with `gc.outcome=pass`, and do not
rewrite the rendered comment. This keeps the reused current-head artifact as a
real no-op path.

Render the normal PR comment to `<gc.github.review_dir>/comment.md` with
`{{pack_root}}/assets/scripts/github_reports.py render-review-comment`, passing
the mapped outcome, `gc.github.head_sha`, and an artifact reference to the
review report. Update workflow root metadata with
`gc.github.comment_path=<absolute comment.md path>` and
`gc.github.review_outcome=<approve|comment|request_changes|block>`.
The source PR URL is {{github_pr_url}}.
