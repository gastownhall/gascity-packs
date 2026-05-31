Register a handle → session alias for address-by-handle routing.

When an inbound Slack message leads with "@<handle>" (optionally followed by
a colon) and the handle matches a registered alias, the adapter delivers
that message to the aliased session — regardless of channel binding, from
any channel. This lets humans address a session by name from anywhere
(e.g. "@mayor: status?"). The aliased session receives the message with the
"@handle" token stripped.

Typical use: at startup register the well-known sessions —
  gc slack-channel handle-alias --handle mayor --session <mayor session id>
  gc slack-channel handle-alias --handle cos   --session <chief-of-staff id>

Single-workspace at Tier 2 — aliases are not scoped per workspace. The
adapter persists them to <city>/.gc/slack-channel/handle_aliases.json.

Usage:
  gc slack-channel handle-alias --handle <handle> --session <id>
  gc slack-channel handle-alias --handle <handle> --remove

Flags:
  --handle    Handle to alias (e.g. "mayor"); a leading "@" is stripped and
              the handle is lowercased. Must match [a-z0-9_-]+.
  --session   Session id the handle routes to.
  --remove    Remove the alias. Idempotent.

Examples:
  gc slack-channel handle-alias --handle mayor --session sess-mayor
  gc slack-channel handle-alias --handle mayor --remove

On success, prints the adapter's JSON receipt.

Requires: GC_CITY_NAME + GC_API_BASE_URL, plus `jq` and `curl` on PATH. The
slack-channel service must be running.
