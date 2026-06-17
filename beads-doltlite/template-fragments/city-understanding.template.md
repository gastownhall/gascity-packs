{{ define "city-understanding" }}
## City: doltlite-gascity

### Purpose

This city exists to develop, test, and maintain the **doltlite backend** for Gas Town and beads. It runs Gas Town's full machinery (mayor, polecats, witnesses, refinery, dogs) on a doltlite storage backend — an embedded prolly-tree SQLite engine with zero server process.

The city is the **primary development and testing ground** for running Gas Town cities without a Dolt MySQL-compatible server.

### Repo and Workspace Layout

- City root: `/data/projects/doltlite-gascity`
- `gascity/` is the main controller repo. Its `default@` workspace is the integration baseline for city behavior.
- `gascity-packs/` is the pack repo. Pack edits should land here, then be rebased onto the `default@` tip before publish or handoff.
- Worker workspaces live under `.gc/workspaces/...` and are for isolated work. They are not the canonical source of pack changes.
- The `beads-doltlite` pack was copied from `gascity/examples/beads-doltlite/` into `gascity-packs/beads-doltlite/` so the pack can evolve in the pack repo without touching the source example.
- The default workspace in `gascity-packs/` is the place to integrate pack changes before they are handed off; worker workspaces are for drafting, not for inventing a second source of truth.

### How The Workspaces Fit Together

Think of the city as one graph with a few named entry points:

- `gascity/default` is where the controller repo keeps the canonical integration tip.
- `gascity-packs/default` is where shared pack edits are merged before they are published.
- `gascity-packs/gastown-lazyjj.furiosa` is a worker workspace for doing isolated pack work without disturbing the default integration tip.
- Other worker workspaces may exist for other agents, but they should converge back to the same tested default head before handoff.

The normal flow is:

1. Inspect the city root and identify the right repo for the change.
2. Work in a worker workspace if the task is isolated.
3. Commit the change in `gascity-packs/` or `gascity/` as appropriate.
4. Rebase that change onto the current `default@` tip.
5. Push or hand off from the default chain, not from a scratch workspace.

The important rule is that the worker workspace is not a competing source of truth. It is a drafting area that should feed the shared default chain.

### The Ship-It Principle

A fix is only real when another user on another machine gets the same result by running the same commands — no manual steps, no ad-hoc edits, no "we already fixed that on this machine." Every change must be in code or config that ships:

- **gascity source** — patches to `cmd/gc/`, `internal/`, or `examples/*/pack/` that compile into the `gc` binary.
- **beads-doltlite source** — patches to `internal/storage/doltlite/` or `cmd/bd/` that compile into the `bd` binary.
- **doltlite C source** — patches to the prolly-tree engine that produce `libdoltlite.so`.
- **city.toml** — declarative config (`backend = "doltlite"`, pack includes, order overrides) that any `gc init` can reproduce.
- **gascity-packs pack edits** — changes to pack fragments, commands, formulas, and metadata belong in `gascity-packs/`, then get rebased onto `default@` before they are pushed or handed off.

Manual edits to runtime files (`.gc/system/packs/`, wrapper scripts, installed binaries) are scaffolding. They prove the fix works but are not the fix. Before declaring done, port every manual edit into its upstream source and rebuild.

### Codebases

| Repo | Location | Purpose |
|------|----------|---------|
| `gastownhall/gascity` | `./gascity/` | Gas Town controller, CLI, examples, and the default workspace baseline |
| `dolthub/doltlite` | `./doltlite/` | C library: prolly-tree SQLite fork (libdoltlite.so) |
| `gascity-packs` | `./gascity-packs/` | Pack repository; this is where shared pack changes are committed and rebased to `default@` |
| `duncan4123/beads-doltlite` | `./beads-doltlite/` | `bd` CLI: beads issue tracker with doltlite storage backend |

### Workspace Roles

| Workspace | Role |
|-----------|------|
| `gascity/default` | Integration tip for controller behavior and repo-wide coordination |
| `gascity-packs/default` | Integration tip for packs and fragments |
| `gascity-packs/gastown-lazyjj.furiosa` | Worker workspace used for isolated editing and recovery |

### Collaboration Pattern

- The controller repo (`gascity/`) and the pack repo (`gascity-packs/`) are related but distinct.
- Packs are authored in `gascity-packs/`, then pushed from the `default` chain once they are clean.
- Worker workspaces are temporary and should be treated as staging areas for individual tasks, not as permanent branches.
- If a change belongs in the shared city model, it should land in the shared default chain so the runner and other agents can pick it up consistently.

### Workspace Map

| Workspace | Location | What it is for |
|-----------|----------|----------------|
| `gascity/default` | `./gascity/` | Controller integration head for code that runs the city itself |
| `gascity-packs/default` | `./gascity-packs/` | Shared pack integration head for pack fragments, commands, and formulas |
| `gascity-packs/gastown-lazyjj.furiosa` | `.gc/workspaces/gascity-packs/jedi/gastown-lazyjj.furiosa` | Worker workspace for isolated lazyjj work and recovery |

### How They Work Together

The city uses a simple chain:

1. A task lands in a worker workspace when an agent needs isolation.
2. The agent makes the smallest useful change there.
3. The change is rebased onto the `default@` tip in the repo that owns it.
4. The default workspace becomes the shared handoff point.
5. Origin and the runner pick up the default-chain commit, not the worker scratch commit.

