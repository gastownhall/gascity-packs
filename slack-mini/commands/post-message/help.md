Post plain text to a Slack channel using the workspace bot token.

This is the only outbound verb at Tier 1 (slack-mini). It relays to the
running slack-mini adapter through gc's /svc/slack-mini reverse proxy; the
adapter calls Slack chat.postMessage. Use it to reply to an inbound mention
in its thread, or to push a notification to a channel.

Flags:
  --channel    Slack channel id (e.g. C0123ABCD) — required.
  --text       Message text — required.
  --thread-ts  Reply inside an existing thread. Pass the inbound message's
               ts (surfaced to your session as the conversation's
               reply-to id) to answer in-thread.

Examples:
  gc slack-mini post-message --channel C0123 --text "build is green"

  gc slack-mini post-message --channel C0123 \
    --thread-ts 1700000000.0001 --text "done — see PR #42"

On success, prints Slack's JSON response: {"ok":true,"ts":...,"channel":...}.
The returned ts is the new message's timestamp.

Requires: GC_CITY_NAME and GC_API_BASE_URL in the environment (gc sets
these for command wrappers), plus `jq` and `curl` on PATH. The slack-mini
service must be running (gc supervises it as a proxy_process).
