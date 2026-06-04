"""Tests for change-point detection of upstream model drift (DESIGN §7.3).

The deferred-feature contract (V3 build brief, bead bh-9if) — the static §7.4
safety hatch made adaptive:

- **no false reset** — a stationary, noisy quality stream (~constant 0.9) yields
  **no** change-point, so a healthy cell is never needlessly reset (the KEY
  correctness property; a false reset would throw away good evidence);
- **detects a real drop** — a stream whose mean falls ~0.9→~0.5 partway through
  yields a change-point flagged *near* the true shift (the drift / silent-
  deprecation case);
- **direction-aware** — ``direction='down'`` ignores an UP-shift; ``'up'`` /
  ``'both'`` catch it;
- **re-weighting** — :func:`recency_weights` drives pre-change observations toward
  zero and keeps post-change ≈ 1 (so the posterior re-learns the new regime); no
  change-point ⇒ all weights ≈ 1.0;
- **streaming == batch** — the stateful :class:`PageHinkley` reproduces the batch
  :func:`detect_changepoints` flag indices exactly;
- **determinism** — all stochastic streams are built from a *seeded*
  :class:`random.Random`, so every assertion is reproducible.

The detector takes a raw list of quality observations, so these tests drive it
directly (no store / config) to isolate the Page-Hinkley machine and the
re-weighting from the rest of CC-TS.
"""

from __future__ import annotations

import os
import random
import statistics
import sys

import pytest

# Make the pack root importable when pytest is run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modeladvisor import changepoint as CP  # noqa: E402

# Default Bernoulli-tuned knobs (the module defaults; named here for clarity).
DELTA = 0.15
LAMBDA = 4.0


# --------------------------------------------------------------------------- #
# Stream builders (all seeded -> deterministic)                                #
# --------------------------------------------------------------------------- #


def _stationary(p: float, n: int, seed: int) -> list[float]:
    """A seeded Bernoulli(p) quality stream of length ``n`` (constant mean p)."""
    rng = random.Random(seed)
    return [1.0 if rng.random() < p else 0.0 for _ in range(n)]


def _shift(p1: float, p2: float, n1: int, n2: int, seed: int) -> list[float]:
    """A seeded stream: Bernoulli(p1) for ``n1`` then Bernoulli(p2) for ``n2``."""
    rng = random.Random(seed)
    head = [1.0 if rng.random() < p1 else 0.0 for _ in range(n1)]
    tail = [1.0 if rng.random() < p2 else 0.0 for _ in range(n2)]
    return head + tail


# --------------------------------------------------------------------------- #
# No false reset on a stationary stream (the KEY property, DESIGN §7.3)         #
# --------------------------------------------------------------------------- #


def test_stationary_stream_no_changepoint():
    """A noisy-but-constant ~0.9 stream must NOT flag a change (no false reset)."""
    for seed in range(40):
        stream = _stationary(0.9, 150, seed)
        cps = CP.detect_changepoints(stream)
        assert cps == [], f"false reset on stationary stream (seed {seed}): {cps}"


def test_stationary_streams_across_means_rarely_false_fire():
    """Across p in {0.2, 0.5, 0.9} the stationary false-reset rate stays very low.

    p=0.5 is the maximum-Bernoulli-variance worst case; the Bernoulli-tuned
    ``delta`` must still keep it near zero or a healthy cell would churn.
    """
    for p in (0.2, 0.5, 0.9):
        fired = sum(
            1 for seed in range(60) if CP.detect_changepoints(_stationary(p, 150, seed))
        )
        assert fired <= 6, f"too many false resets at p={p}: {fired}/60"


def test_perfectly_constant_stream_never_fires():
    """A degenerate all-1.0 (and all-0.0) stream has zero variance -> no flag."""
    assert CP.detect_changepoints([1.0] * 80) == []
    assert CP.detect_changepoints([0.0] * 80) == []


# --------------------------------------------------------------------------- #
# Detects a genuine drop near the true shift (drift / deprecation)             #
# --------------------------------------------------------------------------- #


