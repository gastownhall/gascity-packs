"""Multi-tenant posterior federation — share per-cell aggregates, not telemetry.

DESIGN §7.3 lists **hierarchical-bandit / multi-tenant federation** as a deferred
upgrade: sharing posteriors across consumer repos to accelerate thin-cell
convergence (paper §7), gated on the privacy/trust questions that deferral flags.
This module delivers it *without leaking raw telemetry* — a consumer exports only
the per-cell **observed aggregates** (the pseudocounts its own dispatches earned),
a peer imports them, and a merge folds peer evidence into the **prior** of each
cell, scaled by a trust weight and capped so a peer can inform a thin cell but
never dominate local evidence.

Why aggregates-only is privacy-safe (DESIGN §5 / §7.3 trust precondition):

- The export carries, per cell, exactly three numbers — ``a_obs`` (observed
  success pseudocount), ``b_obs`` (observed failure pseudocount) and ``n`` (the
  raw count). No timestamps, no ``bead_id``, no rationale text, no raw quality
  rows — nothing from which a single dispatch could be reconstructed.
- ``a_obs``/``b_obs`` are the posterior ``a``/``b`` **minus the exporter's
  cold-start prior** for that cell (:func:`modeladvisor.store.cold_start_prior`).
  Subtracting the prior means (a) no prior is double-counted when a peer re-adds
  the mass onto *its own* prior, and (b) the exporter's prior scheme — itself
  derived from config, not data — never leaks. A cell carrying only prior mass
  exports ``a_obs ≈ b_obs ≈ 0`` and is dropped under ``observed_only``.

The merge is the federation analogue of the closed-form pooler
(:meth:`modeladvisor.store.CellStore.pooled`, DESIGN §1.3): peer pseudocounts are
injected as extra **prior** mass, ``trust``-scaled and optionally hard-capped at
``max_peer_mass`` per cell, while the consumer's *own* observed mass is re-applied
at full weight on top. So a thin local cell (little own mass) is moved materially
by a confident peer, a rich local cell (much own mass) barely moves, and with
``trust = 0`` or no peers the result is byte-identical to the local store. This is
the conservative "peers inform, never override" property the deferral requires.

Integration (hook-spec; the integrator wires this, this module edits nothing):
``advisor federate export [--out FILE] [--rig R]`` calls :func:`export_aggregates`
and writes the JSON; ``advisor federate import PEER... [--trust X]`` calls
:func:`load_peer` per path then :func:`merge_peers`. Config (opt-in, default no
peers ⇒ no behaviour change)::

    federation = { peers = ["../other-rig/.beads/telemetry/advisor-federation.json"], trust = 0.3 }

Every function takes its tunables as parameters with sensible defaults, so the
module imports and unit-tests standalone against the code as it is today.
Stdlib-only (``json``, ``math``).
"""

from __future__ import annotations

import json
import math
import os
from typing import Mapping

from modeladvisor.config import AdvisorConfig
from modeladvisor.store import Cell, CellStore, cold_start_prior, parse_cell_key

#: Schema tag stamped on every export and required on every import. Bumping this
#: is how a future aggregate-shape change is rejected loudly rather than silently
#: mis-merged (the export carries pseudocounts; a wrong shape would corrupt a
#: posterior, so we fail closed).
SCHEMA: str = "advisor.federation.v1"

# Numerical floor: observed pseudocounts within this of zero are treated as pure
# prior (float subtraction of prior from posterior leaves rounding dust). A cell
# at exactly its prior exports a_obs == b_obs == 0; this guards the comparison.
_EPS: float = 1e-9


def _cell_prior(cfg: AdvisorConfig, key: str) -> tuple[float, float]:
    """Cold-start prior ``(a, b)`` for ``key`` under ``cfg`` (DESIGN §3.2).

    Parses the cell key for ``(agent, shape, tier_id)`` and resolves the cell's
    effective baseline tier the same way the store does
    (:meth:`CellStore._prior` via :meth:`AdvisorConfig.baseline_tier_id_for`),
    then defers to :func:`modeladvisor.store.cold_start_prior`. This is the prior
    subtracted on export and re-added on merge, so the two operations are exact
    inverses on the prior component.

    Note: a consumer-supplied confidence ``priors.json`` (DESIGN §3.1) is *not*
    consulted here — federation speaks the config-derived cold-start prior so the
    exchanged aggregates are independent of any one tenant's private prior file.
    """
    _provider, agent, shape, tier_id = parse_cell_key(key)
    baseline = cfg.baseline_tier_id_for(agent, shape)
    return cold_start_prior(cfg, tier_id, baseline)


