"""Tests for the distribution-free split-conformal LCB backend (DESIGN §5.2, §7.3).

Covers the load-bearing contract from the v3 build brief (bead ``bh-ah7``):

- **drop-in safety** — a thin (or zero-spread) buffer makes ``conformal_lcb``
  return *exactly* ``engine.wilson_lcb``, so flipping ``lcb_backend`` can never
  change a day-1 cell's decision;
- **asymptotic coincidence with Wilson** — a rich, symmetric, well-calibrated
  buffer drives the bound to the Wilson bound (``Q → z``);
- **calibrated bound ≤ mean** and **finite-sample valid-ish coverage** on a
  synthetic stream of independent cells;
- **catches over-confidence** — a ``pred ≫ obs`` buffer yields a bound strictly
  *below* Wilson at the same cell;
- ring-buffer cap (drop-oldest), ``to_dict``/``from_dict`` round-trip,
  determinism, and ``[0, 1]`` clamping.

The conformity score is ``s_i = (pred_i − obs_i) / sd(pred − obs)`` and the bound
is ``clamp_[0,1](mu − Q_{1−alpha}·sigma)`` (DESIGN §5.2); these tests pin both the
numeric behaviour and the directional guarantees.
"""

from __future__ import annotations

import math
import os
import random
import sys

import pytest

# Make the pack root importable when pytest is run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modeladvisor import engine as E  # noqa: E402
from modeladvisor.conformal import CalibrationBuffer, conformal_lcb  # noqa: E402
from modeladvisor.store import Cell  # noqa: E402

_Z = 1.645  # z_{0.95}, the default one-sided alpha=0.05 (matches cfg.hp.z).


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


def _bernoulli_cell(theta: float, n: int, seed: int) -> tuple[Cell, list[float]]:
    """A cell + the observation list, materialised from ``n`` Bernoulli(theta) draws.

    The cell posterior is ``Beta(1 + #succ, 1 + #fail)`` (a flat prior plus the
    realised outcomes), so ``cell.mean`` tracks the empirical success rate.
    """
    rng = random.Random(seed)
    obs = [1.0 if rng.random() < theta else 0.0 for _ in range(n)]
    a = 1.0 + sum(obs)
    b = 1.0 + (n - sum(obs))
    return Cell(a=a, b=b), obs


def _buffer_from(preds, obs, *, cap: int = 5000) -> CalibrationBuffer:
    buf = CalibrationBuffer(cap=cap)
    for p, o in zip(preds, obs):
        buf.append(p, o)
    return buf


# --------------------------------------------------------------------------- #
# Drop-in safety: thin / degenerate buffer == wilson_lcb exactly               #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "a,b,fill",
    [(40.0, 10.0, 0), (8.0, 2.0, 5), (2.0, 2.0, 19), (100.0, 3.0, 12)],
)
def test_thin_buffer_equals_wilson_exactly(a, b, fill):
    """``len(buffer) < min_buffer`` ⇒ byte-identical to ``engine.wilson_lcb`` (drop-in)."""
    cell = Cell(a=a, b=b)
    buf = CalibrationBuffer()
    for _ in range(fill):  # fewer than the default min_buffer=20
        buf.append(0.8, 1.0)
    assert conformal_lcb(cell, buf, _Z) == E.wilson_lcb(cell, _Z)


def test_zero_spread_buffer_falls_back_to_wilson():
    """A rich buffer with no residual spread (every pred == obs) ⇒ Wilson fallback.

    The standardized-residual quantile is undefined when ``sd(pred − obs) == 0``;
    the bound must degrade to Wilson rather than divide by zero (DESIGN §5.2).
    """
    cell = Cell(a=30.0, b=10.0)
    buf = CalibrationBuffer()
    for _ in range(50):  # well past min_buffer, but all residuals are 0.0
        buf.append(1.0, 1.0)
    assert conformal_lcb(cell, buf, _Z) == E.wilson_lcb(cell, _Z)


