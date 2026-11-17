# Changelog

All notable changes to teams-mini are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — initial release

The Microsoft Teams counterpart of slack-mini: the minimum viable Teams→gc
surface, requested by a design partner whose non-engineering teammates live
in Teams.

### Added

- Two-file Teams adapter (`adapter/main.go`, `adapter/auth.go`; module
  `github.com/gastownhall/gc-teams-mini-adapter`, standard library only):
  - Public Bot Framework messaging endpoint at `/api/messages`. Every
    request's bearer JWT is verified: RS256 signature against the JWKS named
    by the Bot Framework OpenID configuration, issuer, audience (the app
    id), `nbf`/`exp` with 5-minute skew, and the `serviceurl` claim against
    the activity. Keys are cached 24h and refreshed early on an unknown
    `kid`, rate-limited to one refresh per 5 minutes.
  - Handles `message` activities only; in channels and group chats only when
    the bot is mentioned. Activities from another tenant are dropped. Each
    bridged message is POSTed to `/v0/city/{city}/extmsg/inbound`, addressed
    to the mayor session (override with `TEAMS_MINI_INBOUND_TARGET`).
  - Outbound `/post-message` endpoint on the gc-proxied UDS, posting Teams
    markdown via the Bot Framework conversations API, as a new message or a
    reply to an activity. The client-credentials token is cached and
    refreshed a minute before expiry; `TEAMS_APP_TYPE` selects the
    multi-tenant or single-tenant authority.
  - Per-conversation `serviceUrl` remembered in memory from inbound
    activities, with `TEAMS_SERVICE_URL` and a per-call `service_url` as
    fallbacks. Nothing is written to disk.
  - Self-registers as an extmsg adapter on start (`REGISTER_ON_START`).
- `gc teams-mini post-message` verb, a bash wrapper
  (`commands/post-message.sh`) that relays to the adapter through gc's
  `/svc/teams-mini` reverse proxy.
- Teams app manifest (`manifest/manifest.json`) with placeholder icons and
  packaging instructions.
- `pack.toml` declaring the adapter as a `proxy_process` service named
  `teams-mini`; `adapter/run.sh` builds the binary on first start when the
  pack was installed git-only, as the Slack tiers do.

### Notes

- Teams has no ingress-free transport. A public HTTPS endpoint is required.
- No on-disk registries. Conversation bindings, per-session identity and rig
  routing are out of scope for this tier.
