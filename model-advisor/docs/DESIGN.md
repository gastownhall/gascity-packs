# model-advisor — DESIGN

A gc (Gas City) pack that recommends the **cost-minimal model tier** for each
agent/task, subject to a per-task quality-preservation guarantee. Clean-room
implementation of the Blackrim "Conservative Constrained Thompson Sampling"
(CC-TS) model-tier advisor, adapted to gc's agent roster and to a
**config-driven, arbitrary model roster** (not a fixed haiku/sonnet/opus 3-tier).

- Bead: `bh-cc5` of the model-advisor pack effort.
- Status: design only. The next bead builds the engine from this doc.
- Source paper: `jsgerman-oss/research/blackrim-model-advisor-paper`
  (§3 problem formulation, §5 algorithm, §6 evaluation, §7 discussion, appendix).
  This pack is a clean-room re-derivation from the paper's math; it is **not** a
  port of Blackrim's `internal/dispatch/` Go code, and it does not depend on any
  Blackrim artefact, dataset, or offline landscape.

> **Scope guard.** This document specifies behaviour and data, not code. It is
> precise enough that the engine bead can implement the decision rule, the cell
> store, the prior scheme, the quality ingestion, the telemetry schema, and the
> two CLI surfaces without re-reading the paper.

---

## 0. One-paragraph summary

For each cell — a `(provider, agent, shape, tier)` quadruple where `tier` is one
of the user's configured `(provider, model)` run targets — the advisor maintains
a Beta-Bernoulli posterior over the probability that a dispatch to that tier
"preserves quality" (succeeds). Given a request `advise <agent> <shape>`, the
advisor takes the user's reference tier `tier*` (the most-capable / known-good
frontier tier) as the baseline, then **admits a cheaper tier only if a one-sided
lower confidence bound on its quality clears `mu*(agent,shape) - q_tol`** (the
conservative gate). Among admitted tiers it picks the cheapest under an
asymmetric loss that penalises a wrong downgrade far more than it rewards the
saved spend. It returns the recommended tier, a structured rationale, and the
cost differential. Quality is observed primarily from bead lifecycle
(close = success `q=1`, reopen/escalate = failure `q=0`) and secondarily from
higher-fidelity reviewer/eval verdicts, fed back into the posteriors. Everything
is config-driven, audit-first, and degrades to "recommend the baseline tier"
when evidence is thin.

---

## 1. The constrained decision (CC-TS, from §3 + §5)

### 1.1 The object being decided

A **dispatch** routes one bead to one tier. We model task success as a Bernoulli
draw whose probability depends on the cell:

```
q | (agent, shape, tier) ~ Bernoulli(theta[agent,shape,tier]),   q in {0,1}
```

