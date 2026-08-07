Import Mattermost server metadata and the bot token into the shared intake
state.

Example:
  gc mattermost import-app \
    --server-url https://mattermost.example.com \
    --bot-token "$MATTERMOST_BOT_TOKEN" \
    --verification-token 1a2b3c4d5e6f7g8h9i0j1k2l3m

Optional fields:
  --command-name <name>            slash command root, default: gc
  --bot-token-file <path>          read the bot token from a file
  --verification-token-file <path> read the verification token from a file
  --team-allowlist <id>            allow only specific team ids; repeatable
  --channel-allowlist <id>         allow only specific channel ids; repeatable
  --role-allowlist <role>          allow only specific Mattermost role names,
                                   e.g. `system_admin` or `team_admin`; repeatable

The bot token is a personal access token for a Mattermost bot account, created
under System Console -> Integrations -> Bot Accounts. It is stored under the
pack state root so the service can register slash commands and post workflow
status updates.

The verification token is the token Mattermost issues when a slash command or
interactive integration is created. Inbound slash-command and interactive
callbacks are authenticated by comparing that shared token, so there is no
signature key to import.

If you want launcher rooms or ambient-read room bindings, add the bot account
to each channel you intend to read. Mattermost only streams posts for channels
the bot is a member of.
