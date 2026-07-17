Evaluate BMAD implementation readiness.

Treat the installed `bmad-check-implementation-readiness` skill as a methodology reference only.
Do not greet or present menus, and do not wait for user input in headless mode.
Never wait for an interactive selection. Review the approved PRD, architecture,
epics, stories, decomposition artifact, and implementation convoy directly.

Write a deterministic Markdown readiness report under the build artifact root.
Record its absolute path on the workflow root as
`gc.build.implementation_readiness_path`. The report must cover requirement and
story traceability, architecture alignment, UX or operational dependencies,
story independence, verification readiness, and every blocking gap.

When all required evidence is ready, record
`gc.build.implementation_readiness_status=approved` on the workflow root and
close this step with `gc.outcome=pass`. When any required evidence is missing
or contradictory, record
`gc.build.implementation_readiness_status=blocked`, a concise
`gc.blocked_reason`, and close with `gc.outcome=fail`. In other words, the
allowed lifecycle value is
`gc.build.implementation_readiness_status=approved|blocked`; never report an
approval while retaining a blocked reason.

Do not invoke provider-native subagents or upstream BMAD runtime commands.
