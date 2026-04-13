Enable launcher mode for a Discord root room.

Usage:
  gc discord enable-room-launch --guild-id 223456789012345678 323456789012345678
  gc discord enable-room-launch --guild-id 223456789012345678 --response-mode respond_all --default-handle corp/sky 323456789012345678

Launcher-mode rooms are different from direct `bind-room` rooms:

- `@@handle` in the root room launches a thread-scoped session for that agent
- the first agent reply creates the visible Discord thread
- follow-up messages in that managed thread continue to the same session
- `@@handle` inside the managed thread retargets the conversation to another agent
- replying to an agent-authored Discord message inside the managed thread implicitly targets that agent
- unmentioned follow-ups inside the managed thread continue to the last agent the human addressed there
- human-visible replies inside the managed thread are also forwarded to the other participating thread agents as peer input
- include `@@rig/alias` in an agent reply if it should only fan out to a specific peer; untargeted replies to peer publications do not fan out
- direct `bind-room` and launcher mode are mutually exclusive for one room

Launcher mode reads unmentioned guild messages. Discord therefore requires the
app's `Message Content Intent` to be enabled in the Developer Portal before
launcher rooms can route `@@handle` traffic reliably.

`mention_only` is the safe default. `respond_all` requires `--default-handle`
and routes top-level unmentioned messages to that one handle, except top-level
replies, which still require an explicit `@@handle`.

Launcher rooms default to peer fanout enabled for managed threads. Use
`--disable-peer-fanout` to turn that off, or
`--disallow-untargeted-peer-fanout` to require explicit `@@rig/alias` peer
targeting inside the thread.
