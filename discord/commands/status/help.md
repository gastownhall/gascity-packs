Show the current Discord configuration, published URLs, workflow mappings,
chat bindings, and recent activity.

Examples:
  gc discord status
  gc discord status --json

The snapshot includes the public interactions URL, the tenant admin URL,
redacted default and named app configuration, per-app token presence and
gateway health, workflow mappings, chat bindings, recent `/gc fix` requests,
and recent explicit chat publishes. Token values are never shown.