def export_aggregates(store: CellStore, *, observed_only: bool = True) -> dict:
    """Export per-cell **observed aggregates** for federation (DESIGN §7.3).

    Returns a JSON-serialisable document::

        {"schema": "advisor.federation.v1",
         "cells": {cell_key: {"a_obs": ..., "b_obs": ..., "n": ...}, ...}}

    ``a_obs``/``b_obs`` are the cell's posterior ``a``/``b`` with the exporter's
    cold-start prior **subtracted** (:func:`_cell_prior`), i.e. the pseudocount
    mass the cell's *own dispatches* contributed. A weighted observation of
    ``q = 1`` adds ``w`` to ``a_obs``; of ``q = 0`` adds ``w`` to ``b_obs`` — so
    the aggregates are exactly the channel-weighted Bernoulli evidence (DESIGN
    §1.3 Layer 1), with **no prior baked in** (a peer re-adds them onto its own
    prior) and **no prior leaked**.

    The export deliberately carries *nothing else*: no ``ts``/``last_update``, no
    ``bead_id``, no ``signal``/rationale text, no raw records — only the three
    numbers per cell. This is the privacy contract of DESIGN §7.3: a single
    dispatch can never be reconstructed from an aggregate.

    ``observed_only`` (default ``True``): export only cells with ``n > 0``. A cell
    that carries only prior mass exports ``a_obs ≈ b_obs ≈ 0`` and is dropped.
    With ``observed_only = False`` every materialised cell is emitted (still
    prior-subtracted), which a tester may use to assert the prior cancels.

    Deterministic; keys are emitted in sorted order; no I/O.
    """
    cells: dict[str, dict] = {}
    for key in sorted(store.cells):
        cell = store.cells[key]
        if observed_only and cell.n <= 0:
            continue
        prior_a, prior_b = _cell_prior(store.cfg, key)
        a_obs = cell.a - prior_a
        b_obs = cell.b - prior_b
        # Float subtraction can leave a tiny negative; clamp to zero. (Observed
        # pseudocounts are non-negative by construction: a += w·q, b += w·(1-q).)
        if -_EPS < a_obs < 0.0:
            a_obs = 0.0
        if -_EPS < b_obs < 0.0:
            b_obs = 0.0
        cells[key] = {"a_obs": a_obs, "b_obs": b_obs, "n": int(cell.n)}
    return {"schema": SCHEMA, "cells": cells}


class FederationError(ValueError):
    """Raised when a peer export is missing/garbled or carries a wrong schema.

    Federation fails *closed*: a malformed peer cannot silently corrupt a local
    posterior, so every validation failure raises rather than dropping data.
    """


