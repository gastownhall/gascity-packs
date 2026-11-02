
Read the current step bead metadata, get `gc.root_bead_id`, then read workflow
root metadata with `gc bd show <root-bead-id> --json`. Use `gc.github.repo`,
`gc.github.number`, `gc.github.head_sha`, `gc.github.snapshot_path`, and
`gc.github.review_dir` as the context index. If any required key is missing,
hard-fail and report that the snapshot handoff metadata is incomplete.

Look for the current head-SHA review artifacts under `gc.github.review_dir`.
The generic `review-report.md` is a `gc.build.review.v1` artifact; the translated
`verdict-report.md` is the `gc.verdict-report.v1` artifact consumed downstream.
Never validate the raw report with `review-outcome` or store its path as
`gc.github.review_report_path`.

If an older attempt has only `review-report.md`, recover its verdict with the
existing translator before considering reuse:

```bash
{{pack_root}}/assets/scripts/github_reports.py translate-review-report \
  "<gc.github.review_dir>/review-report.md" \
  --output "<gc.github.review_dir>/verdict-report.md"
```

If a validated `verdict-report.md` and current `comment.md` or waiting human
gate already exist for the same repo, PR number, and head SHA, resume that
attempt by refreshing workflow root metadata and stamping
`gc.github.reused_current_output=true`. Do not reuse artifacts from another
head or rerun the generic review for this already validated output.

When reusing, set at least `gc.github.review_report_path=<absolute
verdict-report.md path>`, `gc.github.comment_path=<absolute comment.md path>`,
and `gc.github.review_outcome=<approve|comment|request_changes|block>` on the
workflow root. Retain `gc.github.review_report_raw_path=<absolute
review-report.md path>` separately when the raw artifact exists. Validate the
verdict with `{{pack_root}}/assets/scripts/github_reports.py review-outcome`
before stamping metadata. If the stored sticky comment was deleted, create a
replacement from the existing rendered comment and update workflow root
metadata.

If no current reusable artifacts exist, stamp
`gc.github.reused_current_output=false` and close this step with
`gc.outcome=pass`; do not leave a stale true reuse flag for downstream steps.
