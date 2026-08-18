
Validate auth, token scope, remote, branch names, PR base, collision policy,
protected/default targets, sanitized metadata, final report {{final_report}},
push authorization {{push}}, and open_pr authorization {{open_pr}}.

Sanitized metadata means the PR title/body contain no bead/convoy/epic IDs,
no internal requirement labels (`REQ-001`, `REQ-002`, ...), and no gc
workflow/formula names — fail this check and require a rewrite before
proceeding if any are present.
