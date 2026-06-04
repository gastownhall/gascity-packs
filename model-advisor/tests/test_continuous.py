"""Tests for the continuous quality signal (bead bh-pl7, DESIGN §1.3 + §4 + §7.3).

This suite owns the *continuous-reward* contract: a quality outcome ``q ∈ [0, 1]``
(reviewer score / test-pass fraction) folded into the existing Beta posterior, plus
the optional :class:`GaussianCell` Normal-Inverse-Gamma posterior for unbounded
scores. The store/engine/config are sibling files the integrator wires; we do not
touch them here.

To stay runnable *before* the sibling store/engine are import-clean — the package
``__init__`` eagerly re-exports them — we load both ``modeladvisor/continuous.py``
and the real ``modeladvisor/store.py`` (for its genuine :class:`Cell`) as
**standalone modules** via importlib, registering each in ``sys.modules`` before
executing it (so their ``@dataclass`` decorators resolve). This mirrors the loader
in ``test_ingest.py`` and keeps the suite hermetic regardless of sibling timing.
The "binary path unchanged" test asserts against the *real* ``Cell`` so the
byte-identity claim is verified, not assumed.

Nothing here touches live state: everything operates on in-memory objects.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

PACK_DIR = Path(__file__).resolve().parents[1]
CONT_PATH = PACK_DIR / "modeladvisor" / "continuous.py"
STORE_PATH = PACK_DIR / "modeladvisor" / "store.py"


def _load_standalone(name: str, path: Path):
    """Load a module file standalone, bypassing the package __init__ re-exports."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # register BEFORE exec (dataclasses resolve self-refs)
    spec.loader.exec_module(mod)
    return mod


cont = _load_standalone("mad_continuous_under_test", CONT_PATH)


def _real_cell(a: float, b: float):
    """A genuine ``modeladvisor.store.Cell`` (loaded standalone).

    ``store.py`` imports ``modeladvisor.config``; loading config under its real
    dotted name first keeps ``store`` import-clean without running the package
    ``__init__``. Returns a ``Cell(a, b)`` for byte-identity checks.
    """
    if "modeladvisor" not in sys.modules:
        import types

        pkg = types.ModuleType("modeladvisor")
        pkg.__path__ = [str(PACK_DIR / "modeladvisor")]
        pkg.__package__ = "modeladvisor"
        sys.modules["modeladvisor"] = pkg
    if "modeladvisor.config" not in sys.modules:
        _load_standalone("modeladvisor.config", PACK_DIR / "modeladvisor" / "config.py")
    if "modeladvisor.store" not in sys.modules:
        _load_standalone("modeladvisor.store", STORE_PATH)
    store = sys.modules["modeladvisor.store"]
    return store.Cell(a=a, b=b)


# --------------------------------------------------------------------------- #
# A tiny stand-in Beta cell (Protocol-compatible) for the bounded path.        #
# Mirrors store.Cell.update exactly so apply_continuous can be unit-tested      #
# without importing the package; the byte-identity test uses the REAL Cell.     #
# --------------------------------------------------------------------------- #


class FakeCell:
    """Minimal Beta cell exposing ``.update`` (DESIGN §1.3 Layer 1)."""

    def __init__(self, a: float, b: float) -> None:
        self.a = a
        self.b = b
        self.n = 0
        self.last_update: str | None = None

    @property
    def mean(self) -> float:
        return self.a / (self.a + self.b)

    def update(self, q: float, w: float, ts: str | None) -> None:
        self.a += w * q
        self.b += w * (1.0 - q)
        self.n += 1
        if ts is not None:
            self.last_update = ts


# --------------------------------------------------------------------------- #
# 1. is_valid_q — binary vs continuous (DESIGN §1.1 / §7.3)                     #
# --------------------------------------------------------------------------- #


