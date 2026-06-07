# personas — dynamic principal-engineer persona equip

When a polecat picks up a task, it equips a principal-engineer persona matched to that
task, performs the work at that level, then dematerializes. Recently-used personas stay
warm in a shared cache so other agents reuse them without paying the materialize cost,
and they age out after a period of disuse.

This is the gas-city pack for [blackrim-personas](../README.md). It composes with the
rest of the toolchain: **model-advisor** picks the model *tier*, **provider-forge** picks
the *provider/model*, and **personas** picks the *role*.

> Status: v0 scaffold. Read [`docs/DESIGN.md`](docs/DESIGN.md) for the registry shape,
> the match rule, the TTL reasoning, and the open scope.

## What it provides

| Path | Role |
|------|------|
| `bin/personas` | the `list` / `show` / `lint` / `match` / `equip` / `cache` / `evict` / `sweep` CLI |
| `personas/` | the engine (registry loader + match rule + warm-cache lifecycle) |
| `personas.toml` | the roster (10 principal-engineer personas) + warm-cache TTL policy |
| `hooks/equip-on-task-pickup.sh` | the gas-town SessionStart equip hook |
| `overlay/per-provider/claude/` | wires the equip hook into projected agent settings |
| `template-fragments/use-personas.template.md` | the equip-a-persona discipline fragment |
| `skills/equip-persona/` | agent/operator skill: equip + inspect |
| `docs/DESIGN.md` | registry shape, match rule, TTL reasoning, scope notes |

Stdlib-only (`tomllib` ≥3.11 / `tomli` fallback). No runtime third-party deps — mirrors
`model-advisor` / `provider-forge`'s minimal footprint.

## Quickstart

```bash
# (optional) build the engine venv; bin/personas also runs under any system python3
./setup.sh

# 1. The roster — and check it's complete after an edit
./bin/personas list
./bin/personas lint             # registry integrity check (exit 1 if issues)

# 2. The equip decision for a task (read-only; shows score + why)
./bin/personas match "implement a paginated REST endpoint backed by Postgres"
./bin/personas match --from-bead pers-0fs   # preview a bead's decision (read-only)

# 3. Equip it — materializes the persona into the shared warm cache
./bin/personas equip "audit the upload handler for SSRF"

# 4. A persona's full playbook + verification bar
./bin/personas show principal-security-engineer

# 5. The warm cache (what's materialized + TTL remaining) / age it out
./bin/personas cache
./bin/personas evict principal-backend-engineer   # drop one persona now
./bin/personas sweep            # evict expired   (--all clears everything)
```

`list` / `show` / `lint` / `match` / `cache` are pure reads; `equip` / `evict` / `sweep`
mutate the shared warm cache. `match` and `equip` take `--from-bead <id>` to pull the task
text from a work bead (`match` previews the decision, `equip` materializes it); `equip
--emit-context` prints a Claude Code SessionStart hook payload (used by the equip hook).

## The roster

Ten principal-engineer specialists, each with a domain, a playbook, when-to-equip
conditions, the skills/tools it brings, and a verification bar:

`principal-backend-engineer` · `principal-frontend-engineer` · `principal-systems-engineer` ·
`principal-security-engineer` · `principal-data-engineer` · `principal-platform-engineer` ·
`principal-api-designer` · `principal-test-engineer` · `principal-refactoring-engineer` ·
`principal-docs-engineer`

Extending the suite is adding a `[[persona]]` block to [`personas.toml`](personas.toml).

## Warm cache + TTL

Equipped personas linger in a shared cache (under a rig's `.beads/personas/` by default)
so the next agent reuses them. The aging policy (configurable in `personas.toml`
`[cache]`):

- **Sliding idle TTL: 30 min**, refreshed on every reuse.
- **Absolute ceiling: 2 h**, so even a continuously-reused persona re-reads the registry.

Eviction is lazy (every `equip` / `cache` sweeps expired entries) plus the explicit
`sweep` (expired, by policy) and `evict <id>` (one persona, on demand). See
[`docs/DESIGN.md`](docs/DESIGN.md) §3 for the TTL reasoning and §6 for the CLI.

## Install into a city

Vendor `pack/` into the target city as `packs/personas/`, then:

```bash
packs/personas/install.sh --town            # city-wide
packs/personas/install.sh --rig <name>      # one rig
packs/personas/install.sh --town --dry-run  # preview
```

This registers a direct `source = "packs/personas"` import (the gastown pattern), adds the
`use-personas` discipline fragment (town scope), `gc reload`s so the SessionStart equip
hook is merged into projected settings, and verifies (`gc lint`, skill listed, import
registered, hook projected). Reverse with `uninstall.sh` (same scope flags; `--purge`
drops the venv).

## Tests

```bash
python3 -m pytest -q        # 171 tests, pure stdlib + pytest, no network
```

## License

MIT — see [LICENSE](LICENSE).
