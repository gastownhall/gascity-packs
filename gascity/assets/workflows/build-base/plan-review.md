This is the `build-base` plan-review stage. Treat it as a virtual contract that concrete formulas may override.

Review the plan for traceability to requirements, feasibility, missing edge cases, and implementation readiness. If changes are required, update or route the plan before closing this stage.

Honor interaction_mode {{interaction_mode}} at the plan-review verdict. In
`interactive` mode, do not close this stage on your own verdict: engage the
passive wait + mail human gate (canonical mechanics in
`interactive-human-gate.md`) with gate key `gc.build.plan_review_gate` — park
the session, send exactly one mail to the human, and wait for the explicit
human verdict. In `autonomous` mode, record the verdict and proceed without
waiting on a human. In `headless` mode, never ask questions and never wait on
a human; stop blocked with a machine-readable `gc.blocked_reason` when
required approval input is missing.

Close this step only when the plan is approved or the blocking issues are recorded in the step summary.
