# model-advisor — AUTO-APPLY

Per-agent **auto-apply** automates the v1 `apply` action (bead `bh-917`, v2a). It
is a conservative, evidence-gated loop that keeps **each agent's `model` config
field** at its cost-optimal tier as quality evidence accrues — pack-only, no
gc-core dependency.

Where `bin/advisor apply <agent>` sets *one* agent's model for *one* shape on
demand, `bin/advisor auto-apply` sweeps **every configured agent** and writes the
`model` field only for changes the engine's own gate has already certified.

- Engine / store / config: `docs/DESIGN.md` (the CC-TS decision rule).
- Implementation: `modeladvisor/autoapply.py` (`auto_apply(...)`), surfaced by
  `modeladvisor/cli.py` as the `auto-apply` subcommand.

---

## 1. The per-agent tier policy

An agent runs **one** model but may serve **several shapes** (DESIGN §2.2:
`polecat → {implement, lookup}`, `refinery → {review, judge}`, …). The engine
decides a tier per *(agent, shape)* cell; auto-apply collapses those into a
single per-agent model **without under-serving any shape**:

> For each of the agent's canonical shapes, take the engine's per-shape
> recommended tier. The agent's **conservative tier** is the **safest
> (most-capable) tier among them** — the `argmax` over the cost order.

Why the *most-capable*, not the cheapest? Because one model has to satisfy every
shape the agent serves. The engine returns a *cheaper-than-baseline* tier for a
shape only when that shape's one-sided lower confidence bound has credibly
cleared tolerance (DESIGN §1.3 Layer 2); a shape with thin/cold evidence still
recommends the baseline `tier*`. So the `argmax` lands **below baseline only when
ALL of the agent's shapes have independently earned a cheaper tier**. If even one
shape is still cold, the safest tier is the baseline and the agent is left
untouched. This lifts the engine's conservative "never silently downgrade"
property from the cell to the agent.

**Worked example** (roster `haiku ≺ sonnet ≺ opus`, baseline `opus`):

| Agent      | per-shape recommendations        | conservative tier | outcome |
|------------|----------------------------------|-------------------|---------|
| `polecat`  | implement→`sonnet`, lookup→`sonnet` | `sonnet`        | **downgrade applied** (all shapes cleared) |
| `polecat`  | implement→`sonnet`, lookup→`opus`   | `opus`          | no-op (lookup still cold → safest is baseline) |
| `mayor`    | judge→`opus`, implement→`opus`, lookup→`opus` | `opus` | no-op (cold; already on implicit default) |
| `refinery` | review→`sonnet`, judge→`opus` (Critical) | —          | **blocked** (Critical shape present) |

The **binding shape** in the report is the shape whose recommendation set the
conservative tier (the most-capable one).

---

## 2. The apply gate — when a computed tier is actually written

A per-agent change is written only when **all** hold:

1. **It differs.** The chosen tier's model differs from the agent's current
   `model` config (idempotent no-op refusal otherwise).
2. **The agent is not Critical-pinned.** If *any* of its shapes resolves to a
   `Critical` tolerance class (`q_tol = 0`, `M = ∞`) or carries the
   `force_baseline` safety hatch, the agent is **blocked** — never touched,
   regardless of evidence (DESIGN §1.2 / §7.4). This is the design contract
   operators rely on to let the advisor drive routing at all.
