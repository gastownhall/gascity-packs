---
name: use-provider-forge
description: Dispatch work to a specific provider and model, and know which (provider, model) pairs are real and runnable. Before routing a step to a non-default provider/model, look it up with `forge targets` to get the exact `gc.run_target` / `gc.provider` / `gc.model` triple to stamp on the bead (the mol-review-quorum pattern), and use `forge list` / `forge doctor` to see what exists and what's actually wired. Use whenever you fan work across providers, pick a non-native model, or need to refresh model-advisor's tier roster.
---

# Use Provider Forge

## Overview

gc can already route a dispatch to a *different* provider and model — that capability is
in core. The thing you usually lack is the **list**: which `(provider, model)` pairs exist,
what each costs, which `run_target` it maps to, and whether its CLI is actually installed
and authed. **provider-forge** is that catalog, and `bin/forge` is the read CLI over it.

The discipline this skill teaches has two halves:

1. **Route by the triple.** To send a unit of work to a specific provider+model, stamp three
   metadata keys on the dispatch — `gc.run_target`, `gc.provider`, `gc.model`. This is the
   exact mechanism core's `mol-review-quorum` formula uses to fan review lanes across
   providers. You do not invent a new dispatch path; you set the triple.
2. **Look the triple up; don't guess it.** The valid values for that triple come from the
   catalog. `forge targets` hands you a correct, *live* triple; `forge list` / `forge doctor`
   tell you what exists and what is runnable. Never hand-type a model ID or run target you
   have not confirmed against the catalog.

provider-forge is **read-only**: it tells you the facts and gives you the triple. It never
dispatches, spawns a session, or mutates a bead — *you* (or a formula) do the routing.

## When to Use

- You are about to dispatch a step to a **non-default** provider or model (anything other
  than the agent's native Claude tier) and need the right `run_target` / `provider` / `model`
  to put on it.
- You are authoring or filling in a **graph/quorum formula** that fans lanes across providers
  (like `mol-review-quorum`) and need valid lane `(provider, model, target)` values.
- You want to know **what's runnable right now** — which providers are live versus scaffold,
  and *why* a scaffold one isn't live yet (CLI missing? auth missing?).
- You need to **refresh model-advisor's roster** after editing the catalog (added a model,
  fixed a price, enabled a provider).

**When NOT to use:**

- The work should run on the agent's default provider/model — then just dispatch normally; you
  do not need a routing triple at all.
- You want to *choose* which tier is cost-optimal — that is `model-advisor`'s job
  (`advisor advise`). provider-forge tells you which models *exist*; model-advisor tells you
  which to *use*. Use them together: advise → look up the triple → stamp it.
