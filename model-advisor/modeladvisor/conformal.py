"""Distribution-free split-conformal lower bound (DESIGN §1.3 Layer 2, §5.2, §7.3).

A drop-in alternative LCB backend for the conservative gate. v1 ships the
Wilson-style normal lower bound on the Beta posterior (``engine.wilson_lcb``) as
the *asymptotic stand-in*; DESIGN §5.2 states the paper's formal coverage
guarantee for a **distribution-free conformal** bound built from a rolling,
held-out per-cell calibration buffer of ``(predicted, observed)`` quality pairs.
This module builds that buffer and that bound, designed so it:

- **coincides with Wilson asymptotically** — the bound is
  ``mu − Q·sigma`` where ``sigma`` is the cell's posterior standard error and
  ``Q`` is the ``(1 − alpha)`` empirical quantile of the *standardized*
  calibration residuals. For a well-calibrated cell whose residuals are
  symmetric, ``Q → z_{1−alpha}`` as the buffer grows, so the bound converges to
  the Wilson bound ``mu − z·sigma`` (the v1 default); and
- **degrades to Wilson when the buffer is thin** — with fewer than ``min_buffer``
  calibration points (or a degenerate zero-spread buffer) :func:`conformal_lcb`
  returns *exactly* ``max(0, mu − z·sigma)``, so flipping the ``lcb_backend`` flag
  is a behaviour-preserving change on day-1 cells with no exchangeable history
  (DESIGN §7.3). This is the safe-drop-in contract.

Why this is the conservative-correct backend (DESIGN §5.2 + §7.3): when the cell
is **over-confident** — its predictions systematically exceed realised quality
(``pred ≫ obs``) — the calibration residuals shift positive, their ``(1 − alpha)``
standardized quantile ``Q`` grows past ``z``, and the bound drops *below* Wilson,
so the gate stops admitting the downgrade. The Wilson bound, keyed only off the
posterior spread, cannot see that miscalibration; the conformal bound, keyed off
the realised prediction errors, can. That is the entire point of the deferred
feature.

Stdlib-only (``math``, ``statistics``, ``bisect``) — no numpy/scipy, per the
build brief. Pure functions plus one small ``@dataclass`` for the buffer; no
hidden I/O or globals.

**Conformity score (the residual definition, fixed and documented here once).**
For each calibration pair the raw error is

    e_i = pred_i − obs_i                                  (signed prediction error)

with ``pred_i`` the model's predicted quality at decision time and
``obs_i ∈ {0,1}`` (Bernoulli close/reopen) or ``[0,1]`` (graded eval verdict) the
realised outcome. A *positive* error is an over-prediction (the cell claimed more
quality than it delivered). The conformity score is the **standardized** error
``s_i = e_i / sd(e)`` (so its ``(1 − alpha)`` quantile lands on the same
``z``-scale Wilson uses), and the one-sided ``(1 − alpha)`` conformal lower bound
on the cell's true mean quality is

    q_lo = clamp_[0,1]( mu − Q_{1−alpha}(s) · sigma )

where ``mu``/``sigma`` are the cell's posterior mean and standard error (the same
quantities Wilson uses, so the two backends are directly comparable) and
``Q_{1−alpha}`` is the finite-sample split-conformal quantile — the
``ceil((n+1)(1−alpha))``-th order statistic of the standardized residuals (the
standard split-conformal rank; DESIGN §5.2). For an exchangeable calibration
stream this gives marginal coverage ``Pr[theta ≥ q_lo] ≳ 1 − alpha`` (DESIGN §5
Thm + appendix proof — distribution-free up to the discreteness of a Bernoulli
residual), which — composed with the gate ``q_lo ≥ mu* − q_tol`` — yields the
conservative admission guarantee ``Pr[theta_tier ≥ mu* − q_tol] ≳ 1 − alpha``
(DESIGN §5.2).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from statistics import pstdev
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # avoid an import cycle; only needed for the type hint.
    from modeladvisor.store import Cell


# --------------------------------------------------------------------------- #
# Rolling calibration buffer (DESIGN §4.3, §5.2, §7.3)                          #
# --------------------------------------------------------------------------- #


@dataclass
class CalibrationBuffer:
    """A bounded ring buffer of recent ``(pred, obs)`` calibration pairs for a cell.

    Each pair records the model's **predicted** quality at decision time
    (``pred ∈ [0, 1]``) and the **observed** realised outcome (``obs ∈ {0, 1}`` for
    a Bernoulli close/reopen signal, or ``[0, 1]`` for a graded eval verdict). The
    distribution-free split-conformal bound (:func:`conformal_lcb`) is computed
    from the residuals ``pred − obs`` of these pairs (DESIGN §5.2).

    Ring semantics: at most ``cap`` pairs are retained; appending beyond ``cap``
    drops the **oldest** pair, so the buffer is a sliding window of recent history
    (DESIGN §7.3 "rolling per-cell calibration buffer"). The default ``cap`` of
    500 keeps the window long enough for a stable ``(1 − alpha)`` quantile while
    bounding the per-cell footprint in ``advisor-cells.json``.
    """

    cap: int = 500
    #: Recent (pred, obs) pairs, oldest-first. Length never exceeds ``cap``.
    pairs: list[tuple[float, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cap < 1:
            raise ValueError(f"CalibrationBuffer cap must be >= 1, got {self.cap}")
        # Defend against an over-long ``pairs`` passed straight to the constructor
        # (e.g. a tampered cache): retain only the most-recent ``cap``.
        if len(self.pairs) > self.cap:
            self.pairs = self.pairs[-self.cap :]

    def append(self, pred: float, obs: float) -> None:
        """Append one ``(pred, obs)`` pair, dropping the oldest past ``cap``.

        ``pred`` is clamped to ``[0, 1]`` (a predicted *quality* is a probability);
        ``obs`` is clamped to ``[0, 1]`` (Bernoulli outcomes already are, a graded
        eval verdict may be anywhere in the unit interval). DESIGN §5.2.
        """
        p = _clamp01(float(pred))
        o = _clamp01(float(obs))
        self.pairs.append((p, o))
        if len(self.pairs) > self.cap:
            # Ring-buffer drop-oldest. ``cap >= 1`` so this leaves >= 1 element.
            del self.pairs[0 : len(self.pairs) - self.cap]

    def residuals(self) -> list[float]:
        """The raw prediction errors ``e_i = pred_i − obs_i`` (DESIGN §5.2).

        Positive ⇒ the cell over-predicted (claimed more quality than realised).
        """
        return [p - o for (p, o) in self.pairs]

    def __len__(self) -> int:
        return len(self.pairs)

    # ---- (de)serialisation for the advisor-cells.json cache (DESIGN §5.5) ---- #

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict for the per-cell cache (DESIGN §5.5).

        Pairs are stored as ``[pred, obs]`` lists (JSON has no tuples). ``cap`` is
        persisted so the window length survives a reload.
        """
        return {"cap": self.cap, "pairs": [[p, o] for (p, o) in self.pairs]}

    @classmethod
    def from_dict(cls, d: Mapping) -> "CalibrationBuffer":
        """Inverse of :meth:`to_dict`; tolerant of a missing/empty ``pairs``."""
        cap = int(d.get("cap", 500))
        raw = d.get("pairs") or []
        pairs = [(float(p), float(o)) for p, o in raw]
        return cls(cap=cap, pairs=pairs)


