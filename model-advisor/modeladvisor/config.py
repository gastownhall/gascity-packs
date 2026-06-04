"""Configuration for the model-advisor (``advisor.toml``).

This module loads and validates the advisor's configuration into a single
immutable :class:`AdvisorConfig`. It is stdlib-only — TOML is parsed with
:mod:`tomllib` (Python 3.11+). Nothing here touches the network.

What the config carries (all driven from ``advisor.toml``, nothing hard-coded in
the decision path):

- **roster** — the user's cost-ordered list of model tiers
  (``[[tier]]`` blocks: ``provider``, ``model``, ``tier_id``, ``rank``,
  ``in_cost``, ``out_cost``). ``rank`` induces the ``≺`` cost order used by the
  gate / loss. The baseline (reference) tier ``tier*`` defaults to the
  highest-``rank`` (most-capable) tier.
- **shapes** — the gc-native task taxonomy
  (``lookup``/``implement``/``judge``/``review``/``patrol``, config-extensible),
  each with a default tolerance class; plus per-agent canonical shape sets.
- **tolerance classes** — ``Critical``/``Strict``/``Moderate``/``Lenient`` with
  ``q_tol`` and the asymmetric-loss multiplier ``M`` (``∞/20/5/1``).
- **hyperparameters** — DESIGN appendix-D defaults (``alpha``, ``z``,
  ``theta_eval``, pooling ``lambda``, ``s_prior``, cold-start means, channel
  weights, representative per-shape token budgets).

A sensible :func:`default_config` is always available so the engine works with
zero config files; :data:`SAMPLE_TOML` is the editable starter the pack ships.
"""

from __future__ import annotations

import math
import os
import tomllib
from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence

# --------------------------------------------------------------------------- #
# Canonical names (the seed taxonomy — config can extend, never relied on raw) #
# --------------------------------------------------------------------------- #

#: The four tolerance classes from DESIGN §1.2, in cost-aggressiveness order.
TOLERANCE_CLASS_NAMES = ("Critical", "Strict", "Moderate", "Lenient")

#: The five seed shapes from DESIGN §2.2 (config-extensible).
SEED_SHAPE_NAMES = ("lookup", "implement", "judge", "review", "patrol")

#: ``M = ∞`` for Critical is encoded as +inf; it is a *hard* never-downgrade rule.
_INF = math.inf


# --------------------------------------------------------------------------- #
# Dataclasses                                                                   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Tier:
    """One configured ``(provider, model)`` run target — a roster tier.

    ``rank`` is the user-asserted cost order (1 = cheapest). It is *not* inferred
    from quality. ``in_cost``/``out_cost`` are the rate-sheet $/MTok used for the
    deterministic ``cost(tier, tok_in, tok_out)`` (DESIGN §2.3).
    """

    tier_id: str
    provider: str
    model: str
    rank: int
    in_cost: float
    out_cost: float
    #: gc agent/session-config target to dispatch to (opaque to the advisor).
    run_target: str = ""

    def cost(self, tok_in: float, tok_out: float) -> float:
        """Deterministic dollar cost for a dispatch of this size (DESIGN §2.3)."""
        return tok_in / 1e6 * self.in_cost + tok_out / 1e6 * self.out_cost


@dataclass(frozen=True)
class ToleranceClass:
    """A quality-loss tolerance class (DESIGN §1.2).

    ``q_tol`` is the max allowable absolute quality drop vs the baseline tier.
    ``multiplier`` (``M``) scales the asymmetric cascade loss; ``Critical`` uses
    ``+inf`` which is the *hard* never-downgrade contract (not a tunable).
    """

    name: str
    q_tol: float
    multiplier: float  # M; +inf for Critical

    @property
    def is_critical(self) -> bool:
        return math.isinf(self.multiplier) or self.name == "Critical"


@dataclass(frozen=True)
class Shape:
    """A cognitive task kind (DESIGN §2.2) with its default tolerance class."""

    name: str
    default_tol_class: str  # name of a ToleranceClass


