Enable launcher mode for a Mattermost root channel.

Usage:
  gc mattermost enable-room-launch --team-id 7k3m9x2c5n8b1v4z6q0r2s4t6w 9h5j7k1m3n5p7r9t1v3x5z7b9c
  gc mattermost enable-room-launch --team-id 7k3m9x2c5n8b1v4z6q0r2s4t6w --response-mode respond_all --default-handle corp/sky 9h5j7k1m3n5p7r9t1v3x5z7b9c

Launcher-mode channels are different from direct `bind-room` channels:

- `@@handle` in the root channel launches a thread-scoped session for that agent
- the first agent reply creates the visible thread by replying to the launching
  post; Mattermost threads live inside the same channel and are keyed by the
  root post id, so there is no separate thread channel to bind or join
- follow-up posts in that managed thread continue to the same session
- `@@handle` inside the managed thread retargets the conversation to another agent
- replying to an agent-authored post inside the managed thread implicitly targets that agent
- unmentioned follow-ups inside the managed thread continue to the last agent the human addressed there
- human-visible replies inside the managed thread are also forwarded to the other participating thread agents as peer input
- include `@@rig/alias` in an agent reply if it should only fan out to a specific peer; untargeted replies to peer publications do not fan out
- direct `bind-room` and launcher mode are mutually exclusive for one channel

Launcher mode reads unmentioned channel messages. The bot account must be a
member of the root channel so the WebSocket gateway receives `posted` events
for it, otherwise `@@handle` traffic will not route.

`mention_only` is the safe default. `respond_all` requires `--default-handle`
and routes root-level unmentioned posts to that one handle, except root-level
replies, which still require an explicit `@@handle`.

Launcher rooms default to peer fanout enabled for managed threads. Use
`--disable-peer-fanout` to turn that off, or
`--disallow-untargeted-peer-fanout` to require explicit `@@rig/alias` peer
targeting inside the thread.
