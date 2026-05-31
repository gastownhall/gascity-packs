# gc slack identity

Register a per-session Slack identity override with the local adapter
so messages from this session post under a distinct username + avatar
instead of the default bot identity. Backed by Slack's
`chat:write.customize` scope on `chat.postMessage`.

Identity is stored once at session start; every subsequent
`gc slack reply-current` / `gc slack publish` from the same session
picks it up automatically — no per-message flags needed.

## Usage

```
# Direct flags
gc slack identity --as "Gascity PL" --avatar-emoji robot_face
gc slack identity --as "cos" --avatar-url https://example.com/cos.png

# From .gc/project-brief.md (decentralized, per-rig persona)
gc slack identity --from-brief .gc/project-brief.md
```

## Flags

- `--as NAME` — display name to post under (e.g. `"Gascity PL"`).
- `--avatar-url URL` — image URL for the avatar.
- `--avatar-emoji NAME` — emoji name without colons (e.g. `robot_face`).
  Mutually exclusive with `--avatar-url`.
- `--from-brief PATH` — read `display_name:` / `avatar_url:` /
  `avatar_emoji:` keys from a markdown brief. Direct flags win
  when both are set.
- `--session SID` — override the session id (otherwise auto-resolved
  from `$GC_SESSION_ID`).

At least one of display name / avatar fields must be supplied — calling
with no identity fields fails closed.

## How it works

1. Resolves the current session id from `$GC_SESSION_ID`.
2. POSTs `{session_id, username, icon_url, icon_emoji}` to the local
   adapter `/identity` endpoint.
3. The adapter stores the override in an in-memory map and persists
   to `${IDENTITY_STORE_PATH:-/tmp/gc-slack-adapter/identities.json}`
   so it survives adapter restarts.
4. Every subsequent `/publish` for this `session_id` injects the
   stored fields into Slack's `chat.postMessage`.

## Required Slack scope

The bot token needs `chat:write.customize`. Without it, Slack
silently ignores `username`/`icon_url`/`icon_emoji` and the post
falls through under the default bot identity. Steps:

1. api.slack.com → your app → **OAuth & Permissions**
2. Bot Token Scopes → add `chat:write.customize`
3. **Reinstall to Workspace**

No code change or restart needed after granting the scope — the
next publish picks it up.

## Examples

```bash
# Per-rig PL: read from project brief at session start
gc slack identity --from-brief .gc/project-brief.md

# cos: explicit identity
gc slack identity --as "cos" --avatar-emoji eyes

# Override one field for an existing session
gc slack identity --session gc-12345 --avatar-emoji thinking_face
```