# --------------------------------------------------------------------------- #
# Split-conformal lower confidence bound (DESIGN §5.2)                          #
# --------------------------------------------------------------------------- #


def conformal_lcb(
    cell: "Cell",
    buffer: CalibrationBuffer,
    z: float,
    *,
    alpha: float = 0.05,
    min_buffer: int = 20,
) -> float:
    """One-sided distribution-free lower bound on the cell's true mean quality.

    A **drop-in alternative** to :func:`modeladvisor.engine.wilson_lcb` (the same
    ``(cell, …, z)`` call-shape plus the calibration buffer): both return a
    one-sided lower confidence bound ``q_lo`` the conservative gate compares to
    ``mu* − q_tol`` (DESIGN §1.3 Layer 2). Selected when ``cfg.lcb_backend ==
    'conformal'``; otherwise the engine calls Wilson.

    Behaviour:

    - **Thin / degenerate buffer** (``len(buffer) < min_buffer``, or every residual
      identical so there is no spread to standardize): return *exactly*
      ``max(0.0, cell.mean − z·cell.stderr)`` — the Wilson bound. A cell with no
      exchangeable calibration history (DESIGN §7.3) is bounded precisely as v1
      does today, so enabling the conformal backend can never *change* a thin-cell
      decision. This is the safe-drop-in contract.
    - **Rich buffer** (``len(buffer) ≥ min_buffer``): the split-conformal bound

          s_i  = (pred_i − obs_i) / sd(pred − obs)        (standardized residuals)
          Q    = the ceil((n+1)(1−alpha))-th smallest s_i (clamped into rank range)
          q_lo = clamp_[0,1]( cell.mean − Q · cell.stderr )

      (DESIGN §5.2). For a symmetric well-calibrated stream ``Q → z_{1−alpha}`` so
      ``q_lo`` converges to the Wilson bound; an over-confident cell (``pred ≫
      obs``) shifts the residuals positive, raising ``Q`` past ``z`` and pushing
      ``q_lo`` *below* Wilson — catching the miscalibration the posterior spread
      alone cannot see.

    Parameters
    ----------
    cell:
        The (pooled) cell whose ``mean`` is the point estimate and whose
        ``mean``/``stderr`` define both the Wilson fallback and the conformal
        bound's scale.
    buffer:
        Rolling per-cell calibration buffer of ``(pred, obs)`` pairs.
    z:
        ``z_{1−alpha}`` for the Wilson fallback (the engine passes ``cfg.hp.z``);
        keeps the thin-buffer path byte-identical to ``wilson_lcb``.
    alpha:
        One-sided miscoverage level; the bound targets coverage ``1 − alpha``
        (default 0.05, matching ``cfg.hp.alpha``).
    min_buffer:
        Minimum calibration points before the conformal bound is used; below it,
        fall back to Wilson (default 20).

    Returns
    -------
    float in ``[0, 1]`` — the lower confidence bound ``q_lo``.
    """
    wilson = max(0.0, cell.mean - z * cell.stderr)

    n = len(buffer)
    if n < min_buffer:
        return wilson  # safe drop-in: identical to engine.wilson_lcb(cell, z).

    errs = buffer.residuals()
    sd = pstdev(errs)
    if sd <= 0.0:
        # No residual spread to standardize (e.g. every pred == obs). The conformal
        # quantile is undefined; fall back to Wilson rather than divide by zero.
        return wilson

    scores = sorted(e / sd for e in errs)
    q = _conformal_quantile(scores, alpha)

    return _clamp01(cell.mean - q * cell.stderr)


