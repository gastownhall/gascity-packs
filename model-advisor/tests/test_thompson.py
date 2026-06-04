"""Tests for the genuine Thompson-Sampling mode (DESIGN §1.2–§1.4, §7.3).

The deferred-feature contract (V3 build brief, bead bh-s37):

- **reproducibility** — same seed ⇒ same samples and same choice (DESIGN §1.4
  property 2); different seeds ⇒ varied but always-valid choices;
- **safety** — a ``Critical`` cell never downgrades even when a cheap tier
  samples high; the ``force_baseline`` safety hatch likewise never downgrades
  (DESIGN §1.2 ``M[Critical]=∞`` hard rule / §7.4);
- **directional correctness** — over a fixed seed range a clearly-better cheap
  tier is chosen materially more often than a clearly-worse one (the randomised
  analogue of the gate exploring in proportion to posterior quality);
- **audit completeness** — the structured ``audit`` object carries the samples
  and the reasoning (DESIGN §1.4 property 3).

The module takes ``cells_by_tier`` directly, so these tests drive it with
hand-built :class:`~modeladvisor.store.Cell` posteriors (no store / config
needed) to isolate the sampler + selection logic from pooling.
"""

from __future__ import annotations

import os
import sys

import pytest

# Make the pack root importable when pytest is run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modeladvisor import thompson as T  # noqa: E402
from modeladvisor.store import Cell  # noqa: E402

# A 3-tier cost order (cheapest -> most-capable), baseline = the dearest tier,
# mirroring the default haiku/sonnet/opus roster.
ORDER = ["haiku", "sonnet", "opus"]
BASE = "opus"

# q_tol for the default Moderate class (DESIGN §1.2).
Q_TOL = 0.05


def _cells(haiku: Cell, sonnet: Cell, opus: Cell) -> dict[str, Cell]:
    return {"haiku": haiku, "sonnet": sonnet, "opus": opus}


def _high(mean_count: float = 80.0) -> Cell:
    """A tight, high-quality posterior (mean ~0.99): samples near 1."""
    return Cell(a=mean_count, b=1.0)


def _low(mean_count: float = 80.0) -> Cell:
    """A tight, low-quality posterior (mean ~0.01): samples near 0."""
    return Cell(a=1.0, b=mean_count)


def _baseline_good() -> Cell:
    """A solid baseline posterior (mean ~0.9)."""
    return Cell(a=45.0, b=5.0)


# --------------------------------------------------------------------------- #
# Reproducibility (DESIGN §1.4 property 2)                                      #
# --------------------------------------------------------------------------- #


def test_same_seed_same_samples():
    cells = _cells(_low(), Cell(a=30.0, b=8.0), _baseline_good())
    s1 = T.sample_tier_qualities(ORDER, cells, seed=42)
    s2 = T.sample_tier_qualities(ORDER, cells, seed=42)
    assert s1 == s2
    assert set(s1) == set(ORDER)
    assert all(0.0 <= v <= 1.0 for v in s1.values())


def test_same_seed_same_choice():
    cells = _cells(_low(), Cell(a=30.0, b=8.0), _baseline_good())
    a_id, a_audit = T.thompson_select(
        ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=123
    )
    b_id, b_audit = T.thompson_select(
        ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=123
    )
    assert a_id == b_id
    assert a_audit == b_audit


def test_different_seeds_vary_but_stay_valid():
    # Borderline cheap tier (mean ~0.8) so the draw genuinely varies seed-to-seed.
    cells = _cells(_low(), Cell(a=8.0, b=2.0), _baseline_good())
    chosen = {
        T.thompson_select(
            ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=s
        )[0]
        for s in range(200)
    }
    # Every choice is a real roster tier.
    assert chosen <= set(ORDER)
    # The randomness actually produces more than one outcome over the seed range.
    assert len(chosen) >= 2
    # haiku is near-0 quality and must never be chosen here (would breach the gate).
    assert "haiku" not in chosen