`theta[agent,shape,tier]` ∈ [0,1] is the unknown per-cell success probability.
Cost is a **known deterministic** function of the tier and the realised
input/output token counts (from the user's configured rate sheet); it is never
estimated, only looked up. The advisor's entire job is to estimate `theta` per
cell with calibrated uncertainty and choose tiers accordingly.

**Tier ordering assumption (§3, Assumption 1).** For a fixed `(agent, shape)`,
success probability is weakly increasing in tier strength:

```
theta[.,.,t_1] <= theta[.,.,t_2] <= ... <= theta[.,.,t_K]
```

where `t_1 ≺ ... ≺ t_K` orders tiers cheapest→most-capable. This justifies
extrapolation: if a cheaper tier credibly clears tolerance, every more-capable
tier does too, so the baseline `tier*` is always feasible. The ordering is over
**cost**, which is the user-supplied total order on the roster (see §2.3); it is
an assumption about quality, validated empirically as evidence accrues, not an
input.

### 1.2 The constraint

A per-task **quality-loss tolerance** `q_tol ∈ [0,1]` is the maximum allowable
absolute degradation versus the baseline tier `tier*`. The *true* constraint at
a cell is:

```
theta[agent,shape,tier*] - theta[agent,shape,tier]  <=  q_tol
```

i.e. the candidate tier may not lose more than `q_tol` absolute quality vs the
baseline. Since `theta` is unknown, the advisor enforces the **posterior-credible
analogue** at confidence `1 - alpha` (we use `alpha = 0.05`):

```
Pr_{theta ~ posterior}[ theta[.,.,tier*] - theta[.,.,tier] <= q_tol ]  >=  1 - alpha
```

The **decision** is the cheapest tier in the credibly-feasible set:

```
tier_dagger = argmin_{tier in FeasibleSet(q_tol, alpha)} cost(tier)
```

This is the whole contract in one line: *cheapest tier whose quality stays within
tolerance, with high credibility.* `tier*` is always in the feasible set
(downgrades are constrained; the baseline and upgrades are unconstrained).

#### Tolerance classes

Paper §3 partitions `q_tol` into four operational classes; we keep the same four
and make them config-assignable per `(agent, shape)` (default = Moderate):

| Class    | q_tol    | Asymmetric multiplier `M` | gc workloads (default mapping)                          |
|----------|----------|---------------------------|---------------------------------------------------------|
| Critical | 0        | ∞ (hard: never downgrade) | ADRs, threat models, IR / convoy orchestration, `judge` shape on release-gating work |
| Strict   | < 0.02   | 20                        | production code review, prompt review, refinery merge decisions |
| Moderate | < 0.05   | 5                         | multi-file implement, integration tests, dispatch/routing judgment |
| Lenient  | < 0.10   | 1                         | lookups, runbook/doc drafts, single-file edits, doc rewrites |

`M[Critical] = ∞` is the **design contract**, not a tunable: a Critical cell
never enters the exploration/downgrade set regardless of evidence. This is the
behaviour operators rely on to allow the advisor to drive routing at all.

### 1.3 CC-TS — the four layers

CC-TS is a four-layer policy that realises the credible decision above while
preserving the conservative ("never silently downgrade") property.

#### Layer 1 — Beta-Bernoulli posteriors (§5.1)

Per cell `(agent, shape, tier)`, maintain `Beta(a, b)` on `theta`. Bernoulli is
conjugate, so updates are closed-form. On observing `q ∈ {0,1}` (possibly with a
weight `w ≥ 1` for high-fidelity signals; see §4):

```
a <- a + w*q
b <- b + w*(1 - q)
```

Posterior mean `mu = a/(a+b)`; variance `sigma^2 = a*b / ((a+b)^2 * (a+b+1))`.

**Hierarchical partial pooling (closed-form approximation, §5.1).** Many cells
stay sparse for weeks. Borrow strength across siblings (same agent, other shapes;
and across agents in the same tolerance class) by pseudocount-pooling, capped so
pooling never dominates own-cell evidence:

```
a~ = a + lambda * Σ_{sib} w_sib * a_sib            (b~ analogously)
   weights w_sib ∝ 1 / sibling-posterior-standard-error
   global cap   lambda <= 0.5
```

Use the pooled `(a~, b~)` everywhere the gate/decision/CI reads the posterior.
Full hierarchical Beta inference (Stan/PyMC) is explicitly out of scope — the
closed-form approximation is empirically competitive in the paper's offline
simulations and keeps `recommend` a pure function (see §8).

#### Layer 2 — conservative posterior-rejection gate (§5.2)

The gate decides whether each candidate tier `tier ≺ tier*` is admitted. Compute
a one-sided **lower confidence bound** `q_lo(agent,shape,tier)` on the candidate's
success probability and admit iff it clears baseline-mean-minus-tolerance:

```
ADMIT tier  ⇔  q_lo(agent, shape, tier)  >=  mu*(agent, shape) - q_tol
```

where `mu*` is the posterior-mean quality at the baseline tier `tier*`.

**LCB computation — two interchangeable backends (paper §5.2):**

- **Production default: Wilson-style normal LCB on the Beta posterior.**
  `q_lo = mu - z_{1-alpha} * sqrt(sigma^2)`, with `mu, sigma^2` the pooled Beta
  moments and `z_{0.95} ≈ 1.645`. Cap `q_lo` at 0 for sparse cells (the gate then
  rejects by default — exactly the conservative behaviour we want at low counts).
  *Recommended refinement (paper footnote): use the exact Beta inverse-CDF lower
  bound* `q_lo = BetaInvCDF(alpha; a~, b~)` *when available; the Wald/Wilson
  approximation is biased low at small counts and the paper re-ran its
  convergence numbers with the exact ppf.* The engine SHOULD prefer exact
  Beta-ppf and fall back to the Wilson form only if no inverse-CDF is available.

- **Conformal wrapper (deferred to a flag, paper §5.2 + future-work).** The
  paper's formal guarantee is stated for a distribution-free conformal LCB built
  from a rolling, held-out calibration buffer of `(predicted, observed)` quality
  pairs per cell. With marginal coverage `≥ 1 - alpha`, the gate's admission
  implies `Pr[theta_tier >= mu* - q_tol] >= 1 - alpha` (the conservative
  guarantee, §5 Thm + appendix proof). gc cells will not have an exchangeable
  calibration buffer on day 1, so v1 ships the Wilson/Beta-ppf LCB (which
  coincides with the conformal bound asymptotically as the buffer grows) and
  leaves a `ConformalLCB` backend behind a config flag for when buffers exist.
  See §7 (deferred).

**Critical-class short-circuit.** If the cell's class is Critical (`q_tol = 0`,
`M = ∞`), admit *no* downgrade regardless of evidence. The baseline is the only
feasible tier.

#### Layer 3 — asymmetric-loss decision (§5.3)

Among admitted candidates, pick the action minimising expected asymmetric loss.
A wrong downgrade is far costlier than the saved API spend is valuable. Action
`a ∈ {down, stay, up}`, outcome `ω ∈ {preserved, lost}`:

| Action × outcome              | Loss                                                   |
|-------------------------------|--------------------------------------------------------|
| L(down, preserved)            | `-Δcost(tier*, tier_lower)`   (savings; negative loss) |
| L(down, lost)                 | `Δcost_down * N_dep * M[q_tol_class]`  (cascade)        |
| L(stay, ·)                    | `0` (baseline)                                          |
| L(up, ·)                      | `+Δcost(tier_higher, tier*)`  (overpay)                |

- `Δcost(x, y) = cost(x) - cost(y) > 0` for `y ≺ x`.
- `N_dep` = number of downstream dependents of the bead (blast radius). In gc
  this is read from the bead graph: count of beads that `blocks`/depend on the
  dispatched bead (via `gc graph` / `bd`'s dependency edges). Default `N_dep = 1`
  when unknown.
- `M` = tolerance-class multiplier from §1.2 (∞ / 20 / 5 / 1).

Expected loss uses the posterior: for a candidate downgrade,
`E[L] = -mu_tier·Δcost + (mu* - mu_tier)·M·Δcost·N_dep` (the §3 loss, eq. 6),
with `mu_tier` the pooled posterior mean. Pick `argmin E[L]`; ties broken toward
the cheaper tier. Because Layer 3 only *selects from* the admitted set and never
adds tiers, it preserves the Layer-2 credibility guarantee.

#### Layer 4 — uncertainty-triggered eval (§5.4) — **deferred in v1**

When the chosen tier's posterior CI half-width exceeds `theta_eval` (paper uses
`0.10`), the paper fires a deterministic eval-suite run on that cell and weights
its verdict higher in the likelihood. v1 records the **trigger** (surfaces
"this cell wants an eval" in `inspect`, see §6.2) but does **not** auto-dispatch
an eval; auto-scheduling is deferred (§7). The hook is designed in so the engine
bead can wire it later without schema changes.

