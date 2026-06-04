---
name: use-model-advisor
description: Pick the cost-optimal model tier before dispatching meaningful work. Before slinging a non-trivial bead to an agent, run `advisor advise <agent> <shape>` to get the cheapest model tier that credibly preserves quality, `advisor inspect <agent> <shape>` to see the evidence behind it, and `advisor apply <agent>` to set the recommended tier on that agent's config. Use whenever you are about to choose or change which model an agent runs (implement, review, judge, lookup, patrol work).
---

# Use Model Advisor

## Overview

Every dispatch silently picks a model. Defaulting every agent to the most
capable (most expensive) tier is safe but wasteful; quietly downgrading to a
cheaper tier to save spend is cheap but risky — a wrong downgrade on a
high-blast-radius task cascades. **model-advisor** turns that judgement into a
measured one: for each `(provider, agent, shape, tier)` cell it maintains a
success posterior learned from bead lifecycle and invocation telemetry, and
recommends the **cheapest tier whose quality stays within tolerance, with high
credibility.**

The discipline this skill teaches: **consult the advisor before you commit a
model choice.** It is a read-first, advise-then-apply loop — `advise` to get the
recommendation, `inspect` to audit the evidence, `apply` to set it. The advisor
recommends; you (or an operator) apply.

**The conservative guarantee.** The advisor *never downgrades a tier without
credible evidence.* A cheaper tier is admitted only if a one-sided lower
confidence bound on its success probability clears the baseline tier's quality
minus the task's tolerance, at 95% credibility. With thin or no evidence the
gate rejects by default and the advisor returns the known-good baseline tier.
`Critical`-class work (ADRs, threat models, release gating) is *never* downgraded
regardless of evidence — that is a design contract, not a tunable. So the worst
case is "keep paying for the safe tier," never "silently ship worse work."

## When to Use

- You are about to `gc sling` / route a non-trivial bead and want the
  cost-minimal model for it without risking quality.
- You are setting or revisiting an agent's `model` config field and want it
  grounded in evidence rather than a guess.
