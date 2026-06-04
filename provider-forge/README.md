<div align="center">

# `provider-forge`

### The canonical provider × model catalog for Gas City

Gas City already knows how to send a dispatch to a *different provider and model* — the
routing primitives are in core. What it lacks is a single, machine-readable answer to
**which `(provider, model)` pairs exist**, what they cost, which `run_target` each maps to,
and which ones are actually runnable right now. **provider-forge** is that catalog — one
source of truth that powers enablement checks, builds run targets for cross-provider
dispatch, and **generates [`model-advisor`](../model-advisor)'s tier roster** so the model
list is maintained in exactly one place.

[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Gas City](https://img.shields.io/badge/Gas_City-pack-0f766e?style=flat-square)]()
[![Layer](https://img.shields.io/badge/adds-catalog_·_enablement_·_effort-0f766e?style=flat-square)]()
[![Routing](https://img.shields.io/badge/builds_on-gc.run__target_·_overlays-6d28d9?style=flat-square)]()
[![Source of truth](https://img.shields.io/badge/roster-generated_from_catalog-6d28d9?style=flat-square)]()
[![Providers](https://img.shields.io/badge/providers-2_live_·_7_scaffold-c2410c?style=flat-square)]()
[![Schema](https://img.shields.io/badge/schema-provider--forge.v1-444?style=flat-square)]()
[![No new routing](https://img.shields.io/badge/reinvents_routing-no-555?style=flat-square)]()

[**What it is**](#what-it-is) ·
[**The mechanism**](#the-mechanism-it-builds-on) ·
[**The catalog**](#the-catalog) ·
[**The surfaces**](#the-surfaces) ·
[**Install**](#install--uninstall) ·
[**model-advisor**](#model-advisor-integration) ·
[**Caveats**](#caveats)

</div>

---

## The gap

Routing across providers is a *solved* problem in gc. The core formula
[`mol-review-quorum`](#the-mechanism-it-builds-on) fans two read-only review lanes out to two
**different** providers and models, then routes a third agent to synthesize them — and it does
this today, with no extra machinery, by stamping `gc.run_target` / `gc.provider` / `gc.model`
onto each step bead. The lever exists. The metadata keys exist. The per-provider overlays that
make a non-native CLI behave like a gc agent exist.

What does *not* exist is the **list**. To send a lane to "the cheapest Codex coding model" you
have to already know that it is `gpt-5.3-codex-spark`, that it maps to the `codex-spark` run
target, that the Codex CLI is installed and authed, that it wants `reasoning = high`, and that
it costs roughly $0.50/$2.00 per MTok. That knowledge lives in people's heads and in scattered
config. Worse, [`model-advisor`](../model-advisor) needs the *same* list — its cost-ordered
`[[tier]]` roster — and maintaining two copies guarantees they drift.

provider-forge fills exactly that gap and nothing more. It is the **catalog + enablement +
effort layer** on top of gc's existing routing. It does **not** reinvent routing, ship a new
dispatch path, or wrap `gc sling`.

## What it is

A small, declarative pack built around one file — `catalog.toml` — plus a read-only CLI
(`bin/forge`) that interrogates it. The catalog enumerates every provider gc can target and,
for each, the concrete models, their costs and context limits, their reasoning-effort
options, and the `run_target` each `(provider, model)` resolves to. The CLI turns that data
into the three things a human or an agent actually needs:

| You want… | provider-forge gives you |
|-----------|--------------------------|
| **to know what exists & what's runnable** | `forge list` — the catalog, live vs scaffold, costs, effort |
| **to know what's actually wired up** | `forge doctor` — CLI-installed + auth checks per provider |
| **to dispatch to a specific provider+model** | `forge targets` — every live `run_target` / `gc.provider` / `gc.model` triple to stamp on a bead |
| **to keep model-advisor's roster current** | `forge roster` — emits the cost-ordered `[[tier]]` block from the catalog |

It is **all reads and one generator**. provider-forge never spawns a session, never mutates a
bead, never edits an agent's config. It tells you the facts; you (or `model-advisor`, or a
formula) act on them.

## The mechanism it builds on

provider-forge is deliberately thin because gc already carries the load. Two core primitives do
the actual work of multi-provider routing:

**1. Per-provider overlays.** For each non-native provider, gc ships an overlay under
`.gc/system/packs/core/overlay/per-provider/<provider>/` that teaches that provider's CLI to
behave like a gc agent — wiring its native hook surface to the gc lifecycle (`gc prime` on
session start, `gc nudge drain` / `gc mail check` on prompt submit, `gc handoff` on compaction).
Today gc ships overlays for **codex, copilot, cursor, gemini, kiro, omp, opencode, pi** — eight
providers. (Claude is gc's *native* provider; it needs no overlay — its model is selected by the
agent `model` config field, exported to the session as `GC_AGENT_MODEL`.) The overlay is what
makes "run this work on Codex" mean something to gc at all.

**2. Per-dispatch metadata: `gc.run_target` / `gc.provider` / `gc.model`.** A dispatch carries
metadata, and three keys name *where it should run*:

- `gc.run_target` — the configured gc agent/target that executes the step,
- `gc.provider` — the provider identifier (must have an overlay, or be native),
- `gc.model` — the concrete model the provider should use.

The precedent is core's own [`mol-review-quorum`](#) formula. Each reviewer lane sets, verbatim:

```toml
# review-lane-one — stamped onto the step bead by the formula
metadata = { "gc.run_target" = "{{lane_one_target}}",
             "gc.provider"   = "{{lane_one_provider}}",
             "gc.model"      = "{{lane_one_model}}",
             "gc.reviewer_model" = "{{lane_one_model}}", … }
```

Lane one and lane two get *different* `(target, provider, model)` triples, so the same review
runs on two independent providers and a third agent synthesizes the quorum. **That is the entire
multi-provider routing pattern**, and it is already in the box. provider-forge's job is only to
tell you *which triples are valid* — which `lane_one_provider` / `lane_one_model` /
`lane_one_target` values are real, runnable, and cost what.

> **The honest seam.** The metadata is consumed end-to-end for `provider`/`model`/`run_target`.
> Reasoning **effort** (Codex's `low`/`medium`/`high`/`xhigh`) is the one field with no plumbing
> yet — see [Caveats](#caveats). provider-forge *records* the right effort per model so it is
> ready the day gc grows the seam to forward it.

## The catalog

`catalog.toml` (`schema_version = "provider-forge.v1"`) is the source of truth. Each provider is
a table; each model is an array entry under it.

```toml
default_provider = "claude"            # gc's [workspace] provider

[providers.codex]
cli  = "codex"                         # the binary forge doctor probes
overlay = "codex"                      # the gc per-provider overlay it uses
status = "live"                        # "live" = CLI installed + authed; "scaffold" = overlay only
auth = "~/.codex/auth.json"            # checked by forge doctor
reasoning_levels   = ["low", "medium", "high", "xhigh"]
default_reasoning  = "medium"

[[providers.codex.models]]
id    = "spark"                        # short handle
model = "gpt-5.3-codex-spark"          # the concrete model → gc.model
context = 128000
default_reasoning = "high"             # advisory until the effort seam lands
in_cost  = 0.50                        # $/MTok in   (Codex costs are ESTIMATES)
out_cost = 2.00                        # $/MTok out
run_target = "codex-spark"             # → gc.run_target
note  = "ultra-fast coding"
```

The shape in one glance:

| Field | On | Meaning |
|-------|----|---------|
| `cli`, `overlay`, `status`, `auth` | provider | what to probe, which gc overlay, live/scaffold, where auth lives |
| `reasoning_levels`, `default_reasoning` | provider | the effort dial this provider exposes (empty ⇒ flat, e.g. Claude) |
| `id`, `model`, `run_target` | model | the handle, the concrete `gc.model`, and its `gc.run_target` |
| `context`, `in_cost`, `out_cost` | model | token limit and the rate sheet (`$/MTok`) |
| `default_reasoning`, `note` | model | per-model effort default; free-text hint |
| `exclude_from_roster` | model | set true to keep a specialized model out of the generated `[[tier]]` roster |

Editing one model — adding a row, fixing a price, flipping a provider `live` — updates every
surface at once: what `forge list` shows, what `forge targets` will hand a formula, and the
roster `forge roster` regenerates for model-advisor.

## The surfaces

`bin/forge` is shipped by this pack (the sibling builder writes `pack.toml` + `bin/forge`). Four
subcommands, all reads except where noted; every one takes `--json` for programmatic use.

| Command | Does | Mutates? |
|---------|------|----------|
| `forge list [--all] [--json]` | the catalog as a table — providers, models, costs, context, effort; **live by default**, `--all` adds scaffolds | no |
| `forge doctor [--json]` | enablement: for each live provider, is the `cli` on `PATH`? does `auth` exist? → `ready` / `missing-cli` / `missing-auth` | no |
| `forge roster [--out FILE] [--provider P…]` | emit model-advisor's cost-ordered `[[tier]]` block from the catalog (stdout, or write a file) | no* |
| `forge targets [--json]` | every live `gc.run_target` / `gc.provider` / `gc.model` triple — the dispatch lookup table | no |

\* `roster` is a pure generator; it only writes if you pass `--out` (and then it writes
*advisor* config, never the catalog).

```bash
forge list                            # what can I actually run right now? (live; --all for scaffolds)
forge doctor                          # are my live providers truly wired? (CLI on PATH? auth present?)
forge targets                         # the run_target / provider / model rows to stamp on a bead
#   RUN TARGET     PROVIDER   MODEL
#   codex-gpt54    codex      gpt-5.4
#   …
forge roster --out ../model-advisor/advisor.tiers.toml   # regenerate the tier list
```

`list` / `doctor` / `targets` are read-only and side-effect-free; they never dispatch or touch a
bead. `targets` is the bridge to the [mechanism above](#the-mechanism-it-builds-on): it lists the
`{ run_target, provider, model }` rows — pick the one for the model you want and stamp exactly
those three values onto a step, the way `mol-review-quorum` (or any graph formula) does. (`--json`
makes that pick scriptable.)

## Install & uninstall

provider-forge is a declarative, in-tree pack — a catalog and a read CLI. It carries no engine,
no venv, no hooks; importing it is just registering it so its skill is discovered and `bin/forge`
is on hand. Following the gas-town convention for a local pack, it imports via a **direct config
entry**, not `gc import add`:

```bash
# whole town
#   add to the city-root pack.toml:
#     [imports.provider-forge]
#     source = "packs/provider-forge"
#   (optional) opt the skill in city-wide:
#     city.toml  global_fragments += "use-provider-forge"
gc reload

# one rig
#   add under the matching [[rigs]] in city.toml:
#     [rigs.imports.provider-forge]
#     source = "packs/provider-forge"
gc reload
```

`gc reload` makes the `use-provider-forge` skill discoverable (by directory convention — see the
[skill](skills/use-provider-forge/SKILL.md)); verify with `gc skill list` (it appears
binding-qualified, e.g. `provider-forge.use-provider-forge`). To uninstall, drop the import block
(and any `global_fragments` entry) and `gc reload`. Nothing else is materialized, so removal is a
config revert — the pack mutates no projected settings and no agent config.

## model-advisor integration

provider-forge and [`model-advisor`](../model-advisor) are two halves of one story:
**provider-forge owns *what models exist and cost*; model-advisor owns *which one to use*.** The
seam between them is the roster.

- **Catalog → roster (maintain the list once).** model-advisor's decision rule needs a
  cost-ordered `[[tier]]` roster — its `(provider, model)` run targets ranked cheapest→dearest.
  Rather than hand-maintain that beside the catalog, `forge roster` **generates** it: it reads
  every `live` provider's models (skipping any `exclude_from_roster = true`), orders them by cost,
  and emits the `[[tier]]` block (or writes it with `--out`). One edit to `catalog.toml`, one
  `forge roster`, and the advisor's roster is current. No drift.

- **Advisor → cross-provider apply.** When model-advisor recommends a tier that lives on a
  *different* provider, *applying* it is exactly the [routing pattern above](#the-mechanism-it-builds-on):
  set `gc.provider` / `gc.model` / `gc.run_target` on the work bead (the per-dispatch path
  model-advisor is wiring to the gc-core spawn seam) — and those three values come straight from
  the catalog via `forge targets`. provider-forge supplies the *vocabulary*; model-advisor makes
  the *choice*; gc's metadata mechanism carries it.

The division of labor: **catalog (provider-forge) → recommendation (model-advisor) → dispatch
metadata (gc core).** Neither pack reimplements the other's job, and neither reimplements routing.

## Caveats

Honest about the scope line.

- **Live vs scaffold providers.** Only **codex** and **claude** are *live* — CLI installed and
  authed, runnable now. The other seven gc providers (**gemini, copilot, cursor, kiro, omp,
  opencode, pi**) ship as **scaffolds**: gc *has* their per-provider overlays, but each needs its
  CLI installed, its models filled into `catalog.toml`, and `status` flipped to `live` before it
  can be dispatched to. `forge list --all` shows which providers are still scaffold; once you set
  one `live`, `forge doctor` then verifies its CLI + auth are actually wired. The scaffold model
  lists are intentionally empty — fill them from each provider's own docs when you enable it.

- **Effort enforcement is pending a gc-core seam.** Reasoning **effort** (Codex's
  `low`/`medium`/`high`/`xhigh`) is captured per model in the catalog, but gc has **no effort
  path today** — the launcher forwards `gc.model` (via `GC_AGENT_MODEL`) but nothing forwards a
  non-default effort to the provider CLI. So the `reasoning` / `default_reasoning` fields are
  **advisory** until a small gc-core change lands to forward them — the **same shape** as
  model-advisor's per-dispatch gc-core ask (bind a bead's routing metadata at spawn). The catalog
  records the right effort now so it is ready the day the seam exists.

- **Codex costs are estimates.** The `in_cost` / `out_cost` figures for Codex models are
  **placeholders**, not a billed rate sheet — replace them with your real numbers. They are
  good enough to *cost-order* the roster; they are not invoice-accurate.

- **Catalog is declarative, not auto-discovered.** provider-forge does not scrape provider APIs
  for new models or live prices. It is a curated file you maintain. `forge doctor` verifies
  *enablement* (CLI + auth); it does not verify that a model ID still exists upstream or that a
  price is current.

- **It catalogs; it does not route.** provider-forge adds the missing data layer. The actual
  dispatch is gc's: the overlays, the `gc.run_target` / `gc.provider` / `gc.model` metadata, and
  formulas like `mol-review-quorum` that stamp them. provider-forge never wraps `gc sling`, never
  spawns a session, and never edits agent config.

## License

MIT © Jay German. See [LICENSE](LICENSE).
