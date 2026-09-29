This is the `build-from-plan-base` handoff into the inherited decompose suffix.

Validate that the plan and plan-review artifacts now exist, that the
plan-review verdict approves decomposition, and that downstream decompose
selectors are present.

Do not create implementation beads in this handoff step. Close only after the
inherited `build-from-decompose-base` suffix has the approved plan inputs it
requires.