def load_peer(path_or_obj: str | os.PathLike[str] | Mapping) -> dict:
    """Read + validate a peer export (DESIGN §7.3).

    Accepts either a filesystem path to a JSON document or an already-parsed
    mapping (so the CLI can pass a path and a test can pass a dict). Validates the
    schema tag and the per-cell aggregate shape, returning a normalised
    ``{"schema": ..., "cells": {cell_key: {"a_obs", "b_obs", "n"}}}`` dict with
    numeric fields coerced to ``float``/``int``.

    Raises :class:`FederationError` on: a missing file, non-JSON / non-object
    content, a missing-or-wrong ``schema``, a non-mapping ``cells``, a malformed
    cell key, a missing aggregate field, a non-finite or **negative** pseudocount
    (observed mass cannot be negative), or a negative ``n``. Failing closed keeps
    a corrupt or hostile peer from poisoning the merge.
    """
    if isinstance(path_or_obj, Mapping):
        doc: object = path_or_obj
    elif isinstance(path_or_obj, (str, bytes, os.PathLike)):
        p = os.fspath(path_or_obj)
        if not os.path.exists(p):
            raise FederationError(f"peer export not found: {p!r}")
        try:
            with open(p, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise FederationError(f"peer export {p!r} is not valid JSON: {exc}") from exc
    else:
        raise FederationError(
            f"peer export must be a path or a parsed object, got {type(path_or_obj).__name__}"
        )

    if not isinstance(doc, Mapping):
        raise FederationError("peer export must be a JSON object")
    schema = doc.get("schema")
    if schema != SCHEMA:
        raise FederationError(
            f"peer export has schema {schema!r}, expected {SCHEMA!r}"
        )
    raw_cells = doc.get("cells", {})
    if not isinstance(raw_cells, Mapping):
        raise FederationError("peer export 'cells' must be an object")

    cells: dict[str, dict] = {}
    for key, agg in raw_cells.items():
        try:
            parse_cell_key(str(key))
        except ValueError as exc:
            raise FederationError(f"peer cell key {key!r} is malformed: {exc}") from exc
        if not isinstance(agg, Mapping):
            raise FederationError(f"peer cell {key!r} aggregate must be an object")
        try:
            a_obs = float(agg["a_obs"])
            b_obs = float(agg["b_obs"])
            n = int(agg["n"])
        except KeyError as exc:
            raise FederationError(f"peer cell {key!r} missing field {exc}") from exc
        except (TypeError, ValueError) as exc:
            raise FederationError(f"peer cell {key!r} has a non-numeric field: {exc}") from exc
        if not (math.isfinite(a_obs) and math.isfinite(b_obs)):
            raise FederationError(f"peer cell {key!r} pseudocount is not finite")
        if a_obs < -_EPS or b_obs < -_EPS or n < 0:
            raise FederationError(f"peer cell {key!r} has a negative aggregate")
        cells[str(key)] = {"a_obs": max(a_obs, 0.0), "b_obs": max(b_obs, 0.0), "n": n}

    return {"schema": SCHEMA, "cells": cells}


def merge_peers(
    store: CellStore,
    peers: object,
    *,
    trust: float = 0.3,
    max_peer_mass: float | None = None,
) -> CellStore:
    """Fold peer aggregates into a fresh store as trust-scaled prior mass (§7.3).

    Returns a **new** :class:`CellStore` (the input ``store`` is never mutated),
    built as:

    1. **Cold-start from ``store.cfg``** — same priors the local store began with.
    2. For each cell present in any peer, add the peers' summed
       ``(a_obs, b_obs)`` to that cell's prior, scaled by ``trust`` and (if given)
       hard-capped at ``max_peer_mass`` total injected mass per cell.
    3. **Re-apply the local store's own observed mass at full weight** on top —
       the consumer's own evidence (``a - prior``, ``b - prior`` per observed
       cell) is added undiscounted, so local evidence always outranks borrowed.

    The effect mirrors the closed-form pooler (DESIGN §1.3): peer pseudocounts
    enter as prior, so a **thin** local cell (little own mass) is pulled toward a
    confident peer, while a **rich** local cell (much own mass) barely moves —
    the trust scaling and the own-mass-at-full-weight re-application together cap
    peer influence without a per-cell ratio knob. Properties:

    - ``trust = 0`` ⇒ zero peer contribution ⇒ result equals the local store
      (cold-start + own observed mass), i.e. **no peer influence**.
    - empty ``peers`` (or all peers empty) ⇒ **idempotent**: the rebuilt store has
      the same observed cells as ``store``; local-only cells are untouched by
      absent peers.
    - ``max_peer_mass`` caps the *injected* peer mass per cell, so even a
      huge/hostile peer cannot swamp a thin local cell.

    ``peers`` may be a single peer dict, a path, or an iterable of either; each is
    run through :func:`load_peer` (so callers can pass raw paths). ``trust`` is
    clamped to ``[0, 1]``. Deterministic; the only I/O is reading any peer paths.
    """
    trust = min(max(float(trust), 0.0), 1.0)
    peer_docs = _coerce_peers(peers)

    # Sum peer observed pseudocounts per cell (a peer with more agreement across
    # repos contributes more, before trust-scaling and the cap).
    summed: dict[str, list[float]] = {}
    for doc in peer_docs:
        for key, agg in doc["cells"].items():
            slot = summed.setdefault(key, [0.0, 0.0])
            slot[0] += agg["a_obs"]
            slot[1] += agg["b_obs"]

    merged = CellStore.cold_start(store.cfg, store.priors)

    # 1+2. Seed each peer-touched cell's prior with trust-scaled, capped peer mass.
    if trust > 0.0:
        for key, (pa, pb) in summed.items():
            inj_a = trust * pa
            inj_b = trust * pb
            if max_peer_mass is not None:
                inj_a, inj_b = _cap_mass(inj_a, inj_b, max_peer_mass)
            if inj_a <= 0.0 and inj_b <= 0.0:
                continue
            cell = merged.get(key)  # synthesises the cold-start prior for this cell
            cell.a += inj_a
            cell.b += inj_b

    # 3. Re-apply the local store's own observed mass at full weight on top.
    for key, local in store.observed_cells().items():
        prior_a, prior_b = _cell_prior(store.cfg, key)
        own_a = max(local.a - prior_a, 0.0)
        own_b = max(local.b - prior_b, 0.0)
        cell = merged.get(key)
        cell.a += own_a
        cell.b += own_b
        cell.n += local.n
        # Preserve the local recency stamp (peers carry no timestamps by design).
        if local.last_update is not None:
            cell.last_update = local.last_update

    return merged


def _cap_mass(a: float, b: float, max_mass: float) -> tuple[float, float]:
    """Scale ``(a, b)`` down so ``a + b ≤ max_mass``, preserving the ratio.

    Used to bound the injected peer pseudocount mass per cell so even a very
    confident (or adversarial) peer cannot dominate a thin local cell — the
    federation analogue of the ``pool_lambda`` cap in DESIGN §1.3.
    """
    total = a + b
    if max_mass <= 0.0:
        return 0.0, 0.0
    if total <= max_mass or total <= 0.0:
        return a, b
    scale = max_mass / total
    return a * scale, b * scale


def _coerce_peers(peers: object) -> list[dict]:
    """Normalise ``peers`` to a list of validated peer docs via :func:`load_peer`.

    Accepts a single peer (dict or path) or an iterable of them; ``None`` and the
    empty iterable both yield ``[]`` (the idempotent no-peers case).
    """
    if peers is None:
        return []
    # A single already-validated/parsed peer doc (has the schema tag) or a single
    # path-like: treat as one peer, not an iterable of characters.
    if isinstance(peers, (str, bytes, os.PathLike, Mapping)):
        return [load_peer(peers)]
    out: list[dict] = []
    for p in peers:  # type: ignore[union-attr]
        out.append(load_peer(p))
    return out
