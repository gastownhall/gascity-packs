---
name: map-blast-radius
description: Map the full impact surface of a change to gastownhall/gascity before you commit — callers and their execution contexts (startup/tick/reload/CLI/API/shutdown), downward callees and their risky patterns (stale config, swallowed store errors, leaked goroutines), config-field sync chains, the domain-boundary crossings, concurrency, and cross-repo contracts (gastown/beads). Self-contained — runs on plain git + grep + gh, no internal tooling. Dual-use — Phase 2 of the plan-implementation skill, and a standalone impact map (scoping a refactor, ad-hoc impact mapping, mapping a change for someone else). Use before committing anything that touches the reconciler, controller, lifecycle, dispatch, config, or any cross-subsystem code.
---

# Map the Blast Radius

You are working on a change to
[gastownhall/gascity](https://github.com/gastownhall/gascity) and need to know
what it ripples to before you commit. A narrow-looking change can run on a config
reload, leak a goroutine in a CLI path, or read stale config — the failures a
maintainer's adoption review catches. This skill maps the surface so you catch
them first.

Run it from your local checkout. It uses only `git`, `grep`, and `gh` — no
special index required. (If you've run `codegraph init` in the repo, its
`codegraph_callers` / `codegraph_impact` are faster than grep for caller traces;
fall back to grep when it returns nothing or the call is dynamic.)

> `main` below means the upstream main you're targeting — `origin/main` if origin
> is `gastownhall/gascity`, else `upstream/main`.

## Step 1 — Enumerate touched functions

```bash
git diff main...HEAD --stat
git diff main...HEAD -- '*.go' | grep '^[+-]func ' | grep -v _test.go
```

Record each new/modified function: package, name, exported/unexported.

## Step 2 — Map callers (upward)

For each touched function, find who calls it:

```bash
grep -rn 'FunctionName(' cmd/gc/ internal/ --include='*.go' | grep -v _test.go
```

Classify every caller into an execution context — the context determines the risk:

| Context | Characteristics | Key concern |
|---|---|---|
| `newCityRuntime` | Runs once at startup | Safe for one-time sweeps |
| `controller tick` | Runs every ~30s in the reconcile loop | Must be fast and idempotent |
| `tryReloadConfig` / `update()` | Runs on config-file change | Reading `cs.cfg` directly sees the PREVIOUS config |
| `buildStores(cfg)` | Called from `update()` before the `cs.cfg` swap | Must use the passed `cfg`, not `cs.cfg` |
| `cobra RunE` | CLI one-shot | Process exits after return — goroutines die |
| `API handler` | Long-lived HTTP server | Fire-and-forget goroutines OK |
| `buildOrderDispatcher` | Startup AND reload | No one-time operations here |
| `gracefulStopAll` | Shutdown path | Two-pass: interrupt then force-kill |

## Step 3 — Map callees (downward)

Read each modified function body and trace what it calls. Flag:

- **`cs.cfg` reads** inside anything called from `update()` → stale-config risk (B21)
- **`store.SetMetadata*` / `store.Close` / `store.Create`** → errors must propagate (B12)
- **`shellCommand` / `exec.Command`** → is the timeout shared with another subsystem? (B13)
- **`go func()`** → is the caller a CLI path? Then it needs a completion signal (B17)

## Step 4 — Config-field impact

If the change adds or modifies a config field, verify it appears in **all** of
these — a missing one is a silent drop:

```bash
grep -rn 'FieldName' internal/config/ cmd/gc/ --include='*.go' | grep -v _test.go
```

- `config.Agent` struct
- `config.AgentPatch` struct
- `config.AgentOverride` struct
- `applyAgentPatch()`
- `applyAgentOverride()`
- `poolAgents()` deep-copy in `cmd/gc/pool.go`
- `ApplyAgentDefaults()` if there's a city-wide default
- `Effective*()` accessor if the nil/empty distinction matters (B11)

`TestAgentFieldSync` catches the struct definitions only — the apply functions
and the pool deep-copy must be checked by hand.

## Step 5 — Domain-boundary crossings

Check whether the change crosses any of these boundaries:

| Boundary | Risk |
|---|---|
| Pool agents ↔ named-session agents | Map keys leak; scale checks count both? (B18) |
| User agents ↔ infrastructure agents | Loops applying work config to `control_dispatcher` (B15) |
| Startup path ↔ reload path | One-time ops in the reload path corrupt in-flight goroutines (B16) |
| CLI path ↔ server path | Goroutine lifecycle differs (B17) |
| Config snapshot ↔ live config | `update()`-chain functions read stale `cs.cfg` (B21) |
| Reconciler tick ↔ background goroutines | Shared semaphores/timeouts with unintended scope (B13) |

## Step 6 — Concurrency

If the change involves goroutines, semaphores, or shared state:

```bash
git diff main...HEAD -- '*.go' | grep -E 'go func|\.Lock\(|\.RLock\(|<-|chan '
```

- New goroutine in a CLI path → does it return a completion signal? (B17)
- New semaphore → does it bound exactly the right set of operations? (B13)
- Package-level mutable state written by reload → `atomic.*` / mutex? (B30)
- Shared state guarded by the right mutex (e.g. `serviceStateMu`)?

## Step 7 — Cross-repo impact

Gas City extracts subsystems from `gastownhall/gastown`, depends on
`gastownhall/beads`, and uses `dolthub/dolt` as its storage engine. If your
change touches a contract that spans repos, check it:

- **Beads interface** — if you touch bead-store operations (`Create`,
  `SetMetadata`, `Query`, `Close`), confirm against `gastownhall/beads` that the
  interface contract still holds. Browse the repo on GitHub or
  `gh search code --repo gastownhall/beads '<symbol>'`.
- **Gastown original behavior** — for extracted code, check how `gastownhall/gastown`
  handled the same path. Classify a divergence as `[extraction bug]` (gascity
  broke something gastown gets right), `[inherited]` (gastown has the same
  limitation), or `[intentional divergence]` (document why).
- **Upstream drift** — has gastown/beads/dolt changed recently in this area?
  `gh search commits --repo gastownhall/gastown '<area-keyword>'`. Flag if gascity
  may need to pull in an upstream fix.

## Step 8 — Report

```
Blast Radius — <branch>

Changed functions:
  <pkg>.<Func> — <one-line summary>

Execution contexts:
  <Func> called from: startup / tick / reload / CLI / API / shutdown

Upward callers:
  <Func> ← <caller1> ← <caller2> (context: reload path)

Downward callees:
  <Func> → store.SetMetadata (must propagate error)
  <Func> → go func() (CLI path — needs completion gate)

Config field chain: complete / MISSING <which step>

Domain boundary crossings:
  Pool ↔ named-session    : safe / RISK: <detail>
  User ↔ infra agents     : safe / RISK: <detail>
  Startup ↔ reload        : safe / RISK: <detail>
  CLI ↔ server            : safe / RISK: <detail>
  Snapshot ↔ live config  : safe / RISK: <detail>
  Tick ↔ background        : safe / RISK: <detail>

Concurrency:
  Goroutines: none / N spawned, completion signals: yes/no
  Semaphores: none / scoped to: X subsystem only
  Shared state: none / protected by: <mutex>

Cross-repo:
  Beads interface : compatible / DIVERGES: <detail>
  Gastown original: matches / [extraction bug] / [inherited] / [intentional divergence]
  Upstream drift  : none recent / NEEDS SYNC: <detail>

Risk summary:
  HIGH: <anything a maintainer would call a "major">
  MED:  <anything a maintainer would call a "minor">
  LOW:  <nits, style>

Recommendation: PROCEED / FIX BEFORE COMMIT
```

Keep findings to one line each, with a `file:line` ref. The HIGH/MED items feed
the `Risks` section of your [`plan-implementation`](../plan-implementation/SKILL.md)
plan and the audit in [`review`](../review/SKILL.md).

## When to use

This skill is **dual-use** — a phase of a parent skill AND a standalone utility:

- As **Phase 2 of [`plan-implementation`](../plan-implementation/SKILL.md)**,
  before you write code.
- **Standalone**, for ad-hoc impact mapping — before committing a change that
  touches the reconciler, controller, or lifecycle code; when a change spans
  multiple subsystems (config + runtime, beads + dispatch); when you're unsure
  whether a function runs on startup only or also on reload; when scoping a
  refactor or mapping a change for someone else.