@dataclass(frozen=True)
class Hyperparams:
    """CC-TS hyperparameters (DESIGN appendix D / §3). All config-overridable."""

    # --- gate / CI ---
    alpha: float = 0.05  # one-sided confidence level (1 - alpha = 0.95)
    z: float = 1.645  # z_{1-alpha}; matched to alpha=0.05 one-sided
    theta_eval: float = 0.10  # CI half-width that triggers the (deferred) eval flag

    # --- pooling (DESIGN §1.3 hierarchical partial pooling) ---
    pool_lambda: float = 0.5  # global cap on pseudocount pooling weight

    # --- cold-start prior (DESIGN §3.2) ---
    s_prior: float = 4.0  # total pseudocount for cheaper tiers (weak)
    baseline_a: float = 8.0  # optimistic baseline prior Beta(8, 2) -> mean 0.8
    baseline_b: float = 2.0
    cold_m_lo: float = 0.5  # cheapest-tier prior mean floor
    # cold_m_hi defaults to the baseline mean (baseline_a / (a+b)); see resolved value.

    # --- quality channel weights (DESIGN §4.4) ---
    w_close: float = 1.0
    w_review: float = 3.0
    w_eval: float = 5.0

    # --- representative token budget when realised counts are absent (§5.4) ---
    rep_tok_in: float = 1200.0
    rep_tok_out: float = 400.0

    # --- v3 deferred-feature toggles (DESIGN §7.3; all default to v1 behaviour) ---
    #: Accept a continuous quality signal ``q ∈ [0, 1]`` (reviewer score / test-pass
    #: fraction) instead of the strict Bernoulli ``{0, 1}`` (``continuous.py``). Off
    #: ⇒ the binary path is byte-identical to v1.
    continuous_quality: bool = False
    #: Decision mode: ``"lcb"`` (the v1 deterministic LCB rule) or ``"thompson"``
    #: (genuine seeded Thompson sampling — ``thompson.py``). Off ⇒ v1 byte-identical.
    mode: str = "lcb"
    #: Down-weight stale pre-drift evidence via Page-Hinkley change-point detection
    #: in ``rebuild`` (``changepoint.py``). Off ⇒ the straight-fold replay is
    #: unchanged.
    changepoint: bool = False

    @property
    def baseline_mean(self) -> float:
        return self.baseline_a / (self.baseline_a + self.baseline_b)


