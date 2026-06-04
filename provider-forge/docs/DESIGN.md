# provider-forge — DESIGN

A gc (Gas City) pack that supplies the **canonical provider × model catalog** — the single,
machine-readable list of which `(provider, model)` pairs exist, what they cost, which
`run_target` each maps to, and which are runnable today. It is the **catalog + enablement +
effort layer** on top of gc's *existing* multi-provider routing primitives; it does not add a
new routing path.

- Schema: `provider-forge.v1` (`catalog.toml`).
- Status: catalog + read CLI. The CLI (`bin/forge`) and `pack.toml` are built alongside this
  doc by the sibling builder; this document specifies the data, the mechanism it rides on, and
  the two integration seams (model-advisor roster; cross-provider apply).

> **Scope guard.** This document specifies the catalog's data model and how it plugs into gc's
> routing, not the CLI's internals. It is precise enough that `bin/forge` can implement
> `list` / `doctor` / `roster` / `targets` against the schema, and that a reader can see exactly
> where provider-forge stops and gc-core begins.

---

## 0. One-paragraph summary

gc can already dispatch a unit of work to an arbitrary provider and model: each non-native
provider has a per-provider overlay that makes its CLI behave like a gc agent, and a dispatch
names its destination with three metadata keys — `gc.run_target`, `gc.provider`, `gc.model` —
the exact pattern core's `mol-review-quorum` formula uses to fan review lanes across providers.
What gc lacks is a registry of *which* `(provider, model)` triples are valid, runnable, and
priced. `catalog.toml` is that registry. From it, `bin/forge` answers three questions —
**what exists** (`list`), **what's actually wired** (`doctor`), and **what to stamp on a bead to
route there** (`targets`) — and **generates** model-advisor's cost-ordered `[[tier]]` roster
(`roster`) so the model list is maintained once. The catalog also records reasoning **effort**
per model, ready for a small gc-core seam that does not exist yet. provider-forge is declarative,
read-only, and additive: it owns *data*, gc-core owns *routing*, model-advisor owns *choice*.

---

## 1. The catalog schema (`catalog.toml`)

### 1.1 Top level

```toml
schema_version  = "provider-forge.v1"
default_provider = "claude"            # mirrors gc's [workspace] provider
```

`default_provider` records gc's native/default provider so surfaces can mark it and so the
roster generator knows which provider needs no overlay.

### 1.2 A provider table

```toml
[providers.<name>]
cli     = "<binary>"        # the executable forge doctor probes on PATH
overlay = "<name>"          # the gc per-provider overlay this provider uses (§2.1)
status  = "live" | "scaffold"
native  = true              # optional; true only for gc's default provider (Claude)
auth    = "~/path"          # optional; a file whose existence forge doctor checks
models_cache = "~/path"     # optional; provider-maintained model cache, informational
reasoning_levels  = [ ... ] # the effort dial this provider exposes; [] ⇒ flat (no dial)
default_reasoning = "medium" # provider-level effort default (when levels are non-empty)
```

| Field | Required | Meaning |
|-------|:--------:|---------|
| `cli` | yes | binary name `forge doctor` looks for on `PATH` |
| `overlay` | yes | the `core/overlay/per-provider/<overlay>/` gc ships for this provider |
| `status` | yes | `live` = CLI installed + authed, dispatchable now; `scaffold` = overlay exists, CLI/models not yet present |
| `native` | no | `true` for gc's default provider only; native providers need no overlay |
| `auth` | no | path whose presence indicates the CLI is authed (probed by `doctor`) |
| `models_cache` | no | provider-side model cache path; informational |
| `reasoning_levels` | yes | ordered effort options (e.g. `["low","medium","high","xhigh"]`); `[]` means the provider has no effort dial |
| `default_reasoning` | no | provider default effort; per-model `default_reasoning` overrides it |

### 1.3 A model entry

```toml
[[providers.<name>.models]]
id      = "<handle>"        # short, human handle (unique within the provider)
model   = "<concrete-id>"   # the exact model string → bead gc.model
context = 272000            # token context window
in_cost  = 2.50             # $/MTok input
out_cost = 10.00            # $/MTok output
run_target = "<target>"     # the gc run target → bead gc.run_target
default_reasoning = "high"  # optional; per-model effort (advisory; see §4)
note    = "free text"       # optional; one-line hint
exclude_from_roster = true  # optional; keep this model out of the generated [[tier]] roster (§5)
```

