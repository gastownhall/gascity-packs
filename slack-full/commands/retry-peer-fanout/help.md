# gc slack retry-peer-fanout

Operational recovery for peer-fanout: walks recent
`extmsg.peer_fanout_failed` events and re-issues the per-member
notification for each one that has not already been retried
successfully.

## Usage

```bash
gc slack retry-peer-fanout [--since <duration>] [--conversation <id>] [--max <n>] [--cooldown-seconds <s>]
```

## Flags

- `--since <duration>` — Go duration window for failed events (default `1h`).
- `--conversation <id>` — restrict retries to a single Slack `conversation_id`.
- `--max <n>` — cap on retry attempts per run (default `50`).
- `--cooldown-seconds <s>` — sleep between retries to avoid amplifying a
  Slack rate-limit storm (default `0.25`).

## Idempotence

Each retry attempt emits an `extmsg.peer_fanout_retried` event whose
payload includes the `original_seq` of the corresponding
`extmsg.peer_fanout_failed` event. On re-run, candidates whose
`original_seq` already has a successful `peer_fanout_retried` event are
skipped, so re-running with no transient changes is a no-op.

## Output

Prints a JSON summary with `candidates`, `attempts`, `successes`,
`failures`, `skipped`, plus per-attempt details for log triage.