def test_min_buffer_boundary_is_inclusive():
    """At exactly ``min_buffer − 1`` it is still Wilson; at ``min_buffer`` it engages."""
    cell = Cell(a=30.0, b=10.0)
    rng = random.Random(0)
    buf = CalibrationBuffer()
    for _ in range(19):  # min_buffer - 1
        buf.append(0.9, 1.0 if rng.random() < 0.5 else 0.0)
    assert conformal_lcb(cell, buf, _Z) == E.wilson_lcb(cell, _Z)
    buf.append(0.9, 0.0)  # now len == 20 == min_buffer, with spread
    assert conformal_lcb(cell, buf, _Z) != E.wilson_lcb(cell, _Z)


# --------------------------------------------------------------------------- #
# Asymptotic coincidence with Wilson + calibrated bound ≤ mean                  #
# --------------------------------------------------------------------------- #


def test_symmetric_calibrated_buffer_coincides_with_wilson():
    """A symmetric well-calibrated stream drives ``Q → z`` ⇒ bound → Wilson (§5.2)."""
    cell = Cell(a=80.0, b=20.0)  # mean 0.8, fixed stderr
    rng = random.Random(3)
    # Symmetric, calibrated residuals: graded obs ~ pred + N(0, sigma), pred uniform.
    preds = [rng.uniform(0.2, 0.9) for _ in range(3000)]
    obs = [min(1.0, max(0.0, p + rng.gauss(0.0, 0.1))) for p in preds]
    buf = _buffer_from(preds, obs)

    conformal = conformal_lcb(cell, buf, _Z)
    wilson = E.wilson_lcb(cell, _Z)
    # Converges to Wilson: a symmetric residual's (1-alpha) standardized quantile
    # approaches z, so mu - Q*sigma approaches mu - z*sigma.
    assert conformal == pytest.approx(wilson, abs=0.02)
    assert conformal <= cell.mean  # a lower bound never exceeds the point estimate.


def test_calibrated_rich_buffer_has_validish_coverage():
    """Synthetic stream of independent calibrated cells: coverage is finite-sample valid-ish.

    For each cell ``pred == theta`` (perfectly calibrated). The conformal bound is
    distribution-free up to Bernoulli discreteness; we assert coverage well above a
    conservative floor (the brief's "valid-ish"), comfortably better than chance.
    """
    alpha = 0.05
    trials = 1000
    covered = 0
    rng = random.Random(2026)
    for _ in range(trials):
        theta = rng.uniform(0.30, 0.92)
        n = rng.randint(40, 140)
        cell, obs = _bernoulli_cell(theta, n, rng.randint(0, 1 << 30))
        buf = _buffer_from([theta] * len(obs), obs, cap=200)
        if theta >= conformal_lcb(cell, buf, _Z, alpha=alpha):
            covered += 1
    coverage = covered / trials
    assert coverage >= 0.80, f"coverage {coverage:.3f} below valid-ish floor"


# --------------------------------------------------------------------------- #
# Catches miscalibration: over-confident buffer ⇒ bound below Wilson            #
# --------------------------------------------------------------------------- #


def test_overconfident_buffer_drops_below_wilson():
    """``pred ≫ obs`` shifts residuals positive ⇒ bound strictly below Wilson (§5.2).

    Wilson sees only the posterior spread and cannot detect that the cell's
    predictions overshoot reality; the conformal bound, keyed off realised
    prediction errors, drops to reflect the over-confidence — the whole point of
    the conformal backend.
    """
    cell, obs = _bernoulli_cell(theta=0.6, n=400, seed=9)
    over = _buffer_from([0.95] * len(obs), obs, cap=1000)  # systematic over-prediction
    wilson = E.wilson_lcb(cell, _Z)
    conformal = conformal_lcb(cell, over, _Z)
    assert conformal < wilson