@dataclass(frozen=True)
class AdvisorConfig:
    """The fully-resolved advisor configuration.

    Constructed by :func:`load_config` / :func:`default_config`; treated as
    immutable by the engine (which is a pure function of ``(config, store)``).
    """

    tiers: tuple[Tier, ...]  # cost-ordered (cheapest -> most-capable)
    shapes: tuple[Shape, ...]
    tol_classes: tuple[ToleranceClass, ...]
    #: agent base-name -> its canonical shape set (DESIGN §2.2). Empty / missing
    #: agent means "all configured shapes are canonical for it."
    agent_shapes: Mapping[str, tuple[str, ...]]
    #: Default provider when a caller doesn't pass one (city default).
    default_provider: str
    #: Token tier_id of the baseline / reference tier ``tier*``.
    baseline_tier_id: str
    #: Per-(agent, shape) tolerance-class overrides: {(agent, shape): class_name}.
    tol_overrides: Mapping[tuple[str, str], str]
    #: Per-(agent, shape) baseline-tier overrides (the static safety hatch host).
    baseline_overrides: Mapping[tuple[str, str], str]
    #: Per-(agent, shape) force_baseline flags (DESIGN §7.4 safety hatch).
    force_baseline: Mapping[tuple[str, str], bool]
    #: Per-shape representative token budgets {shape: (tok_in, tok_out)} (§5.4).
    shape_budgets: Mapping[str, tuple[float, float]]
    hp: Hyperparams = field(default_factory=Hyperparams)

    # ---- v3 deferred-feature backends (DESIGN §7.3; default to v1 behaviour) ---- #
    #: Lower-confidence-bound backend for the gate: ``"wilson"`` (v1 normal LCB on
    #: the Beta) or ``"conformal"`` (distribution-free split-conformal — ``conformal.py``).
    #: Conformal degrades to Wilson on a thin/empty calibration buffer, so this is a
    #: safe drop-in.
    lcb_backend: str = "wilson"
    #: Hierarchical pooling backend: ``"closed-form"`` (v1 capped-pseudocount
    #: :meth:`CellStore.pooled`) or ``"empirical-bayes"`` (genuine EB shrinkage —
    #: ``hierarchical.py``).
    pooling: str = "closed-form"
    #: Federation peers (DESIGN §7.3): paths to peer ``advisor-federation.json``
    #: exports whose observed aggregates are folded into priors. Empty ⇒ no peers,
    #: no behaviour change.
    federation_peers: tuple[str, ...] = ()
    #: Trust weight applied to peer aggregates on merge (``federation.merge_peers``).
    federation_trust: float = 0.3
    #: Optional per-cell cap on injected peer pseudocount mass (``None`` ⇒ uncapped).
    federation_max_peer_mass: float | None = None

    # ---- lookup helpers (used by the store + engine) ------------------------ #

    def tier(self, tier_id: str) -> Tier:
        for t in self.tiers:
            if t.tier_id == tier_id:
                return t
        raise KeyError(f"tier_id {tier_id!r} not in roster")

    def has_tier(self, tier_id: str) -> bool:
        return any(t.tier_id == tier_id for t in self.tiers)

    @property
    def baseline_tier(self) -> Tier:
        return self.tier(self.baseline_tier_id)

    def tol_class(self, name: str) -> ToleranceClass:
        for c in self.tol_classes:
            if c.name == name:
                return c
        raise KeyError(f"tolerance class {name!r} not configured")

    def shape(self, name: str) -> Shape:
        for s in self.shapes:
            if s.name == name:
                return s
        raise KeyError(f"shape {name!r} not in taxonomy")

    def has_shape(self, name: str) -> bool:
        return any(s.name == name for s in self.shapes)

    def baseline_tier_id_for(self, agent: str, shape: str) -> str:
        """Resolve the effective baseline tier for a cell (per-cell override wins)."""
        return self.baseline_overrides.get((agent, shape), self.baseline_tier_id)

    def tol_class_for(self, agent: str, shape: str) -> ToleranceClass:
        """Resolve the effective tolerance class for a cell.

        Precedence: per-(agent, shape) override > shape default.
        """
        name = self.tol_overrides.get((agent, shape))
        if name is None:
            name = self.shape(shape).default_tol_class
        return self.tol_class(name)

    def is_forced_baseline(self, agent: str, shape: str) -> bool:
        return bool(self.force_baseline.get((agent, shape), False))

    def budget_for(self, shape: str) -> tuple[float, float]:
        """Representative (tok_in, tok_out) for a shape (§5.4)."""
        if shape in self.shape_budgets:
            return self.shape_budgets[shape]
        return (self.hp.rep_tok_in, self.hp.rep_tok_out)

    def canonical_shapes_for(self, agent: str) -> tuple[str, ...]:
        """Canonical shape set for an agent, defaulting to all shapes (§2.2)."""
        s = self.agent_shapes.get(agent)
        if s:
            return s
        return tuple(sh.name for sh in self.shapes)

    @property
    def tier_ids(self) -> tuple[str, ...]:
        return tuple(t.tier_id for t in self.tiers)

    def cheaper_than(self, tier_id: str) -> tuple[str, ...]:
        """Tier ids strictly cheaper (lower in the cost order) than ``tier_id``."""
        pivot = self._order_index(tier_id)
        return tuple(t.tier_id for t in self.tiers if self._order_index(t.tier_id) < pivot)

    def _order_index(self, tier_id: str) -> int:
        return self.tier_ids.index(tier_id)

    def with_hyperparams(self, **overrides: object) -> "AdvisorConfig":
        """Return a copy with overridden hyperparameters (handy for tests)."""
        return replace(self, hp=replace(self.hp, **overrides))


# --------------------------------------------------------------------------- #
# Defaults                                                                      #
# --------------------------------------------------------------------------- #

#: Default tolerance classes (DESIGN §1.2 table). q_tol uses the strict upper
#: edge of each class band; M is the documented multiplier.
DEFAULT_TOL_CLASSES: tuple[ToleranceClass, ...] = (
    ToleranceClass("Critical", q_tol=0.0, multiplier=_INF),
    ToleranceClass("Strict", q_tol=0.02, multiplier=20.0),
    ToleranceClass("Moderate", q_tol=0.05, multiplier=5.0),
    ToleranceClass("Lenient", q_tol=0.10, multiplier=1.0),
)

#: Default shape -> tolerance-class mapping (DESIGN §2.2 "Typical tolerance").
DEFAULT_SHAPES: tuple[Shape, ...] = (
    Shape("lookup", "Lenient"),
    Shape("implement", "Moderate"),
    Shape("judge", "Moderate"),
    Shape("review", "Strict"),
    Shape("patrol", "Lenient"),
)

