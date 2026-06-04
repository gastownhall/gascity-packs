"""Genuine Thompson-Sampling mode for the tier decision (DESIGN §1.2–§1.4, §7.3).

v1 ships the LCB-gated **deterministic** production rule
(:func:`modeladvisor.engine.recommend`); DESIGN §7.3 leaves a *genuine* per-tier
Beta-sampling mode as a deferred flag, with the ``seed`` hook in ``recommend``
reserved for exactly this. This module is that mode.

The idea (classic Thompson Sampling over the Beta-Bernoulli posteriors of
DESIGN §1.3 Layer 1): instead of comparing one-sided lower bounds, draw one
posterior sample ``theta_tid ~ Beta(a~, b~)`` per tier from a **seeded** RNG and
decide on the *sampled* qualities. Over many seeds this explores cheaper tiers in
proportion to the posterior probability that they truly preserve quality — the
randomised analogue of the deterministic gate — while a single seed is fully
reproducible (DESIGN §1.4 property 2).

The same safety constraints that make the deterministic rule trustworthy are
imposed verbatim here (DESIGN §1.2, §7.2), so the conservative contract holds in
either mode:

- the **baseline ``tier*`` is always admissible** (downgrades are constrained;
  the baseline and upgrades are not);
- a **``Critical`` or force-baselined** cell never admits *any* cheaper tier,
  regardless of how high a cheap tier happens to sample (the ``M[Critical] = ∞``
  hard rule / the §7.4 safety hatch — never a silent downgrade);
- otherwise a cheaper tier is admissible **iff its sampled quality clears the
  baseline's sampled quality minus the class tolerance**,
  ``theta_tid >= theta_base - q_tol`` — the sampled analogue of the Layer-2 gate.

Among the admissible tiers the **cheapest** is chosen; a *downgrade* is therefore
only ever returned when a cheaper tier sampled competitively, and an *upgrade* is
returned only when it strictly beats the baseline's own sample (so the baseline
is preferred on ties and an upgrade is never gratuitous). This guarantees the
function NEVER returns a downgrade for a Critical / forced cell.

Stdlib-only (``random``, ``math``): the sampler is ``random.Random(seed)
.betavariate`` (Cheng's BB/BC algorithm — exact, no scipy). Pure function of its
arguments; deterministic given ``seed``.
"""

from __future__ import annotations

import math
import random
from typing import Mapping

from modeladvisor.store import Cell

# Sentinel rationale strings (mirror the deterministic engine's phrasing so the
# audit object reads consistently across modes).
_BASELINE_RATIONALE = "no cheaper tier sampled competitively (Thompson draw)"
_CRITICAL_RATIONALE = "Critical/forced cell: downgrades disabled (no cheaper tier admissible)"


# --------------------------------------------------------------------------- #
# Sampling (DESIGN §1.3 Layer 1 posteriors, drawn instead of lower-bounded)     #
# --------------------------------------------------------------------------- #


def sample_tier_qualities(
    order: list[str],
    cells_by_tier: Mapping[str, Cell],
    *,
    seed: int | None,
) -> dict[str, float]:
    """Draw one posterior sample ``theta_tid ~ Beta(a~, b~)`` per tier (seeded).

    Realises the Thompson draw over the Beta-Bernoulli posteriors of DESIGN §1.3
    Layer 1: for each tier in ``order`` (the cheapest→most-capable tier-id list),
    sample ``theta_tid`` from that tier's posterior ``Beta(cell.a, cell.b)`` using
    a single seeded :class:`random.Random` so the whole draw is deterministic and
    reproducible given ``seed`` (DESIGN §1.4 property 2). Tiers are sampled in
    ``order`` so the RNG stream — and hence every sample — is stable for a seed.

    Parameters
    ----------
    order:
        Cheapest→most-capable tier-id list (``cfg.tier_ids``).
    cells_by_tier:
        ``tier_id -> Cell`` map of the (pooled) posteriors to sample from.
    seed:
        RNG seed. ``None`` is permitted (non-reproducible, system entropy) but
        callers wanting reproducibility — every test and the production hook —
        pass an explicit integer.

    Returns
    -------
    ``{tier_id: theta}`` with one sample per tier in ``order``, each in ``[0, 1]``.
    """
    rng = random.Random(seed)
    samples: dict[str, float] = {}
    for tid in order:
        cell = cells_by_tier[tid]
        # betavariate requires strictly-positive shape params; cold-start priors
        # and posteriors always satisfy this (a, b > 0 by construction), but guard
        # against a degenerate (0, 0) cell by nudging to a tiny positive epsilon.
        a = cell.a if cell.a > 0.0 else 1e-9
        b = cell.b if cell.b > 0.0 else 1e-9
        samples[tid] = rng.betavariate(a, b)
    return samples


