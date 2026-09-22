# Verified STOP respawn source (residual precision (a))

Measured 2026-09-22 against live `maintainer-city`.

**Finding: the respawn source is `[session_sleep]` `noninteractive = "5m"`
applied by the session reconciler.** A guard STOP does not pour a wisp,
does not fire an order, and does not mutate the work bead. Re-selection
is `find-work` after the session restarts.

See `../pr-body.md` section "Verified STOP respawn source" for the
enumerated checks (wisp sites, `gc order list`, `orphan-sweep`
`is_known_agent`, `nudge-on-route` on `bead.updated`).