- You expect provider-forge to *enforce reasoning effort*. It records effort per model, but gc
  has no effort path yet, so effort is advisory (see [Effort caveat](#effort-is-advisory)).

## The routing triple

Three metadata keys name where a dispatch runs. Set all three together:

| Key | Value | Where it comes from |
|-----|-------|---------------------|
| `gc.run_target` | the configured gc target that executes the step | catalog `run_target` |
| `gc.provider` | the provider identifier (native, or has a gc overlay) | catalog provider name |
| `gc.model` | the concrete model string the provider uses | catalog `model` |

These are exactly the keys `mol-review-quorum` stamps on each reviewer lane. Get their values
from `forge targets` — never improvise them.

## Process

### Step 1 — See what exists / what's runnable

```bash
forge list                 # the catalog — live providers by default
forge list --all           # everything, including scaffolds (overlay-only)
forge doctor               # per live provider: ready / missing-cli / missing-auth
```

`bin/forge` ships with this pack. If it is not on `PATH`, invoke it by its pack-relative path
(e.g. `.../packs/provider-forge/bin/forge list`). All three are **pure reads**.

- `list` shows each `(provider, model)` with its `run_target`, costs (`$/MTok`), context, and
  effort; **live-only by default**, `--all` adds the scaffolds so you can see which providers
  aren't enabled yet.
- `doctor` is the enablement check for the **live** providers: it probes whether each one's `cli`
  is on `PATH` and whether its `auth` file exists, reporting `ready` / `missing-cli` /
  `missing-auth`. Only **codex** and **claude** are live today; the other seven providers are
  scaffolds (gc has their overlays, but they need the CLI installed + models filled in, then
  `status = "live"` — at which point `doctor` starts checking them).

Add `--json` to any of these for structured output.

### Step 2 — Look up the dispatch triple

```bash
forge targets               # every live run_target / provider / model row
#   RUN TARGET     PROVIDER   MODEL
#   codex-gpt54    codex      gpt-5.4
#   codex-spark    codex      gpt-5.3-codex-spark
#   …
```

`targets` lists the `{ run_target, provider, model }` row for every *live* model. Pick the row for
the model you want — those three values are precisely what you stamp on a step. (Use `--json` to
select a row programmatically.) Everything `targets` lists is already live, so no separate
runnability check is needed; use `doctor` if you want to confirm *why* a model is or isn't there.

### Step 3 — Stamp the triple on the dispatch

Set the three keys on the step's `metadata` (in a formula) or on the work bead. The
`mol-review-quorum` pattern, verbatim:

```toml
# a reviewer lane, routed to a specific provider+model via the triple
metadata = { "gc.run_target" = "codex-gpt54",
             "gc.provider"   = "codex",
             "gc.model"      = "gpt-5.4" }
```

For a fan-out (quorum) formula, give each lane a *different* triple — lane one to one
provider/model, lane two to another, a synthesis step to a third target — exactly as
`mol-review-quorum` does with its `lane_one_*` / `lane_two_*` / `synthesis_target` variables.
gc routes each step to its `run_target`; the provider/model travel with it.

### Step 4 — (when you edited the catalog) refresh the advisor roster

```bash
forge roster                                       # print the [[tier]] block
forge roster --out ../model-advisor/advisor.tiers.toml   # write it
```

model-advisor's cost-ordered `[[tier]]` roster is **generated from the catalog** — maintain the
model list in one place. After any catalog edit (new model, price fix, a provider flipped to
`live`), re-run `forge roster` so the advisor's roster stays in sync. It emits only live,
non-`exclude_from_roster` models, cost-ordered; it never writes the catalog.

## Worked Example

You are setting up a two-provider review quorum on a PR and want lane two to run on a fast Codex
model.

1. **Confirm it's runnable.** `forge doctor` → `codex: ready (cli ok, auth ok)`. Good — Codex is
   dispatchable. (Had it said `missing-auth`, you would authenticate the Codex CLI first, or pick
   a live provider.)
2. **Get the triple.** `forge targets` → find the Codex spark row:
   `codex-spark   codex   gpt-5.3-codex-spark`.
3. **Stamp it.** In the quorum formula, lane two's `metadata` gets
   `gc.run_target = "codex-spark"`, `gc.provider = "codex"`, `gc.model = "gpt-5.3-codex-spark"`;
   lane one keeps a Claude triple. The synthesis step routes to its own target. gc fans the two
   lanes across the two providers and synthesizes the quorum — using nothing but the triples.

Note you did **not** type `gpt-5.3-codex-spark` from memory or guess `codex-spark`; both came
from the catalog via `forge targets`, so the dispatch is guaranteed valid and live.

## Why This Matters

- **Valid, live triples — not guesses.** Routing across providers fails silently if you stamp a
  model ID that doesn't exist or a provider that isn't installed. `forge targets` + `forge doctor`
  give you a triple you have confirmed is real and runnable.
- **One source of truth.** The same catalog that answers "what can I route to?" also generates
  model-advisor's roster. Edit a model once; `forge roster` keeps the advisor current. No drift
  between "what exists" and "what the advisor ranks."
- **It rides gc's mechanism, adds no risk.** provider-forge never dispatches or mutates anything.
  The actual routing is gc's own — the overlays and the `gc.run_target`/`gc.provider`/`gc.model`
  triple that `mol-review-quorum` already proves out. This skill just teaches you to use them
  with confirmed data.

<a id="effort-is-advisory"></a>
> **Effort is advisory.** The catalog records reasoning effort
> (Codex's `low`/`medium`/`high`/`xhigh`) per model, but gc has **no effort path today** — the
> launcher forwards the model, not a non-default effort. So a model runs at the provider's
> default effort regardless of the catalog's `default_reasoning`, until a small gc-core seam to
> forward effort lands (same shape as model-advisor's per-dispatch ask). Treat the effort field
> as documentation, not enforcement.

## Verification Gate

Before routing a step to a non-default provider/model:

- [ ] The destination provider is **live** (`forge doctor` / it appears in `forge list` /
      `forge targets`) — not a scaffold that lacks a CLI or auth.
- [ ] The `gc.run_target` / `gc.provider` / `gc.model` triple came from `forge targets`, not from
      memory or a hand-typed model ID.
- [ ] All **three** keys are set together on the step's `metadata` (a `run_target` without its
      `provider`/`model`, or vice-versa, is incomplete).
- [ ] For a fan-out formula, each lane carries its **own** complete triple (lanes are not meant to
      share one).
- [ ] If you edited `catalog.toml`, `forge roster` was re-run so model-advisor's roster matches.

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack contributes a skill by
placing `skills/<name>/SKILL.md` under the pack root, with YAML frontmatter carrying at minimum
`name` and `description` (the body is free-form Markdown, by convention including a "When to Use"
trigger section). This file lives at `provider-forge/skills/use-provider-forge/SKILL.md`, so it is
picked up automatically — `pack.toml` does not enumerate skills. Once the `provider-forge` pack is
imported into a city (vendored under the city's `packs/` and registered via a direct
`source = "packs/provider-forge"` import), the skill surfaces in `gc skill list` binding-qualified
as `<binding>.use-provider-forge` (e.g. `provider-forge.use-provider-forge`), and the materializer
projects it into the per-agent skills sink at `gc start`. Verify with `gc skill list` (and
`gc lint .` / `gc doctor` to surface name collisions). This mirrors how the bundled `core` pack
ships its `core.gc-*` skills and how the sibling `model-advisor` pack ships `use-model-advisor`.
