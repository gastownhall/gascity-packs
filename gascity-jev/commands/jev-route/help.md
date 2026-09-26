Route one task bead through the Jev intake router, then sling the chosen build.

Usage:
  gc <binding> jev-route <bead-id> [--var key=value ...] [--title <root title>] [--dry-run]

The router asks Jev the frozen intake questions about the bead's title and
description. It slings `jev-build-compact` only when the most likely size is
compact at confidence >= the intake band (day one 0.8), the risky surface is
`none`, and no design step is needed. Every other answer, an audited decision,
a tripped circuit breaker, or any Jev failure slings `jev-build`.

`--var` values pass through to `gc sling` (for example
`--var artifact_root=plans/x/build`). The decision is appended to the gate
ledger and passed to the build as `jev_intake_decision`. Prints one JSON line
with the chosen formula, the decision id and the workflow id.