#: Default per-agent canonical shapes (DESIGN §2.2).
DEFAULT_AGENT_SHAPES: dict[str, tuple[str, ...]] = {
    "polecat": ("implement", "lookup"),
    "refinery": ("review", "judge"),
    "witness": ("patrol", "judge"),
    "boot": ("patrol", "judge"),
    "deacon": ("patrol", "judge"),
    "mayor": ("judge", "implement", "lookup"),
}

#: Default Claude roster (illustrative costs, $/MTok). The user edits this.
#: rank 1 = cheapest. Baseline tier* defaults to the highest rank (opus).
DEFAULT_TIERS: tuple[Tier, ...] = (
    Tier(tier_id="haiku", provider="claude", model="claude-haiku-4-5",
         rank=1, in_cost=0.80, out_cost=4.00, run_target="claude-haiku"),
    Tier(tier_id="sonnet", provider="claude", model="claude-sonnet-4-5",
         rank=2, in_cost=3.00, out_cost=15.00, run_target="claude-sonnet"),
    Tier(tier_id="opus", provider="claude", model="claude-opus-4-8",
         rank=3, in_cost=15.00, out_cost=75.00, run_target="claude-opus"),
)


def default_config() -> AdvisorConfig:
    """A complete, sensible default config (Claude haiku/sonnet/opus roster).

    Used when no ``advisor.toml`` is present. Baseline = the most-capable tier.
    """
    return _finalise(
        tiers=list(DEFAULT_TIERS),
        shapes=list(DEFAULT_SHAPES),
        tol_classes=list(DEFAULT_TOL_CLASSES),
        agent_shapes=dict(DEFAULT_AGENT_SHAPES),
        default_provider="claude",
        baseline_tier_id=None,  # -> highest rank
        tol_overrides={},
        baseline_overrides={},
        force_baseline={},
        shape_budgets={},
        hp=Hyperparams(),
    )


# --------------------------------------------------------------------------- #
# Loading / validation                                                          #
# --------------------------------------------------------------------------- #


class ConfigError(ValueError):
    """Raised when ``advisor.toml`` is missing required structure or is invalid."""


def load_config(path: str | os.PathLike[str] | None = None) -> AdvisorConfig:
    """Load ``advisor.toml`` from ``path`` (or return :func:`default_config`).

    If ``path`` is ``None`` or does not exist, the default config is returned so
    the advisor always has a roster to order tiers with. Any *malformed* config
    (e.g. duplicate ranks, an unknown baseline tier, a shape pointing at an
    undefined tolerance class) raises :class:`ConfigError`.
    """
    if path is None:
        return default_config()
    p = os.fspath(path)
    if not os.path.exists(p):
        return default_config()
    with open(p, "rb") as fh:
        raw = tomllib.load(fh)
    return from_mapping(raw)


def from_mapping(raw: Mapping[str, object]) -> AdvisorConfig:
    """Build an :class:`AdvisorConfig` from a parsed-TOML mapping.

    Kept separate from :func:`load_config` so tests can drive it from a dict and
    the CLI can reuse the same validation on an already-parsed document.
    """
    # ---- tolerance classes (fall back to defaults) ----
    tol_classes = _parse_tol_classes(raw.get("tolerance"))
    tol_names = {c.name for c in tol_classes}

    # ---- shapes (fall back to defaults) ----
    shapes = _parse_shapes(raw.get("shape"), tol_names)

    # ---- roster ----
    tiers = _parse_tiers(raw.get("tier"))

    # ---- advisor table (top-level knobs) ----
    adv = raw.get("advisor") or {}
    if not isinstance(adv, Mapping):
        raise ConfigError("[advisor] must be a table")
    default_provider = str(adv.get("default_provider", tiers[0].provider if tiers else "claude"))
    baseline_tier_id = adv.get("baseline_tier")
    baseline_tier_id = str(baseline_tier_id) if baseline_tier_id is not None else None
    # v3 backend selectors (DESIGN §7.3); default to v1 behaviour. Validation that
    # the value names a known backend happens in _finalise.
    lcb_backend = str(adv.get("lcb_backend", "wilson"))
    pooling = str(adv.get("pooling", "closed-form"))

    # ---- federation table (opt-in; default no peers ⇒ no behaviour change) ----
    fed_peers, fed_trust, fed_max_mass = _parse_federation(raw.get("federation"))

    # ---- per-agent canonical shapes + per-cell overrides ----
    agent_shapes, tol_overrides, baseline_overrides, force_baseline = _parse_agents(
        raw.get("agent"), {s.name for s in shapes}, tol_names
    )

    # ---- per-shape representative token budgets ----
    shape_budgets = _parse_shape_budgets(raw.get("shape"))

    # ---- hyperparameters ----
    hp = _parse_hyperparams(raw.get("hyperparams"))

    return _finalise(
        tiers=tiers,
        shapes=shapes,
        tol_classes=tol_classes,
        agent_shapes=agent_shapes,
        default_provider=default_provider,
        baseline_tier_id=baseline_tier_id,
        tol_overrides=tol_overrides,
        baseline_overrides=baseline_overrides,
        force_baseline=force_baseline,
        shape_budgets=shape_budgets,
        hp=hp,
        lcb_backend=lcb_backend,
        pooling=pooling,
        federation_peers=fed_peers,
        federation_trust=fed_trust,
        federation_max_peer_mass=fed_max_mass,
    )


