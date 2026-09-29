
Execute the durable implementation and post-implementation review loop for the
generated implementation convoy.

Selected methodology formulas:

- implementation_formula: {{implementation_formula}}
- implementation_item_formula: {{implementation_item_formula}}
- code_review_formula: {{code_review_formula}}
- review_fix_formula: {{review_fix_formula}}

Selector compatibility was validated at the snapshot gate; the effective
interaction mode is recorded as `gc.var.interaction_mode` on the workflow
root. The requested review mode is {{review_mode}}.

The GitHub issue-fix adapter owns run identity, status comments, human gates,
PR publication, and finalization. The selected methodology formulas own only
how implementation work is drained, how code review is produced, and how failed
review findings are fixed.

Start or reuse `{{implementation_formula}}` against the generated
implementation convoy, passing through drain policy {{drain_policy}},
implementation target {{implementation_target}},
implementation_item_formula {{implementation_item_formula}}, and the
normalized interaction mode when the selected formula accepts them. After
implementation completes, launch `{{code_review_formula}}` with the issue-fix
subject and report paths, passing through review_mode {{review_mode}} and the
normalized interaction mode when the selected formula accepts them. If the
review blocks the fix, run `{{review_fix_formula}}` until the review passes or
the workflow reaches its max iteration limit. In `headless` interaction mode,
never ask questions; on missing required input, stop blocked with a
machine-readable `gc.blocked_reason` instead of waiting on a human.
