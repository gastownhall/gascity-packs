# Multi-App Discord Chat

## Objective

Allow one Gas City Discord pack instance to host multiple Discord bot
identities. Each identity must have isolated credentials, app-aware room and
DM bindings, an independent gateway connection, and same-app replies. Existing
single-app cities must continue to work without configuration or command
changes.

The immediate consumer is the Gas City Inc engineering organization: a team
city can expose its technical lead, product manager, and design partner as
separate Discord bots in one team channel.

## Supported Surface

The multi-app slice covers chat transport:

- app import and credential storage;
- room and DM bindings;
- gateway ingress and per-app policy checks;
- explicit publish and `reply-current`;
- per-app gateway status.

Slash-command interactions, workflow channel/rig maps, room launchers, and
command sync continue to use the legacy/default app in this slice. Named apps
must use explicit chat bindings. This keeps the bridge small while preserving
the existing workflow surface unchanged.

## Contract

### Configuration

The existing `app` and top-level `policy` remain the default app. A new `apps`
registry holds named apps. App names are stable lowercase slugs matching
`[a-z][a-z0-9_-]{0,31}`.

```json
{
  "app": {
    "application_id": "1484616391729483786",
    "public_key": "...",
    "command_name": "gc"
  },
  "policy": {
    "guild_allowlist": ["123"],
    "channel_allowlist": ["456"],
    "role_allowlist": []
  },
  "apps": {
    "ollie": {
      "application_id": "1526662042302287982",
      "public_key": "...",
      "policy": {
        "guild_allowlist": ["123"],
        "channel_allowlist": ["456"],
        "role_allowlist": []
      }
    }
  }
}
```

Bindings gain an optional `app` field. Legacy bindings without it belong to
the default app. Named bindings are keyed by app as well as conversation so
multiple bots can bind the same Discord channel independently.

```json
{
  "id": "room:456@app:ollie",
  "kind": "room",
  "conversation_id": "456",
  "guild_id": "123",
  "app": "ollie",
  "session_names": ["teams.lead"]
}
```

### Secrets

- Default app token: `secrets/bot-token.txt` (unchanged).
- Named app token: `secrets/bot-token-<app>.txt`.
- Every token file is mode `0600` inside the mode `0700` secrets directory.
- Tokens never appear in config, status output, logs, exceptions, or test
  fixtures that can be committed.
- Unknown or invalid app names fail closed before a secret path is built.
- A named app slug is pinned to its first application ID. Replacements use a
  new slug; only same-identity token rotation is supported.

### Commands

The following optional selector is additive:

```text
gc discord import-app --app <name> ...
gc discord bind-room --app <name> ...
gc discord bind-dm --app <name> ...
gc discord publish --app <name> ...
```

Omitting `--app` retains the default app's command shape, configuration, and
binding-selection behavior when an exact default binding exists. The existing
top-level policy remains authoritative and is enforced for default-app ingress,
bind, and publish just as an `apps.<name>.policy` is for named apps. If no
default binding exists, one matching named binding may be resolved
automatically; multiple named candidates are ambiguous and require `--app`.
`reply-current` does not need an app flag for its normal path: it inherits the
app recorded on the current ingress turn.

### Gateway and routing

- The existing `discord-gateway` service starts one `GatewayWorker` per
  configured app with a token.
- A worker receives its app name explicitly; it never infers identity from
  mutable global config.
- Gateway status, queues, reconnect state, and counters are isolated per app.
  One failed connection must not stop another.
- Ingress receipt IDs are app-scoped for named apps so an ignored copy seen by
  one bot cannot suppress delivery by the bot that was actually mentioned.
- Every ingress receipt stores `app`; every publish stores `app`.
- Binding resolution and allowlist checks always receive the worker app.
- Room bind and publish verify Discord's actual guild and parent channel rather
  than trusting caller-supplied binding metadata. Role allowlists remain
  inbound-user checks.
- `reply-current` selects the token from the ingress app and rejects missing or
  stale app references.
- Bot-authored Discord messages remain ignored, preventing bot loops.

Adding, removing, or rotating an app or credential requires
`gc service restart discord-gateway` so the service rebuilds its worker
registry and reconnects with the current token. `gc reload` alone does not
restart an unchanged gateway service.

## Commands for Development

From the `gascity-packs` repository root:

```sh
python3 -m unittest discover -s discord/tests -p 'test_discord_*.py'
python3 -m unittest discord.tests.test_discord_intake_common
python3 -m unittest discord.tests.test_discord_chat_scripts
python3 -m unittest discord.tests.test_discord_gateway_service
```

No dependency is added; implementation uses the Python standard library and
the existing pack helpers.

## Project Structure

- `discord/scripts/discord_intake_common.py`: config, secret, binding, receipt,
  publish, policy, and status contracts.
- `discord/scripts/discord_intake_import.py`: app import CLI.
- `discord/scripts/discord_chat_bind.py`: app-aware binding CLI.
- `discord/scripts/discord_chat_publish.py`: explicit app selection.
- `discord/scripts/discord_chat_reply_current.py`: ingress-app inheritance.
- `discord/scripts/discord_gateway_service.py`: one worker per app and app-aware
  ingress.
- `discord/tests/`: unit and service tests beside the existing Discord suites.
- `discord/README.md` and command help: public usage and migration guidance.

## Code Style

Keep app identity explicit at boundaries and preserve empty-string default app
semantics internally:

```python
app_name = common.validate_app_name(args.app)
binding = common.resolve_chat_binding(
    config,
    kind="room",
    conversation_id=args.conversation_id,
    app_name=app_name,
)
token = common.load_bot_token(app_name)
```

Do not use process-wide mutable app identity, silently fall back from an
unknown named app to default, or catch credential/config errors and continue
with another token.

## Testing Strategy

Tests are written first and must demonstrate failure on the single-app code.
Coverage includes:

1. legacy config, token path, binding IDs, status shape, and commands;
2. normalization and validation of named apps;
3. token isolation and file modes;
4. two bindings for the same room under different apps;
5. app-scoped allowlists and ingress deduplication;
6. same-app `reply-current` and explicit publish;
7. independent gateway ready/failure/reconnect status;
8. unknown and ambiguous app selectors failing closed;
9. bot-message loop prevention with multiple connected bots.

The full Discord pack test suite runs after each vertical slice. Live rollout
then verifies every configured identity with status counters and one inbound
and outbound message in its authorized channel.

## Boundaries

- Always: preserve legacy behavior, validate external/config input, isolate
  secrets, redact errors/status, and test both happy and failure paths.
- Ask first: changing the public interactions URL, enabling named-app slash
  commands, changing the existing default app, or broadening Discord/OpenBao
  permissions.
- Never: commit or print tokens, share one token file between named apps,
  accept ambiguous binding resolution, restart the retired Gas City Inc city,
  or allow one app failure to terminate all gateway workers.

The additive `apps` registry currently shares schema version 1 with the legacy
config. Before rolling back to a pack version that does not understand it,
back up the config and secrets and avoid legacy config-mutating commands, which
would normalize the unknown registry away.

## Success Criteria

- A city can connect at least three named Discord bots concurrently.
- Mentioning each bot in the same room routes only to its bound Gas City
  session.
- `reply-current` posts as the bot that received the turn.
- Importing one app cannot overwrite another app's metadata or token.
- Existing single-app fixtures and live cities require no migration.
- Status reports each app's health and counters without exposing credentials.
- The complete Discord test suite passes, followed by live tests with zero
  failed or dropped messages.

## Open Questions

None for this slice. Named-app interactions and command sync are intentionally
deferred until there is a consumer for them.
