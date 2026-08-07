Publish a human-visible Mattermost message through a saved chat binding.

For agent replies to the current Mattermost turn, prefer:
  gc mattermost reply-current --body-file ./reply.txt

Examples:
  gc mattermost publish --binding room:9h5j7k1m3n5p7r9t1v3x5z7b9c --body "hello humans"
  gc mattermost publish --binding room:9h5j7k1m3n5p7r9t1v3x5z7b9c --trigger 5s7t9u1v3w5x7y9z1a3b5c7d9e --body-file ./reply.txt
  gc mattermost publish --binding room:9h5j7k1m3n5p7r9t1v3x5z7b9c --conversation-id 4f6g8h0j2k4m6n8p0q2r4s6t8u --trigger 5s7t9u1v3w5x7y9z1a3b5c7d9e --body "Reply in another channel"
  gc mattermost publish --binding launch-room:9h5j7k1m3n5p7r9t1v3x5z7b9c --source-event-kind mattermost_human_message --source-ingress-receipt-id in-5s7t9u1v3w5x7y9z1a3b5c7d9e --body-file ./reply.txt
  gc mattermost publish --binding room:9h5j7k1m3n5p7r9t1v3x5z7b9c --source-event-kind mattermost_human_message --source-ingress-receipt-id in-5s7t9u1v3w5x7y9z1a3b5c7d9e --source-session corp--sky --body-file ./reply.txt

`--conversation-id` overrides the destination channel for this send. Use it
when the saved binding points at a different channel than the one the inbound
message arrived from.

`--root-id` overrides the thread root post id for this send. `--reply-to`
overrides the post id used as the reply target. If neither is given, `--trigger`
is used as the reply target when present, and the resulting post joins that
post's thread.

Direct `publish` is primarily for operator-controlled sends or cross-binding
publishes. Peer fanout only participates when you also supply source metadata
such as `--source-event-kind` plus `--source-ingress-receipt-id` or
`--root-ingress-receipt-id`. For agent replies to the latest Mattermost turn,
prefer `gc mattermost reply-current --body-file ...`.

Launcher-backed replies normally should use `reply-current`, not direct
`publish`. When source context includes a room-launch id, the bridge will start
the managed thread on first publish by replying to the launching post, and then
post subsequent messages under that same root post id.

For multi-line or generated content, prefer `--body-file` over inline `--body`.
Do not pipe publish output through filters that can hide failures. Treat a
publish as successful only when the returned JSON contains `record.remote_message_id`.

If the command exits with status `2`, the Mattermost post succeeded but peer
fanout for other bound sessions was partial or needs operator attention.
Inspect `record.peer_delivery` and use `gc mattermost retry-peer-fanout` if
needed.