| Field | Required | Meaning |
|-------|:--------:|---------|
| `id` | yes | short handle, unique per provider; labels the model in `forge list` / `targets` |
| `model` | yes | concrete model string the provider CLI uses; becomes `gc.model` |
| `run_target` | yes | the configured gc target that runs it; becomes `gc.run_target` |
| `context` | yes | context-window size (tokens) |
| `in_cost` / `out_cost` | yes | rate sheet in `$/MTok`; the basis for cost-ordering the roster |
| `default_reasoning` | no | per-model effort default (advisory until §4's seam lands) |
| `note` | no | free-text hint surfaced by `forge list` |
| `exclude_from_roster` | no | `true` ⇒ omit from `forge roster` output (specialized models, e.g. an auto-review model) |

### 1.4 Invariants

- `run_target` values are unique across the whole catalog (one target ⇒ one `(provider, model)`).
- `model.id` is unique within its provider; `(provider, id)` is globally unique.
- A `live` provider should have ≥ 1 model; a `scaffold` provider may have zero (model lists are
  filled in when the provider is enabled).
- Costs are `$/MTok`; they need only be *ordinally* correct to cost-order the roster, but should
  be replaced with real figures where they are estimates (Codex — see §7).
- `reasoning_levels = []` ⇒ the provider has no effort dial; any per-model `default_reasoning`
  is then meaningless and should be omitted (e.g. Claude tiers are flat).

---

## 2. How gc's multi-provider mechanism works

provider-forge adds **no** routing. It is worth stating precisely what it rides on, because the
catalog's whole value is being the registry for these two primitives.

### 2.1 Per-provider overlays

For each **non-native** provider, gc ships an overlay at
`.gc/system/packs/core/overlay/per-provider/<provider>/`. The overlay teaches that provider's
*own* CLI to participate in the gc lifecycle by writing into the CLI's native hook surface — e.g.
the Codex overlay is `.codex/hooks.json` mapping:

- `SessionStart → gc prime --hook --hook-format codex`
- `UserPromptSubmit → gc nudge drain --inject` and `gc mail check --inject`
- `PreCompact → gc handoff --auto`

Each provider's overlay targets its native format: `.codex/hooks.json` (codex),
`.cursor/hooks.json` (cursor), `.gemini/settings.json` (gemini), `.github/…` (copilot),
`AGENTS.md` + `.kiro/…` (kiro), `.omp/hooks/gc-hook.ts` (omp), `.opencode/plugins/…` (opencode),
`.pi/extensions/…` (pi). gc ships overlays for **eight** providers: **codex, copilot, cursor,
gemini, kiro, omp, opencode, pi**.

**Claude is the native provider and has no overlay.** Its model is selected by the agent `model`
config field, which gc resolves and exports to the session as `GC_AGENT_MODEL`; the Claude
adapter is built in. (The catalog still records `overlay = "claude"` as a label for symmetry, but
no such overlay directory is shipped — Claude needs none. `doctor` treats native providers
accordingly.)

The overlay is the precondition for "run this work on provider X" to mean anything: without it,
gc has no way to make that CLI behave like one of its agents.

### 2.2 Per-dispatch metadata: the routing triple

A dispatch carries metadata. Three keys name **where it runs**:

| Key | Value | Constraint |
|-----|-------|------------|
| `gc.run_target` | the configured gc target/agent that executes the step | must be a real target |
| `gc.provider` | provider identifier | must be native, or have an overlay (§2.1) |
| `gc.model` | the concrete model string | must be valid for that provider |

A formula step (or a work bead) sets these in its `metadata` map. gc routes the step to the named
target; the provider/model travel with it. (`gc.model` reaches the provider via `GC_AGENT_MODEL`
on the per-agent path; the per-dispatch binding of bead-`gc.model` at spawn is the gc-core seam
model-advisor is wiring — §6.2.)

### 2.3 The precedent: `mol-review-quorum`

Core's `mol-review-quorum` formula (`.gc/system/packs/core/formulas/mol-review-quorum.toml`,
`contract = "graph.v2"`) is the canonical demonstration. It takes per-lane variables —
`lane_one_provider`, `lane_one_model`, `lane_one_target` (and the same for lane two) — and stamps
each reviewer step:

```toml
# step "review-lane-one"
metadata = { "gc.run_target" = "{{lane_one_target}}",
             "gc.provider"   = "{{lane_one_provider}}",
             "gc.model"      = "{{lane_one_model}}",
             "gc.review_quorum_lane" = "{{lane_one_id}}",
             "gc.reviewer_model"     = "{{lane_one_model}}",
             "gc.output_json_schema" = "review-quorum.lane.v1",
             "gc.output_json_required" = "true" }
```

