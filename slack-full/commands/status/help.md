Read-only diagnostics for the slack pack.

Reports adapter registration state, binding(s) for a chosen session,
and recent inbound/outbound event counts so a single command replaces
the curl + jq combinations that pile up while debugging.

Examples:
  gc slack status                                # global summary
  gc slack status --session gc-83347             # detail for cos's DM session
  gc slack status --since 5m --limit 100         # last 5 minutes, scan up to 100/dir
  gc slack status --json                         # machine-readable

Sources:
  GET /v0/city/<name>/extmsg/adapters
  GET /v0/city/<name>/extmsg/bindings?session_id=<sid>   (only with --session)
  GET /v0/city/<name>/events?type=extmsg.inbound
  GET /v0/city/<name>/events?type=extmsg.outbound

Errors are non-fatal: a failed sub-query degrades that section to
"none / 0" rather than aborting, so a partially-degraded city still
yields a usable status.