def _parse_federation(value: object) -> tuple[tuple[str, ...], float, float | None]:
    """Parse the optional ``[federation]`` table (DESIGN §7.3 multi-tenant).

    Returns ``(peers, trust, max_peer_mass)``. A missing table ⇒ ``((), 0.3, None)``
    — no peers, so the merge is a no-op and behaviour is unchanged. ``peers`` is an
    array of paths to peer ``advisor-federation.json`` exports; ``trust`` scales
    borrowed mass; ``max_peer_mass`` (optional) caps injected peer pseudocount mass
    per cell.
    """
    if value is None:
        return (), 0.3, None
    if not isinstance(value, Mapping):
        raise ConfigError("[federation] must be a table")
    peers_raw = value.get("peers", ())
    if isinstance(peers_raw, (str, bytes)) or not isinstance(peers_raw, Sequence):
        raise ConfigError("[federation] 'peers' must be an array of paths")
    peers = tuple(str(p) for p in peers_raw)
    trust = float(value.get("trust", 0.3))
    mpm = value.get("max_peer_mass")
    max_peer_mass = None if mpm is None else float(mpm)
    return peers, trust, max_peer_mass


def _finalise(
    *,
    tiers: list[Tier],
    shapes: list[Shape],
    tol_classes: list[ToleranceClass],
    agent_shapes: dict,
    default_provider: str,
    baseline_tier_id: str | None,
    tol_overrides: dict,
    baseline_overrides: dict,
    force_baseline: dict,
    shape_budgets: dict,
    hp: Hyperparams,
    lcb_backend: str = "wilson",
    pooling: str = "closed-form",
    federation_peers: tuple[str, ...] = (),
    federation_trust: float = 0.3,
    federation_max_peer_mass: float | None = None,
) -> AdvisorConfig:
    """Validate cross-references and sort the roster into cost order."""
    if not tiers:
        raise ConfigError("roster is empty: at least one [[tier]] is required to order tiers")
    if not shapes:
        raise ConfigError("shape taxonomy is empty: at least one [[shape]] is required")
    if not tol_classes:
        raise ConfigError("no tolerance classes configured")

    # Unique tier ids.
    ids = [t.tier_id for t in tiers]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ConfigError(f"duplicate tier_id(s): {sorted(dupes)}")

    # Sort cheapest -> most-capable. Total order: rank, then in_cost, then
    # out_cost, then tier_id (deterministic tie-break — DESIGN §2.3).
    ordered = tuple(sorted(tiers, key=lambda t: (t.rank, t.in_cost, t.out_cost, t.tier_id)))

    # Baseline defaults to the most-capable (last in cost order) tier.
    if baseline_tier_id is None:
        baseline_tier_id = ordered[-1].tier_id
    if baseline_tier_id not in {t.tier_id for t in ordered}:
        raise ConfigError(
            f"baseline_tier {baseline_tier_id!r} is not in the roster {sorted(ids)}"
        )

    # Shapes must reference defined tolerance classes.
    tol_names = {c.name for c in tol_classes}
    for s in shapes:
        if s.default_tol_class not in tol_names:
            raise ConfigError(
                f"shape {s.name!r} default tolerance class "
                f"{s.default_tol_class!r} is not defined"
            )

    # Per-cell overrides must reference defined tiers / classes / shapes.
    shape_names = {s.name for s in shapes}
    for (agent, shp), cls in tol_overrides.items():
        if shp not in shape_names:
            raise ConfigError(f"tol override for unknown shape {shp!r} (agent {agent!r})")
        if cls not in tol_names:
            raise ConfigError(f"tol override references unknown class {cls!r}")
    for (agent, shp), tid in baseline_overrides.items():
        if tid not in {t.tier_id for t in ordered}:
            raise ConfigError(f"baseline override references unknown tier {tid!r}")

    # v3 backend selectors must name a known backend (DESIGN §7.3).
    if lcb_backend not in {"wilson", "conformal"}:
        raise ConfigError(
            f"lcb_backend {lcb_backend!r} must be one of {{'wilson', 'conformal'}}"
        )
    if pooling not in {"closed-form", "empirical-bayes"}:
        raise ConfigError(
            f"pooling {pooling!r} must be one of {{'closed-form', 'empirical-bayes'}}"
        )

    return AdvisorConfig(
        tiers=ordered,
        shapes=tuple(shapes),
        tol_classes=tuple(tol_classes),
        agent_shapes={k: tuple(v) for k, v in agent_shapes.items()},
        default_provider=default_provider,
        baseline_tier_id=baseline_tier_id,
        tol_overrides=dict(tol_overrides),
        baseline_overrides=dict(baseline_overrides),
        force_baseline=dict(force_baseline),
        shape_budgets=dict(shape_budgets),
        hp=hp,
        lcb_backend=lcb_backend,
        pooling=pooling,
        federation_peers=tuple(federation_peers),
        federation_trust=float(federation_trust),
        federation_max_peer_mass=(
            None if federation_max_peer_mass is None else float(federation_max_peer_mass)
        ),
    )


