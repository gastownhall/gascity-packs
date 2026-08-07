Bind a Mattermost DM channel to exactly one named session.

Examples:
  gc mattermost bind-dm 9h5j7k1m3n5p7r9t1v3x5z7b9c sky

This stores the binding under `.gc/services/mattermost/data/config.json`.
Use exact permanent session names.

The DM channel id is the Mattermost channel id of the direct-message channel
between the bot account and the human, not the human's user id. The bot
account must already be a member of that DM channel.