def test_is_valid_q_binary_vs_continuous() -> None:
    # Binary (v1 default): only the two-point set {0, 1}.
    assert cont.is_valid_q(0.0) is True
    assert cont.is_valid_q(1.0) is True
    assert cont.is_valid_q(0) is True
    assert cont.is_valid_q(1) is True
    assert cont.is_valid_q(0.7) is False  # mid-range rejected when binary
    assert cont.is_valid_q(0.5) is False

    # Continuous: the whole closed unit interval is admissible.
    assert cont.is_valid_q(0.7, continuous=True) is True
    assert cont.is_valid_q(0.0, continuous=True) is True
    assert cont.is_valid_q(1.0, continuous=True) is True
    # ...but nothing outside [0, 1], even in continuous mode.
    assert cont.is_valid_q(1.5, continuous=True) is False
    assert cont.is_valid_q(-0.01, continuous=True) is False


def test_is_valid_q_rejects_non_numeric_and_non_finite() -> None:
    # Never raises; returns False for junk in either mode.
    for mode in (False, True):
        assert cont.is_valid_q(None, continuous=mode) is False
        assert cont.is_valid_q("pass", continuous=mode) is False
        assert cont.is_valid_q(float("nan"), continuous=mode) is False
        assert cont.is_valid_q(float("inf"), continuous=mode) is False


# --------------------------------------------------------------------------- #
# 2. apply_continuous moves the Beta posterior mean correctly (DESIGN §1.3)     #
# --------------------------------------------------------------------------- #


def test_apply_continuous_moves_beta_mean_toward_q() -> None:
    # Optimistic baseline-style prior Beta(8, 2) (mean 0.80). Repeated q=0.7
    # observations must pull the posterior mean down toward 0.7, monotonically.
    cell = FakeCell(8.0, 2.0)
    assert cell.mean == pytest.approx(0.80)
    means = []
    for _ in range(5):
        cont.apply_continuous(cell, 0.7, w=1.0, ts="2026-06-03T00:00:00Z")
        means.append(cell.mean)
    # After 5 unit-weight updates: a=11.5, b=3.5 -> mean = 11.5/15 = 0.76667.
    assert cell.mean == pytest.approx(11.5 / 15.0)
    # Strictly decreasing toward (but not past) 0.7.
    assert all(means[i] > means[i + 1] for i in range(len(means) - 1))
    assert 0.7 < cell.mean < 0.80
    assert cell.n == 5
    assert cell.last_update == "2026-06-03T00:00:00Z"


def test_apply_continuous_weight_scales_the_update() -> None:
    # A reviewer-weight (w=3) continuous observation counts as 3 soft obs.
    cell = FakeCell(1.0, 1.0)
    cont.apply_continuous(cell, 0.75, w=3.0, ts=None)
    assert cell.a == pytest.approx(1.0 + 3.0 * 0.75)  # 3.25
    assert cell.b == pytest.approx(1.0 + 3.0 * 0.25)  # 1.75
    assert cell.n == 1


# --------------------------------------------------------------------------- #
# 3. Clamping of out-of-range q (DESIGN §7.3)                                   #
# --------------------------------------------------------------------------- #


def test_apply_continuous_clamps_out_of_range() -> None:
    # q > 1 clamps to 1 (full soft-success: all mass to a).
    hi = FakeCell(2.0, 2.0)
    cont.apply_continuous(hi, 1.4, w=1.0, ts=None)
    assert hi.a == pytest.approx(3.0)
    assert hi.b == pytest.approx(2.0)

    # q < 0 clamps to 0 (full soft-failure: all mass to b).
    lo = FakeCell(2.0, 2.0)
    cont.apply_continuous(lo, -0.3, w=1.0, ts=None)
    assert lo.a == pytest.approx(2.0)
    assert lo.b == pytest.approx(3.0)


