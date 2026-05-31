# slack-pack manifest

Canonical Slack app manifest for the slack-pack. `app.json` is the
**source of truth** for the Slack app's display info, OAuth scopes,
event subscriptions, and (eventually) slash commands. Use it to
install the slack-pack into a fresh workspace without clicking through
the Slack web UI scope-by-scope.

Schema reference: <https://api.slack.com/reference/manifests>

## What's declared

- **`display_information`** — bot name, short/long description, brand color.
- **`features.bot_user`** — bot display name + `always_online`.
- **`features.app_home`** — Messages tab enabled (DM intake), Home tab off.
- **`features.slash_commands`** — empty list. Slash commands will be
  populated by [`gc slack sync-commands`](../README.md) (gc-cby.2) once
  that command lands. Until then, the slack-pack does not expose any
  `/gc …` shortcuts in Slack.
- **`oauth_config.scopes.bot`** — the minimal scope set the live
  adapter (`examples/slack-pack/adapter/main.go`) requires today.
  Each `*:history` scope pairs with the matching `message.*` event
  subscription below — Slack rejects an install whose subscriptions
  exceed its scopes, so the two lists must move together.
  - `channels:history` — read public channel messages (pairs with
    `message.channels`)
  - `chat:write` — post messages
  - `chat:write.customize` — per-session display-name + avatar overrides
  - `commands` — placeholder for the slash-command surface; required
    for `sync-commands` to register `/gc …` later
  - `files:read` — download user-uploaded files referenced by inbound
    `message` events
  - `files:write` — upload files via `gc slack upload`
  - `groups:history` — read private channel messages (pairs with
    `message.groups`)
  - `im:history` — read DM history (pairs with `message.im`)
  - `mpim:history` — read multi-party DM messages (pairs with
    `message.mpim`)
  - `reactions:write` — `gc slack react` emoji ack
- **`settings.event_subscriptions.bot_events`** — the events the
  adapter actually dispatches on (see `processSlackEvent` in
  `adapter/main.go`):
  - `app_mention` — @-mentions in any channel
  - `message.channels` — public channel messages
  - `message.groups` — private channel messages
  - `message.im` — DMs
  - `message.mpim` — multi-party DMs

## What's NOT declared (intentionally)

- **`users:read`** — `adapter/main.go` defers `users.info` lookups; no
  display-name resolution today. Add it later when the adapter starts
  resolving names.
- **`file_shared`** event — files arrive embedded in `message` events;
  the adapter doesn't subscribe to `file_shared` separately.
- **Concrete `slash_commands` entries** — see above; gc-cby.2 owns this.
- **Interactivity / Socket Mode / Org Deploy / Token Rotation** —
  disabled. The adapter uses HTTP event POSTs (Tailscale Funnel
  terminates `/slack/events`); see `adapter/SETUP.md`.

## Install paths

### Manual (web UI)

1. Go to <https://api.slack.com/apps> → **Create New App** → **From an
   app manifest**.
2. Pick your workspace.
3. Paste the contents of [`app.json`](./app.json) into the JSON tab.
4. **Create**. Slack provisions the bot user, scopes, and event
   subscriptions in one step.
5. **Install to Workspace** to mint the bot token (`xoxb-…`).
6. Continue with `adapter/SETUP.md` from **Step 2 → Event Subscriptions
   Request URL** onward — you still need to plug in your Tailscale
   Funnel URL and copy the signing secret.

### Importing into gc (`gc slack import-app`)

After running the manual install above to mint the app at Slack, capture
the assigned **app id** (`A0…`, found at api.slack.com → your app →
**Basic Information**) and import the manifest into the gc city:

```bash
gc slack import-app examples/slack-pack/manifest/app.json \
  --workspace-id T0123456 \
  --app-id       A0123456
```

This validates the manifest's bot scopes against the set the slack-pack
adapter and downstream commands require, then persists a typed app
record at `<cityPath>/.gc/slack/apps.json` (composite key
`(workspace_id, app_id)`). Re-importing the same `(workspace_id,
app_id)` updates the record in place — the registry never grows from
idempotent re-imports.

`import-app` does **not** call Slack — provisioning the app at Slack is
still a one-time manual step (or, eventually, gc-cby.9's OAuth install
flow). What this command does is establish the foundation that
[`sync-commands`](../README.md) (gc-cby.2),
[`map-channel` / `map-rig`](../README.md) (gc-cby.3 / .4), and friends
read from.

The on-disk shape is described by
[`schema/apps.schema.json`](../schema/apps.schema.json) — that file is
the contract between the gc CLI (writer) and the slack-pack adapter
(reader).

## Required secrets after install

After installing the manifest, the adapter needs three values exported
to its env (see `adapter/SETUP.md` for the full file template):

| Variable                | Source                                                |
| ----------------------- | ----------------------------------------------------- |
| `SLACK_BOT_TOKEN`       | OAuth & Permissions → Bot User OAuth Token (`xoxb-…`) |
| `SLACK_SIGNING_SECRET`  | Basic Information → App Credentials → Signing Secret  |
| `SLACK_WORKSPACE_ID`    | Basic Information → App Credentials → Team ID (`T0…`) |

These are workspace-specific and stay out of git. The manifest is the
only piece of Slack-app config that's checked in.

## Pairing with `sync-commands` (gc-cby.2)

When `gc slack sync-commands` arrives, it will treat this `app.json` as
the desired state and reconcile Slack's live app definition against it
— adding new slash commands, updating descriptions, and removing
deprecated entries. Edits to slash commands SHOULD land here first;
running `sync-commands` propagates them to Slack.

## Validating local edits

```bash
python3 -c "import json; json.load(open('examples/slack-pack/manifest/app.json'))"
```

The pytest suite in `examples/slack-pack/tests/test_manifest.py`
asserts the file parses + carries the required top-level keys; run it
with `pytest examples/slack-pack/tests/test_manifest.py`.
