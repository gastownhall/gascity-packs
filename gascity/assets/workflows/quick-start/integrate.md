Resolve the workflow root from the claimed step metadata, then run
`gc gc source-delivery integrate --root <root-id>`.
This command verifies native ownership, exact review/test/output identity,
clean worktrees and the unchanged integration input. It fast-forwards the local
branch without network access, records integrated_sha and only then closes and
reads back the source task. Do not replace it with a direct bd close, push or
manual merge. A changed input requires explicit recovery and fresh review.

Close only this step with gc.outcome=pass after success. Retain work and source
state on any refusal. Drain the worker.