For this city:

- controller changes belong in `gascity/default`
- pack changes belong in `gascity-packs/default`
- worker investigation and recovery happen in `gascity-packs/gastown-lazyjj.furiosa`

The important mental model is that a worker workspace is not another branch of truth. It is a place to shape a change before it is moved back into the default chain.

### Build Pipeline

```
doltlite C source              beads-doltlite Go source          gascity Go source
  ../configure && make            gc beads-doltlite build bd        gc beads-doltlite build gc
                                  GOFLAGS=-tags=libsqlite3
  doltlite-lib                    CGO_LDFLAGS=-ldoltlite           CGO_ENABLED=1
                                                                    GOFLAGS=-tags=gascity_doltlite_lib,libsqlite3
  → libdoltlite.so ──────────→  bin/bd                             → bin/gc
          └──────────────────────────────────────────────────────→  libdoltlite-linked binaries
```

1. Build `libdoltlite.so` from `dolthub/doltlite` with `make doltlite-lib`
2. Build `bd` from `duncan4123/beads-doltlite` with `gc beads-doltlite build bd`
3. Build `gc` from `gastownhall/gascity` with `gc beads-doltlite build gc` when direct libdoltlite-linked Gas City behavior is needed
4. `bd` binary provides beads CLI; Gas Town's `gc bd` commands shell out to it
5. Gas Town's `gc` binary embeds pack definitions (including the bd pack with `gc-beads-bd.sh` wrapper)
6. Pack updates are authored in `gascity-packs/` and rebased onto `default@` before they are published or pushed

The `gc beads-doltlite build` command is pack-managed. It still requires an existing `gc` binary to run the city and dispatch pack commands, then it builds libdoltlite-linked replacements to `<beads-doltlite>/bin/bd` and `<gascity>/bin/gc` by default. Use `gc beads-doltlite build all` for both binaries. Add `--install` to copy verified binaries to the existing supervisor unit's `gc` path when present, then to the active binary path when it is under `$HOME`, otherwise `$HOME/.local/bin`. Use `--install-dir`, `--bd-install`, and `--gc-install` to choose exact install paths.

Installing a rebuilt `bd` affects new `gc bd` calls as soon as that `bd` path is first on `PATH`. Installing a rebuilt `gc` affects new `gc` invocations immediately, but a running controller still uses the old in-memory binary until it is reloaded or restarted.

### Backend Architecture

- **Storage**: `libdoltlite.so` — embedded prolly-tree engine. Single `.db` file per database, no server process.
- **Pack layering**: `beads-doltlite` is not a replacement for the `bd` pack. It imports and exports `bd`, so normal beads provider operations still use the materialized `bd` pack's `gc-beads-bd.sh` wrapper.
- **Beads CLI**: `gc beads-doltlite build bd` rebuilds `bd` with `CGO_ENABLED=1`, `GOFLAGS=-tags=libsqlite3`, and `CGO_LDFLAGS=-ldoltlite`.
- **Gas City binary**: `gc beads-doltlite build gc` rebuilds `gc` with `CGO_ENABLED=1`, `GOFLAGS=-tags=gascity_doltlite_lib,libsqlite3`, and `CGO_LDFLAGS=-ldoltlite`. Do not use `gascity_native_beads` for this; upstream uses that tag for its pure-Go native beads path.
- **Gas Town integration**: `gc bd` commands delegate to `bd` via `gc-beads-bd.sh` wrapper script. The wrapper detects `BEADS_BACKEND=doltlite` and routes init/operations through doltlite-specific code paths. Optional native `gc` reads can bypass the CLI for selected hot paths, but writes and general `gc bd` behavior still go through `bd`.
- **No Dolt server**: No MySQL protocol, no port, no `dolt sql-server` process. The dolt pack is conditionally skipped when backend is doltlite (see `embed_builtin_packs.go`).

### Key Differences from Dolt-Backed Cities

| Aspect | Dolt (default) | Doltlite |
|--------|---------------|----------|
| Storage | Dolt SQL server (port 37282) | Embedded prolly-tree `.db` file |
| Beads init | `DOLT_COMMIT()` via MySQL | `dolt_commit()` via SQLite built-in |
| Pack auto-install | `dolt` pack included | `dolt` pack skipped |
| Formulas | `mol-dolt-health`, `mol-dolt-remotes-patrol` | `mol-doltlite-maintenance` |
| `--dolt-auto-commit` | Controls VCS commit timing | Same flag passed but doltlite ignores VCS semantics |

### Database Layout

```
.beads/
  metadata.json        → {"backend":"doltlite","database":"doltlite","dolt_database":"hq"}
  doltlite/
    hq.db              → Single-file prolly-tree database (city-level beads)
    .lock              → flock() sentinel for exclusive write access
  routes.jsonl         → Rig prefix routing

gascity/.beads/        → Rig-level beads store (same layout, database: gc.db)
beads-doltlite/.beads/ → Rig-level beads store
```

### Rig Status

| Rig | Prefix | Repo | Role |
|-----|--------|------|------|
| gascity | `gc-` | `gastownhall/gascity` | Gas Town source, CLI, and controller integration |
| gascity-packs | `pack-` | `gascity-packs` | Shared pack repository and published pack changes |
| beads-doltlite | `bd-` | `duncan4123/beads-doltlite` | Beads CLI with doltlite backend |
{{ end }}