def test_downward_shift_detected_near_truth():
    """A ~0.9->~0.5 drop at index 60 is flagged, shortly AFTER the true shift."""
    detected = 0
    first_idxs: list[int] = []
    for seed in range(40):
        stream = _shift(0.9, 0.5, 60, 60, 1000 + seed)
        cps = CP.detect_changepoints(stream)
        if cps:
            detected += 1
            first_idxs.append(cps[0])
            # A Page-Hinkley flag necessarily trails the change (it needs to
            # accumulate evidence), and must land within the post-shift segment.
            assert cps[0] >= 60, f"flag {cps[0]} precedes the true shift (seed {seed})"
            assert cps[0] < 120
    # The drop is large and sustained -> detected on (almost) every seed.
    assert detected >= 38, f"missed the drop too often: {detected}/40"
    # ... and the typical detection lands within ~25 obs of the true shift.
    assert statistics.median(first_idxs) < 90


def test_harsh_deprecation_detected_fast():
    """A severe ~0.95->~0.2 collapse is caught quickly on every seed."""
    for seed in range(30):
        stream = _shift(0.95, 0.2, 50, 50, 5000 + seed)
        cps = CP.detect_changepoints(stream)
        assert cps, f"missed a harsh deprecation (seed {seed})"
        assert cps[0] >= 50
        # Severe drop -> flagged within ~20 observations of the shift.
        assert cps[0] < 70


# --------------------------------------------------------------------------- #
# Direction awareness (DESIGN §7.3: down=drift, up=recovery)                    #
# --------------------------------------------------------------------------- #


def test_direction_down_ignores_upshift():
    """``direction='down'`` must not flag a quality RISE (0.5 -> 0.9)."""
    fired = 0
    for seed in range(40):
        stream = _shift(0.5, 0.9, 60, 60, 3000 + seed)
        if CP.detect_changepoints(stream, direction="down"):
            fired += 1
    # The down-watcher should essentially never trip on a clean up-shift.
    assert fired <= 3, f"down-detector fired on an up-shift {fired}/40 times"


def test_direction_up_detects_upshift():
    """``direction='up'`` flags the rise the down-detector ignores."""
    detected = 0
    for seed in range(40):
        stream = _shift(0.5, 0.9, 60, 60, 3000 + seed)
        cps = CP.detect_changepoints(stream, direction="up")
        if cps:
            detected += 1
            assert cps[0] >= 60
    # The up-watcher is slightly less eager than the down-watcher at these knobs
    # but still catches the clean rise the large majority of the time.
    assert detected >= 34, f"up-detector missed the rise: {detected}/40"


def test_direction_both_catches_drop_and_rise():
    """``direction='both'`` flags either a drop or a rise."""
    drop = _shift(0.9, 0.5, 60, 60, 1234)
    rise = _shift(0.5, 0.9, 60, 60, 4321)
    assert CP.detect_changepoints(drop, direction="both")
    assert CP.detect_changepoints(rise, direction="both")


def test_invalid_direction_rejected():
    with pytest.raises(ValueError):
        CP.detect_changepoints([0.5, 0.5], direction="sideways")
    with pytest.raises(ValueError):
        CP.PageHinkley(direction="north")


# --------------------------------------------------------------------------- #
# Streaming detector matches the batch function (DESIGN §7.3)                   #
# --------------------------------------------------------------------------- #


def test_streaming_matches_batch():
    """Feeding the stream through PageHinkley.update reproduces the batch indices."""
    for seed in range(25):
        stream = _shift(0.9, 0.45, 50, 70, 7000 + seed)
        batch = CP.detect_changepoints(stream)
        ph = CP.PageHinkley()  # same defaults as detect_changepoints
        streamed = [i for i, x in enumerate(stream) if ph.update(x)]
        assert streamed == batch, f"streaming != batch (seed {seed})"


def test_streaming_reset_clears_state():
    """``reset()`` returns the detector to its pristine, no-evidence state."""
    ph = CP.PageHinkley()
    for x in _shift(0.9, 0.3, 40, 40, 9):
        ph.update(x)
    ph.reset()
    assert ph.n == 0
    assert ph._m_down == 0.0 and ph._M_down == 0.0
    assert ph._m_up == 0.0 and ph._m_up_min == 0.0
    # A fresh stationary stream after reset must not immediately fire.
    assert not any(ph.update(x) for x in _stationary(0.9, 60, 3))


