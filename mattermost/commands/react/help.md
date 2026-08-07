# gc mattermost react

Add an emoji reaction to a Mattermost post — typically the latest
inbound post routed to the current session, used as a "got it,
working on a reply" receipt for human posters.

## Usage

```
gc mattermost react [--emoji NAME] [--session SID]
gc mattermost react --conversation-id 9h5j7k1m3n5p7r9t1v3x5z7b9c --message-id 5s7t9u1v3w5x7y9z1a3b5c7d9e [--emoji NAME]
```

## Default mode

With no arguments, the command:

1. Resolves the current session id from `GC_SESSION_ID`.
2. Queries `gc /v0/city/<city>/extmsg/transcript` for the latest
   inbound post routed to that session.
3. POSTs to the local Mattermost adapter `/react` with the post's
   channel id + post id and the chosen emoji.
4. The adapter calls Mattermost `POST /api/v4/reactions` with
   `{user_id, post_id, emoji_name}`.

## Explicit mode

If you already know the channel id and post id, pass them directly.
Both flags must be set together.

## Flags

- `--emoji NAME` — Mattermost `emoji_name`. Plain name, no colons:
  `thumbsup`, not `:thumbsup:`. Surrounding colons are stripped if
  you pass them. Default: `eyes`.
- `--session SID` — override the session id (otherwise auto-resolved).
- `--conversation-id <channel_id>` — explicit channel id (requires `--message-id`).
- `--message-id <post_id>` — explicit post id (requires `--conversation-id`).
- `--current` — explicit "use the latest inbound" mode (the default).

Reacting to a post inside a thread needs only that post's id. The
thread root post id is irrelevant to reactions.

## Failure modes

- No recent inbound for this session → exit 1, message tells you to
  pass explicit flags.
- Mattermost returns HTTP 404 for an unknown post or a channel the bot
  cannot see → receipt `delivered=false`, `failure_kind=not_found`.
- The bot account is not a member of the channel → HTTP 403, receipt
  `delivered=false`, `failure_kind=auth`.
- Re-adding a reaction the bot already added is a no-op on the
  Mattermost side and is treated as success.

## Examples

```bash
# After a system-reminder in a rig channel:
gc mattermost react --emoji eyes

# Acknowledge with a different emoji:
gc mattermost react --emoji thinking_face

# React to a specific post (e.g. from a debug script):
gc mattermost react --conversation-id 9h5j7k1m3n5p7r9t1v3x5z7b9c \
                    --message-id 5s7t9u1v3w5x7y9z1a3b5c7d9e \
                    --emoji white_check_mark
```
