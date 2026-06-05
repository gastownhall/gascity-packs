# cockpit pack — design & open scope forks

> Implements the city-side half of the **GasCity Cockpit** (epic `cockpit-1ll`),
> per the PROPOSED decisions #3 / #4 / #5 in `cockpit-1ll.3`. Those decisions are
> **proposed, pending operator ratification**; the dispatch note asked to *flag
> major forks before hard-coding pack scope*. This document is that flag. Read
> §4 ("Open scope forks") before extending the pack.

## 1. What this pack is

The GasCity Cockpit is **two artifacts, one product**: a VS Code extension (the
client) and this thin `cockpit` pack (the city-side contract). The expensive part
already exists — the supervisor's versioned, self-documenting `/v0` HTTP API
(`/openapi.json`, SSE, the full session/chat/approval surface). The extension is a
pure client of that API. This pack **adds no backend**. It does four things:

1. **Asserts Cockpit-readiness** — `cockpit ready` verifies the live `/v0` API is
   reachable, version-compatible, and exposes the endpoints the Cockpit needs.
2. **Publishes the discovery handshake** — `cockpit discover --write` writes a
   descriptor (API base URL + version + auth model + cities) to a well-known path
   the extension reads to auto-find the API.
3. **Declares the `/v0` contract** — `contract/v0.toml` pins the required API
   version and names the endpoints the extension depends on; `cockpit contract`
   prints it. The extension generates its typed client from `/openapi.json`; this
   contract is the *compatibility gate*.
4. **Ships Mayor IDE-affordance skills** — `cockpit-readiness` and
   `mayor-ide-affordances` (convention-discovered under `skills/`).

It is pure-stdlib (tomllib + urllib), mirroring `provider-forge`'s minimal
footprint: no overlay, no hooks, no prompt fragments — just a CLI, a contract, and
two skills.

## 2. What makes a city "Cockpit-ready"

A city is Cockpit-ready when, against the running supervisor:

- the `/v0` API answers (`/openapi.json` fetch succeeds);
- `info.version` equals `[api] required_version` in the contract (currently
  `0.1.0`); and
- every path in `[endpoints] required` is present in `/openapi.json`.

`cockpit ready` returns **0** ready, **1** reachable-but-incompatible, **2**
unreachable — CI-usable. The required set is the load-bearing subset (health,
beads, chat submit/stream, approvals/pending, events, extmsg); the full capability
map (`[endpoints.capabilities]`) documents the rest for the extension.

## 3. The discovery handshake

`cockpit discover --write` publishes JSON to a **well-known runtime path**:

```
$GC_HOME/runtime/cockpit/api-descriptor.json
```

Descriptor shape (`schema_version = 1`):

```json
{
  "schema_version": 1,
  "kind": "gascity-cockpit-api-descriptor",
  "base_url": "http://127.0.0.1:8372",
  "api_version": "0.1.0",
  "api_title": "Gas City Supervisor API",
  "auth": { "type": "localhost-trust", "token_file": "<GC_HOME>/controller.token" },
  "cities": ["blackrim-hq"],
  "discovered_at": "2026-06-05T06:55:52Z",
  "source": "cockpit discover (pack-side probe)"
}
```

**Two `.gc` roots — read carefully.** The `/v0` API is **supervisor-wide** (one
process serves every city on `:8372`). So the descriptor is supervisor-scoped and
lives under the **supervisor** home, `$GC_HOME` (default `~/.gc`) — *not* a city's
`.gc`. In this town, for example, `GC_HOME=~/.gc` (supervisor home) while the
`blackrim-hq` city's runtime is at `/Users/jayse/Code/.gc`. The descriptor's
`cities[]` lists every city the one API serves. The extension reads this single
descriptor, with a settings override allowed.