### 1.4 The `recommend` procedure (faithful to Alg. 1, §5)

Pure function `recommend(state, cell_key, q_tol_class, baseline_tier) -> (tier_dagger, reasons)`:

```
cands := { tier* }                          # baseline always admitted
for tier in roster \ { tier* }:
    q_lo := LCB(posterior~[agent,shape,tier], alpha)     # Beta-ppf or Wilson
    if tier ≺ tier* and class != Critical and q_lo >= mu*(agent,shape) - q_tol:
        cands += tier                        # Layer 2 gate
    elif tier ≻ tier*:
        cands += tier                        # upgrades unconstrained

tier_dagger := argmin_{tier in cands} E_{theta~posterior~[tier]}[ L(tier, theta; tier*, mu*) ]   # Layer 3

if CIWidth(posterior~[tier_dagger], alpha) > theta_eval:
    flag_eval(agent, shape, tier_dagger)     # Layer 4 (record only, v1)

return tier_dagger, reasons = { cands, per-cand q_lo, per-cand E[L], cost diffs, eval_flag }
```

**Properties the engine MUST preserve** (paper §5 implementation notes — these
are load-bearing for operator trust):

1. **Pure-function `recommend`** — no I/O, no global mutable state. State (the
   posteriors + config) is passed in; the function is exhaustively testable.
2. **Deterministic for tests** — any sampling step is seedable from a `recommend`
   argument, so unit tests can assert decision shapes across pseudo-random draws.
   (The production rule above is LCB-based and already deterministic; keep the
   seed hook for a future genuine-Thompson-Sampling mode.)
3. **Structured `reasons`** — every recommendation returns candidate tiers, per-
   candidate LCBs, expected losses, cost differentials, and the eval flag. This
   IS the audit surface and the operator interface; the paper credits it with
   more operator-trust uplift than any algorithmic improvement. Non-optional.

---

## 2. The cell grid, adapted to gc

Blackrim used a fixed `17 agents × 3–5 shapes × 3 tiers ≈ 170` grid. gc differs
on two axes: a different agent roster, and — critically — **tiers are the user's
configured roster, an arbitrary set, not a fixed 3**.

### 2.1 Agents (the gc roster)

The advisor is agnostic to the roster; it discovers agents from city config
(`gc agent list` / resolved `[[agent]]` blocks). The canonical gastown roster the
design targets:

| Agent      | Scope | Role (drives default shapes)                                  |
|------------|-------|---------------------------------------------------------------|
| `mayor`    | city  | coordinator: dispatch/triage, occasional fast fixes           |
| `deacon`   | city  | patrol/coordination: gate-closing, convoy/dep resolution      |
| `boot`     | city  | watchdog: is-the-deacon-stuck judgment                        |
| `witness`  | rig   | work-health oversight: triage, escalation (no code)           |
| `refinery` | rig   | merge-queue processor: merge/reject decisions (no code)       |
| `polecat`  | rig   | implementer: writes code in a worktree                        |
| `dog` / `crew` | pool | utility/named workers: mixed                              |

New consumer-repo agents (no prior) are first-class — they simply start at the
cold-start prior (§3) and accrue evidence. The roster is **not** hard-coded.

### 2.2 Shapes (the gc task taxonomy)

A **shape** is the *kind of cognitive task*, independent of which agent runs it.
Blackrim's per-agent shapes don't transfer, so we define a small, stable,
gc-native taxonomy. Five canonical shapes (extensible via config):

| Shape       | Meaning                                          | Typical tolerance | Example gc work |
|-------------|--------------------------------------------------|-------------------|-----------------|
| `lookup`    | retrieve/answer/summarise; low blast radius      | Lenient           | research lookup, "where is X", status read |
| `implement` | write/modify code or config; multi-file edits    | Moderate          | polecat feature/bugfix beads |
| `judge`     | routing/triage/decision with downstream effect   | Moderate→Critical | mayor dispatch choice, deacon gate close, release gating |
| `review`    | read-only critique with a verdict                | Strict            | code review, prompt review, refinery merge review |
| `patrol`    | health/oversight monitoring, recurring           | Lenient→Moderate  | witness/boot/deacon heartbeat checks |

Notes:
- The taxonomy is **config-driven**: a `shapes.toml` lists shape names + default
  tolerance class. Five is the seed; consumers can add (e.g. `threat-model`,
  `adr`) and pin those to Critical.
- An agent has a **canonical shape set** (not all 5). Defaults:
  `polecat → {implement, lookup}`, `refinery → {review, judge}`,
  `witness/boot → {patrol, judge}`, `deacon → {patrol, judge}`,
  `mayor → {judge, implement, lookup}`. Cells only exist for an agent's canonical
  shapes (mirrors "not every agent has the same canonical shapes" from §3).
