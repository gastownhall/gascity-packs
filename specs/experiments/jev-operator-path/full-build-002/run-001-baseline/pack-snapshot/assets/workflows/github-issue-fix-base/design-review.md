
Review and refine the generated implementation plan before bead creation. The
default pack implementation runs two focused reviewer agents and a
synthesize/apply loop until the implementation plan is approved. Local packs can
override this step and keep the same sink metadata protocol. The launch alias
is mode {{mode}}; read the effective interaction mode from
`gc.var.interaction_mode` on the workflow root. In `headless` mode, never ask
questions; if required input is missing, stop blocked with a machine-readable
`gc.blocked_reason`.

This is still adapter-owned lifecycle. Toolkit planning formulas may produce a
plan that needs a different review discipline, but the selected methodology
must not own GitHub issue status, run selection, comments, PR publication, or
finalization.
