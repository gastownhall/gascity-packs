Review the BMAD PRD and architecture handoff before decomposition.

Treat the installed `bmad-create-architecture` skill as a methodology reference only.
Do not greet or present menus, and do not wait for user input in headless mode.
Never wait for an interactive selection. Evaluate the approved requirements and
canonical plan directly, and record any unresolved issue as a concrete blocking
or residual-risk finding.

Confirm the architecture is complete enough for
`bmad-create-epics-and-stories` to preserve actual requirement IDs and produce
independently implementable stories. Verify affected boundaries, decisions,
non-goals, and proof commands are explicit. Do not run
`bmad-check-implementation-readiness` here; that BMAD method runs after epics
and stories exist.

Close with `gc.outcome=pass` only when the handoff is ready for decomposition;
otherwise close with `gc.outcome=fail` and a machine-readable blocking reason.

Do not invoke provider-native subagents or upstream BMAD runtime commands.
