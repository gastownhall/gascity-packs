"""Genuine hierarchical Beta-Binomial partial pooling via empirical Bayes.

DESIGN §1.3 ships a *closed-form pooled-pseudocount approximation*
(:meth:`modeladvisor.store.CellStore.pooled`): sibling Beta pseudocounts are
inverse-stderr-weighted and the injected mass is hard-capped at
``pool_lambda × own_mass`` so pooling never dominates. That cap is a blunt
instrument — it shrinks every cell by the *same* fraction regardless of how much
own-cell evidence exists. DESIGN §7.3 lists **full hierarchical Bayesian
inference** as the deferred upgrade; this module delivers it without leaving the
standard library.

The model is the textbook two-level Beta-Binomial (Gelman, *BDA3* §5.3): the
sibling group shares a latent ``Beta(alpha0, beta0)`` *hyperprior* over per-cell
success probabilities ``theta_i``, and each cell's own ``Beta(a_i, b_i)``
likelihood pulls its posterior toward its own data. We fit the hyperprior by
**empirical Bayes** — estimate ``(alpha0, beta0)`` from the group itself
(:func:`estimate_hyperprior`) — then form each cell's pooled posterior as
``(a_own + alpha0, b_own + beta0)`` (:func:`eb_pooled`). This is genuine
hierarchical shrinkage, not a capped approximation:

- a **thin** cell (small ``a+b``) is dominated by the ``(alpha0, beta0)``
  pseudocounts and shrinks hard toward the group mean;
- a **rich** cell (large ``a+b``) barely moves — the hyperprior is a rounding
  error against its own mass;
- as own ``n → ∞`` the pooled mean ``→`` the own-cell mean (the hyperprior
  washes out), exactly the asymptotics the gate/CI want.

This is the property the closed-form cap *cannot* express: the amount of
shrinkage is a continuous function of own-cell evidence, set by the data, with no
single global fraction.

The core is stdlib-only (``math``, ``statistics``). An **optional** full-MCMC
backend (:func:`pymc_pooled`) is import-guarded behind the ``model-advisor[bayes]``
extra and is never imported by the core; absent PyMC it raises a clear error.

Integration (hook-spec; the integrator wires this, this module edits nothing):
:meth:`store.pooled` dispatches to :func:`eb_pooled` when
``cfg.pooling == 'empirical-bayes'`` (config flag ``pooling:
closed-form|empirical-bayes``, default ``closed-form``). Every function here
takes its tunables as parameters with sensible defaults, so the module imports
and unit-tests standalone against the code as it is today.
"""

from __future__ import annotations

import statistics
from typing import Iterable, Mapping

from modeladvisor.store import Cell, CellStore, cell_key

# A weak, uninformative fallback hyperprior — the uniform ``Beta(1, 1)``. Used
# when a sibling group is too small/degenerate to estimate a shared prior from
# (0 or 1 cells, or zero total evidence). It injects ~1 pseudo-observation per
# side: enough to be proper, too little to bias a cell with real data.
_WEAK_PRIOR: tuple[float, float] = (1.0, 1.0)

# Numerical guards. Means are clamped off the {0, 1} boundary so a degenerate
# all-success / all-failure group still yields a proper (finite) Beta.
_EPS = 1e-9
_MEAN_LO = 1e-6
_MEAN_HI = 1.0 - 1e-6

# Cap on the fitted hyperprior concentration ``alpha0 + beta0``. With a
# near-zero between-cell variance the method-of-moments concentration diverges
# (``M = mean(1-mean)/var - 1 → ∞``); we clamp it so an *almost*-identical group
# does not inject an unbounded pseudocount mass. A group this concentrated is
# genuinely informative, but the gate should still be able to learn away from it.
_MAX_CONCENTRATION: float = 1.0e4


def _cell_iter(cells: Iterable[Cell] | Mapping[object, Cell]) -> list[Cell]:
    """Normalise an iterable *or* mapping of sibling cells to a list of ``Cell``."""
    if isinstance(cells, Mapping):
        return list(cells.values())
    return list(cells)