def test_detector_resets_after_flag_so_second_shift_is_found():
    """Two successive drops in one stream are each flagged (reset-on-flag)."""
    # 0.95 (40) -> 0.5 (40) -> 0.1 (40): two distinct downward regime changes.
    rng = random.Random(77)

    def seg(p: float, k: int) -> list[float]:
        return [1.0 if rng.random() < p else 0.0 for _ in range(k)]

    stream = seg(0.95, 40) + seg(0.5, 40) + seg(0.1, 40)
    cps = CP.detect_changepoints(stream)
    assert len(cps) >= 2, f"second shift masked (only {cps})"
    # One flag in each post-shift segment (after 40, and after 80).
    assert any(40 <= c < 80 for c in cps)
    assert any(80 <= c < 120 for c in cps)


# --------------------------------------------------------------------------- #
# Recency re-weighting (DESIGN §7.3)                                            #
# --------------------------------------------------------------------------- #


def test_recency_weights_downweight_pre_change_and_keep_post():
    """Pre-change indices are driven small; post-change indices stay exactly 1.0."""
    stream = _shift(0.9, 0.5, 60, 60, 1011)
    cps = CP.detect_changepoints(stream)
    assert cps  # this seed detects the drop (see test above)
    c_star = max(cps)
    w = CP.recency_weights(len(stream), cps)

    assert len(w) == len(stream)
    assert all(0.0 <= x <= 1.0 for x in w)
    # Post-change: full strength, flat (the regime to re-learn is not discounted).
    assert all(x == 1.0 for x in w[c_star:])
    # Pre-change: substantially down-weighted on average...
    assert statistics.mean(w[:c_star]) < 0.5
    # ... and monotonically decaying the further back you go (older => smaller).
    pre = w[:c_star]
    assert all(pre[i] <= pre[i + 1] for i in range(len(pre) - 1))
    # The oldest observation is essentially forgotten.
    assert pre[0] < 0.05


def test_recency_weights_no_changepoint_all_ones():
    """With no change-point the default is inert: every weight is 1.0.

    A healthy, un-shifted cell must keep all its evidence at full strength — the
    feature never silently discounts a stream that hasn't drifted, even with the
    default ``decay < 1`` (which governs only the pre-shift falloff).
    """
    assert CP.recency_weights(50, []) == [1.0] * 50
    # Even with an aggressive decay, no change-point => still all 1.0.
    assert CP.recency_weights(20, [], decay=0.5) == [1.0] * 20


def test_recency_weights_hard_cut_when_decay_one():
    """``decay == 1`` degenerates to a hard 0/1 cut at the change-point."""
    w = CP.recency_weights(6, [3], decay=1.0)
    assert w == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]


def test_recency_weights_age_decay_only_mode():
    """``post_change_boost=False`` gives pure uniform age-decay (rule 3).

    The reset is skipped; decay is applied stream-wide (newest == 1.0) and the
    past is *never* zeroed out, even though a change-point was supplied.
    """
    w_no_boost = CP.recency_weights(4, [2], decay=0.5, post_change_boost=False)
    assert w_no_boost == [0.125, 0.25, 0.5, 1.0]
    assert all(x > 0.0 for x in w_no_boost)  # nothing hard-cut
    # decay == 1 in age-decay mode -> the identity.
    assert CP.recency_weights(4, [2], decay=1.0, post_change_boost=False) == [1.0] * 4


def test_recency_weights_validation_and_empty():
    """``decay`` must be in (0, 1]; ``n <= 0`` yields an empty vector."""
    assert CP.recency_weights(0, []) == []
    assert CP.recency_weights(-3, [1]) == []
    for bad_decay in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            CP.recency_weights(5, [1], decay=bad_decay)


# --------------------------------------------------------------------------- #
# PageHinkley parameter validation                                             #
# --------------------------------------------------------------------------- #


def test_pagehinkley_param_validation():
    with pytest.raises(ValueError):
        CP.PageHinkley(delta=-0.01)
    with pytest.raises(ValueError):
        CP.PageHinkley(lambda_=0.0)
    # Valid construction does not raise and starts empty.
    ph = CP.PageHinkley(delta=0.1, lambda_=3.0, direction="both")
    assert ph.n == 0


def test_short_streams_never_flag():
    """Empty / single-element streams cannot produce a change-point."""
    assert CP.detect_changepoints([]) == []
    assert CP.detect_changepoints([0.9]) == []
