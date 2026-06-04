"""Change-point detection for upstream model drift / silent deprecation
(DESIGN §7.3 deferred, superseding the §7.4 static safety hatch).

The §7.4 safety hatch is *static*: an operator pins a cell to its baseline tier
(``force_baseline``) when they *notice* upstream drift. This module makes that
mitigation **adaptive** — it reads a cell's time-ordered quality stream and
detects the moment the upstream model's quality *shifts* (a sustained drop = the
drift / silent-deprecation case; a rise = a recovered or upgraded model), so the
gate can **down-weight the stale pre-shift evidence** and the posterior re-learns
the new regime instead of being anchored by months of now-irrelevant history.

It is the temporal complement to the rest of CC-TS: where the gate (DESIGN §1.3
Layer 2) asks *"is this tier good enough right now?"*, change-point detection asks
*"did *right now* stop resembling *the past*?"* — a question the stationary
Beta-Bernoulli posterior cannot ask, because it pools all observations with equal
(only age-blind channel) weight and so dilutes a real regime change into the mean.

Detector — the Page-Hinkley test (PH)
-------------------------------------
PH is the classic stdlib-friendly sequential change detector: a one-sided CUSUM
of each observation's deviation from the running mean, with a small magnitude
tolerance ``delta`` baked in so ordinary noise does not accumulate. Watching for
a **drop** (``direction='down'``, the drift/deprecation case) we track, over the
ordered stream ``x_1..x_t`` (this is the standard downward Page-Hinkley form):

    running mean      x̄_t = mean(x_1..x_t)                 (updated incrementally)
    cumulative sum    m_t  = Σ_{i≤t} ( x_i − x̄_i + delta )  (``+delta`` slack bias)
    running maximum   M_t  = max_{i≤t} m_t
    PH statistic      PH_t = M_t − m_t                       (drop below the peak)

    flag a change  ⇔  PH_t > lambda_

Intuition: while the stream is stationary, ``x_i − x̄_i`` is mean-zero, the
``+ delta`` bias makes ``m_t`` *drift upward*, ``M_t`` tracks that upward drift,
and ``PH_t = M_t − m_t`` stays ~0 — **no false reset on a noisy-but-stationary
stream** (the key correctness property). When the mean *drops*, ``x_i − x̄_i``
turns persistently negative, ``m_t`` falls away from the peak ``M_t`` last
reached, ``PH_t`` climbs past ``lambda_``, and we flag. ``delta`` is the slack
(it must exceed the per-step noise amplitude, so for a Bernoulli quality stream
it is a meaningful fraction, not a tiny epsilon — see the defaults note below);
``lambda_`` is the accumulated-evidence threshold (larger ⇒ later but surer).
For ``direction='up'`` the sign is mirrored — a CUSUM ``m_t = Σ (x_i − x̄_i −
delta)`` tracked against a running *minimum*, flagging when ``m_t − min`` exceeds
``lambda_``; ``'both'`` runs the two one-sided detectors in parallel and flags on
either.

**Defaults for a Bernoulli quality stream (why not a tiny ``delta``).** The
quality observations here are ``q ∈ {0, 1}`` (DESIGN §1.3): a *single* failure
swings the instantaneous value by the full unit, so the per-step noise amplitude
is large and ``delta`` must dominate it or a stationary high-quality cell would
false-trigger on every ``0``. Empirically (sweeping stationary streams at p ∈
{0.2, 0.5, 0.9} vs. a 0.9→0.5 drop), ``delta = 0.15`` with ``lambda_ = 4.0``
gives a ~0 stationary false-reset rate (worst case ≈0.08 at the maximum-variance
p=0.5) while detecting a genuine ~0.4-magnitude regime drop ≳99% of the time
within ~10–20 observations of the true shift. These are the module defaults;
callers with a *continuous* (graded-eval) quality stream of lower per-step
variance can pass a smaller ``delta``.

**Reset behaviour.** On a flag the detector **resets** its accumulators (``m``,
``M``, the running mean, the sample count) so a *second*, later shift in the same
stream is detected independently rather than being masked by the first — i.e.
each returned index opens a fresh regime. :func:`detect_changepoints` records the
index at each flag and continues; :class:`PageHinkley` exposes the same machine
incrementally for streaming callers, so the batch and streaming results coincide
by construction (the batch function simply feeds the stream through one
:class:`PageHinkley`).

Re-weighting — :func:`recency_weights`
--------------------------------------
Given the detected change-points, :func:`recency_weights` produces one weight per
observation (aligned oldest→newest) that the store multiplies into each
observation during ``rebuild`` (the integration seam below). Everything *before
the most recent* change-point is down-weighted (exponentially by how far before
the shift it lies, ``decay**k``, vanishing for stale evidence — or a hard ``0.0``
cut when ``decay == 1``) so the posterior is dominated by the post-shift regime
and re-learns it; observations *at or after* the last change-point keep weight
``1.0`` (flat, so the regime we want to learn is never internally discounted).
With **no** change-point the weights are all ``1.0`` (or, if ``decay < 1`` is
requested, a pure uniform age-decay applied to the whole stream — documented per
argument on the function).

Integration seam (hook-spec; this module edits nothing itself)
--------------------------------------------------------------
- ``config``: a flag ``changepoint: bool = False`` on ``AdvisorConfig.hp``.
- ``store``: when ``cfg.hp.changepoint`` is True, ``CellStore.rebuild`` replays a
  cell's ordered ``quality`` records, calls :func:`detect_changepoints` on their
  ``q`` stream, then multiplies each observation's Beta-update weight ``w`` by the
  matching :func:`recency_weights` entry, so post-drift evidence dominates ``mu``.
- ``cli``: ``advisor drift [--agent A] [--shape S]`` reports the detected shifts
  per cell (the indices + the pre/post means around each).

Stdlib-only (``math``, ``statistics``); pure functions plus one small stateful
``@dataclass`` detector; deterministic (no randomness of its own — any noise in
the *tests* is seeded). DESIGN §5 supplies the ordered ``ts``-stamped quality
stream this consumes; DESIGN §7.3 lists this as the deferred feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Accepted ``direction`` values for the one-sided / two-sided detector.
_DIRECTIONS = ("down", "up", "both")


# --------------------------------------------------------------------------- #
# Streaming detector (the Page-Hinkley machine, DESIGN §7.3)                    #
# --------------------------------------------------------------------------- #


@dataclass
class PageHinkley:
    """A small stateful streaming Page-Hinkley change detector (DESIGN §7.3).

    Feed observations one at a time with :meth:`update`; it returns ``True`` on
    the step at which a *sustained* shift (per ``direction``) crosses the
    ``lambda_`` threshold, and **resets** itself on that step so the next shift in
    the same stream is detected independently. :meth:`reset` clears it manually.

    The accumulators realise the cumulative statistic documented in the module
    docstring. For ``direction='down'`` we accumulate the *downward* excess of
    each observation below the running mean (minus the ``delta`` slack) and flag
    when the running maximum exceeds the current cumulative sum by more than
    ``lambda_``; ``'up'`` mirrors the sign; ``'both'`` keeps both one-sided
    accumulators and flags on either.

    Parameters
    ----------
    delta:
        Magnitude tolerance — slack subtracted from each deviation so ordinary
        noise does not accumulate (≈ half the smallest shift worth flagging).
    lambda_:
        Detection threshold on the Page-Hinkley statistic (larger ⇒ later but
        surer; fewer false positives).
    direction:
        ``'down'`` flags drops (the drift/deprecation case — the default),
        ``'up'`` flags rises, ``'both'`` flags either.

    Notes
    -----
    Pure/​deterministic: state evolves only via :meth:`update`; there is no I/O,
    no global state, and no randomness. Construct one per stream (or call
    :meth:`reset` between streams).
    """

    delta: float = 0.15
    lambda_: float = 4.0
    direction: str = "down"

    # --- running state (reset on construction / flag / .reset()) ---------- #
    n: int = field(default=0, init=False)  # observations since last reset
    _mean: float = field(default=0.0, init=False)  # incremental running mean
    # Down-watcher: cumulative sum (``+delta`` biased) + its running maximum;
    # flags when the sum falls ``lambda_`` below the peak (a sustained drop).
    _m_down: float = field(default=0.0, init=False)
    _M_down: float = field(default=0.0, init=False)
    # Up-watcher: cumulative sum (``-delta`` biased) + its running minimum;
    # flags when the sum rises ``lambda_`` above the trough (a sustained rise).
    _m_up: float = field(default=0.0, init=False)
    _m_up_min: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.direction not in _DIRECTIONS:
            raise ValueError(
                f"direction must be one of {_DIRECTIONS!r}, got {self.direction!r}"
            )
        if self.delta < 0.0:
            raise ValueError(f"delta must be >= 0, got {self.delta!r}")
        if self.lambda_ <= 0.0:
            raise ValueError(f"lambda_ must be > 0, got {self.lambda_!r}")

    def reset(self) -> None:
        """Clear all accumulators (start a fresh regime)."""
        self.n = 0
        self._mean = 0.0
        self._m_down = 0.0
        self._M_down = 0.0
        self._m_up = 0.0
        self._m_up_min = 0.0

    def update(self, x: float) -> bool:
        """Consume one observation; return ``True`` iff a change is flagged now.

        Updates the running mean incrementally (Welford, mean only, **including**
        ``x`` — the standard Page-Hinkley convention), accumulates the one-sided
        cumulative sum(s) for the configured ``direction`` against their running
        extremum, and — when the gap to that extremum exceeds ``lambda_`` — flags
        the change and :meth:`reset`\\ s so the next shift is detected from a
        clean slate (DESIGN §7.3 reset rule).
        """
        xf = float(x)
        # Incremental running mean including x.
        self.n += 1
        self._mean += (xf - self._mean) / self.n
        dev = xf - self._mean  # deviation from the (current) running mean

        flagged = False

        if self.direction in ("down", "both"):
            # Downward CUSUM: m drifts up by +delta on stationary noise; a drop in
            # the mean makes `dev` persistently negative so m falls away from its
            # running max M. Flag when m sits more than lambda_ below the peak.
            self._m_down += dev + self.delta
            if self._m_down > self._M_down:
                self._M_down = self._m_down
            if (self._M_down - self._m_down) > self.lambda_:
                flagged = True

        if not flagged and self.direction in ("up", "both"):
            # Upward CUSUM (mirror): m drifts down by -delta on stationary noise; a
            # rise makes `dev` persistently positive so m climbs above its running
            # min. Flag when m sits more than lambda_ above the trough.
            self._m_up += dev - self.delta
            if self._m_up < self._m_up_min:
                self._m_up_min = self._m_up
            if (self._m_up - self._m_up_min) > self.lambda_:
                flagged = True

        if flagged:
            self.reset()
        return flagged


# --------------------------------------------------------------------------- #
# Batch detection over an ordered quality stream (DESIGN §5 + §7.3)             #
# --------------------------------------------------------------------------- #


def detect_changepoints(
    observations: list[float],
    *,
    delta: float = 0.15,
    lambda_: float = 4.0,
    direction: str = "down",
) -> list[int]:
    """Page-Hinkley change-points over an ordered quality stream (DESIGN §7.3).

    Runs the streaming :class:`PageHinkley` detector across ``observations``
    (a list of floats in ``[0, 1]``, **oldest→newest** — the cell's time-ordered
    ``q`` stream, DESIGN §5) and returns the **indices at which a sustained shift
    is flagged**. Because the detector resets on each flag (see its docstring),
    multiple successive regime changes are each reported once, in order.

    This is exactly the streaming machine fed a whole list, so a caller using
    :class:`PageHinkley` incrementally observes the *same* flag indices — the
    batch and streaming APIs coincide by construction.

    Parameters
    ----------
    observations:
        Ordered quality observations (oldest→newest), each in ``[0, 1]``.
    delta:
        Magnitude tolerance (slack), which must exceed the per-step noise
        amplitude. Default ``0.15`` is tuned for a Bernoulli ``{0,1}`` quality
        stream (a single failure swings the value by a full unit; a tiny epsilon
        would false-trigger every ``0``). Pass smaller for a low-variance
        continuous quality stream.
    lambda_:
        Detection threshold on the cumulative statistic (accumulated, slack-
        adjusted drop). Default ``4.0`` gives a ~0 stationary false-reset rate
        while catching a real ~0.4-magnitude regime shift within ~10–20
        observations; larger ⇒ later but surer.
    direction:
        ``'down'`` (default) watches for DROPS — the drift / silent-deprecation
        case; ``'up'`` for rises; ``'both'`` for either.

    Returns
    -------
    A list of integer indices into ``observations`` at which a change was flagged
    (empty if the stream is stationary within tolerance — *no false reset*).

    Notes
    -----
    Fewer than two observations can never produce a flag (there is no "past" to
    deviate from), so a short or empty stream returns ``[]``.
    """
    ph = PageHinkley(delta=delta, lambda_=lambda_, direction=direction)
    out: list[int] = []
    for i, x in enumerate(observations):
        if ph.update(float(x)):
            out.append(i)
    return out


# --------------------------------------------------------------------------- #
# Recency re-weighting from the detected change-points (DESIGN §7.3)            #
# --------------------------------------------------------------------------- #


def recency_weights(
    n: int,
    changepoints: list[int],
    *,
    decay: float = 0.9,
    post_change_boost: bool = True,
) -> list[float]:
    """Per-observation weights that DOWN-WEIGHT pre-change evidence (DESIGN §7.3).

    Produces a length-``n`` weight vector aligned **oldest→newest** that the store
    multiplies into each observation's Beta-update weight during ``rebuild`` so the
    posterior re-learns the current regime after an upstream shift. Every weight
    lies in ``[0, 1]``.

    The two concerns are kept cleanly separate so the post-shift regime is never
    accidentally gutted:

    1. **Regime reset (the primary job).** The most recent change-point ``c* =
       max(changepoints)`` partitions the stream. When ``post_change_boost`` is
       True (the default):

       - **post-shift** observations (indices ``i >= c*``) keep weight ``1.0`` —
         full strength, *flat*. This is the regime we want the posterior to
         reflect, so it is **never** internally discounted (the "≈1 after"
         contract); and
       - **pre-shift** observations (indices ``i < c*``) are forgotten
         exponentially with how far *before* the shift they lie:
         ``weight = decay ** (c* - i)``. An observation ``k`` steps before the
         change-point keeps ``decay ** k`` of its weight, so stale pre-drift
         evidence vanishes smoothly. With ``decay == 1.0`` the exponential cannot
         shrink, so this degenerates to a **hard cut**: pre-shift ⇒ ``0.0``,
         post-shift ⇒ ``1.0`` (a clean regime boundary). ``decay`` thus spans
         *soft* exponential forgetting (``< 1``) to a *hard* cut (``== 1``).

    2. **No reset to do (no change-points).** With ``post_change_boost`` True (the
       default) and no change-point detected, **every weight is ``1.0``** — the
       feature is *inert on a stationary cell*: a healthy cell with no drift keeps
       all its evidence at full strength (the "no-change ⇒ all 1.0" contract, and
       the conservative default — we never silently discount a cell that hasn't
       shifted). ``decay`` here governs *only* the pre-shift falloff of rule 1; it
       does **not** tilt a stationary stream.

    3. **Age-decay only (opt-in), via ``post_change_boost=False``.** This disables
       the regime reset and instead applies a **pure uniform age-decay** to the
       whole stream: ``weight = decay ** (last - i)`` with ``last = n - 1`` (older
       ⇒ smaller; the newest observation is exactly ``1.0``; ``decay == 1`` ⇒ all
       ``1.0``). Nothing is ever zeroed out. Use this when a caller wants a gentle
       recency tilt *without* the hard change-point forgetting (e.g. to compare
       the two weighting policies).

    Parameters
    ----------
    n:
        Length of the observation stream (the returned vector's length).
    changepoints:
        Indices returned by :func:`detect_changepoints` (only the maximum — the
        most recent shift — drives the split; earlier ones are subsumed by it).
    decay:
        Per-step decay factor in ``(0, 1]`` (older ⇒ smaller). Shapes the
        pre-shift falloff (rule 1) or the opt-in stream-wide age-decay (rule 3).
        ``1.0`` ⇒ a hard regime cut / the identity, per the rules above.
    post_change_boost:
        When True (default) reset around the most recent change-point so the
        posterior re-learns the new regime (and, with no change-point, leave every
        weight at ``1.0``); when False, skip the reset and apply only the uniform
        age-decay (rule 3), never zeroing out the past.

    Returns
    -------
    A list of ``n`` weights, each in ``[0, 1]``, aligned oldest→newest.
    """
    if not (0.0 < decay <= 1.0):
        raise ValueError(f"decay must be in (0, 1], got {decay!r}")
    if n <= 0:
        return []

    last = n - 1
    valid_cps = [c for c in changepoints if 0 <= c < n]

    # --- rule 3: age-decay-only mode (reset explicitly disabled) ------------ #
    # Pure uniform age-decay over the whole stream (newest == 1.0); never zeroes
    # anything out. ``decay == 1`` collapses this to the identity (all 1.0).
    if not post_change_boost:
        if decay >= 1.0:
            return [1.0] * n
        return [decay ** (last - i) for i in range(n)]

    # --- rule 2: reset requested but no change-point -> inert (all 1.0) ------ #
    # A healthy, un-shifted cell keeps every observation at full strength; decay
    # governs only the pre-shift falloff of rule 1, not a stationary stream.
    if not valid_cps:
        return [1.0] * n

    # --- rule 1: reset around the most recent change-point ------------------ #
    # Post-shift kept flat at 1.0 (the regime to re-learn); pre-shift forgotten
    # exponentially by distance before the shift. ``decay == 1`` can't shrink via
    # the exponential, so it degenerates to a hard 0.0 cut at the boundary.
    c_star = max(valid_cps)
    if decay >= 1.0:
        return [1.0 if i >= c_star else 0.0 for i in range(n)]
    return [1.0 if i >= c_star else decay ** (c_star - i) for i in range(n)]
