Register or replace the team-scoped `/gc` slash command for one or more
Mattermost teams.

Examples:
  gc mattermost sync-commands 7k3m9x2c5n8b1v4z6q0r2s4t6w
  gc mattermost sync-commands 7k3m9x2c5n8b1v4z6q0r2s4t6w 3d5f7g9h1j3k5m7n9p1q3r5s7t

Arguments:
  <team_id>...   one or more Mattermost team ids

Registration uses the Mattermost integrations API (`/api/v4/commands`) with the
bot token, so that account needs the `manage_slash_commands` permission on each
team. Existing `/gc` commands owned by the pack are updated in place; the
verification token recorded by `gc mattermost import-app` is reused so inbound
callbacks keep validating.

The command payload is intentionally small in this slice:

- `/gc fix <summary>` opens an interactive dialog for summary and additional
  context using the `trigger_id` from the slash-command callback
- the raw trailing text is also accepted as a fallback `prompt` for clients
  that cannot render the dialog
- role, team, and channel policy is enforced by the workspace service after
  Mattermost delivers the slash command
