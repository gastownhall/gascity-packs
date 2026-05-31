Add an emoji reaction to a Slack message.

Default mode reacts on the latest inbound message delivered to this session
— the "got it, working on a reply" receipt. Explicit mode names the channel
and message ts directly.

Usage:
  gc slack-channel react [--session <id>] [--emoji <name>]
  gc slack-channel react --conversation-id <id> --message-id <ts> [--emoji <name>]

Flags:
  --session          Override the session id (default: $GC_SESSION_ID).
  --emoji            Emoji name without colons (default: eyes). ":eyes:"
                     and "eyes" both work.
  --conversation-id  Slack channel id (explicit mode; requires --message-id).
  --message-id       Slack message ts (explicit mode; requires
                     --conversation-id).

Examples:
  gc slack-channel react
  gc slack-channel react --emoji white_check_mark
  gc slack-channel react --conversation-id C0123 --message-id 1700000000.0001 --emoji tada

already_reacted is treated as success. On success, prints the adapter's
JSON receipt.

Requires: GC_CITY_NAME + GC_API_BASE_URL, plus `jq` and `curl` on PATH, and
the `reactions:write` scope on the Slack app. The slack-channel service must
be running.
