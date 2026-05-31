Import a Slack app manifest into the gc city's slack-pack registry.

Reads the JSON manifest, validates that it declares the bot scopes
the slack-pack adapter and downstream commands require, and persists
an app record keyed by (workspace_id, app_id) at
<cityPath>/.gc/slack/apps.json.

Examples:
  gc slack import-app /path/to/manifest.json --workspace-id T0123456 --app-id A0123456

Re-importing the same (workspace_id, app_id) updates the record in
place — the registry never grows from idempotent re-imports.

Routes to: gc-slack-cli import-app