3. **The change is evidence-admissible:**
   - A **downgrade** (chosen tier cheaper than baseline `tier*`) is admissible
     *by construction* — it can only arise when every shape's gate admitted at
     least this-cheap a tier, so the evidence is already strong. A thin-evidence
     downgrade is *impossible*: the engine never returns a sub-baseline tier
     without gate admission. (auto-apply re-confirms the binding shape's gate
     admission defensively before any sub-baseline write.)
   - An **upgrade** (chosen tier ≥ the agent's *current* tier) is always
     admissible — moving to a more-capable model is the safe direction (e.g.
     evidence retreated, or an operator hand-set a too-cheap model and the
     advisor pulls it back toward the known-good frontier).

We **never auto-downgrade on thin evidence**; the only sub-baseline writes are
ones the engine's gate already certified.

**No-evidence churn guard.** When the conservative tier is just the baseline and
no shape has earned anything cheaper, auto-apply reports a **no-op** rather than
writing an explicit `model = <baseline>` onto a cold agent — that would be config
churn with no decision behind it. The baseline is only *written* to correct an
under-capable hand-set model (current strictly cheaper than baseline).

**Per-agent statuses** (the audit surface):

| status    | meaning |
|-----------|---------|
| `applied` | config written; model changed |
| `dry-run` | a change is planned but `--dry-run` (the default) is in effect |
| `noop`    | chosen model already in effect, or cold-baseline with nothing to do |
| `skipped` | a change was computed but the gate withheld it |
| `blocked` | Critical / `force_baseline` agent — never touched |
| `error`   | could not resolve config / compute (isolated; the sweep continues) |

**Backups & idempotence.** Each config file is backed up **once per run** (the
first time any agent living in it is about to be written) to a timestamped
`.advisor-bak-*` sibling. Re-running with no new evidence is a clean series of
no-op refusals that write nothing.

---

## 3. The CLI surface

```
bin/advisor auto-apply [--town | --rig NAME] [--city PATH] [--dry-run] [--apply] [--json]
```

- **Dry-run by default.** Without `--apply` it computes and prints the full plan
  but writes nothing and creates no backups. `--dry-run` is accepted explicitly
  (it is the default). Pass `--apply` to actually write.
- `--town` (default) sweeps all town/city agents; `--rig NAME` narrows the config
  search + scope label to one rig.
- `--city PATH` sets the city root (else `$GC_CITY` / cwd).
- `--json` emits the full structured per-agent report.
- Config/telemetry are resolved exactly as the other subcommands:
  `--config`/`$ADVISOR_TOML` for `advisor.toml`,
  `--telemetry-dir`/`$ADVISOR_TELEMETRY_DIR` (else `<cwd>/.beads/telemetry`) for
  the live `invocations.jsonl` (rebuilt into the cell store; DESIGN §5.5).

Exit code is `0` on a healthy run (including a dry run with planned changes) and
`1` only if a per-agent error occurred — so a scheduled run's failures surface in
`gc order history` without a dry run looking like a failure.

Example dry-run (the default):

```text
auto-apply [town]  mode: DRY-RUN (no files written)
  provider: claude
  [WOULD   ] polecat
      tier: sonnet (binding shape: implement)   current: (unset) -> chosen: claude-sonnet-4-5
      per-shape: implement=sonnet, lookup=sonnet
      why: set: (unset) -> claude-sonnet-4-5; all shapes cleared tolerance for sonnet (binding: implement).
  [BLOCKED ] refinery
      tier: opus (binding shape: review)   current: (unset) -> chosen: claude-opus-4-8
      per-shape: review=opus, judge=opus
      why: Critical/force_baseline agent (shapes: judge) — never auto-applied.
  [noop    ] mayor
      ...
  ----------------------------------------------------------------
  SUMMARY: 6 agents | 0 applied | 1 planned | 1 no-op | 0 skipped | 1 blocked | 3 error
  NOTE: this was a dry run — re-run with --apply to write the 1 planned change(s).
```

---

## 4. Scheduling artifact (run it periodically)

gc dispatches scheduled / event-driven work via **orders** (`gc order --help`):
flat `orders/<name>.toml` files pairing a *trigger* (`cron` / `cooldown` /
`condition` / `event` / `manual`) with an *action* (a `formula` wisp, or an
`exec` script). auto-apply is a script, so it ships as an **exec order**.

The pack ships two example artifacts (NOT registered against any live city):

| File | Role |
|------|------|
| `orders/model-advisor-auto-apply.toml` | the order: a daily `cron` trigger that runs the wrapper |
| `orders/scripts/auto-apply.sh`         | the exec wrapper: drives `bin/advisor auto-apply` under the pack venv |

`orders/model-advisor-auto-apply.toml`:

```toml
[order]
description = "Keep each agent's model at its evidence-justified cost-optimal tier (model-advisor)"
trigger  = "cron"
schedule = "30 0 * * *"           # 00:30 daily — tune to your evidence velocity
exec     = "$PACK_DIR/orders/scripts/auto-apply.sh"
timeout  = "120s"
enabled  = true
```

`$PACK_DIR` is expanded by the controller to the pack directory. (Exec orders
cannot declare a `pool` — there is no agent pipeline.) To use a fixed inter-run
gap instead of a wall-clock time, switch to a cooldown trigger:

```toml
trigger  = "cooldown"
interval = "24h"
```

### Arming (safe by default)

The wrapper runs in **dry-run** unless you export `MODEL_ADVISOR_AUTO_APPLY=1`
(or `true`/`yes`) in the order's environment. So you can import and observe the
order for a few cycles (watch `gc order history` / the JSON it logs) before it
ever writes config. Optional env knobs the wrapper honours:

| env var | effect | default |
|---------|--------|---------|
| `MODEL_ADVISOR_AUTO_APPLY` | `1`/`true`/`yes` → actually write (else dry-run) | dry-run |
| `MODEL_ADVISOR_RIG`        | narrow scope to one rig (`--rig`)               | town-wide |
| `ADVISOR_TOML`             | path to `advisor.toml`                          | pack default |
| `ADVISOR_TELEMETRY_DIR`    | telemetry dir                                   | `<city>/.beads/telemetry` |

---

## 5. Wiring the schedule — per town and per rig

> The pack does **not** register this order against the live city. Activate it by
> placing it in an orders layer that gc discovers, then verify with
> `gc order list` / `gc order check`, and trigger on demand with `gc order run`.

### Town-wide (all agents)

1. Make the order discoverable. Either import the pack's formula layer in the
   city (gc scans `orders/` in each formula-layer directory), or copy the order
   into a city orders layer:

   ```bash
   mkdir -p "$GC_CITY/.gc/system/packs/model-advisor/orders/scripts"
   cp packs/model-advisor/orders/model-advisor-auto-apply.toml \
      "$GC_CITY/.gc/system/packs/model-advisor/orders/"
   cp packs/model-advisor/orders/scripts/auto-apply.sh \
      "$GC_CITY/.gc/system/packs/model-advisor/orders/scripts/"
   ```

2. Verify it is seen and check its trigger:

   ```bash
   gc order list
   gc order show model-advisor-auto-apply
   gc order check          # is it due?
   ```

3. Dry-run it on demand (safe; env unset → dry-run):

   ```bash
   gc order run model-advisor-auto-apply
   gc order history
   ```

4. Arm it when you trust the plan — set `MODEL_ADVISOR_AUTO_APPLY=1` in the order
   environment (e.g. in the order layer's environment, or wrap the exec). The
   scheduled run will then write evidence-strong changes only.

### Per rig

Scope the run to one rig two ways:

- **Per-rig order layer** — drop the order into that rig's pack orders directory;
  the controller sets `GC_RIG` for rig-scoped orders and the wrapper forwards it
  as `--rig`. Same-name orders in different rigs are disambiguated with
  `gc order run <name> --rig <rig>`.
- **One town order, pinned to a rig** — set `MODEL_ADVISOR_RIG=<rig>` in the
  order environment; the wrapper passes `--rig <rig>` so the config resolver
  narrows the model-field search to that rig's pack layout.

Because the advisor keys cells by **base** agent name (rig-pooled, DESIGN §2.4),
the *decision* for an agent is the same town-wide; `--rig` only narrows **where**
the `model` field is written, not what tier is chosen.

### Cadence guidance

Match the cron cadence to how fast evidence accrues. A busy town closing many
beads converges cells in days — daily (`@daily` / `30 0 * * *`) is reasonable. A
quiet town should run weekly (`30 0 * * 0`) so a handful of closures don't swing
a decision. The decision is conservative either way: more frequent runs cannot
*cause* an unjustified downgrade — they can only apply one sooner once the
evidence is already strong.

---

## 6. Operational notes

- **Reversible.** Every write is backed up once per run; restore from the
  `.advisor-bak-*` sibling to revert.
- **Pin to opt out.** Set a shape (or the agent's gating shape) to the `Critical`
  tolerance class, or `force_baseline = true`, in `advisor.toml` to make an agent
  permanently `blocked` from auto-apply (DESIGN §7.4).
- **Pairs with `inspect`.** Before arming, `bin/advisor inspect <agent> <shape>`
  shows the per-tier posteriors and the quality-drop credible intervals behind
  each decision.
- **Degrades safely.** With no telemetry every agent cold-starts to the baseline
  and auto-apply is an all-no-op sweep that writes nothing.