Lane two gets a *different* triple; a third step (`synthesize-review-quorum`,
`needs = [lane-one, lane-two]`) routes to `synthesis_target` and combines the two durable
outputs. The result: one review fanned across two independent providers/models, synthesized by a
third — using nothing but the metadata triple. **This is the multi-provider routing pattern in
its entirety.** provider-forge exists only to make the lane variables *answerable*: which
`lane_one_provider` / `lane_one_model` / `lane_one_target` values are valid, live, and priced.

---

## 3. The run_target model

A `run_target` is gc's stable name for "a configured place a step can run." In the catalog it is
the join key between an abstract model and a concrete dispatch:

```
(provider, model)  ──catalog──►  run_target  ──gc──►  a spawned session on that provider+model
```

- The catalog declares the mapping `(provider, model) → run_target` (one-to-one, §1.4).
- A dispatch references it as `gc.run_target` and pairs it with `gc.provider` + `gc.model`.
- `forge targets` is the lookup: it lists every live `{ run_target, provider, model }` triple —
  pick the row for the model you want and stamp those three values on a step, i.e. exactly the
  values §2.3 puts in a formula's `metadata`. (`--json` makes the pick scriptable.)

`run_target` is intentionally a *name*, not a spawn recipe: provider-forge does not own how gc
realizes a target into a session (that is gc-core's launcher). It owns the **catalog of valid
names** and their model/cost/effort facts. This keeps the boundary clean — provider-forge is data
about routing, never the act of routing.

---

## 4. The effort gap and the gc-core seam it needs

Reasoning **effort** is a per-model dial on some providers — Codex exposes
`low` / `medium` / `high` / `xhigh`. The catalog captures it (`reasoning_levels` on the provider,
`default_reasoning` on the provider and per model) because the *right* effort is part of a model's
identity for routing (e.g. `spark` wants `high`).

**But gc has no effort path today.** The launcher forwards the model (resolved agent `model` →
`GC_AGENT_MODEL`), and the Codex adapter is even seen to build `--model … --effort …` argv — but
nothing carries a *non-default* effort from a dispatch through to that argv. There is no agent
config field for it and no metadata key gc consumes for it. So:

> **Effort is advisory.** The `reasoning_levels` / `default_reasoning` fields document the
> intended effort and let surfaces display it, but provider-forge cannot *enforce* a non-default
> effort. The model runs at the provider's own default.

**The seam needed** is small and the *same shape* as model-advisor's per-dispatch ask: have gc
forward a routing field from the dispatch to the provider CLI. Concretely, either

1. a metadata key (e.g. `gc.reasoning` / `gc.effort`) that the launcher reads off the routed bead
   and forwards to the provider adapter's `--effort` argv (mirroring how `gc.model` →
   `GC_AGENT_MODEL` would bind at spawn), or
2. an agent/dispatch config field that resolves into the adapter argv the way `model` resolves
   into `GC_AGENT_MODEL`.

Both are localized: the adapter *already* accepts `--effort`; what is missing is the wire from a
dispatch to it. The day that lands, the catalog's effort fields become enforceable with no schema
change. (Tracked as a gc-core PR alongside model-advisor's per-dispatch binding.)

---

## 5. The model-advisor integration (catalog → roster)

[`model-advisor`](../model-advisor) recommends the cost-minimal model tier per `(agent, shape)`.
Its decision rule needs a cost-ordered `[[tier]]` roster — each tier a `(provider, model)` run
target with a cost rank. That roster is the **same list** as the catalog, projected. Maintaining
two copies guarantees drift, so the catalog is the source and `forge roster` is the generator.

**`forge roster` algorithm:**

1. Collect every model under every `status = "live"` provider.
2. Drop any model with `exclude_from_roster = true` (specialized models — e.g. an auto-review
   model — that should not be in a general roster).
3. Order the remainder by cost (a blended `in_cost`/`out_cost` measure, cheapest → dearest) and
   assign `rank`.
4. Emit a `[[tier]]` block in model-advisor's config shape — for each tier: `id` (from model
   `id`), `provider`, `model` (concrete), `run_target`, `in_cost`, `out_cost`, `rank`.
5. Print to stdout, or write to a file with `--out FILE` (it writes *advisor* config, never the
   catalog).

So the maintenance loop is: edit `catalog.toml` (add a model, fix a price, flip a provider to
`live`) → `forge roster --out …` → model-advisor's roster is current. One edit, one place.

> **Scaffold providers are excluded automatically** — only `live` models reach the roster, so
> model-advisor never ranks a tier you cannot actually dispatch to. As you enable a scaffold
> provider (install CLI, fill models, set `live`), re-running `forge roster` folds it in.

---

## 6. The dispatch integration (advisor → cross-provider apply)