def test_apply_continuous_rejects_non_finite() -> None:
    cell = FakeCell(1.0, 1.0)
    with pytest.raises(ValueError):
        cont.apply_continuous(cell, float("nan"), w=1.0, ts=None)
    with pytest.raises(ValueError):
        cont.apply_continuous(cell, float("inf"), w=1.0, ts=None)
    # The cell was never mutated by the rejected calls.
    assert (cell.a, cell.b, cell.n) == (1.0, 1.0, 0)


# --------------------------------------------------------------------------- #
# 4. Binary path is byte-identical to v1 — against the REAL store.Cell.         #
#    (The brief's hard requirement: feature-on with {0,1} data == v1.)          #
# --------------------------------------------------------------------------- #


def test_binary_path_unchanged_vs_real_cell() -> None:
    # Drive the same {0,1} sequence through (a) the real Cell.update (the v1
    # binary path) and (b) apply_continuous; the resulting (a, b, n, last_update)
    # must be bit-for-bit identical.
    seq = [(1.0, 1.0, "t1"), (0.0, 3.0, "t2"), (1.0, 5.0, "t3"), (1.0, 1.0, None)]

    v1 = _real_cell(8.0, 2.0)
    for q, w, ts in seq:
        v1.update(q, w, ts)

    via_cont = _real_cell(8.0, 2.0)
    for q, w, ts in seq:
        cont.apply_continuous(via_cont, q, w, ts)

    assert via_cont.to_dict() == v1.to_dict()
    assert via_cont.a == v1.a and via_cont.b == v1.b
    assert via_cont.n == v1.n and via_cont.last_update == v1.last_update


# --------------------------------------------------------------------------- #
# 5. normalise_score — unbounded raw -> [0, 1], clamped (DESIGN §7.3)           #
# --------------------------------------------------------------------------- #


def test_normalise_score_maps_and_clamps() -> None:
    # A reviewer 0-100 score maps linearly into [0, 1].
    assert cont.normalise_score(0.0, 0.0, 100.0) == pytest.approx(0.0)
    assert cont.normalise_score(50.0, 0.0, 100.0) == pytest.approx(0.5)
    assert cont.normalise_score(100.0, 0.0, 100.0) == pytest.approx(1.0)
    # Out-of-range raw clamps to the nearest edge.
    assert cont.normalise_score(120.0, 0.0, 100.0) == pytest.approx(1.0)
    assert cont.normalise_score(-10.0, 0.0, 100.0) == pytest.approx(0.0)
    # Degenerate range -> neutral midpoint (no information).
    assert cont.normalise_score(42.0, 5.0, 5.0) == pytest.approx(0.5)
    # Swapped bounds are oriented, not an error.
    assert cont.normalise_score(25.0, 100.0, 0.0) == pytest.approx(0.25)
    # Output is always a valid continuous q.
    assert cont.is_valid_q(cont.normalise_score(73.4, 10.0, 90.0), continuous=True)


def test_normalise_then_apply_round_trip() -> None:
    # End-to-end: a raw reviewer score -> normalised q -> Beta update.
    cell = FakeCell(1.0, 1.0)
    q = cont.normalise_score(85.0, 0.0, 100.0)  # 0.85
    cont.apply_continuous(cell, q, w=1.0, ts=None)
    assert cell.a == pytest.approx(1.85)
    assert cell.b == pytest.approx(1.15)


# --------------------------------------------------------------------------- #
# 6. GaussianCell — update moves the mean, lcb sanity, round-trip (DESIGN §7.3) #
# --------------------------------------------------------------------------- #


