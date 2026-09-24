
Selected planning methodology formula: {{planning_formula}}.

Mechanically derive `requirements.md` from the issue body and triage report.
Mark the requirements artifact `status: approved` in `interactive`,
`autonomous`, and `headless` modes. For `not_reproduced` plus `test_hardening`,
state test hardening explicitly and do not claim a confirmed bug fix. The
launch alias is mode {{mode}}; read the effective interaction mode from
`gc.var.interaction_mode` on the workflow root. In `headless` mode, never ask
questions; if required input is missing, stop blocked with a machine-readable
`gc.blocked_reason` instead of waiting on a human.

This base adapter keeps requirements and implementation-plan generation as
separate lifecycle steps so human gates and sticky issue status stay stable.
Concrete issue-fix wrappers may override this step to delegate to
`{{planning_formula}}`, but they must still write the same
`gc.github.requirements_path` artifact before downstream steps run.

Read `gc.github.requirements_path` from workflow root metadata and write the
approved artifact to that absolute path. Do not choose or invent a different
path. If the metadata is missing or points outside the run directory, fail hard
instead of guessing a run directory.

Downstream implementation-plan, design-review, and create-beads steps must read
the artifact through `gc.github.requirements_path`.
