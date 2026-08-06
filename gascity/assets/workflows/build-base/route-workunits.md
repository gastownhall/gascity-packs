This is the `build-base` route-workunits stage. Treat it as a virtual contract that concrete formulas may override.

The decomposition stage created the implementation convoy and its work-unit
beads, but ad-hoc `gc bd create` leaves those beads route-less
(`gc.routed_to` empty). Pool demand keys exclusively on `gc.routed_to`, so a
route-less work-unit is invisible to every pool and cannot be claimed until it
is routed. This stage makes the decomposed work-units claimable.

The routing is applied and verified by the automated check
`.gc/scripts/checks/route-workunits.sh`, which resolves the implementation
convoy (`gc.build.implementation_convoy_id`, fallback `gc.input_convoy_id`) and
the declared `implementation_target` off the workflow root, then stamps
`gc.routed_to` and `gc.execution_routed_to` to that target on every route-less
member. The stamp is coded, not agent-remembered; do not stamp routes by hand.

Confirm the implementation convoy is recorded on the workflow root, then close
this step. If the convoy or `implementation_target` is missing, do not paper
over it — the check fails loudly so the gap is surfaced rather than leaving
work-units to sit unclaimable. Never ask questions in headless mode.