# --------------------------------------------------------------------------- #
# Safety: Critical / forced never downgrade (DESIGN §1.2, §7.4)                 #
# --------------------------------------------------------------------------- #


def test_critical_never_downgrades_even_when_cheap_samples_high():
    # Both cheap tiers sample ~1.0; only Critical stops the downgrade.
    cells = _cells(_high(), _high(), _baseline_good())
    for s in range(300):
        chosen, audit = T.thompson_select(
            ORDER, cells, BASE, q_tol=0.0, is_critical=True, forced=False, seed=s
        )
        assert chosen == BASE, f"Critical downgraded on seed {s}"
        # No cheaper tier is ever admissible.
        for row in audit["tiers"]:
            if row["action"] == "down":
                assert row["admitted"] is False


def test_forced_baseline_never_downgrades():
    cells = _cells(_high(), _high(), _baseline_good())
    for s in range(300):
        chosen, audit = T.thompson_select(
            ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=True, seed=s
        )
        assert chosen == BASE, f"force_baseline downgraded on seed {s}"
        assert audit["forced_baseline"] is True
        assert audit["no_downgrade"] is True


def test_critical_audit_marks_no_downgrade_and_keeps_upgrades_possible():
    # An upgrade tier above baseline is still allowed under Critical (never a
    # *downgrade*); only cheaper tiers are blocked. Order: cheap, BASE, dear.
    order = ["cheap", "mid", "dear"]
    cells = {
        "cheap": _high(),         # would downgrade -> must be blocked
        "mid": _baseline_good(),  # baseline
        "dear": _high(),          # upgrade -> allowed if it beats baseline sample
    }
    saw_upgrade = False
    for s in range(200):
        chosen, audit = T.thompson_select(
            order, cells, "mid", q_tol=0.0, is_critical=True, forced=False, seed=s
        )
        # Never a downgrade to the cheaper tier.
        assert chosen != "cheap"
        assert order.index(chosen) >= order.index("mid")
        if chosen == "dear":
            saw_upgrade = True
    assert saw_upgrade, "an upgrade should still be reachable under Critical"


# --------------------------------------------------------------------------- #
# Directional correctness (light statistical test, fixed seed range)           #
# --------------------------------------------------------------------------- #


def test_better_cheap_tier_chosen_more_often_than_worse():
    """A clearly-better cheap tier wins materially more draws than a worse one.

    haiku ~ Beta(85, 5)  (mean ~0.94, the *better* cheap tier)
    sonnet ~ Beta(20, 25) (mean ~0.44, the *worse* cheap tier)
    baseline opus ~ Beta(45, 5) (mean ~0.9). q_tol = 0.10 (Lenient).
    Over a fixed seed range the better cheap tier (haiku, also the cheapest) is
    selected far more often than the worse one.
    """
    cells = _cells(Cell(a=85.0, b=5.0), Cell(a=20.0, b=25.0), _baseline_good())
    counts = {"haiku": 0, "sonnet": 0, "opus": 0}
    for s in range(500):
        chosen, _ = T.thompson_select(
            ORDER, cells, BASE, q_tol=0.10, is_critical=False, forced=False, seed=s
        )
        counts[chosen] += 1
    # The better cheap tier dominates the worse one decisively.
    assert counts["haiku"] > counts["sonnet"]
    assert counts["haiku"] > 3 * max(counts["sonnet"], 1)


def test_strong_cheap_tier_usually_downgrades():
    """A cheap tier that is clearly good should be picked the large majority of draws."""
    cells = _cells(_low(), _high(), _baseline_good())  # sonnet ~1.0, haiku ~0
    downgrades = sum(
        T.thompson_select(
            ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=s
        )[0]
        == "sonnet"
        for s in range(300)
    )
    assert downgrades > 270  # ~ always (sonnet samples ~1 >= baseline - q_tol)


def test_hopeless_cheap_tiers_keep_baseline():
    """When every cheaper tier is clearly bad, the baseline is kept (no downgrade)."""
    cells = _cells(_low(), _low(), _baseline_good())
    for s in range(200):
        chosen, audit = T.thompson_select(
            ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=s
        )
        assert chosen == BASE
        assert audit["decision"].startswith("no cheaper tier")


