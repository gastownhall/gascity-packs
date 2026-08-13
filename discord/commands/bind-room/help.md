Bind a Discord channel or thread to one or more named sessions.

Examples:
  gc discord bind-room 123456789012345678 sky lawrence
  gc discord bind-room --guild-id 223456789012345678 123456789012345678 sky lawrence
  gc discord bind-room --guild-id 223456789012345678 --enable-ambient-read 123456789012345678 sky lawrence
  gc discord bind-room --guild-id 223456789012345678 --enable-ambient-read --allow-untargeted-ambient-delivery 123456789012345678 randy
  gc discord bind-room --guild-id 223456789012345678 --enable-broadcast-mentions 123456789012345678 sky lawrence
  gc discord bind-room --guild-id 223456789012345678 --enable-peer-fanout 123456789012345678 corp--sky corp--priya
  gc discord bind-room --guild-id 223456789012345678 --enable-peer-fanout --allow-untargeted-peer-fanout 123456789012345678 corp--sky corp--priya

This stores the binding under `.gc/services/discord/data/config.json`.
Use exact permanent session names.
Direct `bind-room` routing is mutually exclusive with `gc discord enable-room-launch`
for the same room.

Ambient read is disabled by default. When enabled, messages in this bound room
or bound thread no longer need to mention the bot, but they still must
explicitly target one or more `@session_name` values to route. Parent-room
thread inheritance still requires a bot mention unless the thread itself is
also bound. Ambient-read bindings remain targeted-only even when the bot is
mentioned directly, unless `--allow-untargeted-ambient-delivery` is enabled on
an ambient-read room with exactly one bound session. In that sticky single-agent
mode, every visible message routes to the one bound session, including messages
that contain a non-exact shorthand mention.

Ambient read consumes unmentioned guild messages. Discord therefore requires
the app's `Message Content Intent` to be enabled in the Developer Portal
before ambient-read routing will work reliably.

Broadcast mentions are disabled by default. Discord does not list `@everyone`,
`@here`, or `@role` mentions in a message's `mentions[]`, and they are
deliberately excluded from default routing, so a bound room ignores them. When
`--enable-broadcast-mentions` is set, an `@everyone`/`@here` ping wakes the
bound session(s), and an `@role` ping wakes them when the bot actually holds the
mentioned role (its auto-created managed role, or a shared role assigned to it).
This is opt-in per binding because `@everyone` is usually meant for humans and
is noisy in busy servers. `@everyone` still only fires when the author has
permission to mention everyone.

Peer fanout is disabled by default. When enabled, the bridge can reinject one
session's room publish to other bound sessions as `discord_peer_publication`
events without re-reading bot messages from Discord.

Peer-fanout-enabled room bindings require lowercase canonical session names.
Useful flags:

- `--enable-ambient-read` / `--disable-ambient-read`
- `--allow-untargeted-ambient-delivery` / `--disallow-untargeted-ambient-delivery`
- `--enable-broadcast-mentions` / `--disable-broadcast-mentions`
- `--enable-peer-fanout` / `--disable-peer-fanout`
- `--allow-untargeted-peer-fanout` / `--disallow-untargeted-peer-fanout`
- `--max-peer-triggered-publishes-per-root N`
- `--max-total-peer-deliveries-per-root N`
- `--max-peer-triggered-publishes-per-session-per-minute N`