- You want to know *why* a tier is (or isn't) recommended — the credible
  quality-drop interval, the per-tier confidence bound, the cost differential.
- You are deciding whether a cheaper tier has earned its way in yet for a given
  agent + task shape.

**When NOT to use:**

- Trivial / throwaway work where the model choice does not matter — just sling.
- Incident response, where exploration is wrong: pin the baseline tier
  (`force_baseline`) and skip the advisor until the incident clears.
- You have no roster configured yet — populate `advisor.toml` first (the advisor
  cannot order tiers by cost without it; see [Configuration](#configuration)).

## The Shapes

A **shape** is the *kind of cognitive task*, independent of which agent runs it.
The advisor keys recommendations on `(agent, shape)`; pass the shape that best
describes the work:

| Shape       | Meaning                                          | Typical tolerance |
|-------------|--------------------------------------------------|-------------------|
| `lookup`    | retrieve / answer / summarise; low blast radius  | Lenient           |
| `implement` | write / modify code or config; multi-file edits  | Moderate          |
| `judge`     | routing / triage / decision with downstream effect | Moderate→Critical |
| `review`    | read-only critique with a verdict                | Strict            |
| `patrol`    | health / oversight monitoring, recurring         | Lenient→Moderate  |

The taxonomy is config-extensible (`advisor.toml`); a consumer can add e.g.
`threat-model` and pin it `Critical`.

## Process

### Step 1 — Ask for the recommendation

```bash
advisor advise <agent> <shape>
# e.g.  advisor advise polecat implement
```

`bin/advisor` is shipped with this pack. If it is not already on `PATH`, invoke
it by its pack-relative path (e.g. `.../packs/model-advisor/bin/advisor advise
…`). Optional flags refine the cell: `--tol <class>` overrides the tolerance
class, `--provider <p>` / `--rig <r>` scope the cell, `--baseline <tier>` pins a
different reference tier. The command is a **pure read** — it never dispatches,
mutates a bead, or changes config.

It prints the recommended `tier_id` (with the concrete model), a one-line
rationale, and the cost differential versus each roster tier. Two shapes of
answer you will see:

- **A downgrade earned its way in** —
  *"sonnet: LCB q_lo=0.82 ≥ baseline mean 0.80 − 0.05 tol; cheapest admitted
  tier; expected loss −$0.011/dispatch vs opus."*
- **Cold-start / thin evidence (the conservative default)** —
  *"opus (baseline): no cheaper tier clears tolerance — haiku q_lo=0.41,
  sonnet q_lo=0.58 both < 0.75 threshold (thin evidence, n<5)."*

Add `--json` to get the full structured `reasons` object (candidates, per-tier
`q_lo`, expected loss, cost diffs, eval flag) for programmatic routing.

### Step 2 — Inspect the evidence (when the call is consequential)

```bash
advisor inspect <agent> <shape>
```

This is the audit surface — a read-only deep view of the `(agent, shape)` cells
across the whole roster:

- per-tier posterior `Beta(a, b)`, mean, the lower confidence bound `q_lo`,
  observation count `n`, last-update time, and admit/reject under the current
  tolerance;
- the **credible interval on the quality drop** vs baseline for each candidate —
  the quantity the constraint actually bounds, e.g.
  *"haiku: quality-drop 95% CI [0.06, 0.31] — exceeds 0.05 tol";*
- the **highest-value eval probe** — the widest cell that is *gating* a decision,
  named so a human can resolve it: *"widest gating cell: sonnet (CI half-width
  0.14 > 0.10); run an eval on claude::polecat::implement::sonnet."*

Use `inspect` whenever you want to understand *why* `advise` said what it said,
or to judge whether a cell has enough evidence to trust a downgrade.

### Step 3 — Apply the recommendation (deliberate, per-agent)

```bash
advisor apply <agent>
```

`apply` sets the advisor's recommended tier on the agent's `model` config field
(and triggers a reload so the next session honours it). This is the v1
application path: **per-agent**, not per-dispatch. It is a deliberate write — run
it when you have reviewed the recommendation and want it to take effect. Until
you `apply`, nothing changes: the advisor only advises.

Per-dispatch auto-apply (stamping the advised tier on a bead at `gc sling` time)
is **v2** and gated on a small gc-core change — see the README. In v1, the
advise→inspect→apply loop is the contract.

## Worked Example

You are about to dispatch a multi-file feature bead to `polecat`.

1. `advisor advise polecat implement` → recommends `sonnet`, rationale
   *"q_lo=0.82 ≥ 0.80 − 0.05 tol; cheapest admitted; −$0.011/dispatch vs opus."*
2. The recommendation is a downgrade from the `opus` baseline, so you check the
   evidence: `advisor inspect polecat implement` shows `sonnet` at `n=37`,
   quality-drop 95% CI `[0.00, 0.04]` (within the 0.05 Moderate tolerance), and
   no gating eval outstanding. The downgrade is credible.
3. You set it: `advisor apply polecat` pins `sonnet` for polecat's implement
   work. Future `implement` dispatches run the cheaper tier; quality keeps
   feeding the posterior, and if it ever slips, the next `advise` will say so.

Had `inspect` shown `n=3` and a wide interval, `advise` would have returned the
`opus` baseline instead — and you would simply keep paying for the safe tier
until evidence accrued. That is the conservative guarantee in practice.

## Why This Matters

- **Cost economy with a quality floor.** The advisor spends the cheapest tier it
  can *prove* is good enough, and falls back to the safe tier whenever it can't —
  capturing savings on well-characterised cells without gambling on thin ones.
- **Auditability.** Every recommendation carries its evidence (`reasons`):
  candidate tiers, confidence bounds, credible quality-drop intervals, cost
  diffs. You can always see *why*, which is what makes it safe to let the advisor
  inform routing at all.
- **It degrades, never blocks.** Missing telemetry ⇒ cold-start baseline; missing
  token counts ⇒ a representative budget; thin evidence ⇒ the safe tier. The
  advisor cannot stall a dispatch — worst case it recommends the baseline.

## Verification Gate

Before committing a model choice for consequential work:

- [ ] `advisor advise <agent> <shape>` was consulted for the dispatch's shape.
- [ ] For a recommended **downgrade**, `advisor inspect` was checked — the
      credible quality-drop interval is within tolerance and no gating eval is
      outstanding — before `apply`.
- [ ] `Critical`-class work was left on its baseline tier (never downgraded).
- [ ] Where the recommendation was adopted, it was set via `advisor apply
      <agent>` (a deliberate write), not an ad-hoc untracked config edit.

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack
contributes a skill by placing `skills/<name>/SKILL.md` under the pack root, with
YAML frontmatter carrying at minimum `name` and `description` (the body is
free-form Markdown, by convention including a "When to Use" trigger section).
This file lives at `model-advisor/skills/use-model-advisor/SKILL.md`, so it is
picked up automatically — `pack.toml` does not enumerate skills. Once the
`model-advisor` pack is imported into a city (vendored under the city's `packs/`
and registered via a direct `source = "packs/model-advisor"` import), the skill
surfaces in `gc skill list` binding-qualified as `<binding>.use-model-advisor`
(e.g. `model-advisor.use-model-advisor`), and the materializer projects it into
the per-agent skills sink at `gc start`. Verify with `gc skill list` (and
`gc lint .` / `gc doctor` to surface name collisions). This mirrors how the
bundled `core` pack ships its `core.gc-*` skills.
