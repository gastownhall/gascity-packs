
Read `gc.github.public_comment_gate`, `gc.github.comment_path`,
`gc.github.head_sha`, and any existing comment metadata from workflow root
metadata. Hard-stop with `gc.outcome=fail` and `gc.failure_class=hard` unless
`gc.github.public_comment_gate` is `approved` or `not_required`; never post when
the gate is `rejected`, `revision_requested`, or missing.

When the gate is `approved`, re-render the comment with the human-approved flag
before posting so the public comment records the approval state. Then create or
update exactly one normal PR comment for this head SHA through
`{{pack_root}}/assets/scripts/github_api.py comment-create "{{github_pr_url}}" --body-file <gc.github.comment_path>` or
`{{pack_root}}/assets/scripts/github_api.py comment-update`. Update workflow
root metadata with the GitHub comment id and URL. Do not submit formal GitHub
review events in v0.
