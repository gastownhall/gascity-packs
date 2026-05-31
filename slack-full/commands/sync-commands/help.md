Reconcile the locally-imported Slack app's slash commands with what's
live in Slack.

Reads the imported app record from <cityPath>/.gc/slack/apps.json
(built by 'gc slack import-app'), calls Slack apps.manifest.export to
read the live manifest, diffs the two slash-command sets, and (unless
--dry-run) calls apps.manifest.update to push the local manifest.
After update, apps.manifest.export is called once more to verify
convergence.

Examples:
  gc slack sync-commands --workspace-id T0123 --app-id A0123
  gc slack sync-commands --workspace-id T0123 --app-id A0123 --dry-run
  gc slack sync-commands --workspace-id T0123 --app-id A0123 --output json

The verb refuses to push when manifest fields OUTSIDE
features.slash_commands have drifted from local — pass
--allow-non-command-drift to opt into a full-manifest replace.

The Slack configuration access token (xoxe.xoxp-...) is read from the
SLACK_CONFIG_ACCESS_TOKEN environment variable, or from --token.

Routes to: gc-slack-cli sync-commands