def estimate_hyperprior(
    cells: Iterable[Cell] | Mapping[object, Cell],
    *,
    max_concentration: float = _MAX_CONCENTRATION,
    weak_prior: tuple[float, float] = _WEAK_PRIOR,
) -> tuple[float, float]:
    """Estimate the shared ``Beta(alpha0, beta0)`` hyperprior for a sibling group.

    **Estimator — method of moments on the per-cell observed means** (Gelman,
    *BDA3* §5.3; the standard empirical-Bayes fit for a Beta-Binomial). For each
    sibling cell take its observed mean ``p_i = a_i / (a_i + b_i)`` and match the
    first two moments of those means to a ``Beta(alpha0, beta0)``:

    ::

        m = mean_i(p_i)                      # grand mean  -> E[theta]
        v = var_i(p_i)                       # between-cell variance -> Var[theta]
        M = m * (1 - m) / v  -  1            # implied Beta concentration alpha0+beta0
        alpha0 = m * M ,   beta0 = (1 - m) * M

    Moment-matching (rather than the EM fixed point of the Beta-Binomial marginal
    likelihood) is chosen deliberately: it is closed-form, allocation-free,
    deterministic, and has no convergence/seed surface — all properties the pure,
    seedable ``recommend`` contract (DESIGN §5 implementation notes) prizes. It is
    the same estimator the paper's offline simulations used for the shared prior.

    **Degenerate handling** (documented, returns a *proper* prior in every case):

    - **0 cells** → ``weak_prior`` (default uniform ``Beta(1, 1)``): nothing to
      pool from, so inject a vanishing, unbiased prior.
    - **1 cell**, or every cell empty (``a + b == 0``) → a weak prior *anchored at
      the available grand mean* with unit total mass (``Beta(m, 1 - m)``): we know
      roughly where the group sits but have no between-cell signal to set a
      concentration, so we stay maximally humble.
    - **All-same means** (``v == 0``) → the concentration diverges; clamp it to
      ``max_concentration``. The fit still tracks the (very tight) group mean.
    - **Over-dispersed group** (``v ≥ m(1 - m)``, i.e. more spread than *any* Beta
      can express, ``M ≤ 0``) → fall back to a weak prior anchored at the grand
      mean: the data refute a shared Beta, so we do not invent a concentration.

    The grand mean is clamped to ``(1e-6, 1 - 1e-6)`` so an all-success or
    all-failure group still yields finite, positive ``(alpha0, beta0)``.

    Returns ``(alpha0, beta0)`` with ``alpha0, beta0 > 0`` (a proper Beta).
    Deterministic and side-effect-free.
    """
    cell_list = _cell_iter(cells)

    # Per-cell observed means, over cells that carry any evidence at all.
    means = [c.mean for c in cell_list if (c.a + c.b) > _EPS]

    if not means:
        # 0 cells, or every cell has zero mass: nothing to estimate.
        return weak_prior

    m = statistics.mean(means)
    m = min(max(m, _MEAN_LO), _MEAN_HI)

    if len(means) < 2:
        # A single (effective) sibling: we have a location but no dispersion
        # signal. Anchor a unit-mass weak prior at it (mean m, concentration 1).
        return m, 1.0 - m

    # Sample (n-1) variance of the per-cell means.
    v = statistics.variance(means)

    spread_ceiling = m * (1.0 - m)
    if v <= _EPS:
        # All-same means: Beta concentration diverges; clamp it. The fitted prior
        # still sits at the (very tight) group mean.
        conc = max_concentration
    elif v >= spread_ceiling:
        # More between-cell spread than any Beta supports (M would be <= 0): the
        # group refutes a shared Beta. Stay humble — weak prior at the grand mean.
        return m, 1.0 - m
    else:
        conc = spread_ceiling / v - 1.0
        conc = min(conc, max_concentration)

    conc = max(conc, _EPS)
    alpha0 = m * conc
    beta0 = (1.0 - m) * conc
    return alpha0, beta0


def eb_pooled(
    store: CellStore,
    provider: str,
    agent: str,
    shape: str,
    tier_id: str,
    *,
    max_prior_mass: float | None = None,
) -> Cell:
    """Empirical-Bayes pooled cell — a drop-in for :meth:`CellStore.pooled`.

    Gathers the cell's sibling group (the *same* grouping the closed-form pooler
    uses — :meth:`CellStore._sibling_keys` plus the own cell), fits the shared
    ``Beta(alpha0, beta0)`` hyperprior over the group via
    :func:`estimate_hyperprior`, then shrinks the own cell toward it by **adding
    the hyperprior pseudocounts to the own observed counts**:

    ::

        (a~, b~) = (a_own + alpha0,  b_own + beta0)

    This is the exact posterior of the two-level Beta-Binomial under the
    empirical-Bayes plug-in (DESIGN §1.3 / §7.3). The shrinkage is automatic and
    evidence-weighted: a thin cell is swamped by ``(alpha0, beta0)`` and pulled to
    the group mean; a rich cell barely moves; as own ``n → ∞`` the pooled mean
    converges to the own-cell mean. Unlike :meth:`CellStore.pooled` there is no
    fixed ``pool_lambda`` cap — the *data* (via own-cell mass) decide how much
    pooling happens.

    ``max_prior_mass`` is an **optional** safety cap on the injected pseudocount
    mass ``alpha0 + beta0``. ``None`` (the default) means *genuine, uncapped EB*:
    let the fitted hyperprior speak in full. If set, the hyperprior is rescaled
    *down* to that total mass when it exceeds it, preserving the group mean
    ``alpha0 / (alpha0 + beta0)`` — useful when an operator wants the closed-form
    pooler's "own evidence stays dominant" guarantee back (e.g.
    ``max_prior_mass = pool_lambda × own_mass``).

    The returned ``Cell`` carries the own cell's ``n`` and ``last_update`` (the
    pooling overlay does not invent observations). Deterministic; no I/O.
    """
    own = store.get(cell_key(provider, agent, shape, tier_id))

    # The sibling group is the own cell plus its DESIGN §1.3 siblings (same tier:
    # same agent / other shapes, and same tolerance class / other agents). We
    # include the own cell so a lone-but-rich cell still anchors its own prior.
    sib_keys = store._sibling_keys(provider, agent, shape, tier_id)
    group: list[Cell] = [own] + [store.get(sk) for sk in sib_keys]

    alpha0, beta0 = estimate_hyperprior(group)

    if max_prior_mass is not None:
        mass = alpha0 + beta0
        if mass > max_prior_mass and mass > _EPS:
            scale = max_prior_mass / mass
            alpha0 *= scale
            beta0 *= scale

    return Cell(
        a=own.a + alpha0,
        b=own.b + beta0,
        n=own.n,
        last_update=own.last_update,
    )


