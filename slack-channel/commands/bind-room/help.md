Bind a Slack room/channel to one or more gc sessions.

Once bound, any human message in that channel is delivered to every listed
session — this is the Tier 2 "team channel ↔ session graph": several gc
sessions can listen to one channel at once. Re-binding the same channel
replaces the session list. Pass each session's own id (the value of
`$GC_SESSION_ID` in that session) so `reply-current` and `react` resolve
correctly.

Single-rig only at Tier 2 — binding a channel to a whole rig (and
channel-name patterns) is Tier 3 (slack-full).

Usage:
  gc slack-channel bind-room <channel_id> <session_id> [session_id...]

Arguments:
  channel_id   Slack channel id (e.g. C0123ABCD or G0123ABCD).
  session_id   One or more gc session ids to deliver inbound messages to.

Examples:
  gc slack-channel bind-room C0123ABCD sess-pl
  gc slack-channel bind-room C0123ABCD sess-pl sess-cos sess-reviewer

On success, prints the stored binding as JSON. The binding is persisted to
<city>/.gc/slack-channel/channel_mappings.json.

Requires: GC_CITY_NAME + GC_API_BASE_URL in the environment, plus `jq` and
`curl` on PATH. The slack-channel service must be running.
