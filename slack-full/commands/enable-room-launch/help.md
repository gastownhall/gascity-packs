Enable Slack-launcher mode on a Slack channel.

Persists a (workspace_id, channel_id) → pool_template record at
<cityPath>/.gc/slack/room_launch_mappings.json. The slack-pack adapter
reads this file at startup and uses it to handle '@@<handle>' posts:
such a post in an enabled channel spawns a new gc session under the
configured pool template, registers <handle> as the session's alias,
and binds the Slack thread to the new session so subsequent
'@<handle>' posts in the same thread route to it.

Examples:
  gc slack enable-room-launch C0123 --workspace-id T1 \\
    --launcher mission-control/launcher

The binding is idempotent: re-binding the same channel preserves the
original CreatedAt and replaces pool_template.

The pool_template is operator-supplied and intentionally opaque to
gc. Gas City has ZERO hardcoded role names; the slack-pack adapter
passes this string verbatim to gc's session-create endpoint as the
'name' field, so it must match an agent template the city actually
configures.

Routes to: gc-slack-cli enable-room-launch