- **Shape inference at dispatch.** A dispatch is mapped to a shape by, in order:
  (1) explicit `--shape` flag / `gc.shape` bead metadata; (2) the formula in use
  (e.g. `mol-review-quorum → review`, `mol-polecat-work → implement`); (3) a
  default shape declared on the agent. The engine MUST record the resolved shape
  on the telemetry record (§5) so offline re-aggregation is possible.

### 2.3 Tiers = the user's configured model roster (the key divergence)

In gc a **tier is a configured `(provider, model)` run target**, and the roster
is whatever the user configures — **arbitrary cardinality**, possibly per-rig.
This is grounded in how gc already routes model-specific work: the
`mol-review-quorum` formula carries `gc.run_target`, `gc.provider`, `gc.model` on
each step, proving the platform already treats "which model" as a first-class,
config-supplied dispatch parameter. The advisor reuses that mechanism.

The advisor reads a **roster config** (`roster.toml` in the pack / city config):

```
# illustrative — the engine reads this, does not hard-code it
[[tier]]
id        = "haiku"                 # stable cell-key token
provider  = "claude"
model     = "claude-haiku-..."      # opaque to the advisor
run_target= "..."                   # gc agent/session-config target to dispatch to
rank      = 1                       # cost order; 1 = cheapest
in_cost   = 0.25                    # $/MTok input   (rate sheet)
out_cost  = 0.50                    # $/MTok output
[[tier]]
id = "sonnet" ; rank = 2 ; in_cost = 3.00  ; out_cost = 6.00  ; ...
[[tier]]
id = "opus"   ; rank = 3 ; in_cost = 15.00 ; out_cost = 30.00 ; ...
```

Requirements the engine enforces over the roster:
- **Total cost order.** `rank` induces the `≺` order used by Layer 2/3. If two
  tiers tie on `rank`, fall back to `in_cost` then `out_cost`. The order is
  user-asserted, not inferred from quality.
- **Baseline / reference tier `tier*`.** Configurable; default = the
  highest-`rank` (most-capable) tier — the "known-good frontier." All downgrade
  constraints are relative to it. An operator may pin a lower `tier*` per cell
  (the static safety hatch, §7).
- **`cost(tier, tok_in, tok_out)` = `tok_in/1e6 * in_cost + tok_out/1e6 * out_cost`.**
  Deterministic, exact given token counts. `Δcost` is differences of this.
- **Arbitrary K.** Nothing assumes K = 3. The roster may be 2 tiers or 7; the
  feasible-set scan is `O(K)` per recommend.
- **Per-rig rosters.** A rig may override the roster (different providers/models
  per project); cells are keyed by provider (below) so rosters never collide.

### 2.4 Cell keying

A **cell** is the unit of posterior bookkeeping. Key:

```
cell_key = "<provider>::<agent>::<shape>::<tier_id>"
        e.g.  "claude::polecat::implement::sonnet"
```

- `provider` is included so multi-provider / per-rig rosters never alias.
- `agent` is the **base agent name** (e.g. `polecat`), not the instance
  (`whiskeyshop/gastown.polecat#3`) — siblings of the same role pool evidence
  into one cell. Rig qualification is intentionally dropped from the key so a
  role's behaviour generalises across rigs; per-rig splitting is a future option
  (add `<rig>` to the key) if a role proves rig-dependent.
- `shape` is the resolved canonical shape (§2.2).
- `tier_id` is the roster token (§2.3), not the raw model string (models change;
  the token is stable, and the model string is recorded in telemetry for audit).

The **posterior store** is `Map[cell_key] -> { a, b, n, last_update }` persisted
as `.beads/telemetry/advisor-cells.json` (rebuildable by replaying
`invocations.jsonl`, so it is a cache, not a source of truth). A `(agent, shape)`
pair owns one cell per roster tier; `mu*` reads the `tier*` cell of the same
`(provider, agent, shape)`.

---

## 3. Priors (cold-start, since gc has no offline landscape)

Blackrim seeds every cell from an offline agent×shape×tier landscape with a
confidence percentage per cell. gc has **no such landscape on day 1**, so the
design specifies a conservative cold-start that still benefits from a landscape
later.

### 3.1 Confidence → Beta pseudocounts (paper §5.1, kept verbatim for when a landscape exists)

If a cell *does* have an offline/operator-supplied confidence `c ∈ [0,100]`:

```
a_prior = max(1, round(c / 5))
b_prior = max(1, round((100 - c) / 5))
```

So 95% → `Beta(19,1)` (very informative), 65% → `Beta(13,7)` (mean 0.65, sd≈0.10),
50% → `Beta(10,10)` ("roughly even, known"), no evidence → `Beta(1,1)` (uniform).
Properties (appendix C): monotone in `c`, bounded influence (≤20/side, so ~20 real
observations dominate any prior), sane uniform. This path is used only when a
consumer ships a `priors.json`; gc does not require one.

### 3.2 Default cold-start scheme (gc's day-1 reality) — **conservative, cost-ordered**

With no landscape, the prior must encode two beliefs at once: (a) the tier
ordering (more-capable ⇒ ≥ quality), and (b) "we don't actually know yet, so
don't downgrade." The scheme:

1. **Baseline tier `tier*`: optimistic.** Seed `Beta(a0, b0)` with a high mean,
   e.g. `Beta(8, 2)` (mean 0.8). The baseline is the known-good frontier; we trust
   it. This makes `mu*` start high so the gate threshold `mu* - q_tol` is
   meaningfully strict for cheaper tiers.
