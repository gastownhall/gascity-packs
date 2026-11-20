# teams-mini

**Talk to your Gas City mayor from Microsoft Teams.** Register a bot, add it
to a team or chat, `@`-mention it, and the mention bridges to your gc mayor
session. Reply back with one verb.

teams-mini is the Teams counterpart of [slack-mini](../slack-mini): the
smallest surface that gets a human talking to gc over Teams. It ships a small
two-file adapter and one outbound verb. No conversation bindings, no
per-session identity, no multi-rig routing.

## What you get

- **Inbound:** `@gc mayor what's the convoy status?` in a channel, group chat
  or personal chat with the bot → delivered to your gc mayor session.
- **Outbound:** `gc teams-mini post-message --conversation <id> --text "…"` →
  posts into that conversation, optionally as a reply to a specific message.

## How it reaches you

Teams bots talk through the **Azure Bot Service** (the Bot Framework). Teams
POSTs each message to a public HTTPS URL you register on the bot, with a
signed token proving it came from Microsoft; the adapter verifies the token
against Microsoft's published keys and bridges the message into gc. Replies
go back through the Bot Framework REST API with a token the adapter obtains
using the bot's app id and secret.

There is no ingress-free transport like Slack's Socket Mode. You need a public
HTTPS endpoint; [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) or
any reverse proxy that terminates TLS will do.

## Install

### 1. Register the bot (Azure, ~5 min)

1. In the [Azure portal](https://portal.azure.com) create an **Azure Bot**
   resource. Pick **Multi Tenant** (default) or **Single Tenant** for *Type of
   App*, and let it create a new Microsoft App ID.
2. On the bot's **Configuration** blade note the **Microsoft App ID**. Click
   **Manage Password** (it opens the app registration behind the bot) and
   create a client secret; copy its **value** now, it is shown once.
3. Still under **Configuration**, set **Messaging endpoint** to
   `https://<your-public-host>/api/messages` (see step 3 for the host).
4. Under **Channels**, add **Microsoft Teams** and accept the terms.
5. Note your **Entra tenant id** (Entra admin center → Overview).

The Azure Bot resource itself is free; it only routes messages.

### 2. Configure the city (1 min)

Import the pack:

```sh
gc import add https://github.com/gastownhall/gascity-packs.git//teams-mini
```

That writes the import and pins the release in `packs.lock`. The same import
by hand in `pack.toml`, followed by `gc import install`:

```toml
[imports.teams-mini]
source = "https://github.com/gastownhall/gascity-packs.git//teams-mini"
```

To work on the pack from a local checkout, point `source` at the path:

```toml
[imports.teams-mini]
source = "../gascity-packs/teams-mini"
```

Provide the adapter's environment (e.g. in your city service env or
`~/.config/gc-teams-mini-adapter/env`):

```sh
TEAMS_APP_ID=11111111-2222-3333-4444-555555555555   # Microsoft App ID
TEAMS_APP_PASSWORD=...                              # the client secret value
TEAMS_TENANT_ID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee # your Entra tenant
GC_CITY_NAME=<your-city-name>                       # the gc city to bridge into
```

That is the full required set, four variables. If you chose **Single Tenant**
in step 1, also set `TEAMS_APP_TYPE=single-tenant`; the bot must then live in
the same tenant as `TEAMS_TENANT_ID`.

### 3. Expose the endpoint and start (2 min)

The adapter listens for Bot Framework traffic on public TCP
(`LISTEN_PUBLIC`, default `0.0.0.0:8777`). Terminate TLS in front of it and
give Azure the public URL:

```sh
tailscale funnel 8777
```

Then confirm the bot's **Messaging endpoint** is
`https://<funnel-host>/api/messages`. Start your city; the log line to look
for is `public listener serving on 0.0.0.0:8777`.

### 4. Add the app to Teams (2 min)

Build the Teams app package from [`manifest/`](./manifest) (the README there
has the three commands), upload it in Teams via **Apps → Manage your apps →
Upload a custom app**, and add it to a team, a group chat, or yourself.

Mention the bot. The adapter logs `inbound: conv=… kind=room …` and your
mayor session receives the message.

## Outbound

```sh
gc teams-mini post-message --conversation "19:abc@thread.tacv2" --text "build is green"
gc teams-mini post-message --conversation "19:abc@thread.tacv2;messageid=1699" \
  --reply-to 1700000000001 --text "done — see PR #42"
```

The conversation id and the reply-to id are the ones surfaced to your session
with the inbound message. The Bot Framework requires replies to go back
through the regional service that delivered the message; the adapter
remembers that per conversation while it runs. For a conversation it has not
seen since start, pass `--service-url` or set `TEAMS_SERVICE_URL` (for most
European tenants `https://smba.trafficmanager.net/emea/`, for the Americas
`https://smba.trafficmanager.net/amer/`; the exact value is in any inbound
activity's `serviceUrl`).

## Things that will not work, so you don't lose an hour on them

- **The Bot Framework Emulator.** It signs requests with a different issuer,
  so the adapter refuses every one of them. Test from Teams itself.
- **Posting into a conversation the bot is not in.** Microsoft answers 403.
  Add the app to the team or chat first, or mention the bot once so the
  conversation exists.
- **Government and sovereign clouds.** The Microsoft endpoints are the public
  ones and are not configurable.
- **Running behind your own sign-in.** If your Gas City sits behind an SSO
  gateway, `/api/messages` has to be reachable by Microsoft's bot service
  without logging in. The adapter verifies Microsoft's signature itself, so
  exempting that one path is safe.

## What's verified on the inbound path

Every request to `/api/messages` must carry a Bot Framework JWT. The adapter
checks its RS256 signature against the keys Microsoft publishes, the issuer,
the audience (your app id), the validity window, and that the token's
`serviceurl` matches the activity's. Activities from any other tenant are
dropped. Only `message` activities are bridged, and in channels and group
chats only when the bot itself is mentioned. Nothing is bridged on a failed
check.

The one thing the token does not cover is the request body, which is how the
Bot Framework works rather than a choice here. The TLS terminator in front of
port 8777 is therefore part of the trust boundary: it must be real TLS to a
host you control (Funnel is), not a plain-http hop across a network you don't.

## Environment reference

| Variable | Required | Meaning |
| --- | --- | --- |
| `TEAMS_APP_ID` | yes | Microsoft App ID of the Azure Bot |
| `TEAMS_APP_PASSWORD` | yes | Client secret for that app |
| `TEAMS_TENANT_ID` | yes | Entra tenant id; the extmsg account id and inbound tenant filter |
| `GC_CITY_NAME` | yes | gc city to bridge into |
| `TEAMS_APP_TYPE` | no | `multi-tenant` (default) or `single-tenant` |
| `TEAMS_SERVICE_URL` | no | Fallback service URL for conversations not seen since start |
| `TEAMS_MINI_INBOUND_TARGET` | no | Session handle inbound mentions address (default `mayor`) |
| `LISTEN_PUBLIC` | no | Public bind for `/api/messages` (default `0.0.0.0:8777`) |
| `LISTEN_INTERNAL` | no | Internal bind when not run as a gc service (default `127.0.0.1:8778`) |
| `ADAPTER_PROVIDER` | no | extmsg provider name (default `teams`) |
| `REGISTER_ON_START` | no | Self-register with gc on start (default `true`) |

## Development

```sh
cd adapter && go test ./...
```

The adapter has no dependencies outside the Go standard library. Tests cover
token verification (including key rollover and tampering), activity
filtering, the bridge into gc, and the outbound post against a fake Bot
Framework. They do not exercise a live Teams tenant.