def test_gaussian_cell_update_tracks_location_and_shrinks_stderr() -> None:
    gc = cont.GaussianCell()  # weak prior centred at 0
    assert gc.mean == pytest.approx(0.0)
    # A tight cluster around 10: enough data overwhelms the prior-at-0 and the
    # location estimate converges to the cluster mean.
    cluster = [10.0, 10.1, 9.9, 10.05, 9.95] * 6  # 30 obs, sample mean ~10
    stderr_by_n: list[float] = []
    for i, x in enumerate(cluster, start=1):
        gc.update(x)
        if i in (5, 10, 20, 30):
            stderr_by_n.append(gc.stderr)
    # Location estimate has converged toward the data mean (~10).
    assert gc.mean == pytest.approx(10.0, abs=0.5)
    assert gc.n == len(cluster)
    # Uncertainty on the *location* strictly shrinks as more of the same signal
    # accrues (the load-bearing "more data -> tighter posterior" property).
    assert all(stderr_by_n[i] > stderr_by_n[i + 1] for i in range(len(stderr_by_n) - 1))
    # data_variance (spread of the scores themselves) is a sane positive estimate.
    assert gc.data_variance > 0.0


def test_gaussian_cell_lcb_is_below_mean_and_unbounded() -> None:
    gc = cont.GaussianCell()
    for x in [-5.0, -4.0, -6.0, -5.5, -4.5]:  # genuinely negative scores
        gc.update(x)
    z = 1.645
    lcb = gc.lcb(z)
    # One-sided lower bound sits strictly below the mean...
    assert lcb < gc.mean
    assert lcb == pytest.approx(gc.mean - z * gc.stderr)
    # ...and is NOT clamped to 0 (unbounded score: negative LCB preserved).
    assert lcb < 0.0
    # A larger z gives a looser (lower) bound.
    assert gc.lcb(2.5) < gc.lcb(1.0)


def test_gaussian_cell_round_trip_dict() -> None:
    gc = cont.GaussianCell()
    for x in [3.0, 7.0, 5.0, 6.0]:
        gc.update(x)
    d = gc.to_dict()
    assert set(d) == {"mu", "lam", "alpha", "beta", "n"}
    back = cont.GaussianCell.from_dict(d)
    assert back == gc  # dataclass eq over all five fields
    assert back.to_dict() == d
    # Continuing to update the restored cell matches updating the original.
    gc.update(8.0)
    back.update(8.0)
    assert back.to_dict() == gc.to_dict()


def test_gaussian_cell_rejects_non_finite_update() -> None:
    gc = cont.GaussianCell()
    with pytest.raises(ValueError):
        gc.update(float("nan"))
    with pytest.raises(ValueError):
        gc.update(float("inf"))


# --------------------------------------------------------------------------- #
# 7. Determinism / replay-order invariance (DESIGN §5.5 rebuildability)         #
# --------------------------------------------------------------------------- #


def test_determinism_continuous_replay_is_reproducible() -> None:
    # Same continuous sequence -> identical Beta state, twice (no hidden state).
    seq = [0.3, 0.9, 0.55, 1.2, -0.4, 0.7]
    a = FakeCell(2.0, 2.0)
    b = FakeCell(2.0, 2.0)
    for q in seq:
        cont.apply_continuous(a, q, w=2.0, ts=None)
        cont.apply_continuous(b, q, w=2.0, ts=None)
    assert (a.a, a.b, a.n) == (b.a, b.b, b.n)


def test_gaussian_update_is_order_invariant() -> None:
    # The NIG sequential update is algebraically the batch update, so the final
    # posterior must not depend on the order observations are replayed in
    # (load-bearing for the rebuildable cell-store cache, DESIGN §5.5).
    xs = [10.0, 12.0, 11.0, 9.0, 13.0, 10.0, 11.0, 12.0]
    fwd = cont.GaussianCell()
    rev = cont.GaussianCell()
    for x in xs:
        fwd.update(x)
    for x in reversed(xs):
        rev.update(x)
    assert fwd.mu == pytest.approx(rev.mu)
    assert fwd.lam == pytest.approx(rev.lam)
    assert fwd.alpha == pytest.approx(rev.alpha)
    assert fwd.beta == pytest.approx(rev.beta)
    assert math.isclose(fwd.lcb(1.645), rev.lcb(1.645), rel_tol=1e-12, abs_tol=1e-12)