2. **Cheaper tiers: pessimistic, monotone in cost.** Seed each non-baseline tier
   with a *lower* mean than the next-more-capable tier, but a **wide** posterior
   so the LCB is low and the gate rejects until evidence accrues. Concretely, set
   the prior mean by linear interpolation on `rank` between a floor `m_lo` (for
   the cheapest tier) and the baseline mean, with small total pseudocount
   `s_prior` (weak), e.g.:
   ```
   mean(tier) = m_lo + (m_hi - m_lo) * (rank(tier) - 1) / (rank(tier*) - 1)
   a = mean * s_prior ;  b = (1 - mean) * s_prior      with s_prior ≈ 4
   ```
   Suggested defaults: `m_lo = 0.5`, `m_hi = mean(tier*) = 0.8`, `s_prior = 4`.
   The small `s_prior` keeps the prior weak (means a handful of real observations
   move it) while the depressed mean + wide spread makes the **LCB start below any
   plausible `mu* - q_tol`**, so the cold-start policy is exactly *"recommend the
   baseline `tier*` until a cheaper tier earns its way in."*
3. **Net day-1 behaviour:** the advisor returns `tier*` for every cell, with a
   rationale of the form *"no cheaper tier has cleared tolerance (insufficient
   evidence)."* No silent downgrades before evidence — the conservative contract
   holds vacuously at cold start. This matches the paper's finding that flat/weak
   priors converge in ~19 eval-triggered dispatches per thin cell, vs ~0 when a
   strong landscape prior is present.

This cold-start is the **safe default**; a consumer who supplies a `priors.json`
(via §3.1) gets immediate convergence on well-characterised cells.

### 3.3 Prior → posterior update

Posteriors are the priors updated by observed quality (§1.3 Layer 1):
`a += w*q`, `b += w*(1-q)` per observation, with the partial-pooling overlay
(§1.3) applied at read time. Bounded-influence priors guarantee ~`s_prior + a few
dozen` observations fully dominate the cold-start belief. The store is
append-friendly: each `invocations.jsonl` quality event is one update.

---

## 4. Quality channels in gc

The paper is emphatic (§7, "lessons from deployment"): *the bandit is the easy
part; the reward signal is the hard part.* gc's advantage is that bead lifecycle
already encodes task outcomes. Three channels, in increasing fidelity:

### 4.1 Channel A — bead closure (PRIMARY, always available)

The default, zero-extra-instrumentation signal:

- **`q = 1` (preserved):** the dispatched bead is **closed** by the refinery
  (`bd close` / status → `closed`) without a prior reopen, AND not reopened within
  a debounce window (default 24h). A clean close = the work landed.
- **`q = 0` (lost):** the bead is **reopened** (`bd reopen`), **escalated** (a
  `set-state`/label transition such as `escalated`, or witness escalation to
  mayor), or the dispatch's closing record carries `gc.outcome = fail` /
  `gc.failure_class = hard`. `transient` failures (rate-limit/infra) are **not**
  `q = 0` — they are dropped (no observation), because they don't reflect tier
  quality.

Weight `w = 1` (baseline-fidelity). The mapping (close→1, reopen/escalate→0) is
the gc-native instantiation of the paper's "downstream task closure" channel.

### 4.2 Channel B — reviewer / verdict signal (SECONDARY, higher fidelity)

When a review formula runs (e.g. `mol-review-quorum`, refinery review), it emits
a structured `verdict ∈ {pass, pass_with_findings, fail, blocked}` plus
`gc.outcome`. Map to Bernoulli:

```
pass               -> q = 1
pass_with_findings -> q = 1   (conservative-friendly: a clean-enough pass)
fail               -> q = 0
blocked            -> dropped (infra/precondition, not a quality signal)
```

This is a *direct* observation of the cell that produced the artefact (it carries
`gc.model` / `gc.provider`, so it keys exactly). Weight `w_review > 1` (default
`3`): a reviewer judgment is worth several closures.

### 4.3 Channel C — eval-suite verdict (HIGHEST fidelity)

A deterministic eval run against held-out fixtures emits a judge verdict
`{pass, fail, partial}`. Conservative mapping (paper §3): `partial -> 0`,
`pass -> 1`, `fail -> 0`. Ground truth is known, so weight highest
(`w_eval`, default `5`). In v1 eval runs are **operator-initiated** (Layer 4
auto-scheduling deferred, §7), but their verdicts are ingested with full weight
whenever they exist, and they (later) populate the conformal calibration buffer.

### 4.4 Weighting & precedence

- A single dispatch yields **at most one** observation per cell, choosing the
  **highest-fidelity channel available** for that dispatch (C > B > A). Do not
  double-count: if a bead got a reviewer verdict, the closure is not separately
  counted for the same dispatch.
- Weights are config (`w_close=1`, `w_review=3`, `w_eval=5` defaults). They enter
  Layer 1 as the `w` multiplier on `(a, b)`.
- **Debounce / late signals.** Closure observations are emitted only after the
  reopen-debounce window to avoid counting a close that is immediately reverted.
  A reopen after the window arriving *late* emits a corrective `q = 0` for a new
  observation (we do not retro-edit; the posterior self-corrects with the next
  update).
- **Attribution.** An observation attaches to the cell of the **dispatch that
  produced the work**, identified by the dispatch's recorded
  `(provider, agent, shape, tier_id)` (the `bead_id` ↔ dispatch join, §5). Quality
  observed on a bead whose dispatch wasn't advisor-recorded is dropped.

---

## 5. Telemetry schema

