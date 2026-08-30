This is the `planning-base` methodology contract plan-review step.

Concrete methodology packs override this step to approve, revise, or reject the
plan artifact. Close pass only after the plan artifact is approved and ready for
the decomposition contract.

The requested review authority is `{{review_mode}}`: in `report` mode, record
findings and a verdict without mutating the plan; in `agent` mode, also produce
a structured fix handoff for the planning author to apply; in `interactive`
mode, safe plan fixes may be applied directly with every change and reason
recorded. The interaction posture is `{{interaction_mode}}`; in `headless`
mode, never ask questions and stop blocked with a machine-readable
`gc.blocked_reason` when approval input is missing.
