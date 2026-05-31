Publish a message into a Slack channel by id, bypassing the binding lookup.

Unlike `publish`, the channel is named explicitly, so a session can post
into a channel it has no binding for — useful for a session bound to
several channels, or for one-off posts. The session id (defaulting to the
current session) still selects the identity override applied to the post.

Usage:
  gc slack-channel publish-to-channel --channel <id>
                                      (--body <text> | --body-file <path>)
                                      [--session <id>] [--thread-ts <ts>]

Flags:
  --channel    Slack channel id (C..., G..., or D...) — required.
  --body       Message text. Mutually exclusive with --body-file.
  --body-file  Read the message body from a file.
  --session    Session to attribute the post to (identity override).
               Defaults to the current session ($GC_SESSION_ID).
  --thread-ts  Slack message ts to thread under (optional).

Examples:
  gc slack-channel publish-to-channel --channel C0123 --body "deploy started"
  gc slack-channel publish-to-channel --channel C0123 \
    --thread-ts 1700000000.0001 --body "done"

On success, prints the adapter's JSON receipt {"ok":true,"ts":...}.

Requires: GC_CITY_NAME + GC_API_BASE_URL, plus `jq` and `curl` on PATH. The
slack-channel service must be running.