The engine reads/writes **`.beads/telemetry/invocations.jsonl`** (one JSON object
per line; this is the paper's named sink and gc already keeps sibling JSONL there,
e.g. `routes.jsonl`, `interactions.jsonl`). Two logical record kinds share the
file, distinguished by `kind`:

### 5.1 `kind = "dispatch"` — written at dispatch time

The fields the engine needs to (a) reconstruct the cell and (b) later join a
quality outcome:

| Field         | Type   | Meaning                                                        |
|---------------|--------|----------------------------------------------------------------|
| `schema_version` | str | record schema version (e.g. `"advisor.v1"`)                  |
| `kind`        | str    | `"dispatch"`                                                   |
| `ts`          | str    | RFC3339 timestamp (dispatch time)                              |
| `bead_id`     | str    | the routed bead (join key to the quality record)              |
| `provider`    | str    | resolved provider (e.g. `claude`)                             |
| `agent`       | str    | **base** agent name (e.g. `polecat`)                          |
| `agent_instance` | str | full instance for audit (e.g. `whiskeyshop/gastown.polecat`) |
| `rig`         | str    | rig name (audit / future per-rig keying)                      |
| `shape`       | str    | resolved canonical shape (§2.2)                              |
| `tier_id`     | str    | roster tier token actually dispatched (§2.3)                 |
| `model`       | str    | concrete model string at dispatch (audit; models drift)      |
| `q_tol_class` | str    | tolerance class applied (Critical/Strict/Moderate/Lenient)   |
| `baseline_tier` | str  | `tier*` token in effect for this cell                        |
| `advised_tier`| str    | what the advisor recommended (may differ if operator overrode)|
| `forced_baseline` | bool | whether the static safety hatch forced `tier*` (§7)        |
| `cell_key`    | str    | denormalised `provider::agent::shape::tier_id` (convenience) |

> `cell_key = provider :: agent :: shape :: tier_id`. The dispatch→cell mapping is
> exactly this concatenation; nothing else is needed to locate the posterior.

### 5.2 `kind = "quality"` — written when an outcome is observed

| Field         | Type   | Meaning                                                        |
|---------------|--------|----------------------------------------------------------------|
| `schema_version` | str | `"advisor.v1"`                                                |
| `kind`        | str    | `"quality"`                                                   |
| `ts`          | str    | RFC3339 (observation time)                                    |
| `bead_id`     | str    | join key back to the `dispatch` record                       |
| `cell_key`    | str    | the cell credited (copied from the joined dispatch)          |
| `q`           | int    | `0` or `1` (Bernoulli outcome)                               |
| `channel`     | str    | `"close"` \| `"review"` \| `"eval"` (which channel fired)    |
| `weight`      | num    | `w` applied to the Beta update (§4.4)                        |
| `signal`      | str    | raw signal for audit (`closed`, `reopened`, `fail`, `pass_with_findings`, `partial`, …) |
| `n_dep`       | int    | downstream dependents at observation time (for loss audit)   |

### 5.3 Optional `kind = "recommendation"` (audit of advise calls)

Recording every `advise`/`inspect` call's `reasons` object is recommended for the
operator-agreement instrument the paper plans, but optional for v1. If written:
`{ kind:"recommendation", ts, cell_key, advised_tier, candidates:[{tier_id, q_lo,
exp_loss, cost_diff}], eval_flag }`.

### 5.4 Token counts

Cost needs `tok_in`/`tok_out`. If the dispatch path exposes realised token counts
(provider usage), record them on the `quality` (or a follow-up) record as
`tok_in`, `tok_out`. If unavailable, the engine uses a **configured representative
budget** per shape (the paper does the same — illustrative `1200 in / 400 out`)
for cost differentials; this is exact arithmetic on a fixed budget, flagged as
representative in the rationale.

### 5.5 Cell-store cache

`.beads/telemetry/advisor-cells.json` = `Map[cell_key] -> {a, b, n, last_update}`,
the materialised posteriors. It is a **cache**: deleting it and replaying
`invocations.jsonl` (priors + every `quality` record in order) reproduces it
exactly. The engine MUST treat the JSONL as the source of truth and the cell
store as rebuildable.

---

## 6. Surfaces (CLI)

Two read-only surfaces, mirroring the paper's `gt dispatch --advise` and
`gt advisor inspect`. Both default to human text and support `--json` (emit the
`reasons` object). Pack-provided as `gc`-discoverable commands (e.g. installed
under the pack's `bin/` and surfaced as `model-advisor advise|inspect`, or wired
as a `gc` subcommand by the engine bead — naming finalised there).

### 6.1 `advise <agent> <shape> [--tol <class>] [--provider <p>] [--rig <r>] [--baseline <tier>]`

Mirrors `gt dispatch --advise`. Returns the recommendation for the cell.

