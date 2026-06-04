<div align="center">

# `model-advisor`

### Cost-minimal model-tier selection for Gas City agents

Agents stop **overpaying for the strong model** on work a cheaper one handles just as
well — without ever silently shipping worse work. For each `(provider, agent, shape,
tier)` cell the advisor learns a success posterior from bead lifecycle + telemetry and
recommends the **cheapest tier whose quality stays within tolerance, with 95%
credibility.** A clean-room implementation of *[Conservative Constrained Thompson
Sampling](https://github.com/jsgerman-oss/research/tree/main/blackrim-model-advisor-paper)*.

[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Gas City](https://img.shields.io/badge/Gas_City-pack-0f766e?style=flat-square)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)]()
[![Engine](https://img.shields.io/badge/engine-stdlib_only-444?style=flat-square)]()
[![Decision](https://img.shields.io/badge/rule-CC--TS-0f766e?style=flat-square)]()
[![Bound](https://img.shields.io/badge/gate-Wilson_LCB-6d28d9?style=flat-square)]()
[![Guarantee](https://img.shields.io/badge/never-downgrades_blind-c2410c?style=flat-square)]()
[![Scope](https://img.shields.io/badge/v1-learn_·_recommend_·_apply_·_auto--apply-555?style=flat-square)]()
[![Advanced](https://img.shields.io/badge/advanced-8_opt--in_modes-6d28d9?style=flat-square)]()

[**Quick start**](#quick-start) ·
[**How it works**](#how-it-works) ·
[**The surfaces**](#the-surfaces) ·
[**Install**](#install--uninstall) ·
[**Config**](#configuration) ·
[**Caveats**](#caveats) ·
[**Lineage**](#research-lineage)

</div>

---

## The cost tax

Its sibling pack, [`ast-lens`](../ast-lens), cut the **read tax** — agents reading whole
files when an outline would do. **model-advisor** cuts the *next* line item: the **cost
tax** — agents running the strongest, most expensive model on *every* dispatch because
nobody measured whether a cheaper one would have been fine.

The naive fixes both fail. Pin everything to the frontier tier and you overpay on the
lookup, the doc rewrite, the single-file edit — work a mid tier nails every time. Pin a
cheaper tier to save money and you gamble: a wrong answer on an ADR or a release-gating
review cascades through every bead that depended on it. The right tier is a *per-task*
decision, and it should be made on **evidence**, not vibes.

That is the whole job of the advisor. It watches outcomes, learns which tiers actually
preserve quality for which `(agent, shape)`, and recommends the cheapest one it can
*prove* is good enough — falling back to the known-good baseline whenever it can't.

```text
$ advisor advise polecat implement

  recommend: sonnet   (claude-sonnet-…)        ← cheaper than the opus baseline
  why:       q_lo=0.82 ≥ baseline mean 0.80 − 0.05 tol; cheapest admitted tier
  saving:    −$0.011 / dispatch vs opus        (at the representative token budget)

$ advisor advise refinery review

  recommend: opus     (claude-opus-…)          ← baseline held
  why:       no cheaper tier clears tolerance — sonnet q_lo=0.58 < 0.75 threshold
             (thin evidence, n<5). Recommending the known-good tier.
```

## What it does

Quality in gc is already encoded in the work: a clean bead **close** means the dispatch
landed; a **reopen / escalate** means it didn't. The advisor harvests that signal (plus
higher-fidelity reviewer and eval verdicts), maintains a `Beta(a, b)` posterior per cell,
and runs the **CC-TS decision rule** on every recommendation:

1. **Learn.** A Stop/SubagentStop hook records each invocation; bead lifecycle supplies
   the outcome. Each `(provider, agent, shape, tier)` cell accrues a calibrated success
   posterior. Telemetry lands in `.beads/telemetry/invocations.jsonl`; the cell-store
   cache is rebuildable from it.
2. **Gate (conservative).** A cheaper tier is *admitted* only if a one-sided lower
   confidence bound on its success clears `baseline mean − q_tol` at 95% credibility.
   Thin or zero evidence ⇒ the gate rejects ⇒ the baseline tier wins. `Critical` cells
   are never downgraded, full stop.
3. **Choose (asymmetric loss).** Among admitted tiers, pick the one minimising an
   asymmetric loss that penalises a wrong downgrade far more than it rewards the saved
   spend — scaled by the bead's downstream blast radius.
4. **Recommend / apply.** `advise` returns the tier + a structured, auditable rationale;
   `inspect` shows the evidence; `apply` sets the tier on the agent's config. **The
   advisor recommends; you apply.**

> **The conservative guarantee.** Every recommended downgrade is credible at 95%; the
> baseline is always feasible; the cold-start recommends the baseline until a cheaper
> tier *earns* its way in. The worst case is overpaying for the safe tier — never
> silently shipping worse work. This is the property that makes it safe to let the
> advisor inform routing at all.

## What's in the box

| Layer | What it is | File |
|-------|------------|------|
| **Engine** | the pure, stdlib-only CC-TS decision rule + cell store | `modeladvisor/` |
| **CLI** | `advise` / `inspect` / `apply` / `auto-apply` + advanced (`eval-schedule` / `federate` / `drift`) | `bin/advisor` |
| **Skill** | teaches agents to advise-before-dispatch | `skills/use-model-advisor/SKILL.md` |
| **Prompt fragment** | the cost-aware discipline, in every agent's context | `template-fragments/model-advisor.template.md` |
| **Telemetry hook** | records each invocation (Stop / SubagentStop) | `overlay/…/settings.json` + `hooks/capture-invocation.sh` |
| **Config** | the model roster + shape taxonomy + tolerance classes | `advisor.toml` |
| **Scheduler** | a gc `order` to run `auto-apply` on a cadence (safe unless armed) | `orders/` + `docs/AUTO-APPLY.md` |
| **Advanced modes** | 8 opt-in research extensions (conformal · empirical-Bayes · Thompson · continuous · cascade · federation · drift · eval-sched) | `modeladvisor/` · §7.3 |

## Quick start

```bash
./setup.sh                              # one-time: build the engine venv (stdlib only)
./bin/advisor advise polecat implement  # cost-minimal tier for this agent + shape
./bin/advisor inspect polecat implement # the evidence behind it (per-tier posterior)
./bin/advisor apply polecat             # set the recommended tier on the agent
```

Every read surface takes `--json` to emit the structured `reasons` object for
programmatic routing.

## How it works

The decision is the paper's, made gc-native. A **shape** is the *kind of task* (not the
agent): `lookup`, `implement`, `judge`, `review`, `patrol` — config-extensible. A **tier**
is one of *your configured* `(provider, model)` run targets, cost-ordered — an arbitrary
roster, not a fixed haiku/sonnet/opus three. A **cell** is
`provider::agent::shape::tier_id`, and `recommend(state, cell, tol, baseline)` is a
**pure, deterministic function**: same posteriors + config in, same tier + rationale out.
That purity is why the rule is exhaustively testable and why the `reasons` object — the
candidate tiers, their confidence bounds, the credible quality-drop intervals, the cost
diffs — is a first-class audit surface, not an afterthought.

It **degrades, never blocks.** No roster ⇒ a clear error (it can't order tiers by cost
without one). No telemetry ⇒ conservative cold-start. No token counts ⇒ a representative
budget. Thin evidence ⇒ the baseline tier. The advisor can never stall a dispatch — worst
case it recommends the safe tier. Full math: [`docs/DESIGN.md`](docs/DESIGN.md).

## The surfaces

Two pure reads and one deliberate write — plus the opt-in
[Advanced modes](#advanced-modes-opt-in) surfaces (`eval-schedule`, `federate`, `drift`).

| Command | Does | Mutates? |
|---------|------|----------|
| `advisor advise <agent> <shape>` | recommend the cost-minimal tier + rationale + cost diff | no |
| `advisor inspect <agent> <shape>` | per-tier posterior, credible quality-drop CI, the highest-value eval probe | no |
| `advisor apply <agent>` | set the recommended tier on the agent's `model` config + reload | **yes** |
| `advisor auto-apply [--town\|--rig N]` | sweep every agent and apply the evidence-strong tier (safest-across-shapes; dry-run by default) | **yes** |

`advise`/`inspect` never dispatch, touch a bead, or change config. `apply` is the per-agent
application path, on demand; `auto-apply` automates that sweep across all agents —
conservatively (never auto-downgrading thin-evidence or `Critical` cells) — and can be
scheduled with a gc `order`. See [`docs/AUTO-APPLY.md`](docs/AUTO-APPLY.md).

## Advanced modes (opt-in)

The eight extensions the paper designs but v1 deliberately left off ([`docs/DESIGN.md`](docs/DESIGN.md) §7.3)
now ship — each a self-contained, stdlib-only module behind a **default-off** flag, so the
conservative v1 rule stays the default and turning one on is a one-line config change. v1
behavior is byte-identical when they're off.

| Mode | Flag / surface | What it adds |
|------|----------------|--------------|
| **Conformal calibration** | `lcb_backend = "conformal"` | distribution-free split-conformal gate bound (rolling `(pred, obs)` buffer) in place of the asymptotic Wilson LCB |
| **Full hierarchical Bayes** | `pooling = "empirical-bayes"` | a genuine empirical-Bayes Beta-Binomial pooler (method-of-moments hyperprior + evidence-weighted shrinkage); optional `[bayes]` PyMC backend |
| **Thompson sampling** | `mode = "thompson"` · `advise --thompson --seed N` | seeded per-tier Beta sampling instead of the deterministic rule — still gate- and `Critical`-safe, reproducible per seed |
| **Continuous quality** | `continuous_quality = true` | graded `q ∈ [0,1]` outcomes (reviewer score / test-pass fraction) feeding the Beta; optional Gaussian (NIG) posterior for unbounded scores |
| **Critical-path cascade** | `advise --cascade-bead ID` | DAG-propagated effective `N_dep` from the bead dependency graph — an ADR that blocks N builders carries a larger blast radius than a leaf |
| **Multi-tenant federation** | `[federation]` peers · `advisor federate` | share **aggregates only** (never raw telemetry) across repos to warm thin cells, trust-weighted so local evidence always dominates |
| **Change-point drift** | `changepoint = true` · `advisor drift` | Page-Hinkley detection of upstream model drift/deprecation + recency re-weighting so the gate re-learns the new regime |
| **Auto-scheduled eval** | `advisor eval-schedule [--apply]` | rank gating cells by CI-width × unlock-value and dispatch eval probes proportional to posterior width (dry-run default; schedulable via a gc `order`) |

All eight are covered by the suite (228 tests) and never weaken the `Critical`
never-downgrade guarantee. Math + rationale: [`docs/DESIGN.md`](docs/DESIGN.md) §7.3.

## Install & uninstall

Turn it on for **one rig** or the **whole town**, reversibly:

```bash
./setup.sh                          # build the engine venv (one-time)

./install.sh --rig myrig            # one rig: skill + telemetry hook for its agents
./install.sh --town                 # city-wide: + opts the discipline fragment into every agent

./uninstall.sh --rig myrig          # clean reversal (strips the merged Stop hook too)
./uninstall.sh --town --purge       # …and drop the venv
```

```
install.sh    (--town | --rig <name>) [--dry-run] [--city <path>] [--no-reload]
uninstall.sh  (--town | --rig <name>) [--dry-run] [--city <path>] [--purge] [--no-reload]
```

Both are **idempotent**, **back up every file they edit** (`<file>.model-advisor.bak.<ts>`),
support **`--dry-run`** (prints the plan, changes nothing), and **fail loudly** on
unexpected state. A local in-tree pack imports via a *direct* config entry — the gas-town
convention — not `gc import add`:

- `--town` adds `[imports.model-advisor]` (`source = "packs/model-advisor"`) to the
  city-root `pack.toml`, and opts `"use-model-advisor"` into `city.toml`
  `global_fragments`.
- `--rig <name>` adds `[rigs.imports.model-advisor]` under the matching `[[rigs]]` in
  `city.toml` (the fragment, a city-wide list, is left alone).

`gc reload` then materializes the Claude `Stop`/`SubagentStop` overlay; gc **deep-merges**
the telemetry hook into projected settings without clobbering the core hooks. Because that
merge never *deletes*, `uninstall.sh` explicitly strips our hook entry (matched by the
unique `model-advisor/hooks/capture-invocation.sh` command substring) from every projected
`settings.json`, preserving any other hook, then re-projects clean. Town and rig installs
both round-trip `city.toml` / `pack.toml` byte-identical.

## Configuration

Everything is config-driven; nothing is hard-coded. Edit `advisor.toml`:

| Knob | What it is | Default |
|------|------------|:-------:|
| `[[tier]]` roster | your `(provider, model)` run targets, cost-ordered by `rank` | *(required)* |
| baseline tier `tier*` | the known-good reference all downgrades are judged against | highest `rank` |
| shape taxonomy | task kinds + per-agent canonical shape sets | the 5 seed shapes |
| tolerance class | per-`(agent, shape)` quality budget: `Critical`/`Strict`/`Moderate`/`Lenient` | `Moderate` |
| `q_tol` / `M` | the per-class quality-loss tolerance + asymmetric multiplier (`∞`/`20`/`5`/`1`) | paper defaults |
| channel weights | `close:1`, `review:3`, `eval:5` | as shown |
| `force_baseline` | safety hatch: pin a cell to its baseline, short-circuit all learning | off |
| advanced modes | 8 opt-in flags — `lcb_backend`, `pooling`, `mode`, `continuous_quality`, `changepoint`, `[federation]` ([Advanced modes](#advanced-modes-opt-in)) | all off |

The pack ships an editable starter (`SAMPLE_TOML`); a consumer with a characterised
landscape can also supply a `priors.json` for immediate convergence. Full reference:
[`docs/DESIGN.md`](docs/DESIGN.md) §2–§3.

## Caveats

Honest about the scope line.

- **Apply granularity.** v1 ships *per-agent* apply — manual (`apply`) and automated
  (`auto-apply`, an evidence-gated sweep you can schedule). It's coarse: one tier per agent,
  changeable by a config edit + reload. **Per-dispatch** application (the advised tier per
  *task/shape*) is the next step — the gc-core seam is now **implemented and PR'd** to
  `gastownhall/gascity` (the reconciler binds a work bead's `gc.model` at spawn), activating
  once it lands. Background: [`docs/INTEGRATION-FEASIBILITY.md`](docs/INTEGRATION-FEASIBILITY.md).
- **The reward signal is the hard part.** Bead closure is the primary channel and is fully
  supported today; reviewer/eval verdicts are higher-fidelity secondaries when present. The
  advisor only ever learns from outcomes it can attribute to a recorded dispatch.
- **Conservative by design ⇒ it converges deliberately.** A thin cell recommends the
  baseline until evidence accrues (~a couple dozen observations dominate the cold-start
  prior). That is the point, not a defect: it never trades quality for speed of savings.
- **The research extensions ship opt-in.** Every feature the paper designs but v1 left off —
  conformal calibration, full (empirical-Bayes) hierarchical pooling, Thompson sampling,
  continuous quality, critical-path cascade, federation, change-point drift, and
  auto-scheduled eval — is now implemented behind a **default-off** flag
  ([Advanced modes](#advanced-modes-opt-in)). The conservative deterministic rule remains the
  default, and enabling any mode never weakens the `Critical` never-downgrade guarantee.
- **It advises; you decide.** During an incident, pin the baseline (`force_baseline`) and
  don't explore. The advisor never drives routing on its own in v1.

## Research lineage

model-advisor is a clean-room build of **_[Conservative Constrained Thompson Sampling for
Cost-Aware Model-Tier
Selection](https://github.com/jsgerman-oss/research/tree/main/blackrim-model-advisor-paper)_**,
implemented from the paper's §3 problem formulation and §5 algorithm — **not** ported from
Blackrim's `internal/dispatch/` Go code, and depending on no Blackrim artefact, dataset, or
offline landscape. The load-bearing parts are kept faithfully — the constrained decision
rule, the conservative LCB gate, the asymmetric loss with class multipliers, the
`M[Critical] = ∞` hard rule, the pure-function `recommend` with its structured `reasons` —
and adapted where gc differs: an arbitrary config-driven roster (not a fixed three tiers),
a gc-native shape taxonomy, provider-keyed cells, a conservative cost-ordered cold-start in
place of an offline landscape, and bead lifecycle as the primary quality channel.

## License

MIT © Jay German. See [LICENSE](LICENSE).
