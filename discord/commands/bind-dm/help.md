Bind a Discord DM channel to exactly one named session.

Examples:
  gc discord bind-dm 123456789012345678 sky
  gc discord bind-dm --app ollie 223456789012345678 teams.lead

This stores the binding under `.gc/services/discord/data/config.json`.
Use exact permanent session names.
Use `--app <name>` when the DM belongs to a named bot.
