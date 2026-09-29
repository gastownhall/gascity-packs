
Read `gc.github.public_comment_gate`, `gc.github.comment_path`, and any existing
comment metadata from workflow root metadata. Hard-stop with `gc.outcome=fail`
and `gc.failure_class=hard` unless `gc.github.public_comment_gate` is
`approved` or `not_required`; never post when the gate is `rejected`,
`revision_requested`, or missing.

When the gate is `approved`, re-render the body-hash-keyed issue comment with
the human-approved flag before posting so approved `security_sensitive` or `p0`
analysis can be included intentionally. Then create or update the
body-hash-keyed issue comment through
`{{pack_root}}/assets/scripts/github_api.py comment-create "{{github_issue_url}}" --body-file <gc.github.comment_path>` or
`{{pack_root}}/assets/scripts/github_api.py comment-update`. Update workflow
root metadata with the GitHub comment id and URL. Do not call `gh` directly
except to diagnose a wrapper failure.
