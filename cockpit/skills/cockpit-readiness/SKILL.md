---
name: cockpit-readiness
description: Verify a gas city is GasCity Cockpit-ready and publish the discovery handshake the VS Code extension needs. Run `cockpit ready` to assert the live /v0 API is reachable + version-compatible + has the endpoints the Cockpit depends on, `cockpit discover --write` to publish the API descriptor the extension auto-discovers, and `cockpit contract` to see the /v0 version + endpoints the Cockpit pins. Use whenever you set up the Cockpit on a city, debug "API unavailable" in the extension, or re-establish discovery after a gc start / stop / restart.
---

# Cockpit Readiness

## Overview

The **GasCity Cockpit** is a VS Code extension (the client) plus this thin `cockpit`
pack (the city-side contract). The extension is a pure client of the supervisor's
existing `/v0` HTTP API — the same versioned, self-documenting API (`/openapi.json`,
SSE, the full session/chat/approval surface) the web dashboard uses. This pack does
**not** run a backend; it makes a city *Cockpit-ready* and publishes the discovery
handshake.

Two facts shape everything this skill does:

1. **The `/v0` API is always-on.** It is served by the **supervisor** (one process,
   all cities) on `127.0.0.1:8372` by default. There is no per-city "enable the API"
   toggle — if the supervisor is running, the API is up. So "make a city Cockpit-ready"
   is **assert + publish**, not flip a switch.
2. **Discovery is a small descriptor file.** Today nothing on disk advertises the API
   address (it was historically found by `lsof`). This pack writes a discovery
   descriptor to a well-known path so the extension auto-finds the API and degrades
   gracefully when it goes away.

`bin/cockpit` is the read/verify/publish CLI. `ready` and `contract` are pure reads;
`discover` only writes with `--write`/`--out`.

## When to Use

- You are **setting up the Cockpit** on a city and need to confirm it can drive it.
- The extension shows **"API unavailable"** and you need to tell whether the supervisor
  is down, the version drifted, or discovery is stale.
- After a **`gc start` / `gc stop` / restart** — the API is transient; re-publish the
  descriptor so the extension reconnects.
- You are **bumping the extension** and need to confirm the live `/v0` version still
  matches the pinned contract (`cockpit contract`).

**When NOT to use:**

- To start the city — that's `gc start`. This skill assumes a running supervisor; it
  *checks*, it does not boot.
- To register the Cockpit as a conversation participant — that is the **extmsg adapter**
  story (a runtime registration; see `cockpit adapter` and cockpit-1ll.12 / DESIGN.md),
  not readiness.

## Process

### Step 1 — Assert the city is Cockpit-ready

```bash
cockpit ready                       # against http://127.0.0.1:8372 by default
cockpit ready --city blackrim-hq    # also fetch that city's readiness
cockpit ready --json                # structured verdict for tooling
```

`ready` fetches `/openapi.json`, then checks three things and reports a single verdict:

- **reachable** — the supervisor `/v0` API answered;
- **version** — live `info.version` equals the contract's `required_version` (the `/v0`
  surface is a moving dev build, so this catches drift);
- **endpoints** — every load-bearing path the Cockpit needs (health, beads, chat
  submit/stream, approvals/pending, events, extmsg) is present in `/openapi.json`.

Exit codes are CI-usable: **0** Cockpit-ready, **1** reachable but incompatible
(version/endpoints), **2** API unreachable. `bin/cockpit` ships with this pack; if it is
not on `PATH`, invoke it by pack-relative path (e.g. `.../packs/cockpit/bin/cockpit ready`).

### Step 2 — Publish the discovery descriptor

```bash
cockpit discover --write                          # publish to $GC_HOME/runtime/cockpit/api-descriptor.json
cockpit discover --write --city blackrim-hq       # record the city in the descriptor
cockpit discover --out /path/to/descriptor.json   # write somewhere explicit instead
```

`discover` probes the live API and writes a small JSON descriptor — base URL, `/v0`
version, auth model, the cities it serves — to a **well-known path under `GC_HOME`**
(the supervisor home, default `~/.gc`; **note** this is the supervisor-global `.gc`, not a
city's `.gc`). The extension reads this descriptor to auto-find the API, with a settings
override allowed. Without `--write`/`--out` it just prints the descriptor.

> Run with `GC_HOME` set (the supervisor sets it) so the descriptor lands in the right
> runtime root and the token path resolves. In a bare shell, pass `--out` explicitly.

### Step 3 — (reference) See the contract the extension pins

```bash
cockpit contract            # version + discovery + required endpoints
cockpit contract --json     # the full machine-readable contract
```

`contract` prints `contract/v0.toml`: the pinned API version, the discovery descriptor
path, the auth model, and the required-endpoint gate. The extension generates its typed
client from `/openapi.json`; this contract is the **compatibility gate**, not the client.

## Worked Example

The operator installed the Cockpit extension but it shows "API unavailable".

1. **Is the API even up?** `cockpit ready` → `status: UNREACHABLE`. The supervisor isn't
   serving. `gc start` the city, then re-run: `cockpit ready` → `COCKPIT-READY`.
2. **Publish discovery.** `cockpit discover --write --city blackrim-hq` →
   `published -> /Users/you/.gc/runtime/cockpit/api-descriptor.json`. The extension's
   discovery poll picks it up and connects.
3. **Later, a `gc stop`/`gc start` cycle.** The extension drops to "API unavailable"
   (expected — availability is transient). Re-run `cockpit discover --write`; the
   extension reconnects. (Ideally the supervisor refreshes this descriptor itself at
   bind time — see DESIGN.md fork #3.)

## Why This Matters

- **One clear readiness signal.** Instead of `lsof`-ing for a port and eyeballing JSON,
  `cockpit ready` gives a single, version-aware verdict with a meaningful exit code.
- **Version drift is caught early.** `/v0` is a live dev build; pinning + asserting the
  version stops the extension from silently breaking when the API shape moves.
- **Discovery is explicit and resilient.** The descriptor is the contracted way the
  extension finds the API and knows when it's gone — no inspection, no guessing.

## Verification Gate

Before telling an operator the Cockpit is ready on a city:

- [ ] `cockpit ready` exits **0** (`COCKPIT-READY`) — reachable, version matches, all
      required endpoints present. A `1` means version/endpoint drift; a `2` means start
      the city first.
- [ ] `cockpit discover --write` published a descriptor (the path is printed) with
      `GC_HOME` pointing at the supervisor home.
- [ ] The descriptor's `cities` lists the city the operator expects to drive.
- [ ] You did **not** confuse the rig name with the city name — the API is city-scoped
      under `/v0/city/{cityName}/...`; confirm the name via `cockpit ready --city <name>`
      or `GET /v0/cities`.

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack contributes a
skill by placing `skills/<name>/SKILL.md` under the pack root, with YAML frontmatter
carrying at minimum `name` and `description`. This file lives at
`cockpit/skills/cockpit-readiness/SKILL.md`, so it is picked up automatically —
`pack.toml` does not enumerate skills. Once the `cockpit` pack is imported into a city
(vendored under `packs/cockpit` and registered via a direct `source = "packs/cockpit"`
import), the skill surfaces in `gc skill list` binding-qualified as
`cockpit.cockpit-readiness`, and the materializer projects it into the per-agent skills
sink at `gc start`. Verify with `gc skill list` (and `gc lint .` / `gc doctor`).
