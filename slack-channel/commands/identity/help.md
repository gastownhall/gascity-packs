Register a per-session Slack identity override.

Each gc session can post under a distinct username + avatar (Slack's
`chat:write.customize`). Call this once at session start; every subsequent
`publish` / `publish-to-channel` / `reply-current` from that session posts
under the chosen identity. The adapter persists the override to
<city>/.gc/slack-channel/identities.json.

The Slack app must have `chat:write.customize` granted (and be reinstalled)
for the override to take effect — without it, Slack ignores the
username/icon and the post falls through under the default bot identity.

Usage:
  gc slack-channel identity [--session <id>] --as <name>
                            [--avatar-url <url> | --avatar-emoji <name>]
  gc slack-channel identity [--session <id>] --remove

Flags:
  --session       Session to set identity for (default: $GC_SESSION_ID).
  --as            Display name to post under (e.g. "Gas City PL").
  --avatar-url    Avatar image URL. Mutually exclusive with --avatar-emoji.
  --avatar-emoji  Avatar emoji name without colons (e.g. "robot_face").
                  Mutually exclusive with --avatar-url.
  --remove        Remove the session's identity override. Idempotent.

At least one of --as / --avatar-url / --avatar-emoji is required unless
--remove is given.

Examples:
  gc slack-channel identity --as "Gas City PL" --avatar-emoji robot_face
  gc slack-channel identity --session sess-pl --as "Reviewer"
  gc slack-channel identity --remove

On success, prints the adapter's JSON receipt.

Requires: GC_CITY_NAME + GC_API_BASE_URL, plus `jq` and `curl` on PATH. The
slack-channel service must be running.