# --------------------------------------------------------------------------- #
# Selection mechanics                                                           #
# --------------------------------------------------------------------------- #


def test_picks_cheapest_among_admissible():
    """Both cheap tiers sample high -> the cheapest (haiku) is chosen."""
    cells = _cells(_high(), _high(), _baseline_good())
    for s in range(100):
        chosen, audit = T.thompson_select(
            ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=s
        )
        # haiku and sonnet both clear the gate -> cheapest wins.
        assert chosen == "haiku"
        assert "haiku" in audit["admissible"] and "sonnet" in audit["admissible"]


def test_upgrade_only_when_strictly_better_than_baseline():
    """An upgrade is selected only if it strictly beats the baseline's own sample.

    Cheapest tier is hopeless, so no downgrade; whether we stay or upgrade depends
    purely on whether the dearer tier's sample exceeds the baseline's.
    """
    cells = _cells(_low(), _baseline_good(), _high())  # haiku ~0, sonnet baseline, opus ~1
    order = ["haiku", "sonnet", "opus"]
    for s in range(200):
        chosen, audit = T.thompson_select(
            order, cells, "sonnet", q_tol=Q_TOL, is_critical=False, forced=False, seed=s
        )
        assert chosen != "haiku"  # cheaper tier is hopeless -> never a downgrade
        theta = audit["samples"]
        if chosen == "opus":
            assert theta["opus"] > theta["sonnet"]
        else:
            assert chosen == "sonnet"
            assert theta["opus"] <= theta["sonnet"]


# --------------------------------------------------------------------------- #
# Audit completeness (DESIGN §1.4 property 3)                                   #
# --------------------------------------------------------------------------- #


def test_audit_completeness():
    cells = _cells(_low(), Cell(a=30.0, b=8.0), _baseline_good())
    chosen, audit = T.thompson_select(
        ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=7
    )
    # Top-level audit keys.
    for key in (
        "mode", "seed", "baseline_tier", "baseline_theta", "q_tol", "critical",
        "forced_baseline", "no_downgrade", "samples", "tiers", "admissible",
        "chosen_tier", "decision",
    ):
        assert key in audit, f"missing audit key {key!r}"
    assert audit["mode"] == "thompson"
    assert audit["seed"] == 7
    assert audit["chosen_tier"] == chosen
    assert audit["baseline_tier"] == BASE
    # samples + per-tier rows span the whole roster.
    assert set(audit["samples"]) == set(ORDER)
    assert {r["tier_id"] for r in audit["tiers"]} == set(ORDER)
    # baseline_theta echoes the baseline's sample.
    assert audit["baseline_theta"] == audit["samples"][BASE]
    # every per-tier row carries the reasoning fields.
    for row in audit["tiers"]:
        for k in ("tier_id", "action", "theta", "admitted", "reason"):
            assert k in row
        assert isinstance(row["reason"], str) and row["reason"]
    # the chosen tier is admissible, and the baseline always is.
    assert chosen in audit["admissible"]
    assert BASE in audit["admissible"]


def test_sample_qualities_respects_order_and_keys():
    cells = _cells(_low(), _high(), _baseline_good())
    samples = T.sample_tier_qualities(ORDER, cells, seed=1)
    assert list(samples.keys()) == ORDER  # iteration follows the cost order
    assert all(isinstance(v, float) for v in samples.values())


def test_degenerate_zero_param_cell_does_not_crash():
    """A degenerate (0, 0) cell is nudged to epsilon rather than crashing betavariate."""
    cells = _cells(Cell(a=0.0, b=0.0), _high(), _baseline_good())
    samples = T.sample_tier_qualities(ORDER, cells, seed=3)
    assert 0.0 <= samples["haiku"] <= 1.0
    chosen, _ = T.thompson_select(
        ORDER, cells, BASE, q_tol=Q_TOL, is_critical=False, forced=False, seed=3
    )
    assert chosen in ORDER
