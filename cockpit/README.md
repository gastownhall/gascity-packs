# cockpit — GasCity Cockpit city-side enabler pack

The **GasCity Cockpit** is a VS Code extension (the client) plus this thin gascity
pack (the city-side contract). The extension is a pure client of the supervisor's
existing `/v0` HTTP API; this pack makes a city **Cockpit-ready** and publishes the
discovery handshake the extension needs. It adds **no backend**.

> Status: v1 scaffold for epic `cockpit-1ll`, per the PROPOSED decisions in
> `cockpit-1ll.3`. **Read [`docs/DESIGN.md`](docs/DESIGN.md) §4 — three scope forks
> are flagged there for ratification before the pack is extended.**

## What it provides

| Path | Role |
|------|------|
| `bin/cockpit` | the `ready` / `discover` / `contract` / `adapter` CLI |
| `cockpit/` | the engine (pure-stdlib probe + contract reader) |
| `contract/v0.toml` | the `/v0` API contract the extension pins (version + endpoints) |
| `skills/cockpit-readiness/` | operator/agent skill: verify + publish discovery |
| `skills/mayor-ide-affordances/` | Mayor skill: emit IDE-legible affordances |
| `docs/DESIGN.md` | Cockpit-ready definition, discovery handshake, **scope forks** |

Stdlib-only (`tomllib` ≥3.11 / `tomli` fallback; `urllib` for the probe). No overlay,
no hooks, no prompt fragments — mirrors `provider-forge`'s minimal footprint.

## Quickstart

```bash
# (optional) build the engine venv; bin/cockpit also runs under any system python3
./setup.sh

# 1. Is this city Cockpit-ready? (exit 0 ready / 1 incompatible / 2 unreachable)
./bin/cockpit ready

# 2. Publish the discovery descriptor the extension auto-discovers
GC_HOME=~/.gc ./bin/cockpit discover --write --city <cityName>

# 3. See the /v0 contract the extension pins
./bin/cockpit contract

# 4. See the extmsg adapter registration spec (submitted at runtime; cockpit-1ll.12)
./bin/cockpit adapter --city <cityName>
```

`ready` and `contract` are pure reads; `discover` only writes with `--write`/`--out`;
`adapter` prints the spec and does **not** register (extmsg registration is a runtime
call — see DESIGN.md fork #2).

## Install into a city

Vendor `pack/` into the target city as `packs/cockpit/`, then:

```bash
packs/cockpit/install.sh --town            # city-wide
packs/cockpit/install.sh --rig <name>      # one rig
packs/cockpit/install.sh --town --dry-run  # preview
```

This registers a direct `source = "packs/cockpit"` import (the gastown pattern),
`gc reload`s, and verifies (`gc lint`, import registered, `cockpit ready` smoke).
Reverse with `uninstall.sh` (same scope flags; `--purge` to drop the venv).

## Tests

```bash
python3 -m pytest -q        # 30 tests, pure stdlib + pytest, no network
```

## License

MIT — see [LICENSE](LICENSE).
