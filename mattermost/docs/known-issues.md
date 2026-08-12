# Known issues / operational gotchas

Findings from standing this pack up for real on a production Gas City
host — its first genuine live deployment (dot-wau, 2026-08-09/11).
Every pack command (`import-app`, `bind-room`, `publish`, the gateway
service) worked correctly against real Mattermost traffic; nothing here
required a code change to the pack itself. Organized by where the
problem actually lives, since that matters for anyone triaging a
similar deployment.

## Real gaps in this pack (worth fixing or at least flagging in review)

### No CLI to remove a chat binding

Once created via `bind-room`, there's no `gc mattermost unbind` /
`remove-binding` command. If you bind the wrong channel, the only fix
is a direct edit of the city's
`.gc/services/mattermost/data/config.json`: load the JSON, pop the
stale key out of `.chat.bindings`, write back atomically
(temp file + rename) — same shape as the pack's own `atomic_write_json`
helper. Binding-discovery logic that picks the first `kind == "room"`
entry (e.g. a caller mirroring `deploy.sh`'s `mm_binding()` pattern)
will otherwise nondeterministically pick a stale binding left behind
by an earlier mistake. A first-class unbind command would remove the
need for this workaround entirely.

### `bind-room` doesn't check channel membership before binding

A bot token that authenticates successfully isn't necessarily a bot
that's a *member* of the channel you're binding — Mattermost channel
membership is separate from token validity, and `bind-room` happily
creates a binding for a channel the bot can't actually post to.
`gc mattermost publish` against such a binding fails with an HTTP 403
from Mattermost at *publish* time, not at bind time — by which point
you've already told yourself the setup succeeded. A pre-flight
`GET /api/v4/channels/<id>/members/me` check inside `bind-room` (warn
or fail loud if the bot isn't a member) would surface this immediately
instead of on the first real message.

### Workspace-name mismatch silently falls back to the wrong API port

`gc_api_base_url()` / `discover_supervisor_gc_api_scope()` resolve the
city's local control API by looking up the city's `workspace_name`
(from `.gc/site.toml` / `city.toml`) against the supervisor's live
`/v0/cities` list. If that name doesn't match anything currently
registered (e.g. `.gc/site.toml` has a stale name left over from a
prior registration), discovery just returns empty and the code falls
through to the **legacy, pre-supervisor** default port (9443) instead
of the real supervisor port (8372) — with no error, no warning. Every
subsequent `gc-api` call from the gateway then fails with a generic
connection-refused, which looks exactly like a networking problem and
gives zero hint that the actual issue is a name mismatch. This one
cost real debugging time. Concretely:

```
$ curl http://127.0.0.1:8372/v0/cities
{"items":[{"name":"phosphorus-city", ...}]}   # what's actually registered

$ cat .gc/site.toml
workspace_name = "dotfiles"                    # what the pack was looking for — no match
```

**Suggested fix:** when `discover_supervisor_gc_api_scope()` gets a
non-empty `/v0/cities` response but finds no matching name, log (or
surface via `gc mattermost status`) something like `city
"<workspace_name>" not found among registered cities: [<names>]` —
even just at debug level — instead of silently changing which port
gets used.

## Bugs in the `gc` binary itself (`gastownhall/gascity` — a different repo, not this pack)

### `gc import add` mis-parses branch names containing `/`

The GitHub tree-URL form (`https://github.com/<org>/<repo>/tree/<ref>/<path>`)
is ambiguous when `<ref>` itself contains a slash — e.g. a branch named
`feat/mattermost-pack`. The import parser splits on the first `/`
after `tree/`, so `.../tree/feat/mattermost-pack/mattermost` gets read
as ref=`feat`, path=`mattermost-pack/mattermost`, which doesn't exist,
and the import fails with a "missing pack.toml" error naming that
wrong path.

**Workaround:** use the `.git//<subpath>` form with an explicit
`--version sha:<commit>` instead, which has no ambiguity:

```bash
gc import add "https://github.com/<org>/<repo>.git//mattermost" \
  --version "sha:<commit>" --name mattermost
```

## Environment/deployment pitfalls (config and host state, not code)

### The bot can publish long before it can listen

`gc mattermost publish --binding <id> --body-file <path>` is a
stateless one-shot REST call — it works as soon as `import-app` has
stored a valid bot token, independent of whether the city's own
controller/supervisor has fully started. **Actually receiving and
responding to messages (DMs, @-mentions) is a different story** — that
needs the `mattermost-gateway` / `mattermost-interactions` `[[service]]`
processes running, which only happens once the city's controller
finishes initializing. If that controller is stuck (see the two causes
below), `gc mattermost publish` still works fine, `gc service list`
shows the gateway as `config` only (no live URL, no process), and
messaging the bot gets total silence. `gc status` reporting
`Controller: supervisor-managed (PID <n>, init failed)` is the first
thing to check.

Two concrete things that can wedge a controller's init on a host also
running `bd`/beads:

1. **`bd`/`dolt` not installed / not on PATH** — `gc register`'s beads
   lifecycle step fails outright (`dolt: command not found`), and the
   controller keeps retrying and failing on the supervisor's timer.
2. **`bd` beads-store schema skew** — if the Dolt database has been
   migrated ahead of what the installed `bd`/`gc` binaries understand
   (`schema version mismatch: database is at vNN, binary knows up to
   vMM`), `gc`'s internal `bd` subprocess calls fail silently and the
   session reconciler can never progress ANY session bead past
   `start-pending` — not just mattermost-related ones. Fixed live via
   `BD_IGNORE_SCHEMA_SKEW=1` in the environment of the process that
   spawns sessions (a systemd drop-in + actually cycling the daemon,
   since env changes don't reach an already-running detached process).
   This is a generic `gc`/`beads` compatibility issue, not mattermost-
   pack-specific, but it manifests identically to gateway/session
   problems and is easy to misattribute.

### `gc`/`beads`/`dolt` version coupling

`gc` links against a specific `beads` version at build time. If the
standalone `bd`/`dolt` binaries on a host drift from what that build
expects, `gc` can silently fall back to a much slower fork-per-op `bd`
subprocess path instead of its native in-process store — documented
elsewhere in this fleet as the direct cause of a multi-hour Dolt
connection-storm incident on a different host. Known-good pairing
referenced at that time: `gascity 1.4.0 ↔ beads 1.1.0 ↔ dolt 2.2.3`;
nixpkgs' own `dolt`/`beads` packages were noted as mismatched versions
at the time of writing. Before installing/upgrading any one of the
three, check what the others actually need — don't bump in isolation.

### Bot identity: use the host's own dedicated bot, not an unrelated one

If your fleet already has a bot-per-purpose convention (e.g. one bot
per host/city, separate from bots used for other automation's own
status pings), **use the dedicated one** for `import-app`. Using the
wrong (but valid) token is exactly how the channel-membership gap above
gets discovered the hard way — the bot authenticates fine, and the
403 only shows up at publish time.

## Positive finding: the pack is model/provider-agnostic on the receiving end

Wired a Gas City session's `start_command` to run `codex` against
OpenRouter (a free-tier NVIDIA Nemotron model, non-Claude, no OAuth
login) instead of the default Claude provider, purely to validate
routing without needing interactive auth on a headless host. The
mattermost-v0 prompt fragment + gateway routing worked identically —
the pack has no hidden dependency on which agent/provider is behind
the session it's routing to.
