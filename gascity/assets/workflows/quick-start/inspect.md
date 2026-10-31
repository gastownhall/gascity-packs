Resolve the workflow root from the claimed step metadata. Read its record with
`gc gc source-delivery show --root <root-id>`.
You are the independent reviewer: do not edit implementation files or repair
them. Read the source task and acceptance criteria, inspect the full diff from
base_sha to the owned worktree HEAD, inspect tests and run appropriate checks.
Review the actual source, including correctness, missing tests and scope.

Record the exact full HEAD SHA and a terminal verdict using
`gc gc source-delivery review --root <root-id>
--sha <full-commit-sha> --status <approved|changes_required|blocked>
--findings <one argument containing actionable findings>`.
Use approved only with no unresolved findings; omit --findings then. Rejections
must include evidence and required fixes. Do not record a stale SHA or approve
based only on the implementer summary. The native check separately executes
the fixed verification command against the approved commit.

A recorded rejection is a successful review step, so close this step with
 gc.outcome=pass even when changes are required; the check owns bounded repair.
Do not integrate or close the source task. Drain after closing this step.
