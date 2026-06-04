"""Tests for the empirical-Bayes hierarchical pooler (DESIGN §1.3 / §7.3).

The closed-form ``CellStore.pooled`` shrinks every cell by a fixed
``pool_lambda`` fraction; :mod:`modeladvisor.hierarchical` replaces it with a
genuine two-level Beta-Binomial fit by empirical Bayes. The load-bearing
properties we assert:

- **hyperprior recovery** — fitting a synthetic group drawn from a known
  ``Beta(alpha0, beta0)`` recovers (approximately) the planted mean/concentration;
- **shrinkage monotonicity** (the key test) — a *thin* cell is pulled toward the
  group mean strictly more than a *rich* cell with the same own-mean;
- **own-cell asymptotics** — as own ``n → ∞`` the pooled mean → the own-cell mean;
- **degenerate groups** (empty / single / all-identical) return a proper prior and
  never crash;
- the optional ``pymc_pooled`` backend raises a clear error when PyMC is absent;
- determinism.
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

from modeladvisor import config as C  # noqa: E402
from modeladvisor import hierarchical as H  # noqa: E402
from modeladvisor import store as S  # noqa: E402
from modeladvisor.store import Cell, cell_key  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures + helpers                                                            #
# --------------------------------------------------------------------------- #


@pytest.fixture
def cfg() -> C.AdvisorConfig:
    """Default Claude haiku/sonnet/opus roster, baseline = opus."""
    return C.default_config()


def _mean(a: float, b: float) -> float:
    return a / (a + b)


def _synthetic_group(alpha0: float, beta0: float, *, k: int, n: int, seed: int) -> list[Cell]:
    """``k`` sibling cells, each ``theta_i ~ Beta(alpha0, beta0)`` then
    ``n`` Bernoulli trials -> ``Beta(1 + successes, 1 + failures)``."""
    rng = random.Random(seed)
    out: list[Cell] = []
    for _ in range(k):
        theta = rng.betavariate(alpha0, beta0)
        s = sum(1 for _ in range(n) if rng.random() < theta)
        out.append(Cell(a=1.0 + s, b=1.0 + (n - s)))
    return out


def _store_with(cfg: C.AdvisorConfig, records) -> S.CellStore:
    st = S.CellStore.cold_start(cfg)
    st.apply_records(records)
    return st


def _q(cfg, agent, shape, tier, q, i, *, provider="claude"):
    return {
        "kind": "quality",
        "ts": f"2026-06-01T00:00:{i % 60:02d}Z",
        "bead_id": f"bh-{agent}-{shape}-{tier}-{i}",
        "cell_key": cell_key(provider, agent, shape, tier),
        "q": q,
        "channel": "close",
    }


def _wins(cfg, agent, shape, tier, n):
    return [_q(cfg, agent, shape, tier, 1, i) for i in range(n)]


def _losses(cfg, agent, shape, tier, n):
    return [_q(cfg, agent, shape, tier, 0, i) for i in range(n)]


# --------------------------------------------------------------------------- #
# estimate_hyperprior — recovery on a known Beta                                #
# --------------------------------------------------------------------------- #


def test_hyperprior_recovers_planted_mean_and_concentration():
    # Plant a Beta(6, 4): mean 0.6, moderate concentration 10. With many fairly
    # rich siblings the method-of-moments fit should land close on the mean and in
    # the right ballpark on the concentration.
    group = _synthetic_group(6.0, 4.0, k=40, n=60, seed=7)
    a0, b0 = H.estimate_hyperprior(group)
    assert a0 > 0 and b0 > 0
    assert _mean(a0, b0) == pytest.approx(0.6, abs=0.06)
    # Concentration recovery is noisier than the mean; a generous band suffices to
    # prove we are fitting dispersion, not just defaulting to a weak prior.
    conc = a0 + b0
    assert 3.0 < conc < 60.0


def test_hyperprior_mean_tracks_a_high_group():
    # A group centred high (Beta(9, 1), mean 0.9) yields a high-mean hyperprior.
    group = _synthetic_group(9.0, 1.0, k=30, n=50, seed=11)
    a0, b0 = H.estimate_hyperprior(group)
    assert _mean(a0, b0) > 0.75


# --------------------------------------------------------------------------- #
# Shrinkage monotonicity — THE key test                                        #
# --------------------------------------------------------------------------- #


def test_thin_cell_shrinks_more_than_rich_cell():
    # Shared hyperprior fitted from a group centred well above 0.5.
    group = _synthetic_group(8.0, 2.0, k=12, n=40, seed=3)
    a0, b0 = H.estimate_hyperprior(group)
    group_mean = _mean(a0, b0)
    assert group_mean > 0.6  # the group pulls upward

    own_mean = 0.5
    # Same own-mean, very different own-mass.
    thin = Cell(a=1.0, b=1.0)        # mass 2
    rich = Cell(a=120.0, b=120.0)    # mass 240

    thin_pooled = _mean(thin.a + a0, thin.b + b0)
    rich_pooled = _mean(rich.a + a0, rich.b + b0)

    # Both shrink toward the (higher) group mean...
    assert thin_pooled > own_mean
    assert rich_pooled > own_mean
    # ...but the thin cell moves strictly, substantially more.
    thin_shift = thin_pooled - own_mean
    rich_shift = rich_pooled - own_mean
    assert thin_shift > rich_shift
    assert thin_shift > 5.0 * rich_shift


def test_pooled_mean_converges_to_own_mean_as_n_grows():
    group = _synthetic_group(2.0, 8.0, k=10, n=30, seed=5)  # group mean ~0.2
    a0, b0 = H.estimate_hyperprior(group)
    own_mean = 0.5

    prev_gap = 1.0
    for mass in (4.0, 40.0, 400.0, 4000.0, 40000.0):
        own = Cell(a=mass / 2.0, b=mass / 2.0)  # own mean fixed at 0.5
        pooled = _mean(own.a + a0, own.b + b0)
        gap = abs(pooled - own_mean)
        assert gap < prev_gap  # monotonically approaches the own mean
        prev_gap = gap
    assert prev_gap < 1e-3  # essentially reduces to own-cell at huge n


# --------------------------------------------------------------------------- #
# Degenerate groups — proper prior, no crash                                   #
# --------------------------------------------------------------------------- #


def test_empty_group_returns_weak_prior():
    assert H.estimate_hyperprior([]) == (1.0, 1.0)
    # A group of all-empty cells (zero mass) is treated as no evidence.
    assert H.estimate_hyperprior([Cell(a=0.0, b=0.0), Cell(a=0.0, b=0.0)]) == (1.0, 1.0)


def test_single_cell_group_is_a_weak_prior_at_its_mean():
    # One sibling, mean 0.75: anchored unit-mass prior (no dispersion signal).
    a0, b0 = H.estimate_hyperprior([Cell(a=3.0, b=1.0)])
    assert _mean(a0, b0) == pytest.approx(0.75)
    assert a0 + b0 == pytest.approx(1.0)


def test_identical_means_do_not_blow_up():
    # All cells share mean 0.7 exactly -> zero between-cell variance. The fit must
    # stay finite (clamped concentration), proper, and centred on the mean.
    group = [Cell(a=7.0, b=3.0) for _ in range(6)]
    a0, b0 = H.estimate_hyperprior(group)
    assert _mean(a0, b0) == pytest.approx(0.7)
    assert 0 < a0 + b0 <= H._MAX_CONCENTRATION + 1.0

    # All-success and all-failure groups must also yield a finite, proper Beta.
    for c in (Cell(a=10.0, b=0.0), Cell(a=0.0, b=10.0)):
        ax, bx = H.estimate_hyperprior([c, c, c])
        assert ax > 0 and bx > 0 and math.isfinite(ax) and math.isfinite(bx)


def test_overdispersed_group_falls_back_to_weak_anchor():
    # Bimodal group (means near 0 and near 1) has between-cell variance larger
    # than any Beta can express -> fall back to a weak prior at the grand mean.
    group = [Cell(a=1.0, b=99.0), Cell(a=99.0, b=1.0)]
    a0, b0 = H.estimate_hyperprior(group)
    assert a0 + b0 == pytest.approx(1.0)  # weak, unit mass
    assert _mean(a0, b0) == pytest.approx(0.5, abs=0.05)


# --------------------------------------------------------------------------- #
# eb_pooled — drop-in over a real store                                        #
# --------------------------------------------------------------------------- #


def test_eb_pooled_pulls_thin_cell_toward_rich_siblings(cfg):
    # mayor/judge/sonnet has a rich sibling group across agents (DESIGN §1.3).
    # Make every sibling strongly successful, leave the own cell thin/neutral.
    # NB mayor/judge IS the own cell, so it is excluded from the sibling loop;
    # mayor's cross-shape siblings (implement, lookup) are populated separately.
    recs = []
    for agent in ("witness", "boot", "deacon", "refinery"):
        recs += _wins(cfg, agent, "judge", "sonnet", 40)
    recs += _wins(cfg, "mayor", "implement", "sonnet", 40)
    recs += _wins(cfg, "mayor", "lookup", "sonnet", 40)
    # Own cell: one win, one loss (mean ~ prior, thin).
    recs += _wins(cfg, "mayor", "judge", "sonnet", 1) + _losses(cfg, "mayor", "judge", "sonnet", 1)
    st = _store_with(cfg, recs)

    own = st.get(cell_key("claude", "mayor", "judge", "sonnet"))
    pooled = H.eb_pooled(st, "claude", "mayor", "judge", "sonnet")
    # The high-performing siblings drag the thin own cell's mean up materially.
    assert pooled.mean > own.mean + 0.1
    # Bookkeeping is carried from the own cell, not invented.
    assert pooled.n == own.n
    assert pooled.last_update == own.last_update


def test_eb_pooled_barely_moves_a_rich_own_cell(cfg):
    # Same high siblings, but now the own cell is rich and disagrees (low mean).
    recs = []
    for agent in ("mayor", "witness", "boot", "deacon", "refinery"):
        recs += _wins(cfg, agent, "judge", "sonnet", 40)
    # Own cell: 200 obs at ~0.5 (rich, contradicts the siblings).
    recs += _wins(cfg, "mayor", "judge", "sonnet", 100) + _losses(cfg, "mayor", "judge", "sonnet", 100)
    st = _store_with(cfg, recs)

    own = st.get(cell_key("claude", "mayor", "judge", "sonnet"))
    pooled = H.eb_pooled(st, "claude", "mayor", "judge", "sonnet")
    # Rich own-cell evidence dominates: the pooled mean barely budges.
    assert abs(pooled.mean - own.mean) < 0.05


def test_eb_pooled_max_prior_mass_cap_limits_injection(cfg):
    # With a tiny cap the injected pseudocount mass cannot exceed it, so a thin
    # cell is pulled far less than under uncapped EB. mayor/judge is the own cell
    # (thin: 1 win, 1 loss); the high-performing siblings supply the pull.
    recs = []
    for agent in ("witness", "boot", "deacon", "refinery"):
        recs += _wins(cfg, agent, "judge", "sonnet", 50)
    recs += _wins(cfg, "mayor", "implement", "sonnet", 50)
    recs += _wins(cfg, "mayor", "lookup", "sonnet", 50)
    recs += _wins(cfg, "mayor", "judge", "sonnet", 1) + _losses(cfg, "mayor", "judge", "sonnet", 1)
    st = _store_with(cfg, recs)

    own = st.get(cell_key("claude", "mayor", "judge", "sonnet"))
    uncapped = H.eb_pooled(st, "claude", "mayor", "judge", "sonnet")
    capped = H.eb_pooled(st, "claude", "mayor", "judge", "sonnet", max_prior_mass=1.0)

    own_mass = own.a + own.b
    capped_injected = (capped.a + capped.b) - own_mass
    assert capped_injected == pytest.approx(1.0, abs=1e-6)
    # The cap shrinks less than full EB: capped mean sits between own and uncapped.
    assert own.mean < capped.mean < uncapped.mean


def test_eb_pooled_is_deterministic(cfg):
    recs = _wins(cfg, "mayor", "judge", "sonnet", 7) + _losses(cfg, "mayor", "judge", "sonnet", 2)
    recs += _wins(cfg, "witness", "judge", "sonnet", 11)
    st = _store_with(cfg, recs)
    a = H.eb_pooled(st, "claude", "mayor", "judge", "sonnet")
    b = H.eb_pooled(st, "claude", "mayor", "judge", "sonnet")
    assert (a.a, a.b, a.n, a.last_update) == (b.a, b.b, b.n, b.last_update)


def test_eb_pooled_no_siblings_reduces_to_own_plus_anchor(cfg):
    # A cell whose siblings are all empty: the group is effectively just the own
    # cell, so the fit is a weak anchor at the own mean and pooling is gentle.
    recs = _wins(cfg, "polecat", "implement", "haiku", 10) + _losses(cfg, "polecat", "implement", "haiku", 10)
    st = _store_with(cfg, recs)
    own = st.get(cell_key("claude", "polecat", "implement", "haiku"))
    pooled = H.eb_pooled(st, "claude", "polecat", "implement", "haiku")
    # Own mean ~0.5; weak anchor keeps the pooled mean close to it.
    assert pooled.mean == pytest.approx(own.mean, abs=0.05)


# --------------------------------------------------------------------------- #
# Optional PyMC backend — graceful absence                                     #
# --------------------------------------------------------------------------- #


def test_pymc_pooled_raises_clearly_without_pymc(cfg):
    # We test ONLY the graceful-absence path (the brief): with PyMC installed the
    # full-MCMC backend is an optional extra we do not exercise here.
    try:
        import pymc  # type: ignore  # noqa: F401
        pytest.skip("pymc is installed; the graceful-absence path is not exercised")
    except ImportError:
        pass
    st = S.CellStore.cold_start(cfg)
    with pytest.raises(RuntimeError) as ei:
        H.pymc_pooled(st, "claude", "mayor", "judge", "sonnet")
    msg = str(ei.value)
    assert "model-advisor[bayes]" in msg
