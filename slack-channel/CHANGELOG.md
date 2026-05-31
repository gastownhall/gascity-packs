# Changelog

All notable changes to slack-channel are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — Tier 2

Initial release. slack-channel is Tier 2 of the Slack pack family — the
"team channel ↔ session graph" middle tier, built fresh on slack-mini's
single-file kernel rather than carved down from slack-full (`gc-yrw.4`).

### Added

- Multi-file Slack adapter (`adapter/*.go`, module
  `github.com/sjarmak/gc-slack-channel-adapter`), built on the slack-mini
  kernel:
  - Public Slack Events API receiver at `/slack/events`, HMAC-verified with
    `SLACK_SIGNING_SECRET` and a 5-minute replay window.
  - **Widened inbound routing**: handles `message.*` events as well as
    `app_mention`. A message in a bound channel is delivered to every bound
    session; `@handle[:]` addresses route to the aliased session from any
    channel; an unbound, unaliased `app_mention` falls back to the default
    target (preserving Tier 1's "talk to mayor from any channel").
  - Three adapter-owned on-disk registries under
    `<GC_CITY_PATH>/.gc/slack-channel/`, written atomically and reloaded
    into memory: `channel_mappings.json`, `identities.json`,
    `handle_aliases.json`. JSON Schemas in `schema/`.
  - Outbound verb endpoints: `/publish`, `/publish-to-channel`,
    `/reply-current`, `/react`, all applying the session's identity override
    (`chat:write.customize`) to `chat.postMessage`.
  - `/slack/interactions` endpoint that verifies the signature and acks
    interactive payloads (basic modal-button ack; no custom modal handling).
  - Self-registers as an extmsg adapter on start (`REGISTER_ON_START`).
- Eight verbs, each a bash wrapper (`commands/<verb>.sh`) relaying to the
  adapter through gc's `/svc/slack-channel` reverse proxy — no operator CLI
  binary at this tier:
  - `bind-dm`, `bind-room` — bind a channel/DM to one or more sessions.
  - `publish`, `publish-to-channel` — post into a session's bound channel,
    or into any channel by id.
  - `reply-current` — reply into the conversation of the session's latest
    inbound message (optionally threaded).
  - `react` — add an emoji reaction to the latest inbound (or an explicit
    message).
  - `identity` — register/remove a per-session username + avatar override.
  - `handle-alias` — register/remove a `@handle → session` alias.
- Slack app manifest (`manifest/app.json`): scopes `app_mentions:read`,
  `channels:history`, `groups:history`, `im:history`, `mpim:history`,
  `chat:write`, `chat:write.public`, `chat:write.customize`,
  `reactions:write`; subscribes to `app_mention` and `message.*`.
- `pack.toml` declaring the adapter as a `proxy_process` service named
  `slack-channel`.

### Notes

- Independent of slack-mini and slack-full — no shared Go modules.
- Tier 2 excludes (those are slack-full / Tier 3): multi-rig routing,
  channel-name pattern resolvers, room-launch, the apps registry +
  slash-command intake, peer fanout, file upload, and double-handle
  dispatch.
- Pick exactly one Slack tier per city.
