Import Discord app metadata and the bot token into the shared intake state.

Example:
  bao kv get -field=bot_token internal/kv/example/agents/default/discord |
    gc discord import-app \
      --application-id 123456789012345678 \
      --public-key 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
      --bot-token-file /dev/stdin

Import an additional chat bot without replacing the default app:
  bao kv get -field=bot_token internal/kv/example/agents/ollie/discord |
    gc discord import-app \
      --app ollie \
      --application-id 223456789012345678 \
      --public-key abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789 \
      --bot-token-file /dev/stdin

Optional fields:
  --app <name>                 named chat app; omit for the default app
  --command-name <name>         slash command root, default: gc
  --bot-token-file <path>       read the bot token from a file
  --guild-allowlist <id>        allow only specific guild ids; repeatable
  --channel-allowlist <id>      allow only specific parent channel ids; repeatable
  --role-allowlist <id>         allow only specific Discord role ids; repeatable

The public key is the Discord app's interaction verification key. The bot
token is stored under the pack state root so the service can sync commands and
post workflow status updates.

Named apps have isolated metadata, policy, token files, gateway connections,
and chat bindings. Slash commands and workflow mappings continue to use the
default app. A supplied named token is verified online against its application
ID before local config or secrets are changed. Omitted allowlist flags preserve
existing policy. A named application ID is immutable; import a replacement
under a new app name. Run `gc service restart discord-gateway` after adding,
removing, or rotating named apps and credentials so the gateway starts the new
connection.
An explicitly supplied empty token file fails before config mutation.

If you want launcher rooms or ambient-read room bindings, also enable
`Message Content Intent` for the app in the Discord Developer Portal.