- **Inputs:** agent (base name), shape; optional tolerance-class override (else
  the cell's configured default), provider (else city default), baseline tier
  (else configured `tier*`).
- **Computes:** `recommend(...)` (§1.4) over the live posteriors.
- **Outputs (human):**
  - recommended `tier_id` (+ concrete model);
  - **rationale string** — e.g. *"sonnet: LCB q_lo=0.82 ≥ baseline mean 0.80 −
    0.05 tol; cheapest admitted tier; expected loss −$0.011/dispatch vs opus"* or,
    cold-start, *"opus (baseline): no cheaper tier clears tolerance — haiku
    q_lo=0.41, sonnet q_lo=0.58 both < 0.75 threshold (thin evidence, n<5)."*
  - **cost differential** vs each roster tier (and vs baseline), at the
    representative or realised token budget.
- **`--json`:** the full `reasons` object (candidates, per-candidate `q_lo`,
  `exp_loss`, `cost_diff`, `eval_flag`).
- **Integration:** intended to back a `gc sling --advise`-style hook so the
  dispatcher (mayor/formula) can consult the advisor before choosing a run target.
  v1 ships the standalone surface; the sling hook is an engine-bead follow-up.

### 6.2 `inspect <agent> <shape> [--provider <p>]`

Mirrors `gt advisor inspect`. Read-only deep view of the `(agent, shape)` cells
across the whole roster.

- **Per-tier posterior:** `Beta(a~, b~)`, mean, the LCB `q_lo`, observation count
  `n`, last-update time, and admit/reject under the current tolerance.
- **Credible interval on the quality drop** vs baseline: report the
  `1 - alpha` credible interval on `theta[tier*] - theta[tier]` for each candidate
  (so the operator sees the credible *degradation*, the quantity the constraint
  bounds), e.g. *"haiku: quality-drop 95% CI [0.06, 0.31] — exceeds 0.05 tol."*
- **Next eval to resolve the widest cell:** identify the cell (tier) with the
  widest posterior CI half-width that is *also* gating a decision (i.e. its width
  is why a cheaper tier can't be admitted), and name it as the highest-value eval
  probe — *"widest gating cell: sonnet (CI half-width 0.14 > 0.10); run an eval on
  claude::polecat::implement::sonnet to resolve."* This is the operator-facing
  realisation of Layer 4's uncertainty-trigger (the auto-dispatch is deferred,
  §7; `inspect` surfaces the recommendation so a human can run it).
- **`--json`:** the per-tier table + the widest-cell pointer.

Both surfaces are **pure reads** over the cell store/JSONL; neither dispatches,
mutates beads, or changes config.

---

## 7. What's adapted vs the paper, and what's deferred

### 7.1 Adapted (deliberate divergences)

| Paper                                          | This pack                                                                 |
|------------------------------------------------|---------------------------------------------------------------------------|
| Fixed 3 tiers (haiku/sonnet/opus)              | **Arbitrary user-configured roster** of `(provider, model)` run targets, cost-ordered by `rank`; `O(K)` over any K. Grounded in gc's existing `gc.run_target/provider/model` dispatch metadata. |
| 17 fixed agents, per-agent ad-hoc shapes       | gc roster discovered from config (mayor/deacon/boot/witness/refinery/polecat/dog/crew + consumer agents); a **5-shape gc-native taxonomy** (lookup/implement/judge/review/patrol), config-extensible, with per-agent canonical shape sets. |
| Cell = agent×shape×tier                         | Cell = **provider×agent×shape×tier**, agent = base role (rig-pooled). Provider in the key for multi-provider/per-rig rosters. |
| Offline empirical landscape seeds every prior  | **Conservative cost-ordered cold-start** (optimistic baseline, pessimistic-wide cheaper tiers ⇒ day-1 = "recommend baseline until earned"); the confidence→pseudocount rule is retained for consumers who supply a `priors.json`. |
| Quality via reviewer/eval/downstream closure   | **Bead lifecycle as primary** (close→1, reopen/escalate→0), reviewer verdicts (`pass/pass_with_findings/fail/blocked`) and eval (`pass/partial/fail`) as weighted higher-fidelity secondaries. Same three-channel philosophy, gc-native sources. |
| Conformal LCB (rolling calibration buffer)     | **Wilson / exact-Beta-ppf LCB** in v1 (coincides asymptotically); conformal backend behind a flag for when buffers exist. |
| `gt dispatch --advise` / `gt advisor inspect`  | `advise <agent> <shape>` / `inspect <agent> <shape>` (same semantics, gc CLI). |

### 7.2 Kept faithfully (the load-bearing parts — do not water down)

- The **constrained decision rule** (§1.2): cheapest tier whose posterior-credible
  quality-drop ≤ `q_tol` at `1 - alpha = 0.95`.
- The **conservative gate** (§1.3 Layer 2): one-sided LCB ≥ `mu* - q_tol`; baseline
  always feasible; cold-start rejects by default.
- The **asymmetric loss** (§1.3 Layer 3) with class multipliers ∞/20/5/1 and the
  cascade term scaled by downstream-dependent count `N_dep`.
- The **`M[Critical] = ∞` hard rule**: Critical cells never enter the
  downgrade/exploration set. This is the design contract, not a tunable.
- The **conservative property** (§5 Thm): every recommended downgrade is credible
  at `1 - alpha` — preserved because Layer 3 only removes from the admitted set.
- **Pure-function `recommend`, deterministic tests, structured `reasons`**
  (audit-first). The paper attributes operator trust to the `reasons` object more
  than to algorithmic accuracy.
- **Bounded-influence priors** (≤20/side) so real evidence dominates fast.

### 7.3 Deferred (explicitly out of v1 scope; designed-for, not built)

> **STATUS — implemented in v3 (2026-06-03).** Every item below is now built, each behind a
> **default-off** flag, so the v1 design context that follows still describes the *default*
> behavior. Map: Layer-4 eval → `advisor eval-schedule`; conformal → `lcb_backend=conformal`;
> hierarchical → `pooling=empirical-bayes` (stdlib empirical-Bayes; optional PyMC extra);
> federation → `[federation]` + `advisor federate`; cascade → `advise --cascade-bead`;
> continuous → `continuous_quality=true`; Thompson → `mode=thompson`; change-point →
> `changepoint=true` + `advisor drift`. See the README **"Advanced modes"** and
> `docs/V3-BUILD-BRIEF.md`. The text below is preserved as the original design rationale.

- **Layer 4 auto-scheduled eval.** v1 *records* the uncertainty trigger and
  *surfaces* the highest-value eval in `inspect`, but does not auto-dispatch eval
  runs. Auto-scheduling proportional to posterior width is a later bead. The
  schema and trigger hook are in place.
- **Strict conformal calibration.** The rolling per-cell `(predicted, observed)`
  calibration buffer and the distribution-free `ConformalLCB` backend are deferred
  until cells have exchangeable history; v1's Wilson/Beta-ppf LCB is the
  asymptotic stand-in.
- **Full hierarchical Bayesian inference.** v1 uses the closed-form pooled-
  pseudocount approximation (§1.3); Stan/PyMC Beta-Beta inference is out of scope.
- **Hierarchical-bandit / multi-tenant federation.** Sharing posteriors across
  consumer repos to accelerate thin-cell convergence (paper §7 "when this won't
  work") — privacy/trust questions, deferred.
- **Sequential / critical-path-aware cascade modelling.** v1 treats each dispatch
  as one-shot with an `N_dep` blast-radius scalar; a contextual-MDP treatment of
  an ADR cascading into N builder dispatches (paper §7) is deferred.
- **Continuous quality signal.** v1 is Bernoulli (pass/fail). A Gaussian/Beta
  continuous-score posterior (paper OQ-A6) is deferred.
- **Genuine Thompson Sampling mode.** v1 ships the LCB-gated deterministic rule
  (the paper's production rule). A seeded per-tier Beta-sampling mode is left as a
  flag (the seed hook in `recommend` exists for it).
- **Change-point detection** for upstream model drift/deprecation. Deferred; the
  static-baseline safety hatch (below) is the v1 mitigation.

### 7.4 Safety hatch (kept from §7, ships in v1)

Static frontmatter / configured tier is the **policy floor**: an operator can pin
a cell to its baseline `tier*` via a `force_baseline = true` flag, short-circuiting
all learning and playing the configured tier. Motivated by (a) incident response
(exploration is wrong during an incident) and (b) upstream model drift outpacing
the posteriors. The advisor recommends; the operator can always lock. This is the
trust precondition under which the advisor is allowed to drive routing at all.

---

## 8. Implementation notes for the engine bead

- **`recommend(state, cell_key, q_tol_class, baseline_tier) -> (tier, reasons)`
  is a pure function.** No I/O, no globals. `state` = the in-memory cell store +
  roster config. This makes the decision exhaustively unit-testable and is a hard
  requirement (paper §5).
- **Keep the Beta sampler seedable** even though v1's rule is LCB-deterministic —
  it future-proofs the genuine-TS mode and makes any randomised test reproducible.
- **`reasons` is the contract surface.** Populate candidates, per-candidate `q_lo`,
  `exp_loss`, `cost_diff`, and `eval_flag` on *every* call. Both `advise` and
  `inspect` render from it; `--json` emits it verbatim.
- **Sources of truth vs caches.** `invocations.jsonl` (append-only) is truth;
  `advisor-cells.json` is a rebuildable materialisation. Never trust the cache
  over the log.
- **Degradation.** Missing roster config ⇒ surface a clear error (the advisor
  cannot order tiers without it). Missing priors ⇒ cold-start (§3.2). Missing
  token counts ⇒ representative budget (§5.4). Thin/zero evidence ⇒ recommend
  baseline. The advisor must never *block* a dispatch; worst case it recommends
  `tier*`.
- **Config files the engine reads:** `roster.toml` (tiers), `shapes.toml`
  (shape names + default tolerance class + per-agent canonical shapes),
  optional `priors.json` (confidence-seeded cold start). All discovered via the
  pack's config; nothing hard-coded.
- **Hyperparameter defaults (paper appendix D):** `alpha = 0.05`,
  `theta_eval = 0.10`, pooling cap `lambda = 0.5`, `M = {∞, 20, 5, 1}`,
  `s_prior ≈ 4`, channel weights `{close:1, review:3, eval:5}`,
  reopen-debounce `24h`. All config-overridable.

---

## 9. Acceptance (what "the engine implements this doc" means)

1. Reads a config-driven roster of arbitrary K tiers and a config-driven shape
   taxonomy; keys cells as `provider::agent::shape::tier_id`.
2. Maintains per-cell `Beta(a,b)` posteriors with closed-form Bernoulli updates
   and capped pseudocount pooling; persists to a rebuildable cell-store cache
   over `invocations.jsonl`.
3. Cold-starts conservatively (baseline-only recommendations until cheaper tiers
   earn admission); honours a supplied `priors.json` via the confidence rule.
4. Implements the gate (LCB ≥ `mu* - q_tol`, baseline always feasible, Critical
   never downgrades) and the asymmetric-loss selection, as a pure, deterministic,
   seedable `recommend` returning a structured `reasons` object.
5. Ingests quality from bead closure (primary) + reviewer/eval verdicts
   (weighted), attributing each observation to the producing dispatch's cell.
6. Emits the `dispatch` and `quality` telemetry records (§5) to
   `.beads/telemetry/invocations.jsonl`.
7. Ships `advise <agent> <shape>` (tier + rationale + cost diff) and
   `inspect <agent> <shape>` (per-tier posterior, quality-drop credible interval,
   widest-gating-cell eval pointer), both with `--json`.
8. Provides the `force_baseline` safety hatch.
