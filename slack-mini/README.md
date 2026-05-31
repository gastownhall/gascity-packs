# slack-mini

**Talk to your Gas City mayor from Slack.** Add a bot to your workspace,
`@`-mention it from any channel, and the mention bridges to your gc mayor
session. Reply back with one verb.

slack-mini is **Tier 1** of the Slack pack family — the smallest surface
that gets a human talking to gc over Slack. It ships a single-file adapter
and one outbound verb. No channel bindings, no per-session identity, no
multi-rig routing — those live in `slack-channel` (Tier 2) and `slack-full`
(Tier 3). See the [slack-pack tiering design memo](../docs/design/slack-pack-tiering.md)
(landing separately).

> Pick exactly one Slack tier per city. The tiers are alternatives, not
> layers you stack.

## What you get

- **Inbound:** `@gc-mayor what's the convoy status?` in any channel the bot
  is in → delivered to your gc mayor session.
- **Outbound:** `gc slack-mini post-message --channel C0123 --text "…"` →
  posts to a channel, optionally in a thread.

## Install in 3 minutes

### 1. Create the Slack app (1 min)

Create an app from the shipped manifest at
[`manifest/app.json`](./manifest/app.json):

1. <https://api.slack.com/apps> → **Create New App** → **From a manifest**.
2. Pick your workspace, paste `manifest/app.json`, create.
3. **Install to Workspace** and copy the **Bot User OAuth Token**
   (`xoxb-…`).
4. From **Basic Information**, copy the **Signing Secret**.

The manifest requests only three scopes — `app_mentions:read`,
`chat:write`, `chat:write.public` — and subscribes to the `app_mention`
event.

### 2. Configure the city (1 min)

Import the pack in your city's `pack.toml`:

```toml
[imports.slack-mini]
source = "../packs/slack-mini"
```

Provide the adapter's environment (e.g. in your city service env or
`~/.config/gc-slack-mini-adapter/env`):

```sh
SLACK_BOT_TOKEN=xoxb-...          # from step 1
SLACK_SIGNING_SECRET=...          # from step 1
SLACK_WORKSPACE_ID=T0123ABCD      # your Slack team id
GC_CITY_NAME=<your-city-name>     # the gc city to bridge into
```

That's the full required set — four variables.

### 3. Expose the events endpoint and start (1 min)

The adapter listens for Slack events on public TCP (`LISTEN_PUBLIC`,
default `0.0.0.0:8775`). Terminate TLS in front of it and give Slack a
public URL — [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) is
the easy path:

```sh
tailscale funnel 8775
```

Then in the Slack app's **Event Subscriptions**, set the Request URL to
`https://<your-funnel-host>/slack/events`. Slack sends a one-time
`url_verification` challenge, which the adapter answers automatically.

gc supervises the adapter as a `proxy_process` service (named
`slack-mini`); building the binary is a one-time `go build` in `adapter/`
(see [Build](#build)). Start your city and `@`-mention the bot.

## Replying in a thread

When the mayor session handles an inbound mention, the conversation carries
the Slack message `ts` as its reply-to id. Answer in the same thread with:

```sh
gc slack-mini post-message --channel C0123 \
  --thread-ts 1700000000.0001 --text "on it — see PR #42"
```

## Build

The adapter is a single Go file with no external dependencies:

```sh
cd adapter
go build -o gc-slack-mini-adapter ./...
```

The built binary is git-ignored; the `[[service]]` block runs it in place.

## Configuration reference

| Variable | Required | Default | Purpose |
| --- | :---: | --- | --- |
| `SLACK_BOT_TOKEN` | ✓ | — | Bot token for `chat.postMessage` and the inbound POST. |
| `SLACK_SIGNING_SECRET` | ✓ | — | HMAC secret for verifying Slack requests. |
| `SLACK_WORKSPACE_ID` | ✓ | — | Slack team id (the extmsg account id). |
| `GC_CITY_NAME` | ✓ | — | gc city to bridge into. |
| `LISTEN_PUBLIC` | | `0.0.0.0:8775` | Public bind for `/slack/events`. |
| `LISTEN_INTERNAL` | | `127.0.0.1:8776` | TCP bind for `/post-message` when not run as a gc proxy_process (no `GC_SERVICE_SOCKET`). |
| `REGISTER_ON_START` | | `true` | Self-register as an extmsg adapter on start. |
| `SLACK_MINI_INBOUND_TARGET` | | `mayor` | Session handle inbound mentions address. |
| `SLACK_API_BASE` | | `https://slack.com/api` | Slack web API origin (override for relays/tests). |
| `GC_API_BASE_URL` | | `http://127.0.0.1:9443` | gc API base. |

`GC_SERVICE_SOCKET`, `GC_SERVICE_URL_PREFIX`, and `GC_API_BASE_URL` are
injected by gc when the adapter runs as a `proxy_process` service.

## Upgrading to a larger tier

To gain channel bindings, per-session identity, or multi-rig routing, swap
this pack for `slack-channel` or `slack-full`. The bot token, signing
secret, and workspace id carry over unchanged. See the tiering memo's
migration section.