### 6.1 The division of labor

```
provider-forge          model-advisor              gc core
──────────────          ─────────────              ───────
catalog of valid    →   chooses the cheapest   →   carries the choice as the
(provider, model)       tier that credibly         routing triple on a bead
run targets + costs     preserves quality          (gc.run_target/provider/model)
```

Each pack owns one layer and reimplements nothing of the others. provider-forge supplies the
*vocabulary* (which triples exist), model-advisor makes the *choice*, gc's metadata mechanism
(§2) carries it.

### 6.2 Cross-provider apply is the routing triple

model-advisor's roster (§5) can include tiers on *different providers*. When it recommends a tier
that is not the agent's current provider, applying it is exactly the §2.3 pattern: set
**`gc.provider` / `gc.model` / `gc.run_target`** on the work bead. Those three values are precisely
the `forge targets` row for that model. So a cross-provider apply is:

1. model-advisor recommends tier *T* (provider *P*, model *M*).
2. `forge targets` → pick the row whose `provider`/`model` is *P*/*M* → `{ run_target, provider, model }`.
3. Stamp that triple on the work bead's metadata — the per-dispatch routing model-advisor is
   wiring to gc-core's spawn seam (the launcher binding a routed bead's `gc.model` →
   `GC_AGENT_MODEL` at spawn; the same seam family as §4's effort wire).

provider-forge does not perform the apply (it mutates nothing). It guarantees the triple
model-advisor stamps is *valid and live* — that is its contribution to the dispatch path.

---

## 7. Live vs scaffold, and the honest edges

- **Live:** `claude` (native; model via `GC_AGENT_MODEL`) and `codex` (CLI + auth present). These
  are dispatchable now and populate the roster.
- **Scaffold:** `gemini, copilot, cursor, kiro, omp, opencode, pi`. gc ships their overlays
  (§2.1), so the *routing* half is ready, but each needs its CLI installed, its models filled into
  the catalog, and `status` flipped to `live`. Their model arrays are intentionally empty; fill
  them from each provider's docs on enablement. `forge list --all` surfaces which providers are
  still scaffold; once one is set `live`, `forge doctor` then checks whether its CLI + auth are
  actually present.
- **Codex costs are estimates.** Codex `in_cost`/`out_cost` are placeholders — ordinally fine for
  ranking, not invoice-accurate. Replace with a real rate sheet.
- **The catalog is curated, not scraped.** provider-forge does not poll provider APIs for new
  models or live prices. `doctor` checks *enablement* (CLI + auth), not upstream model existence
  or price currency.

---

## 8. Surfaces (CLI) — contract

`bin/forge` (built by the sibling builder). All reads; `roster` writes only with `--out`. Every
command supports `--json`.

| Command | Reads | Emits |
|---------|-------|-------|
| `forge list [--all] [--json]` | catalog | table: provider, model, run_target, costs, context, effort, status (**live by default**; `--all` adds scaffolds) |
| `forge doctor [--json]` | catalog + filesystem (`cli` on `PATH`, `auth` exists) | per live provider: `ready` / `missing-cli` / `missing-auth` (no-`auth` ⇒ authed-by-other-means) |
| `forge roster [--out FILE] [--provider P…]` | catalog (live, non-excluded) | model-advisor `[[tier]]` block, cost-ordered (§5) |
| `forge targets [--json]` | catalog (live) | the `{ run_target, provider, model }` rows to stamp (§3, §6.2) |

Degradation: `list`/`targets` are pure reads of the catalog; `doctor` is the only one that touches
the filesystem and degrades to a `missing-cli` / `missing-auth` status (and a non-zero exit) rather
than erroring when a CLI or auth file is absent; `roster` is a pure generator and never reads
outside the catalog.

---

## 9. Acceptance (what "implements this doc" means)

- `catalog.toml` validates against §1 (schema_version, provider tables, model arrays, invariants).
- `forge list` shows live catalog entries with costs/context/effort; `--all` adds scaffolds.
- `forge doctor` classifies each **live** provider as `ready` / `missing-cli` / `missing-auth` by
  probing `cli` on `PATH` and `auth` existence (a provider with no `auth` is authed-by-other-means,
  e.g. Claude's native session).
- `forge targets` lists the exact `{ run_target, provider, model }` rows §2.3 stamps, for every
  live model.
- `forge roster` emits a cost-ordered `[[tier]]` block from live, non-`exclude_from_roster` models
  that model-advisor consumes unchanged; `--out` writes advisor config only.
- No surface dispatches, spawns a session, mutates a bead, or edits agent config. Routing remains
  gc-core's (§2); choice remains model-advisor's (§5–§6).
