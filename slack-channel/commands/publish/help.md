Publish a message into the Slack channel a session is bound to.

`publish` resolves the channel from the session's binding — use it for
unprompted posts (status pings, cron-driven updates) that don't depend on a
prior inbound message. If the session has a registered identity override,
the message posts under that username/avatar.

The session must be bound to exactly one channel. If it is bound to none,
run `bind-dm`/`bind-room` first; if it is bound to several, use
`publish-to-channel --channel` to disambiguate.

Use `reply-current` instead when you want to thread under a message that
just arrived.

Usage:
  gc slack-channel publish [--session <id>] (--body <text> | --body-file <path>)
                           [--reply-to <ts>]

Flags:
  --session    Session whose binding to publish into. Defaults to the
               current session ($GC_SESSION_ID).
  --body       Message text. Mutually exclusive with --body-file.
  --body-file  Read the message body from a file.
  --reply-to   Slack message ts to thread under (optional).

Examples:
  gc slack-channel publish --body "build is green"
  gc slack-channel publish --session sess-pl --body-file /tmp/status.md

On success, prints the adapter's JSON receipt {"ok":true,"ts":...}.

Requires: GC_CITY_NAME + GC_API_BASE_URL, plus `jq` and `curl` on PATH. The
slack-channel service must be running.
