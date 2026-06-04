{{ define "use-model-advisor" }}
## Dispatch Discipline: Advise Before You Spend

The model an agent runs is a cost decision and a quality decision at once.
Defaulting everything to the strongest tier is safe but burns budget; quietly
dropping to a cheaper tier is cheap but can cascade a wrong answer through every
bead that depended on it. The advisor makes that trade-off *measured*: it learns
a success posterior per `(agent, shape, tier)` and recommends the cheapest tier
whose quality stays within tolerance, with 95% credibility.

**The rule:** before dispatching **meaningful work**, consult the advisor for the
task's shape, then commit a tier deliberately.

```bash
advisor advise <agent> <shape>
```

`advisor` is read-only and stateless on `advise`/`inspect`; it never blocks or
mutates a dispatch. It prints the recommended tier, a one-line rationale, and the
cost differential against every roster tier.

**The loop:**
1. **Advise first.** Run `advisor advise <agent> <shape>` (shapes: `lookup`,
   `implement`, `judge`, `review`, `patrol`). For most dispatches the
   recommendation + its rationale is the whole answer — take the tier and go.
2. **Inspect before a downgrade.** If the recommendation is *cheaper than the
   baseline*, check the evidence: `advisor inspect <agent> <shape>` shows the
   per-tier confidence bound, the credible quality-drop interval vs baseline, and
   whether a gating eval is outstanding. Adopt the downgrade only when the
   interval is within tolerance.
3. **Apply deliberately.** `advisor apply <agent>` sets the recommended tier on
   the agent's config. Until you apply, nothing changes — the advisor only
   advises.

**The conservative guarantee — why this is safe to follow:** the advisor *never
downgrades without credible evidence.* A cheaper tier is admitted only if a
one-sided lower bound on its success clears `baseline − tolerance` at 95%
credibility; with thin or no evidence the gate rejects and you get the known-good
baseline tier. `Critical` work (ADRs, threat models, release gating) is never
downgraded at all. So the worst case is overpaying for the safe tier — never
silently shipping worse work. The trade-off is asymmetric and the advisor sits on
the safe side of it by construction.

**For trivial or throwaway work**, skip it — the model choice does not matter.
During an **incident**, pin the baseline (`force_baseline`) and don't explore.
When the dispatch is consequential and the spend is real, advise first.
{{ end }}
