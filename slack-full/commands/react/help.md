# gc slack react

Add an emoji reaction to a Slack message — typically the latest
inbound message routed to the current session, used as a "got it,
working on a reply" receipt for human posters.

## Usage

```
gc slack react [--emoji NAME] [--session SID]
gc slack react --conversation-id Cxxx --message-id 1234.5678 [--emoji NAME]
```

## Default mode

With no arguments, the command:

1. Resolves the current session id from `GC_SESSION_ID`.
2. Queries `gc /v0/city/<city>/extmsg/transcript` for the latest
   inbound message routed to that session.
3. POSTs to the local Slack adapter `/react` with the message's
   conversation id + ts and the chosen emoji.
4. The adapter calls Slack `reactions.add`.

## Explicit mode

If you already know the channel id and message ts, pass them
directly. Both flags must be set together.

## Flags

- `--emoji NAME` — emoji name, with or without colons. Default: `eyes`.
- `--session SID` — override the session id (otherwise auto-resolved).
- `--conversation-id Cxxx` — explicit channel id (requires `--message-id`).
- `--message-id 1234.5678` — explicit message ts (requires `--conversation-id`).
- `--current` — explicit "use the latest inbound" mode (the default).

## Failure modes

- No recent inbound for this session → exit 1, message tells you to
  pass explicit flags.
- Slack `channel_not_found`/`message_not_found` → receipt
  `delivered=false`, `failure_kind=not_found`.
- Slack `already_reacted` → benign, treated as success.

## Examples

```bash
# After a system-reminder in a rig channel:
gc slack react --emoji eyes

# Acknowledge with a different emoji:
gc slack react --emoji thinking_face

# React to a specific message (e.g. from a debug script):
gc slack react --conversation-id C0B1A0CKEH0 \
               --message-id 1733184537.123456 \
               --emoji white_check_mark
```
