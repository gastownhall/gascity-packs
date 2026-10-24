# Outbound delivery evidence

For text publishes, Slack's successful `chat.postMessage` response with a
message timestamp means the message was accepted: `delivered=true`, with no
`failure_kind`. A subsequent readback cannot turn that accepted write into a
failed publish. This prevents callers from duplicating posts after a read
failure. Actual write rejections and responses without a timestamp still fail.

The adapter separately checks the exact timestamp and the reference marker
(or canonicalized text for unmarked posts) via
`conversations.history`, or `conversations.replies` for a threaded reply. The
thread query selects `oldest=latest=message_id`, `inclusive=true`, and `limit=2`
to leave room for the parent plus the selected reply. Readback retries remain
bounded to three attempts, 200 ms apart, with a four-second request timeout.

Successful confirmation omits `metadata.readback` on the publish response.
Unconfirmed reads retain `delivered=true` and describe the result in metadata:

| `metadata.readback` | Observation |
| --- | --- |
| `readback_unconfirmed` | The selected timestamp was absent, or its text did not match. |
| `readback_unavailable` | The read request, HTTP response, or response decoding failed. |
| `readback_auth` | Slack rejected the read token or its history scope. |

These are read diagnostics, not new members of gc's closed publish-failure
vocabulary. A content mismatch can indicate truncation, a later edit, or an
unrecognized Slack rewrite. `metadata.truncated=true`, when supplied by Slack,
survives alongside the readback result. Inspect the existing message before
deciding to send a correction; do not automatically repost it.

`gc slack publish`, `publish-to-channel`, and `reply-current` print the full
result envelope on this upstream base, including the receipt metadata. They
exit zero when the receipt carries a message timestamp, including legacy
receipts with `delivered=false`. An unconfirmed readback is reported on stderr
with the timestamp, including legacy failures whose metadata was absent.
Unknown responses without acceptance evidence still exit nonzero.

Within the existing two-minute in-memory idempotency window, a retry of an
accepted but unconfirmed post rechecks that timestamp. An empty read or text
mismatch never releases its key for reposting. Metadata is copied at the cache
boundary, and a slower unconfirmed read cannot downgrade confirmed evidence.
Cache expiry, restart behavior, and unkeyed publishes' lack of deduplication
are unchanged.

This upstream version still uses reference markers on keyed messages and a
canonical text comparison for unkeyed messages. Redundant mailto/tel auto-link
labels, URL wrappers, reference display labels and Slack's entity trio are
folded for text comparison; different destinations and code spans remain
literal. Other stored-text differences remain diagnostic readback uncertainty
without undoing timestamp acceptance. The newer fork's emoji/URL comparator,
marker removal, and durable receipt lookup are separate work and are not part
of this upstream patch. File uploads and company-turn reports retain their
own protocols.