def pymc_pooled(
    store: CellStore,
    provider: str,
    agent: str,
    shape: str,
    tier_id: str,
    *,
    draws: int = 2000,
    tune: int = 1000,
    seed: int = 0,
) -> Cell:
    """Full-MCMC hierarchical Beta-Binomial pooling — **optional** PyMC backend.

    This is the heavyweight cousin of :func:`eb_pooled`: instead of the
    empirical-Bayes plug-in it samples the *joint* posterior of the hyperprior
    ``(alpha0, beta0)`` and the per-cell ``theta_i`` with PyMC's NUTS sampler,
    then summarises the own cell's ``theta`` posterior back into an equivalent
    ``Beta(a~, b~)`` by moment-matching. It captures hyperprior uncertainty that
    the EB point-estimate ignores.

    PyMC is **not** a core dependency (DESIGN's stdlib-only rule); it lives behind
    the optional ``model-advisor[bayes]`` extra. This function is import-guarded:
    with PyMC absent it raises a clear :class:`RuntimeError` telling the operator
    how to enable it. The core never imports it; only the graceful-absence path is
    exercised in the test suite.

    ``draws``/``tune``/``seed`` thread through to the sampler so a run is
    reproducible (the DESIGN §5 seedability contract); they are inert when PyMC is
    unavailable.
    """
    try:  # pragma: no cover - exercised only when the optional extra is installed
        import pymc as pm  # type: ignore
    except ImportError as exc:  # pragma: no cover - the tested path is the message
        raise RuntimeError(
            "install model-advisor[bayes] for the PyMC backend "
            "(the stdlib empirical-Bayes pooler eb_pooled is the default)"
        ) from exc

    # pragma: no cover below — only runs with the optional extra present.
    own = store.get(cell_key(provider, agent, shape, tier_id))  # pragma: no cover
    sib_keys = store._sibling_keys(provider, agent, shape, tier_id)  # pragma: no cover
    group = [own] + [store.get(sk) for sk in sib_keys]  # pragma: no cover

    # Integerised observed successes/trials per sibling (Binomial likelihood).
    trials = [max(int(round(c.a + c.b)), 0) for c in group]  # pragma: no cover
    succ = [min(max(int(round(c.a)), 0), t) for c, t in zip(group, trials)]  # pragma: no cover

    with pm.Model():  # pragma: no cover
        # Weakly-informative hyperprior on the Beta(alpha0, beta0) concentration
        # + mean, the standard BDA3 §5.3 parameterisation.
        kappa = pm.HalfNormal("kappa", sigma=50.0)
        phi = pm.Beta("phi", alpha=1.0, beta=1.0)
        alpha0 = phi * kappa
        beta0 = (1.0 - phi) * kappa
        theta = pm.Beta("theta", alpha=alpha0, beta=beta0, shape=len(group))
        pm.Binomial("y", n=trials, p=theta, observed=succ)
        idata = pm.sample(
            draws=draws, tune=tune, chains=2, random_seed=seed,
            progressbar=False, compute_convergence_checks=False,
        )

    post = idata.posterior["theta"].values[:, :, 0].reshape(-1)  # pragma: no cover
    mu = float(post.mean())  # pragma: no cover
    var = float(post.var())  # pragma: no cover
    mu = min(max(mu, _MEAN_LO), _MEAN_HI)  # pragma: no cover
    # Moment-match the own-cell theta posterior back to an equivalent Beta.
    if var <= _EPS:  # pragma: no cover
        conc = _MAX_CONCENTRATION
    else:  # pragma: no cover
        conc = max(mu * (1.0 - mu) / var - 1.0, _EPS)
    return Cell(  # pragma: no cover
        a=mu * conc,
        b=(1.0 - mu) * conc,
        n=own.n,
        last_update=own.last_update,
    )