# --------------------------------------------------------------------------- #
# Internals                                                                     #
# --------------------------------------------------------------------------- #


def _conformal_quantile(sorted_scores: list[float], alpha: float) -> float:
    """The finite-sample split-conformal ``(1 − alpha)`` quantile (DESIGN §5.2).

    Uses the standard conformal rank ``k = ceil((n + 1)(1 − alpha))`` and returns
    the ``k``-th order statistic (1-indexed) of ``sorted_scores``. ``k`` is clamped
    to ``[1, n]``: when ``(n + 1)(1 − alpha) > n`` (too few points to realise the
    requested coverage from the sample alone) the textbook recipe returns ``+inf``;
    we instead take the sample maximum (the most conservative *finite* bound),
    which only *lowers* ``q_lo`` and so never weakens the gate's conservative
    property. ``bisect`` resolves the 1-indexed rank ``k`` to a 0-indexed slot over
    the contiguous rank list, robust if the rank rule is later generalised to a
    fractional position.
    """
    n = len(sorted_scores)
    k = math.ceil((n + 1) * (1.0 - alpha))  # 1-indexed conformal rank.
    k = min(max(k, 1), n)  # clamp into the realisable range [1, n].
    idx = bisect.bisect_left(range(1, n + 1), k)  # 1-indexed k -> 0-indexed slot.
    return sorted_scores[idx]


def _clamp01(x: float) -> float:
    """Clamp ``x`` into ``[0.0, 1.0]`` (quality is a probability; DESIGN §5.2)."""
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x
