
Update the sticky issue-fix status comment at terminal success, failure,
blocked, or unavailable states. Write final run metadata containing source bead
id, body hash, triage report path, generated planning artifact paths,
implementation convoy id, build final report, PR URL when present, and whether
the run was resumed or newly created. Include launch input URL
{{github_issue_url}}, artifact root {{artifact_root}}, mode {{mode}}, PR mode
{{pr_mode}}, and drain policy {{drain_policy}}.

Every public GitHub comment body starts with the universal factory marker
line `<!-- gc-agent:v1 -->`, followed by the workflow-specific `gc:github-*`
marker. `github_reports.py` renders it and `github_api.py comment-create` /
`comment-update` enforce it; never strip or reorder it when editing a body.
