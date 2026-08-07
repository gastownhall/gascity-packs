Bind a Mattermost channel or thread to one or more named sessions.

Examples:
  gc mattermost bind-room 9h5j7k1m3n5p7r9t1v3x5z7b9c sky lawrence
  gc mattermost bind-room --team-id 7k3m9x2c5n8b1v4z6q0r2s4t6w 9h5j7k1m3n5p7r9t1v3x5z7b9c sky lawrence
  gc mattermost bind-room --team-id 7k3m9x2c5n8b1v4z6q0r2s4t6w --enable-ambient-read 9h5j7k1m3n5p7r9t1v3x5z7b9c sky lawrence
  gc mattermost bind-room --team-id 7k3m9x2c5n8b1v4z6q0r2s4t6w --enable-ambient-read --allow-untargeted-ambient-delivery 9h5j7k1m3n5p7r9t1v3x5z7b9c randy
  gc mattermost bind-room --team-id 7k3m9x2c5n8b1v4z6q0r2s4t6w --enable-peer-fanout 9h5j7k1m3n5p7r9t1v3x5z7b9c corp--sky corp--priya
  gc mattermost bind-room --team-id 7k3m9x2c5n8b1v4z6q0r2s4t6w --enable-peer-fanout --allow-untargeted-peer-fanout 9h5j7k1m3n5p7r9t1v3x5z7b9c corp--sky corp--priya

This stores the binding under `.gc/services/mattermost/data/config.json`.
Use exact permanent session names.
Direct `bind-room` routing is mutually exclusive with
`gc mattermost enable-room-launch` for the same room.

A Mattermost thread is not a separate channel. To bind a single thread rather
than a whole channel, pass the channel id plus the thread's root post id:

  gc mattermost bind-room --root-id 2a4b6c8d0e2f4g6h8i0j2k4m6n 9h5j7k1m3n5p7r9t1v3x5z7b9c sky

Ambient read is disabled by default. When enabled, messages in this bound
channel or bound thread no longer need to mention the bot, but they still must
explicitly target one or more `@session_name` values to route. Posts in a
thread inherit the parent channel binding but still require a bot mention
unless the thread root itself is also bound. Ambient-read bindings remain
targeted-only even when the bot is mentioned directly, unless
`--allow-untargeted-ambient-delivery` is enabled on an ambient-read room with
exactly one bound session. In that sticky single-agent mode, every visible
message routes to the one bound session, including messages that contain a
non-exact shorthand mention.

Ambient read consumes unmentioned channel messages. Mattermost delivers those
posts over the WebSocket gateway only for channels the bot account has joined,
so add the bot to the channel before enabling ambient read. Private channels
additionally require an explicit invite.

Peer fanout is disabled by default. When enabled, the bridge can reinject one
session's room publish to other bound sessions as `mattermost_peer_publication`
events without re-reading bot posts from Mattermost.

Peer-fanout-enabled room bindings require lowercase canonical session names.
Useful flags:

- `--enable-ambient-read` / `--disable-ambient-read`
- `--allow-untargeted-ambient-delivery` / `--disallow-untargeted-ambient-delivery`
- `--enable-peer-fanout` / `--disable-peer-fanout`
- `--allow-untargeted-peer-fanout` / `--disallow-untargeted-peer-fanout`
- `--max-peer-triggered-publishes-per-root N`
- `--max-total-peer-deliveries-per-root N`
- `--max-peer-triggered-publishes-per-session-per-minute N`
