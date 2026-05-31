# slack-pack OAuth install (gc-cby.9)

The OAuth install path lets a non-developer human in another Slack
workspace install the slack-pack into a fresh `gc` city without
hand-editing the adapter's env file. It replaces the manual web-UI
copy-paste of the bot token at the end of [`adapter/SETUP.md`](../adapter/SETUP.md).

Single-tenant by design: one `gc` city → one Slack workspace. Multi-
tenant token routing (one adapter serving many workspaces) is out of
scope and tracked separately.

## Prerequisites

You still need the same Slack-side scaffolding as the manual flow:

- A Slack app installed at <https://api.slack.com/apps> (use the
  manifest at [`manifest/app.json`](../manifest/app.json) — see
  [`manifest/README.md`](../manifest/README.md) for the import flow).
- A public HTTPS URL for the adapter's `:8765` listener (Tailscale
  Funnel works; see [`adapter/SETUP.md`](../adapter/SETUP.md) Step 1).
- A `gc` city with `GC_CITY_PATH` set in the adapter's environment.

## Step 1 — capture OAuth credentials

In the Slack app dashboard:

- **Basic Information → App Credentials**:
  - Copy the **Client ID** → set as `SLACK_CLIENT_ID`.
  - Copy the **Client Secret** → set as `SLACK_CLIENT_SECRET`.
  - Copy the **Signing Secret** → set as `SLACK_SIGNING_SECRET` (used
    by the adapter for inbound HMAC verification; the OAuth callback
    stamps the same value onto the apps registry record so the
    multi-app verify path in `gc-cby.16` finds it).
- **OAuth & Permissions → Redirect URLs**:
  - Add `https://<your-tunnel>.ts.net/slack/oauth/callback`.
  - **Save URLs**.

## Step 2 — start the adapter with OAuth env

Configure the adapter's environment with the values above plus the
redirect URI you registered:

```bash
export SLACK_CLIENT_ID='1234567890.1234567890'
export SLACK_CLIENT_SECRET='...'
export SLACK_SIGNING_SECRET='...'
export SLACK_REDIRECT_URI='https://<your-tunnel>.ts.net/slack/oauth/callback'
export GC_CITY_PATH='/path/to/gc/city'
export GC_CITY_NAME='your-city'
# SLACK_BOT_TOKEN and SLACK_WORKSPACE_ID intentionally NOT set yet —
# the OAuth callback will mint them.
```

The bot token and workspace id come from the OAuth grant; do not set
them yet. The adapter still needs `GC_CITY_NAME` to construct API
URLs, so leave that one set.

Start the adapter as you would normally
(see [`adapter/run.sh`](../adapter/run.sh) for the long-form
invocation). On startup the log line

```
oauth install endpoints registered: redirect_uri=https://<your-tunnel>.ts.net/slack/oauth/callback
```

confirms the install handlers are live. (Without `SLACK_CLIENT_ID`
the handlers are not registered and the rest of this doc does not
apply.)

> **Note:** the adapter will refuse to start without
> `SLACK_BOT_TOKEN` set, because the outbound publish path needs it.
> For first-time install: set `SLACK_BOT_TOKEN=placeholder`
> temporarily, run the OAuth flow below to mint the real token, then
> restart with the real token sourced from `install.env`.

## Step 3 — run the install flow

In a browser **logged into the target Slack workspace**, visit:

```
https://<your-tunnel>.ts.net/slack/oauth/start
```

Slack walks the operator through the standard "Add to Workspace"
prompt with the bot scopes from [`manifest/app.json`](../manifest/app.json).
On approval, Slack redirects back to `/slack/oauth/callback` with a
short-lived authorization code. The adapter:

1. Verifies the CSRF state cookie matches the redirected `state` param.
2. Exchanges the code via Slack's `oauth.v2.access` endpoint.
3. Persists an entry in the apps registry at
   `<cityPath>/.gc/slack/apps.json` with the freshly-minted bot user
   id, workspace id, app id, scopes, and the configured signing
   secret.
4. Writes a shell-sourceable env file to
   `<cityPath>/.gc/slack/install.env` containing the new
   `SLACK_BOT_TOKEN`, `SLACK_WORKSPACE_ID`, and `SLACK_APP_ID`. The
   file is mode 0600 — it carries a long-lived bot token and is not
   world-readable.
5. Renders a plain-text success page with the path to the env file.
   The bot token is **not** echoed in the page so the install URL is
   safe to share over Slack.

## Step 4 — restart with the new token

Stop the adapter, source the install env, and start again:

```bash
set -a; source <cityPath>/.gc/slack/install.env; set +a
unset SLACK_CLIENT_ID SLACK_CLIENT_SECRET SLACK_REDIRECT_URI  # OAuth flow no longer needed
./gc-slack-adapter
```

After the restart the adapter is fully operational with the freshly-
issued bot token. Inbound `/slack/events` are HMAC-verified against
the apps registry's signing secret (set during the OAuth callback),
matching the multi-app lookup path from `gc-cby.16`.

## Notes

- **Re-running the install** for the same workspace is idempotent —
  Slack issues a new bot token and the apps registry record is
  overwritten in place. The previous bot token is invalidated by
  Slack and cannot be re-used.
- **Disabling OAuth post-install** is recommended for production:
  unset `SLACK_CLIENT_ID` and restart so the install endpoints are
  no longer registered. The apps registry record persists so the
  signing-secret lookup keeps working.
- **Slack does not return the signing secret** in `oauth.v2.access`.
  It must be supplied via `SLACK_SIGNING_SECRET` at install time.
  Empty signing secret on the apps registry record falls back to the
  env-var-only verify path documented in `gc-cby.16`.
- **No multi-tenant routing.** A single adapter process binds one
  `SLACK_BOT_TOKEN` and posts on behalf of one workspace. Running
  multiple workspaces requires multiple adapters with separate
  city paths.
