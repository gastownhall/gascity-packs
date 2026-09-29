
Render the sticky status comment with
`{{pack_root}}/assets/scripts/github_reports.py render-issue-fix-status`, then
create or update it with
`{{pack_root}}/assets/scripts/github_api.py comment-create "{{github_issue_url}}" --body-file <status-comment.md>` or
`{{pack_root}}/assets/scripts/github_api.py comment-update`. Keep one sticky
status comment per issue-fix run and replace deleted comments idempotently.
