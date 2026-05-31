Bind a Slack DM channel to one or more gc sessions.

Once bound, any message a human sends in that DM is delivered to every
listed session (not just `@`-mentions). Re-binding the same DM replaces the
session list. Pass the session's own id (the value of `$GC_SESSION_ID` in
that session) so `reply-current` and `react` can resolve "the message I
just received".

Usage:
  gc slack-channel bind-dm <channel_id> <session_id> [session_id...]

Arguments:
  channel_id   Slack DM id (e.g. D0123ABCD).
  session_id   One or more gc session ids to deliver inbound messages to.

Examples:
  gc slack-channel bind-dm D0123ABCD sess-mayor
  gc slack-channel bind-dm D0123ABCD sess-pl sess-cos

On success, prints the stored binding as JSON. The binding is persisted to
<city>/.gc/slack-channel/channel_mappings.json.

Requires: GC_CITY_NAME + GC_API_BASE_URL in the environment (gc sets these
for command wrappers), plus `jq` and `curl` on PATH. The slack-channel
service must be running.
