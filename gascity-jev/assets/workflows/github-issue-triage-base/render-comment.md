
Read workflow root metadata from `gc bd show <root-bead-id> --json`.
If workflow root metadata has `gc.github.reused_current_output=true`, validate
that `gc.github.comment_path` points to an existing `comment.md` under
`gc.github.triage_dir`, validate the reused triage report still matches
`gc.github.repo`, `gc.github.number`, and `gc.github.body_hash`, close this step
with `gc.outcome=pass`, and do not rewrite the rendered comment. This keeps the
reused current body-hash artifact as a real no-op path.

Render one body-hash-keyed public comment from `gc.github.triage_report_path`
to `<gc.github.triage_dir>/comment.md`. The comment must include a durable
workflow marker for the repo, issue number, and body hash. Use
`{{pack_root}}/assets/scripts/github_reports.py render-triage-comment` so the
structured front-matter fields are followed by the triage report analysis body
for human and future-agent readers. For `security_sensitive` or `priority: p0`,
render only safe public summary text until the human gate approves the final
comment body. Update workflow root metadata with
`gc.github.comment_path=<absolute comment.md path>`. The source issue URL is
{{github_issue_url}}.
