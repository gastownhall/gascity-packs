Show the current Mattermost configuration, published URLs, workflow mappings,
chat bindings, and recent activity.

Examples:
  gc mattermost status
  gc mattermost status --json

The snapshot includes the public callback URL registered with Mattermost slash
commands, the tenant admin URL, redacted server configuration (server URL, bot
account, redacted bot and verification tokens), workflow mappings, chat
bindings, recent `/gc fix` requests, and recent explicit chat publishes.
