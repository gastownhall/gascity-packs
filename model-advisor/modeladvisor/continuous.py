"""Continuous quality signal: ``q ∈ [0, 1]`` plus an unbounded-score posterior.

v1 of the advisor is **Bernoulli** (DESIGN §1.1, §4): every quality observation is
``q ∈ {0, 1}`` (a clean close vs a reopen/escalate). DESIGN §7.3 ("Continuous
quality signal") and the quality-channel discussion (§4) anticipate a richer
reward — a reviewer score, a fraction of passing tests — that lives on the unit
interval rather than the two-point set ``{0, 1}``. This module is the deferred
feature: it makes the existing Beta machinery accept a continuous ``q ∈ [0, 1]``
and adds an optional Gaussian (Normal-Inverse-Gamma) posterior for the case where
the raw score is genuinely **unbounded** and you don't want to squash it into
``[0, 1]``.

Why the Beta update already works for continuous ``q`` (DESIGN §1.3 Layer 1).
The closed-form update is::

    a += w·q ;  b += w·(1 − q)

For ``q ∈ {0, 1}`` this is the conjugate Bernoulli update; for ``q ∈ [0, 1]`` it
is the natural fractional-count generalisation (a "soft" success of mass ``w·q``
and a "soft" failure of mass ``w·(1 − q)``). The posterior mean still moves toward
the running ``q`` exactly as the moments demand, and every downstream consumer (the
gate's LCB, the asymmetric loss, the credible interval — all read only the Beta
*moments*) is unchanged. The **only** thing standing in the way is
:func:`modeladvisor.store.CellStore.apply_quality`, which guards
``qf not in (0.0, 1.0)`` and drops anything else (defensive against a malformed
binary row). This module supplies the validate-clamp-apply path the store calls
once that guard is relaxed under a config flag.

Two posteriors, two regimes:

* :func:`apply_continuous` — for a **bounded** score already mapped to ``[0, 1]``
  (reviewer 0–1, test-pass fraction). Feeds the existing Beta :class:`Cell`; the
  binary path is a strict special case, so flipping the feature on with only
  ``{0, 1}`` data reproduces v1 **byte-for-byte** (DESIGN §7.3 conservative
  default — see the module test ``test_binary_path_unchanged``).
* :class:`GaussianCell` — for an **unbounded** continuous score (a reviewer 0–100,
  a latency-savings z-score) you don't want to compress into ``[0, 1]``. A
  Normal-Inverse-Gamma conjugate posterior over an unknown mean *and* variance
  (DESIGN OQ-A6 "Gaussian … continuous-score posterior"). Its one-sided lower
  bound :meth:`GaussianCell.lcb` mirrors the Beta gate's ``mu − z·stderr`` form
  (cf. :func:`modeladvisor.engine.wilson_lcb`) so a future Gaussian-backed gate
  reads identically.

Stdlib-only (``math``, ``dataclasses``); pure, deterministic, no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Protocol


# --------------------------------------------------------------------------- #
# Validation + the Beta (bounded) path (DESIGN §1.3 Layer 1, §7.3)             #
# --------------------------------------------------------------------------- #


class _BetaCell(Protocol):
    """Structural type for the bits of :class:`modeladvisor.store.Cell` we touch.

    Declared as a ``Protocol`` so this module imports **standalone** (the brief's
    hard rule #4): we never import ``store`` at module load, we just rely on the
    real ``Cell`` exposing ``.update(q, w, ts)`` (DESIGN §1.3). Any object with a
    compatible ``update`` works, which also keeps the unit tests hermetic.
    """

    def update(self, q: float, w: float, ts: str | None) -> None: ...


def is_valid_q(q: object, *, continuous: bool = False) -> bool:
    """Is ``q`` an admissible quality outcome?  (DESIGN §1.1 / §7.3.)

    * ``continuous=False`` (the v1 default): the strict Bernoulli set ``q ∈ {0, 1}``
      — exactly the guard :func:`modeladvisor.store.CellStore.apply_quality` enforces
      today, so swapping this in for the inline check is behaviour-preserving.
    * ``continuous=True``: the unit interval ``0 ≤ q ≤ 1`` (a reviewer score, a
      test-pass fraction). ``NaN``/``inf`` and non-numerics are rejected either way.

    Returns ``False`` (never raises) for anything non-numeric, so it is safe to call
    directly on a raw telemetry value.
    """
    try:
        qf = float(q)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if not math.isfinite(qf):
        return False
    if continuous:
        return 0.0 <= qf <= 1.0
    return qf in (0.0, 1.0)


def clamp_unit(q: float) -> float:
    """Clamp a float into ``[0, 1]`` (the Beta support). DESIGN §7.3."""
    if q < 0.0:
        return 0.0
    if q > 1.0:
        return 1.0
    return q


def apply_continuous(cell: _BetaCell, q: float, w: float, ts: str | None) -> None:
    """Apply one **continuous** quality observation ``q ∈ [0, 1]`` to a Beta cell.

    The reward is validated as a finite number then **clamped** into ``[0, 1]``
    (a reviewer that emits ``1.02`` or a fraction computed as ``-0.0`` must not
    corrupt the Beta support), and applied via the cell's own conjugate update
    ``a += w·q ; b += w·(1 − q)`` (DESIGN §1.3 Layer 1) — we reuse ``cell.update``
    rather than touching ``a``/``b`` so the count/last-update bookkeeping and any
    future change to the update stay in one place (the store).

    For ``q ∈ {0, 1}`` this is identical to the v1 binary update (the brief's
    byte-identical requirement); for ``q ∈ (0, 1)`` it is the fractional-count
    generalisation. ``w`` is the channel weight (DESIGN §4.4); ``ts`` the RFC3339
    observation time (or ``None``).

    Raises ``ValueError`` if ``q`` is non-finite/non-numeric (a programming error
    at this layer — the store calls :func:`is_valid_q` first, so a bad row is
    dropped upstream rather than reaching here).
    """
    if not is_valid_q(q, continuous=True):
        # is_valid_q also rejects <0 / >1, but those are *clampable*; distinguish
        # "out of range but finite" (clamp) from "not a finite number" (reject).
        try:
            qf = float(q)
        except (TypeError, ValueError):
            raise ValueError(f"continuous q must be numeric, got {q!r}") from None
        if not math.isfinite(qf):
            raise ValueError(f"continuous q must be finite, got {q!r}")
        qf = clamp_unit(qf)
    else:
        qf = clamp_unit(float(q))
    cell.update(qf, float(w), ts)


def normalise_score(raw: float, lo: float, hi: float) -> float:
    """Map an unbounded raw score onto ``[0, 1]`` by min-max scaling, clamped.

    ``(raw − lo) / (hi − lo)``, clamped into ``[0, 1]`` (DESIGN §7.3 — turn a
    reviewer 0–100 or a bounded-range score into a Beta-ready ``q``). This is the
    cheap alternative to :class:`GaussianCell` when you *do* know the score's
    range and are happy to squash it.

    A degenerate range (``hi == lo``) carries no information, so we map any finite
    ``raw`` to the midpoint ``0.5`` (maximal Beta-update neutrality — pulls the
    posterior toward neither success nor failure). ``hi < lo`` is treated as a
    swapped but still valid range (we orient on ``min``/``max``). Non-finite
    ``raw`` clamps to the nearest edge (``+inf → 1``, ``−inf → 0``); ``NaN → 0.5``.
    """
    if math.isnan(raw):
        return 0.5
    low, high = (lo, hi) if lo <= hi else (hi, lo)
    span = high - low
    if span <= 0.0:
        return 0.5
    return clamp_unit((raw - low) / span)


# --------------------------------------------------------------------------- #
# Gaussian (unbounded) posterior — Normal-Inverse-Gamma (DESIGN §7.3 / OQ-A6)  #
# --------------------------------------------------------------------------- #


@dataclass
class GaussianCell:
    """Normal-Inverse-Gamma posterior over an **unbounded** continuous score.

    For a reviewer score on, say, 0–100 that you do *not* want to squash into
    ``[0, 1]`` (DESIGN §7.3 "Gaussian … continuous-score posterior", OQ-A6), model
    the observations as ``x ~ Normal(θ, σ²)`` with **both** ``θ`` (location) and
    ``σ²`` (scale) unknown. The conjugate prior is Normal-Inverse-Gamma
    ``NIG(mu, lam, alpha, beta)``:

    * ``mu``   — prior mean of the location ``θ``.
    * ``lam``  — prior pseudo-count on the location (precision scaling; ``λ`` real
      observations' worth of confidence in ``mu``).
    * ``alpha``, ``beta`` — shape/scale of the Inverse-Gamma over ``σ²``
      (``alpha`` ≈ prior d.o.f./2, ``beta`` ≈ prior sum-of-squares/2).
    * ``n``    — raw observation count (bookkeeping, mirrors :class:`Cell.n`).

    The sequential update for one datum ``x`` is the standard closed form
    (Murphy, *Conjugate Bayesian analysis of the Gaussian*, eqs. 85–89), so the
    cell stays a pure accumulator like the Beta :class:`Cell`. The marginal
    posterior on the location ``θ`` is Student-t with ``2·alpha`` d.o.f., mean
    ``mu`` and scale² ``beta / (alpha·lam)``; :meth:`mean`, :meth:`stderr` and the
    one-sided :meth:`lcb` read off that marginal so a Gaussian-backed gate mirrors
    the Beta gate's ``mu − z·stderr`` (cf. :func:`modeladvisor.engine.wilson_lcb`).

    Defaults give a weak, broad, **proper** prior centred at 0 (``lam = 1`` →
    one observation dominates; ``alpha = beta = 1`` → a wide Inverse-Gamma) so a
    fresh cell defers to data fast — the unbounded analogue of the Beta cold-start's
    bounded-influence priors (DESIGN §3).
    """

    mu: float = 0.0
    lam: float = 1.0
    alpha: float = 1.0
    beta: float = 1.0
    n: int = 0

    def update(self, x: float) -> None:
        """Fold in one observation ``x`` (NIG sequential update, DESIGN §7.3).

        Closed-form conjugate update for a single Normal datum::

            mu'    = (lam·mu + x) / (lam + 1)
            lam'   = lam + 1
            alpha' = alpha + 1/2
            beta'  = beta + (lam · (x − mu)²) / (2 · (lam + 1))

        The ``beta`` increment is the per-step contribution to the residual
        sum-of-squares; accumulating it sequentially is algebraically identical to
        the batch update, so replay order does not matter (deterministic).
        """
        xf = float(x)
        if not math.isfinite(xf):
            raise ValueError(f"GaussianCell.update needs a finite x, got {x!r}")
        lam0, mu0 = self.lam, self.mu
        self.mu = (lam0 * mu0 + xf) / (lam0 + 1.0)
        self.lam = lam0 + 1.0
        self.alpha = self.alpha + 0.5
        self.beta = self.beta + (lam0 * (xf - mu0) * (xf - mu0)) / (2.0 * (lam0 + 1.0))
        self.n += 1

    # ---- posterior moments on the location θ (Student-t marginal) ---------- #

    @property
    def mean(self) -> float:
        """Posterior mean of the location ``θ`` (the Student-t mean, ``= mu``)."""
        return self.mu

    @property
    def variance(self) -> float:
        """Posterior variance of the **location estimate** ``θ`` (not of the data).

        Variance of the Student-t marginal on ``θ``: ``beta / (lam · (alpha − 1))``
        for ``alpha > 1`` (its scale² ``beta/(alpha·lam)`` inflated by the t
        d.o.f. factor ``alpha/(alpha − 1)``). For ``alpha ≤ 1`` the t-variance is
        undefined/infinite; we fall back to the scale² ``beta / (alpha · lam)`` so
        callers always get a finite, monotone-shrinking uncertainty.
        """
        if self.alpha > 1.0:
            return self.beta / (self.lam * (self.alpha - 1.0))
        return self.beta / (self.alpha * self.lam)

    @property
    def stderr(self) -> float:
        """Standard error of the location estimate ``sqrt(variance)`` (DESIGN §7.3)."""
        return math.sqrt(self.variance)

    @property
    def data_variance(self) -> float:
        """Posterior point estimate of the **observation** variance ``σ²``.

        The Inverse-Gamma mean ``beta / (alpha − 1)`` (``alpha > 1``), else the
        mode ``beta / (alpha + 1)``. Exposed for callers that want the spread of
        the *scores* themselves rather than of their mean (e.g. a tolerance band).
        """
        if self.alpha > 1.0:
            return self.beta / (self.alpha - 1.0)
        return self.beta / (self.alpha + 1.0)

    def lcb(self, z: float) -> float:
        """One-sided lower confidence bound on the location ``mean − z·stderr``.

        Mirrors the Beta gate's :func:`modeladvisor.engine.wilson_lcb` (a normal
        approximation to the Student-t lower tail; ``z = 1.645`` ≈ ``z_{0.95}`` for
        the one-sided ``alpha = 0.05``). **Not** clamped to ``[0, 1]`` — the whole
        point of the Gaussian cell is an unbounded score, so a negative lower bound
        is meaningful and must be preserved (contrast the Beta LCB's ``max(0, …)``).
        Use a Student-t quantile for ``z`` if exact small-sample coverage matters.
        """
        return self.mean - z * self.stderr

    # ---- persistence (mirrors Cell.to_dict / from_dict) -------------------- #

    def to_dict(self) -> dict:
        """Serialise to a plain JSON-able dict (mirrors :meth:`Cell.to_dict`)."""
        return {
            "mu": self.mu,
            "lam": self.lam,
            "alpha": self.alpha,
            "beta": self.beta,
            "n": self.n,
        }

    @classmethod
    def from_dict(cls, d: Mapping) -> "GaussianCell":
        """Inverse of :meth:`to_dict` (mirrors :meth:`Cell.from_dict`)."""
        return cls(
            mu=float(d["mu"]),
            lam=float(d["lam"]),
            alpha=float(d["alpha"]),
            beta=float(d["beta"]),
            n=int(d.get("n", 0)),
        )
