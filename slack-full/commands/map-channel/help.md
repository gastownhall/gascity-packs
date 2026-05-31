Bind a Slack channel to a gc session for slash-command routing.

Persists a (workspace_id, channel_id) → session record at
<cityPath>/.gc/slack/channel_mappings.json. The slack-pack adapter
reads this file at startup and routes incoming /slack/interactions
slash-command requests for the channel to the bound session.

Examples:
  gc slack map-channel C0123 --workspace-id T0123 --session gc-83347
  gc slack map-channel C0123 --workspace-id T0123 --remove

The binding is idempotent: re-binding the same channel preserves the
original CreatedAt and overwrites the target fields. --remove always
exits 0 (no-op when no binding exists).

For rig→channel bindings, use 'gc slack map-rig' instead.

Routes to: gc-slack-cli map-channel