# --------------------------------------------------------------------------- #
# Selection under the safety constraints (DESIGN §1.2, §1.4 Alg. 1, §7.2)        #
# --------------------------------------------------------------------------- #


def thompson_select(
    order: list[str],
    cells_by_tier: Mapping[str, Cell],
    base_id: str,
    *,
    q_tol: float,
    is_critical: bool,
    forced: bool,
    seed: int | None,
) -> tuple[str, dict]:
    """Pick the cost-minimal tier from one seeded Thompson draw, safely.

    Faithful to the constrained decision of DESIGN §1.2 / Alg. 1, but with the
    Layer-2 gate evaluated on a *sampled* quality instead of a lower bound:

    1. Draw ``theta_tid ~ Beta`` per tier (:func:`sample_tier_qualities`, seeded).
    2. Build the admissible set:

       - the **baseline** ``base_id`` is always admissible;
       - if ``is_critical`` or ``forced``, **no** tier cheaper than ``base_id`` is
         admissible (hard never-downgrade rule / safety hatch, DESIGN §1.2, §7.4);
       - otherwise a cheaper tier is admissible iff
         ``theta_tier >= theta_base - q_tol`` (sampled Layer-2 gate, DESIGN §5.2);
       - an **upgrade** (more capable than baseline) is admissible only if it
         *strictly* beats the baseline's own sample (``theta_up > theta_base``),
         so the baseline wins ties and upgrades are never gratuitous.

    3. Choose the **cheapest** admissible tier (lowest index in ``order``).

    Because every cheaper tier is excluded outright for a Critical / forced cell,
    and otherwise only included when it sampled competitively, this NEVER returns
    a downgrade for a Critical / forced cell, and only ever downgrades when a
    cheaper tier genuinely sampled within tolerance (DESIGN §7.2 conservative
    property, preserved under sampling).

    Parameters
    ----------
    order:
        Cheapest→most-capable tier-id list (``cfg.tier_ids``).
    cells_by_tier:
        ``tier_id -> Cell`` (pooled) posteriors, one per tier in ``order``.
    base_id:
        The baseline / reference tier ``tier*`` (must be in ``order``).
    q_tol:
        The tolerance-class ``q_tol`` (max allowable sampled quality drop).
    is_critical:
        Whether the cell's tolerance class is ``Critical`` (never downgrade).
    forced:
        Whether the ``force_baseline`` safety hatch is active (never downgrade).
    seed:
        RNG seed threaded from ``recommend`` (reproducible given the seed).

    Returns
    -------
    ``(chosen_id, audit)``. ``audit`` is the structured reasoning surface
    (DESIGN §1.4 property 3): the per-tier samples, the baseline sample, the
    admissible set with per-tier admit reasons, the mode, the seed, and the
    chosen tier — enough to fully explain (and replay) the draw.
    """
    if base_id not in cells_by_tier:
        raise KeyError(f"baseline tier {base_id!r} not in sampled cells")
    base_idx = order.index(base_id)

    samples = sample_tier_qualities(order, cells_by_tier, seed=seed)
    theta_base = samples[base_id]
    no_downgrade = bool(is_critical or forced)

    tiers_audit: list[dict] = []
    admissible: list[str] = []

    for tid in order:
        idx = order.index(tid)
        theta = samples[tid]

        if tid == base_id:
            admit = True
            action = "stay"
            reason = "baseline (always admissible)"
        elif idx > base_idx:
            action = "up"
            # Upgrades are unconstrained by the gate, but only *selected* if they
            # strictly beat the baseline's own sample (else the cheaper baseline
            # wins on tie — upgrades are never gratuitous).
            admit = theta > theta_base
            if admit:
                reason = f"upgrade: theta={theta:.4f} > baseline theta={theta_base:.4f}"
            else:
                reason = (
                    f"upgrade not selected: theta={theta:.4f} "
                    f"<= baseline theta={theta_base:.4f}"
                )
        else:
            action = "down"
            if no_downgrade:
                admit = False
                reason = _CRITICAL_RATIONALE
            else:
                threshold = theta_base - q_tol
                admit = theta >= threshold
                if admit:
                    reason = (
                        f"admitted: sampled theta={theta:.4f} >= {threshold:.4f} "
                        f"(baseline theta {theta_base:.4f} - q_tol {q_tol:.4f})"
                    )
                else:
                    reason = (
                        f"rejected: sampled theta={theta:.4f} < {threshold:.4f} "
                        f"(baseline theta {theta_base:.4f} - q_tol {q_tol:.4f})"
                    )

        if admit:
            admissible.append(tid)

        tiers_audit.append(
            {
                "tier_id": tid,
                "action": action,
                "theta": round(theta, 6),
                "admitted": admit,
                "reason": reason,
            }
        )

    # ------------------------------------------------------------------ #
    # Selection (cost-minimal under the sampled gate, DESIGN §1.2):       #
    #                                                                     #
    #   1. if any *cheaper* tier sampled competitively, take the CHEAPEST #
    #      of them — a downgrade is warranted and we minimise cost;       #
    #   2. else stay at baseline, UNLESS an *upgrade* strictly beat the   #
    #      baseline's own sample, in which case take the cheapest such    #
    #      upgrade. Upgrades are thus never gratuitous and a downgrade is #
    #      always preferred when one cleared the gate.                    #
    #                                                                     #
    # The baseline is always admissible, so a choice always exists. A     #
    # downgrade is unreachable whenever ``no_downgrade`` (Critical /      #
    # forced), so this NEVER downgrades such a cell.                      #
    # ------------------------------------------------------------------ #
    down_admitted = [t for t in admissible if order.index(t) < base_idx]
    up_admitted = [t for t in admissible if order.index(t) > base_idx]

    if down_admitted:
        chosen_id = min(down_admitted, key=order.index)  # cheapest downgrade
        decision = (
            f"downgrade to {chosen_id}: cheapest tier whose Thompson sample "
            f"cleared baseline theta {theta_base:.4f} - q_tol {q_tol:.4f}"
        )
    elif up_admitted:
        chosen_id = min(up_admitted, key=order.index)  # cheapest beating upgrade
        decision = (
            f"upgrade to {chosen_id}: no cheaper tier admissible and sample "
            f"{samples[chosen_id]:.4f} strictly beat baseline theta {theta_base:.4f}"
        )
    else:
        chosen_id = base_id
        decision = _CRITICAL_RATIONALE if no_downgrade else _BASELINE_RATIONALE

    audit = {
        "mode": "thompson",
        "seed": seed,
        "baseline_tier": base_id,
        "baseline_theta": round(theta_base, 6),
        "q_tol": q_tol,
        "critical": bool(is_critical),
        "forced_baseline": bool(forced),
        "no_downgrade": no_downgrade,
        "samples": {tid: round(samples[tid], 6) for tid in order},
        "tiers": tiers_audit,
        "admissible": list(admissible),
        "chosen_tier": chosen_id,
        "decision": decision,
    }
    return chosen_id, audit