# ---- section parsers ------------------------------------------------------- #


def _as_list_of_tables(value: object, section: str) -> list[Mapping[str, object]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConfigError(f"[[{section}]] must be an array of tables")
    out: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ConfigError(f"each [[{section}]] entry must be a table")
        out.append(item)
    return out


def _parse_tiers(value: object) -> list[Tier]:
    rows = _as_list_of_tables(value, "tier")
    if not rows:
        return list(DEFAULT_TIERS)
    tiers: list[Tier] = []
    for i, r in enumerate(rows):
        try:
            tier_id = str(r["id"]) if "id" in r else str(r["tier_id"])
        except KeyError:
            raise ConfigError(f"[[tier]] #{i} missing 'id' (tier_id)")
        if "rank" not in r:
            raise ConfigError(f"[[tier]] {tier_id!r} missing 'rank'")
        tiers.append(
            Tier(
                tier_id=tier_id,
                provider=str(r.get("provider", "claude")),
                model=str(r.get("model", "")),
                rank=int(r["rank"]),
                in_cost=float(r.get("in_cost", 0.0)),
                out_cost=float(r.get("out_cost", 0.0)),
                run_target=str(r.get("run_target", "")),
            )
        )
    return tiers


def _parse_shapes(value: object, tol_names: set[str]) -> list[Shape]:
    rows = _as_list_of_tables(value, "shape")
    if not rows:
        return list(DEFAULT_SHAPES)
    shapes: list[Shape] = []
    seen: set[str] = set()
    for i, r in enumerate(rows):
        if "name" not in r:
            raise ConfigError(f"[[shape]] #{i} missing 'name'")
        name = str(r["name"])
        if name in seen:
            raise ConfigError(f"duplicate shape {name!r}")
        seen.add(name)
        cls = str(r.get("tol_class", r.get("default_tol_class", "Moderate")))
        shapes.append(Shape(name=name, default_tol_class=cls))
    return shapes


def _parse_shape_budgets(value: object) -> dict[str, tuple[float, float]]:
    rows = _as_list_of_tables(value, "shape")
    out: dict[str, tuple[float, float]] = {}
    for r in rows:
        if "name" not in r:
            continue
        if "tok_in" in r or "tok_out" in r:
            out[str(r["name"])] = (float(r.get("tok_in", 0.0)), float(r.get("tok_out", 0.0)))
    return out


def _parse_tol_classes(value: object) -> list[ToleranceClass]:
    rows = _as_list_of_tables(value, "tolerance")
    if not rows:
        return list(DEFAULT_TOL_CLASSES)
    classes: list[ToleranceClass] = []
    for i, r in enumerate(rows):
        if "name" not in r:
            raise ConfigError(f"[[tolerance]] #{i} missing 'name'")
        name = str(r["name"])
        q_tol = float(r.get("q_tol", 0.05))
        m_raw = r.get("multiplier", r.get("M", 5.0))
        if isinstance(m_raw, str) and m_raw.strip().lower() in {"inf", "infinity", "+inf"}:
            multiplier = _INF
        else:
            multiplier = float(m_raw)
        # A q_tol of exactly 0 is Critical by construction.
        if q_tol <= 0.0 and not math.isinf(multiplier):
            multiplier = _INF
        classes.append(ToleranceClass(name=name, q_tol=q_tol, multiplier=multiplier))
    return classes


def _parse_agents(
    value: object, shape_names: set[str], tol_names: set[str]
) -> tuple[dict, dict, dict, dict]:
    rows = _as_list_of_tables(value, "agent")
    agent_shapes: dict[str, tuple[str, ...]] = {}
    tol_overrides: dict[tuple[str, str], str] = {}
    baseline_overrides: dict[tuple[str, str], str] = {}
    force_baseline: dict[tuple[str, str], bool] = {}
    if not rows:
        return dict(DEFAULT_AGENT_SHAPES), tol_overrides, baseline_overrides, force_baseline
    for i, r in enumerate(rows):
        if "name" not in r:
            raise ConfigError(f"[[agent]] #{i} missing 'name'")
        agent = str(r["name"])
        shps = r.get("shapes")
        if shps is not None:
            if not isinstance(shps, Sequence) or isinstance(shps, (str, bytes)):
                raise ConfigError(f"agent {agent!r} 'shapes' must be an array of names")
            agent_shapes[agent] = tuple(str(s) for s in shps)
        # Per-cell overrides live under [[agent.cell]] sub-tables.
        cells = r.get("cell")
        for c in _as_list_of_tables(cells, "agent.cell"):
            if "shape" not in c:
                raise ConfigError(f"agent {agent!r} [[agent.cell]] missing 'shape'")
            shp = str(c["shape"])
            if "tol_class" in c:
                tol_overrides[(agent, shp)] = str(c["tol_class"])
            if "baseline_tier" in c:
                baseline_overrides[(agent, shp)] = str(c["baseline_tier"])
            if "force_baseline" in c:
                force_baseline[(agent, shp)] = bool(c["force_baseline"])
    # If a config declares [[agent]] blocks but none of the defaults, keep the
    # documented role defaults for any agent it didn't mention.
    for a, s in DEFAULT_AGENT_SHAPES.items():
        agent_shapes.setdefault(a, s)
    return agent_shapes, tol_overrides, baseline_overrides, force_baseline


def _as_bool(value: object) -> bool:
    """Coerce a TOML/JSON value to ``bool`` (true/1/yes/on are truthy strings)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def _parse_hyperparams(value: object) -> Hyperparams:
    if value is None:
        return Hyperparams()
    if not isinstance(value, Mapping):
        raise ConfigError("[hyperparams] must be a table")
    base = Hyperparams()
    # Accept any subset of fields; ignore unknowns gracefully but type-coerce known ones.
    fields = {
        "alpha": float, "z": float, "theta_eval": float, "pool_lambda": float,
        "s_prior": float, "baseline_a": float, "baseline_b": float,
        "cold_m_lo": float, "w_close": float, "w_review": float, "w_eval": float,
        "rep_tok_in": float, "rep_tok_out": float,
        # v3 deferred-feature toggles (DESIGN §7.3); default to v1 behaviour.
        "continuous_quality": _as_bool, "mode": str, "changepoint": _as_bool,
    }
    kwargs = {}
    for k, conv in fields.items():
        if k in value:
            kwargs[k] = conv(value[k])
    return replace(base, **kwargs)


# --------------------------------------------------------------------------- #
# Sample advisor.toml (the editable starter the pack ships)                     #
# --------------------------------------------------------------------------- #

SAMPLE_TOML = '''\
# advisor.toml — model-advisor configuration (edit me).
#
# This file defines the cost-ordered model roster, the task-shape taxonomy, the
# quality-loss tolerance classes, and per-agent defaults. Everything the CC-TS
# engine needs to order tiers and gate downgrades lives here. Deleting this file
# falls back to a built-in Claude haiku/sonnet/opus default with the same shape.
#
# Cell key = "<provider>::<agent>::<shape>::<tier_id>".

[advisor]
default_provider = "claude"
# Baseline / reference tier (tier*). All downgrade constraints are relative to
# it. Defaults to the highest-rank (most-capable) tier if omitted.
baseline_tier = "opus"

# --------------------------------------------------------------------------- #
# Roster — the user's cost-ordered model tiers. rank 1 = cheapest.            #
# in_cost / out_cost are $/MTok (illustrative; replace with your rate sheet). #
# --------------------------------------------------------------------------- #
[[tier]]
id         = "haiku"
provider   = "claude"
model      = "claude-haiku-4-5"
run_target = "claude-haiku"
rank       = 1
in_cost    = 0.80
out_cost   = 4.00

[[tier]]
id         = "sonnet"
provider   = "claude"
model      = "claude-sonnet-4-5"
run_target = "claude-sonnet"
rank       = 2
in_cost    = 3.00
out_cost   = 15.00

[[tier]]
id         = "opus"
provider   = "claude"
model      = "claude-opus-4-8"
run_target = "claude-opus"
rank       = 3
in_cost    = 15.00
out_cost   = 75.00

# --------------------------------------------------------------------------- #
# Tolerance classes — max allowable quality drop (q_tol) + asymmetric         #
# multiplier M. Critical is a HARD never-downgrade rule (M = inf).            #
# --------------------------------------------------------------------------- #
[[tolerance]]
name = "Critical"
q_tol = 0.0
multiplier = "inf"

[[tolerance]]
name = "Strict"
q_tol = 0.02
multiplier = 20

[[tolerance]]
name = "Moderate"
q_tol = 0.05
multiplier = 5

[[tolerance]]
name = "Lenient"
q_tol = 0.10
multiplier = 1

# --------------------------------------------------------------------------- #
# Shapes — the gc-native task taxonomy. Each shape has a default tolerance     #
# class and an optional representative token budget (tok_in/tok_out) used for #
# cost differentials when realised token counts are unavailable.             #
# --------------------------------------------------------------------------- #
[[shape]]
name = "lookup"
tol_class = "Lenient"
tok_in = 800
tok_out = 200

[[shape]]
name = "implement"
tol_class = "Moderate"
tok_in = 4000
tok_out = 1500

[[shape]]
name = "judge"
tol_class = "Moderate"
tok_in = 1500
tok_out = 400

[[shape]]
name = "review"
tol_class = "Strict"
tok_in = 3000
tok_out = 800

[[shape]]
name = "patrol"
tol_class = "Lenient"
tok_in = 1000
tok_out = 300

# --------------------------------------------------------------------------- #
# Agents — canonical shape sets + optional per-cell overrides. Cells only      #
# exist for an agent's canonical shapes. Use [[agent.cell]] to pin a stricter #
# tolerance, a lower baseline, or the force_baseline safety hatch.           #
# --------------------------------------------------------------------------- #
[[agent]]
name = "polecat"
shapes = ["implement", "lookup"]

[[agent]]
name = "refinery"
shapes = ["review", "judge"]

  # Refinery release-gating decisions are Critical (never downgrade).
  [[agent.cell]]
  shape = "judge"
  tol_class = "Critical"

[[agent]]
name = "mayor"
shapes = ["judge", "implement", "lookup"]

[[agent]]
name = "witness"
shapes = ["patrol", "judge"]

[[agent]]
name = "boot"
shapes = ["patrol", "judge"]

[[agent]]
name = "deacon"
shapes = ["patrol", "judge"]

# --------------------------------------------------------------------------- #
# Hyperparameters (CC-TS appendix D defaults). All optional.                  #
# --------------------------------------------------------------------------- #
[hyperparams]
alpha       = 0.05   # one-sided confidence (1 - alpha = 0.95)
z           = 1.645  # z_{0.95}, matched to alpha
theta_eval  = 0.10   # CI half-width that flags a cell for an eval probe
pool_lambda = 0.5    # cap on cross-sibling pseudocount pooling
s_prior     = 4.0    # cold-start pseudocount for cheaper tiers (weak)
baseline_a  = 8.0    # optimistic baseline prior Beta(8, 2) -> mean 0.80
baseline_b  = 2.0
cold_m_lo   = 0.5    # cheapest-tier cold-start prior mean
w_close     = 1.0    # quality channel weights (close < review < eval)
w_review    = 3.0
w_eval      = 5.0
'''


def write_sample_toml(path: str | os.PathLike[str], *, overwrite: bool = False) -> str:
    """Write :data:`SAMPLE_TOML` to ``path``. Returns the path written.

    Refuses to clobber an existing file unless ``overwrite=True``.
    """
    p = os.fspath(path)
    if os.path.exists(p) and not overwrite:
        raise FileExistsError(f"{p} exists; pass overwrite=True to replace it")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_TOML)
    return p