def test_overconfident_is_lower_than_calibrated_at_same_cell():
    """At one fixed cell, an over-confident buffer bounds lower than a calibrated one."""
    cell, obs = _bernoulli_cell(theta=0.6, n=400, seed=21)
    calibrated = _buffer_from([cell.mean] * len(obs), obs, cap=1000)
    over = _buffer_from([0.99] * len(obs), obs, cap=1000)
    assert conformal_lcb(cell, over, _Z) <= conformal_lcb(cell, calibrated, _Z)


# --------------------------------------------------------------------------- #
# Buffer mechanics: ring cap, round-trip, clamping                             #
# --------------------------------------------------------------------------- #


def test_ring_buffer_drops_oldest_at_cap():
    """Appending past ``cap`` keeps only the most-recent ``cap`` pairs (DESIGN §7.3)."""
    buf = CalibrationBuffer(cap=3)
    for i in range(10):
        buf.append(i / 10.0, 1.0)
    assert len(buf) == 3
    # The three most-recent appends (i = 7, 8, 9) survive, oldest-first.
    assert buf.pairs == [(0.7, 1.0), (0.8, 1.0), (0.9, 1.0)]


def test_cap_must_be_positive():
    with pytest.raises(ValueError):
        CalibrationBuffer(cap=0)


def test_to_from_dict_round_trip():
    """``from_dict(to_dict(b))`` reproduces the buffer exactly (cache round-trip §5.5)."""
    buf = CalibrationBuffer(cap=7)
    for i in range(5):
        buf.append(0.1 * i, float(i % 2))
    restored = CalibrationBuffer.from_dict(buf.to_dict())
    assert restored.cap == buf.cap
    assert restored.pairs == buf.pairs


def test_from_dict_truncates_overlong_pairs_to_cap():
    """A tampered/over-long cached ``pairs`` is truncated to the most-recent ``cap``."""
    b = CalibrationBuffer.from_dict(
        {"cap": 3, "pairs": [[0.1, 0], [0.2, 1], [0.3, 0], [0.4, 1], [0.5, 0]]}
    )
    assert len(b) == 3
    assert b.pairs == [(0.3, 0.0), (0.4, 1.0), (0.5, 0.0)]


def test_append_clamps_into_unit_interval():
    """Out-of-range ``pred``/``obs`` are clamped to ``[0, 1]`` (quality is a probability)."""
    buf = CalibrationBuffer()
    buf.append(1.5, -0.3)
    buf.append(-2.0, 4.0)
    assert buf.pairs == [(1.0, 0.0), (0.0, 1.0)]


def test_bound_is_clamped_into_unit_interval():
    """The returned bound is always within ``[0, 1]`` even under extreme miscalibration.

    A tight, low-mean cell (small ``sigma``) whose predictions are wildly
    over-confident yields a large standardized quantile ``Q``; ``mu − Q·sigma``
    goes negative and must clamp to 0.0 (DESIGN §5.2).
    """
    cell = Cell(a=5.0, b=45.0)  # mean 0.1, tight posterior (small stderr)
    rng = random.Random(1)
    buf = CalibrationBuffer(cap=300)
    for _ in range(300):  # pred 0.99 vs obs ~ Bernoulli(0.1) ⇒ large positive residuals
        buf.append(0.99, 1.0 if rng.random() < 0.1 else 0.0)
    q = conformal_lcb(cell, buf, _Z)
    assert 0.0 <= q <= 1.0
    assert q == 0.0  # the large positive quantile pushes mu - Q*sigma below 0 ⇒ clamp.


# --------------------------------------------------------------------------- #
# Determinism                                                                   #
# --------------------------------------------------------------------------- #


def test_determinism_same_inputs_same_output():
    """No hidden randomness: identical (cell, buffer) ⇒ identical bound across calls."""
    cell, obs = _bernoulli_cell(theta=0.7, n=300, seed=42)
    buf = _buffer_from([0.85] * len(obs), obs, cap=1000)
    first = conformal_lcb(cell, buf, _Z)
    for _ in range(5):
        assert conformal_lcb(cell, buf, _Z) == first
    # And it is a plain float (the engine compares it to the gate threshold).
    assert isinstance(first, float) and math.isfinite(first)
