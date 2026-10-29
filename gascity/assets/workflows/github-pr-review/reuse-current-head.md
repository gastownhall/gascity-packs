
Read the current step bead metadata, get `gc.root_bead_id`, then read workflow
root metadata with `gc bd show <root-bead-id> --json`. Use `gc.github.repo`,
`gc.github.number`, `gc.github.head_sha`, `gc.github.snapshot_path`, and
`gc.github.review_dir` as the context index. If any required key is missing,
hard-fail and report that the snapshot handoff metadata is incomplete.

Look for the current head-SHA review artifacts under `gc.github.review_dir`.
If a validated `review-report.md` and current `comment.md` or waiting human
gate already exists for the same repo, PR number, and head SHA, resume that
attempt by refreshing workflow root metadata and stamping
`gc.github.reused_current_output=true`.

When reusing, set at least `gc.github.review_report_path=<absolute
review-report.md path>`, `gc.github.comment_path=<absolute comment.md path>`,
and `gc.github.review_outcome=<approve|comment|request_changes|block>` on the
workflow root. Validate the report with
`{{pack_root}}/assets/scripts/github_reports.py review-outcome` before stamping
metadata. If the stored sticky comment was deleted, create a replacement from
the existing rendered comment and update workflow root metadata.

If no current reusable artifacts exist, stamp
`gc.github.reused_current_output=false` and close this step with
`gc.outcome=pass`; do not leave a stale true reuse flag for downstream steps.
