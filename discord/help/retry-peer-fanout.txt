Retry failed peer fanout deliveries for a saved room publish without reposting
the Discord message.

Examples:
  gc discord retry-peer-fanout discord-publish-123
  gc discord retry-peer-fanout --include-unknown discord-publish-123
  gc discord retry-peer-fanout --target corp--priya --target corp--eve discord-publish-123

This command only re-drives saved peer targets from the publish record. It does
not repost to Discord and it reuses the same deterministic idempotency keys.
It is an operator repair path and intentionally does not re-apply peer-fanout
budget limits.

Use `--include-unknown` only after checking the target session transcript. A
`delivery_unknown` target may already have received the peer envelope.
