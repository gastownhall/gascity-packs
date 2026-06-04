"""Per-agent **auto-apply** — automate the v1 ``apply`` as an evidence-gated loop.

This is bead ``bh-917`` (v2a): a conservative, audit-first automation of the
single-agent ``cli.apply`` action.  Where ``apply`` sets *one* agent's ``model``
config field for *one* shape on demand, :func:`auto_apply` sweeps **every
configured agent**, computes a *conservative per-agent tier*, and writes the
``model`` field only when the evidence is strong enough that the engine's own
gate has already admitted the change.  It is pack-only: it depends solely on the
sibling :mod:`modeladvisor.engine` / :mod:`modeladvisor.config` /
:mod:`modeladvisor.store` modules and reuses :mod:`modeladvisor.cli`'s
format-preserving config editor (no gc-core dependency).

--------------------------------------------------------------------------- #
The per-agent tier policy (the heart of v2a)
--------------------------------------------------------------------------- #

An agent runs **one** model, but may serve **several shapes** (DESIGN §2.2:
``polecat → {implement, lookup}``, ``refinery → {review, judge}``, …).  The
engine's :func:`recommend` decides a tier *per (agent, shape) cell*; auto-apply
must collapse those into a single per-agent model without ever under-serving a
shape.  The rule:

    For each of the agent's canonical shapes, take the engine's per-shape
    recommended tier.  The agent's **conservative tier** is the *safest
    (most-capable) tier among them* — i.e. ``argmax`` over the cost order.

Why ``max`` (most-capable), not ``min`` (cheapest)?  Because a single model has
to satisfy *every* shape the agent serves.  Picking the most-capable per-shape
recommendation guarantees **no shape is under-served**.  The engine only returns
a *cheaper-than-baseline* tier for a shape when that shape's one-sided lower
confidence bound has credibly cleared tolerance (DESIGN §1.3 Layer 2); a shape
with thin/cold evidence still recommends the baseline ``tier*``.  Therefore the
``max`` lands **below baseline only when ALL of the agent's shapes have
independently earned a cheaper tier** — exactly the contract "unless ALL the
agent's shapes credibly clear tolerance for a cheaper tier."  If even one shape
is still cold, the ``max`` is the baseline and the agent is left untouched.  This
is the conservative property lifted from the cell to the agent: no silent
downgrade before evidence.

--------------------------------------------------------------------------- #
The apply gate (when a computed tier is actually written)
--------------------------------------------------------------------------- #

A per-agent change is written only when **all** hold:

  (i)   the chosen tier's model **differs** from the agent's current ``model``
        config (idempotent no-op refusal otherwise);
  (ii)  the agent is **not Critical-pinned** — if *any* of its shapes resolves
        to a ``Critical`` tolerance class (``q_tol = 0``, ``M = ∞``) or carries
        the ``force_baseline`` safety hatch, the agent is **blocked**: never
        touched, regardless of evidence (DESIGN §1.2 / §7.4 — the design
        contract operators rely on to let the advisor drive routing at all);
  (iii) the change is **evidence-admissible**:
          * a **downgrade** (chosen tier cheaper than the baseline ``tier*``)
            is admissible *by construction* — it can only arise when every
            shape's gate admitted at least this-cheap a tier, so the evidence is
            already strong.  A thin-evidence downgrade is impossible because the
            engine never returns a sub-baseline tier without gate admission.
          * an **upgrade** (chosen tier ≥ the agent's *current* tier) is always
            admissible — moving to a more-capable model is the safe direction
            (e.g. evidence retreated, or an operator hand-set a too-cheap model
            and the advisor pulls it back toward the known-good frontier).
        We **never auto-downgrade on thin evidence**; the only sub-baseline
        writes are ones the engine's gate already certified.

Idempotence & backups: a config file is backed up **once per run** (the first
time any agent that lives in it is about to be written), to a timestamped
``.advisor-bak-*`` sibling, reusing :func:`cli.backup_file`.  Re-running with no
new evidence is a clean series of no-op refusals that write nothing.  ``dry_run``
(the default-safe mode) computes and reports the full plan but never opens a file
for writing and never creates a backup.

The result is a structured, per-agent report (``current → chosen``, the binding
shape and reason, and an ``applied`` / ``skipped`` / ``blocked`` / ``noop`` /
``error`` status) — the audit surface, mirroring the engine's ``reasons``
contract (DESIGN §1.4 property 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from modeladvisor import cli as _cli

# Per-agent outcome codes (stable; the CLI / JSON consumers key on these).
STATUS_APPLIED = "applied"  # config written: model changed
STATUS_NOOP = "noop"  # chosen model already in effect (idempotent)
STATUS_BLOCKED = "blocked"  # Critical / force_baseline agent — never touched
STATUS_SKIPPED = "skipped"  # a change was computed but the gate withheld it
STATUS_DRYRUN = "dry-run"  # a change is planned but --dry-run is in effect
STATUS_ERROR = "error"  # could not resolve config / compute (per-agent isolated)


@dataclass
class AgentDecision:
    """The auto-apply decision + audit trail for one agent."""

    agent: str
    status: str
    current_model: Optional[str] = None
    chosen_model: Optional[str] = None
    chosen_tier: Optional[str] = None
    baseline_tier: Optional[str] = None
    #: The shape whose per-shape recommendation set the conservative tier.
    binding_shape: Optional[str] = None
    #: Direction of the change relative to the *current* model: "down"|"up"|None.
    direction: Optional[str] = None
    reason: str = ""
    #: Per-shape recommended tiers (audit): {shape: tier_id}.
    per_shape: dict = field(default_factory=dict)
    #: Whether any of the agent's shapes is Critical / force_baseline.
    critical: bool = False
    config_path: Optional[str] = None
    config_scope: Optional[str] = None
    backup_path: Optional[str] = None

    @property
    def changed(self) -> bool:
        return self.status == STATUS_APPLIED

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "status": self.status,
            "current_model": self.current_model,
            "chosen_model": self.chosen_model,
            "chosen_tier": self.chosen_tier,
            "baseline_tier": self.baseline_tier,
            "binding_shape": self.binding_shape,
            "direction": self.direction,
            "reason": self.reason,
            "per_shape": dict(self.per_shape),
            "critical": self.critical,
            "config_path": self.config_path,
            "config_scope": self.config_scope,
            "backup_path": self.backup_path,
        }


@dataclass
class AutoApplyReport:
    """The whole-run report: per-agent decisions + a roll-up summary."""

    scope: str
    dry_run: bool
    provider: str
    decisions: list = field(default_factory=list)

    # ---- roll-up counters -------------------------------------------------- #
    def count(self, status: str) -> int:
        return sum(1 for d in self.decisions if d.status == status)

    @property
    def applied(self) -> list:
        return [d for d in self.decisions if d.status == STATUS_APPLIED]

    @property
    def any_applied(self) -> bool:
        return any(d.status == STATUS_APPLIED for d in self.decisions)

    def summary(self) -> dict:
        return {
            "agents": len(self.decisions),
            STATUS_APPLIED: self.count(STATUS_APPLIED),
            STATUS_DRYRUN: self.count(STATUS_DRYRUN),
            STATUS_NOOP: self.count(STATUS_NOOP),
            STATUS_SKIPPED: self.count(STATUS_SKIPPED),
            STATUS_BLOCKED: self.count(STATUS_BLOCKED),
            STATUS_ERROR: self.count(STATUS_ERROR),
        }

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "dry_run": self.dry_run,
            "provider": self.provider,
            "summary": self.summary(),
            "decisions": [d.to_dict() for d in self.decisions],
        }


# --------------------------------------------------------------------------- #
# Cost-order helpers (the "≺" order is the position in cfg.tier_ids)            #
# --------------------------------------------------------------------------- #


def _rank(cfg: Any, tier_id: str) -> int:
    """Position of ``tier_id`` in the cost order (0 = cheapest). -1 if unknown."""
    ids = list(cfg.tier_ids)
    return ids.index(tier_id) if tier_id in ids else -1


def _model_to_tier(cfg: Any, model: Optional[str]) -> Optional[str]:
    """Reverse-map a concrete ``model`` string to its roster tier id (or None)."""
    if not model:
        return None
    for t in cfg.tiers:
        if t.model == model:
            return t.tier_id
    return None


def _agents_in_scope(cfg: Any, *, scope: str, agents: Optional[Sequence[str]]) -> list:
    """The base agent names to sweep.

    ``scope`` is advisory metadata for the report (``"town"`` / ``"rig:<n>"``);
    the actual agent set comes from the config's declared agents (``agent_shapes``
    keys) unless an explicit ``agents`` list is supplied.  The advisor keys cells
    by **base** agent name (rig-pooled, DESIGN §2.4), so the same per-agent model
    decision applies whether the operator scopes the *write* at town or rig level
    — the rig narrowing happens in the config resolver, not here.
    """
    if agents:
        return list(agents)
    declared = getattr(cfg, "agent_shapes", None) or {}
    return sorted(declared.keys())


# --------------------------------------------------------------------------- #
# Per-agent decision                                                            #
# --------------------------------------------------------------------------- #


def decide_agent(
    agent: str,
    cfg: Any,
    store: Any,
    engine: Any,
    *,
    provider: str,
) -> AgentDecision:
    """Compute the conservative per-agent tier + apply intent for one agent.

    Pure (no I/O, no config-file read): runs the engine over each canonical
    shape, takes the safest (most-capable) per-shape recommendation, and records
    the binding shape + direction.  The *current model* and the actual write
    happen in :func:`auto_apply`, which owns the file editor.
    """
    shapes = list(cfg.canonical_shapes_for(agent))
    if not shapes:
        return AgentDecision(
            agent=agent,
            status=STATUS_SKIPPED,
            reason="agent has no canonical shapes configured",
        )

    # Critical / force-baseline detection: if ANY shape is pinned, the agent is
    # blocked from auto-apply entirely (belt-and-braces with the engine, which
    # already refuses to downgrade such a cell).
    critical_shapes = []
    for shp in shapes:
        try:
            if cfg.tol_class_for(agent, shp).is_critical or cfg.is_forced_baseline(agent, shp):
                critical_shapes.append(shp)
        except Exception:
            # An unknown shape/class shouldn't abort the whole agent; treat as
            # non-critical and let the engine call below surface any real error.
            continue
    is_critical = bool(critical_shapes)

    # Per-shape recommendations → safest (max-rank) tier.
    per_shape: dict[str, str] = {}
    safest_tier: Optional[str] = None
    safest_rank = -1
    binding_shape: Optional[str] = None
    baseline_tier: Optional[str] = None
    for shp in shapes:
        rec = engine.recommend(agent, shp, cfg, store, provider=provider)
        tid = _cli._get(rec, "tier_id")
        if baseline_tier is None:
            reasons = _cli._get(rec, "reasons", {}) or {}
            cell = reasons.get("cell", {}) if isinstance(reasons, dict) else {}
            baseline_tier = cell.get("baseline_tier") or cfg.baseline_tier_id_for(agent, shp)
        per_shape[shp] = tid
        r = _rank(cfg, tid)
        if r > safest_rank:
            safest_rank = r
            safest_tier = tid
            binding_shape = shp

    chosen_tier = safest_tier
    chosen_model = cfg.tier(chosen_tier).model if chosen_tier else None

    decision = AgentDecision(
        agent=agent,
        status=STATUS_SKIPPED,  # provisional; resolved by auto_apply once current is known
        chosen_tier=chosen_tier,
        chosen_model=chosen_model,
        baseline_tier=baseline_tier,
        binding_shape=binding_shape,
        per_shape=per_shape,
        critical=is_critical,
    )

    if is_critical:
        decision.status = STATUS_BLOCKED
        decision.reason = (
            f"Critical/force_baseline agent (shapes: {', '.join(critical_shapes)}) — "
            "never auto-applied; baseline is the only feasible tier."
        )
    return decision


# --------------------------------------------------------------------------- #
# The sweep                                                                     #
# --------------------------------------------------------------------------- #


def auto_apply(
    cfg: Any,
    store: Any,
    *,
    scope: str = "town",
    dry_run: bool = True,
    provider: Optional[str] = None,
    agents: Optional[Sequence[str]] = None,
    city: Optional[str] = None,
    rig: Optional[str] = None,
    engine: Any = None,
) -> AutoApplyReport:
    """Sweep every configured agent and apply each one's conservative tier.

    See the module docstring for the full policy.  In one line: for each agent,
    write its ``model`` config to the *safest tier across its shapes* — but only
    when that differs from the current model, the agent is not Critical-pinned,
    and the change is evidence-admissible (a sub-baseline tier the engine's gate
    already certified, or any upgrade toward the known-good frontier).

    Parameters
    ----------
    cfg, store:
        The resolved advisor config and the materialised cell store (the engine
        state).  ``store`` should be built from live telemetry by the caller
        (``CellStore.rebuild`` over ``invocations.jsonl``); auto-apply only reads
        it.
    scope:
        Advisory label recorded in the report (``"town"`` or ``"rig:<name>"``).
        The agent *set* is the config's declared agents (or ``agents``); the
        write *location* is resolved per agent via ``city`` / ``rig``.
    dry_run:
        When True (the safe default), compute and report the full plan but write
        nothing and create no backups.
    provider:
        Cell-key provider; defaults to ``cfg.default_provider``.
    agents:
        Explicit agent list override (else every agent declared in config).
    city, rig:
        Forwarded to :func:`cli.resolve_agent_config` to locate each agent's
        config file/scope (the same resolver ``apply`` uses).
    engine:
        Injectable engine module (defaults to the real
        :mod:`modeladvisor.engine`); tests pass a stub.

    Returns
    -------
    :class:`AutoApplyReport` with a per-agent :class:`AgentDecision` list and a
    roll-up summary.  This function never raises for a per-agent problem (config
    unresolved, etc.) — it records a ``STATUS_ERROR`` decision and continues, so
    one mis-configured agent cannot abort the whole sweep.
    """
    if engine is None:
        engine = _cli._load_engine()
    provider = provider or getattr(cfg, "default_provider", None) or "claude"

    report = AutoApplyReport(scope=scope, dry_run=dry_run, provider=provider)
    backed_up: set[str] = set()  # files already backed up this run (once each)

    for agent in _agents_in_scope(cfg, scope=scope, agents=agents):
        try:
            decision = decide_agent(agent, cfg, store, engine, provider=provider)
        except Exception as e:  # engine/config blew up for this agent only
            report.decisions.append(
                AgentDecision(
                    agent=agent,
                    status=STATUS_ERROR,
                    reason=f"could not compute recommendation: {e}",
                )
            )
            continue

        # Blocked agents are reported and never touched.
        if decision.status == STATUS_BLOCKED:
            report.decisions.append(decision)
            continue

        if not decision.chosen_model:
            decision.status = STATUS_ERROR
            decision.reason = "engine returned no concrete model for the binding shape"
            report.decisions.append(decision)
            continue

        # Resolve where this agent's model field lives.
        try:
            target = _cli.resolve_agent_config(agent, city=city, rig=rig)
        except _cli.ConfigResolveError as e:
            decision.status = STATUS_ERROR
            decision.reason = f"config not resolvable: {e}"
            report.decisions.append(decision)
            continue

        decision.config_path = target.path
        decision.config_scope = target.describe()
        current = _cli.read_model_field(target)
        decision.current_model = current

        # Idempotent no-op: chosen model already in effect.
        if current is not None and current == decision.chosen_model:
            decision.status = STATUS_NOOP
            decision.reason = (
                f"chosen model '{decision.chosen_model}' already set — no change."
            )
            report.decisions.append(decision)
            continue

        # Classify the change direction vs the CURRENT model (for the gate).
        cur_tier = _model_to_tier(cfg, current)
        cur_rank = _rank(cfg, cur_tier) if cur_tier else None
        chosen_rank = _rank(cfg, decision.chosen_tier)
        base_rank = _rank(cfg, decision.baseline_tier) if decision.baseline_tier else None

        if cur_rank is None:
            # Current model is unset or off-roster: writing the advisor's choice
            # is moving to a known, evidence-or-baseline tier — admissible.
            decision.direction = "set"
        elif chosen_rank > cur_rank:
            decision.direction = "up"
        elif chosen_rank < cur_rank:
            decision.direction = "down"
        else:
            decision.direction = None  # same rank, different model string

        is_downgrade_vs_baseline = base_rank is not None and chosen_rank < base_rank

        # ---- no-evidence baseline guard (don't churn the implicit default) ----
        # If the conservative tier is just the baseline (no shape earned a cheaper
        # tier) and the current model is unset / off-roster / already at-or-above
        # baseline, there is no evidence-driven change to make: the agent is
        # already (implicitly or explicitly) on a safe-enough model.  Writing an
        # explicit ``model = <baseline>`` here would be churn with no decision
        # behind it, and runs counter to "apply only evidence-strong changes".
        # We only write the baseline when the *current* model is strictly cheaper
        # than it (restoring an under-capable hand-set model toward the frontier).
        chosen_is_baseline = base_rank is not None and chosen_rank == base_rank
        current_at_or_above_chosen = cur_rank is not None and cur_rank >= chosen_rank
        if chosen_is_baseline and (cur_rank is None or current_at_or_above_chosen):
            decision.status = STATUS_NOOP
            decision.direction = None
            decision.reason = (
                f"conservative tier is the baseline '{decision.chosen_tier}' and no "
                "shape has earned a cheaper tier yet (thin evidence) — leaving the "
                "agent on its current/implicit default; nothing to apply."
            )
            report.decisions.append(decision)
            continue

        # ---- the evidence-admissibility gate ---- #
        # A sub-baseline tier can ONLY be produced by the engine's gate admitting
        # it for every shape (see module docstring), so any chosen downgrade is
        # already evidence-strong.  Upgrades / restores toward the frontier are
        # always safe.  The one thing we refuse is a sub-baseline write whose
        # *binding shape* did not actually clear the gate — which cannot happen
        # via decide_agent, but we assert the invariant defensively.
        admissible = True
        gate_reason = ""
        if is_downgrade_vs_baseline:
            # Re-confirm the binding shape's recommendation is the chosen tier and
            # the engine flagged it admitted (not a cold-start baseline echo).
            rec = engine.recommend(
                agent, decision.binding_shape, cfg, store, provider=provider
            )
            reasons = _cli._get(rec, "reasons", {}) or {}
            cands = reasons.get("candidates", []) if isinstance(reasons, dict) else []
            row = next(
                (c for c in cands if _cli._get(c, "tier_id") == decision.chosen_tier),
                None,
            )
            admitted = bool(_cli._get(row, "admitted")) if row else False
            if not (admitted and _cli._get(rec, "tier_id") == decision.chosen_tier):
                admissible = False
                gate_reason = (
                    "withheld: sub-baseline tier not gate-admitted for the binding "
                    "shape (thin evidence) — never auto-downgrade without evidence."
                )

        if not admissible:
            decision.status = STATUS_SKIPPED
            decision.reason = gate_reason
            report.decisions.append(decision)
            continue

        # Build the human reason for the (real or dry-run) change.
        arrow = "downgrade" if decision.direction == "down" else (
            "upgrade" if decision.direction == "up" else "set"
        )
        cur_disp = current if current is not None else "(unset)"
        evidence = (
            f"all shapes cleared tolerance for {decision.chosen_tier} "
            f"(binding: {decision.binding_shape})"
            if is_downgrade_vs_baseline
            else f"safest across shapes is {decision.chosen_tier} "
            f"(binding: {decision.binding_shape})"
        )
        decision.reason = (
            f"{arrow}: {cur_disp} -> {decision.chosen_model}; {evidence}."
        )

        if dry_run:
            decision.status = STATUS_DRYRUN
            report.decisions.append(decision)
            continue

        # ---- write (back up the file once per run) ---- #
        # Route the agent to the WHOLE chosen tier — provider + model +
        # run_target — not just the model, so a cross-provider (e.g. Codex) tier
        # actually runs on its provider.  Additive + byte-preserving; ``model``
        # is still always written (back-compat).
        chosen = cfg.tier(decision.chosen_tier)
        try:
            if target.path not in backed_up:
                decision.backup_path = _cli.backup_file(target.path)
                backed_up.add(target.path)
            _cli.set_tier_fields(
                target,
                provider=chosen.provider,
                model=chosen.model,
                run_target=chosen.run_target,
            )
            decision.status = STATUS_APPLIED
        except Exception as e:
            decision.status = STATUS_ERROR
            decision.reason = f"write failed: {e}"
        report.decisions.append(decision)

    return report
