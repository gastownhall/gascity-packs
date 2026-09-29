
Invoke `github-issue-triage` with GitHub issue URL {{github_issue_url}} and
artifact root {{artifact_root}}. Because triage is idempotent by issue body
hash, this either returns the existing current-hash triage report/comment or
creates a new one.