**Resilience.** API availability is transient: `gc stop` takes it down, `gc start`
brings it back (possibly on a new build). The extension must treat the descriptor
as a hint, reconnect with backoff, and show an explicit "API unavailable" state.
Re-run `cockpit discover --write` after a restart to refresh it. (Ideally the
supervisor refreshes the descriptor itself — see fork #3.)

**Auth (PRD decision #5).** v1 is **localhost-trust**: the `/v0` API does *not*
enforce a bearer token today; reaching `127.0.0.1:8372` *is* the authorization.
The descriptor records `auth.type = "localhost-trust"` and references
`controller.token` so a future remote/auth story is *additive* (design the boundary
now, build remote later). No remote in v1.

## 4. Open scope forks  ⚠️  (flag before hard-coding)

The PROPOSED pack scope says the pack should "enable the API service, register the
Cockpit extmsg adapter, write the discovery handshake." Investigating how gascity
actually works surfaced three places where the proposed wording does **not** map
cleanly onto a static pack. This pack ships the honest groundwork and flags each
fork rather than hard-coding around it. Each needs an operator/Mayor decision.

### Fork #1 — "Enable the API service" — there is nothing to enable

**Reality.** The `/v0` API is served by the **supervisor** and is **always-on**
when the supervisor runs (`cmd_supervisor.go` starts the listener unconditionally;
bind/port come from `~/.gc/supervisor.toml` `[supervisor]`, default
`127.0.0.1:8372`). There is **no per-city or per-pack "enable the API" toggle**.
The legacy per-city `[api]` block is disabled-by-default and deprecated; the
supervisor serves all cities at `/v0/city/{cityName}/...`.

**What this pack does instead.** Treats "enable" as **assert + verify**:
`cockpit ready` confirms the always-on API is reachable and compatible. It does not
fabricate a switch that doesn't exist.

**Recommended ratification.** Reword the deliverable from "enable the API service"
to "**assert the API service is up and `/v0`-compatible**." If an opt-in/opt-out of
the API per city is genuinely wanted, that's a **gastown** feature request (supervisor
config), filed upstream — not built here.

### Fork #2 — "Register the Cockpit extmsg adapter" — it's a runtime call, and it's `cockpit-1ll.12`

**Reality.** extmsg adapter registration is `POST /v0/city/{cityName}/extmsg/adapters`
with `{provider, account_id, name, callback_url, capabilities}`. The registry is
**in-memory and ephemeral** (lost on controller restart), and an adapter needs a
**reachable `callback_url`** for outbound delivery — i.e. a *running HTTP service*.
The Cockpit is a VS Code extension (a client), not a server. So a static pack
`install.sh` **cannot durably register** the adapter. Moreover, extmsg participant
integration is its own downstream bead — **`cockpit-1ll.12`**, which `cockpit-1ll.14`
*blocks*.

**What this pack does instead.** Ships the **adapter contract + spec**, not a
half-working registration:
- `contract/v0.toml` `[extmsg]` declares the provider id (`cockpit`) + capabilities;
- `cockpit adapter [--city] [--callback-url] [--json]` prints the exact endpoint and
  POST body the host will submit at runtime — clearly marked RUNTIME / `cockpit-1ll.12`.
It deliberately does **not** perform a register that would be ephemeral and
callback-less.

**Recommended ratification.** Keep durable registration in **`cockpit-1ll.12`**,
where the extension/host owns the callback service and re-registers on connect. If a
**declarative / persistent** adapter registration is wanted (so a pack *can* declare
an adapter that survives restart), that is a **gastown** ask — file it; do not
simulate persistence from the pack.

### Fork #3 — "Write the discovery handshake" — best owned by the supervisor

**Reality.** Nothing on disk advertises the API address today; the clean place to
write the descriptor is the **supervisor**, at listener-bind time (it knows the
bound address, and can remove the file on shutdown — exactly how it manages
`supervisor.sock`). A pack/CLI can only *probe-and-write after the fact*, which is
inherently staler and racier across restarts.

**What this pack does instead.** Provides `cockpit discover --write` so the
descriptor exists now (closing the no-api-addr-file gap), and defines the descriptor
**path + schema** as the contract. This is the pragmatic v1.

**Recommended ratification.** Adopt the pack-side descriptor as the v1 contract, and
file a **gastown** ask to have the **supervisor write/remove this exact descriptor**
at bind/shutdown (same path + schema), so discovery becomes self-maintaining and
the pack's `discover --write` becomes a fallback. The PRD's out-of-scope note
explicitly allows the discovery handshake (and extmsg registration) to touch
gastown; everything else found is *filed against gastown, not built here*.

## 5. Relationship to sibling beads

- `cockpit-1ll`   — the epic / PRD (canonical).
- `cockpit-1ll.3` — the 7 design decisions (PROPOSED). This pack implements the
  pack-relevant halves of #3 (pack + delivery), #4 (discovery + resilience), #5
  (identity/auth boundary).
- `cockpit-1ll.12` — extmsg participant integration (Phase 3), **blocked by**
  `cockpit-1ll.14`. Fork #2's durable adapter registration belongs here.
- `cockpit-1ll.4` — transcript-fidelity spike (GREEN); gates decision #6 (chat
  content fidelity), which the `mayor-ide-affordances` skill assumes.

## 6. Deployment

This rig (`gascity-cockpit`) owns the source for **both** artifacts: the extension
(future) and this pack (`pack/`). The existing town packs (`model-advisor`,
`provider-forge`, `ast-lens`) are each vendored at `<city>/packs/<name>/` and
imported via a direct `source = "packs/<name>"` entry. To deploy this pack, **vendor
`pack/` into the target city as `packs/cockpit/`** (copy/clone) and run
`packs/cockpit/install.sh --town` (or `--rig <name>`). `install.sh` records the
import relative to the city root when the pack lives under it, else absolute.

> **Minor structural fork.** This is a mono-repo (extension + pack in one rig),
> unlike the one-repo-per-pack model of the existing three. If the town's tooling
> assumes a pack repo *is* the pack root, we either (a) vendor only `pack/` into
> `packs/cockpit/`, or (b) split the pack into its own repo later. (a) is the v1
> path and needs no upstream change.

## 7. Testing

Per the PRD's testing decisions, the testable seam is the typed-client/contract
layer, not the VS-Code glue. Tests (`tests/`, pytest, pure stdlib) cover:

- **contract** — the shipped `contract/v0.toml` loads, pins `0.1.0`, declares the
  load-bearing endpoints, and yields a well-formed adapter spec; malformed
  contracts fail loudly.
- **discovery** — `probe_api` (hermetic, monkeypatched HTTP) for reachable /
  unreachable / health-non-fatal; `assess_readiness` for version + missing-path
  verdicts; descriptor round-trips on disk and honors `GC_HOME`.
- **cli** — `ready` exit-code state machine (0/1/2), `discover` write, `contract`
  and `adapter` text+JSON.

A thin **live-contract** check (mirroring gascity's
`test/integration/*_live_contract_test.go`) is `cockpit ready` itself run against a
throwaway test city — it fails if the `/v0` shapes the Cockpit depends on drift.
