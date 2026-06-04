"""Critical-path-aware (DAG-propagated) effective blast radius (DESIGN §1.3 L3, §7.3).

DESIGN §1.3 Layer 3 scales the asymmetric cascade penalty by ``N_dep`` — the
"number of downstream dependents of the bead (blast radius)". v1
(:func:`modeladvisor.engine.recommend` / :func:`_expected_loss`) treats that as a
**flat scalar**: every dispatch carries the same ``N_dep`` (default ``1``)
regardless of where it sits in the dependency graph. The cascade term in
``_expected_loss`` is literally ``drop * multiplier * delta_cost * N_dep`` with a
single integer ``N_dep``.

DESIGN §7.3 lists **"sequential / critical-path-aware cascade modelling"** as
deferred: the full contextual-MDP treatment of an ADR cascading into N builder
dispatches is out of scope, but the *tractable, faithful core* — propagating the
blast radius through the dependency DAG — is not. This module is that core.

The idea: a bead that blocks 3 ADRs that each block 4 builders has a far larger
*effective* blast radius than a leaf task, because a wrong downgrade on it
poisons everything reachable downstream, not just its immediate children. We
compute that **effective** ``N_dep`` by counting the bead's downstream-reachable
dependents (the transitive closure of "this bead blocks …"), with an optional
depth ``decay`` so nearer dependents can be weighted more heavily than distant
ones:

::

    n_dep_eff = base_n_dep  +  Σ_{d reachable from root}  decay ** depth(d)

where ``depth(root) = 0`` (the root's own dispatch is the ``base_n_dep`` floor —
the §1.3 "default N_dep = 1 when unknown"), and each downstream dependent sits at
``depth ≥ 1``. Consequences:

- a **leaf** (root blocks nothing reachable) ⇒ ``n_dep_eff == base_n_dep`` — the
  flat-scalar behaviour, recovered exactly;
- with ``decay == 1.0`` ⇒ ``base_n_dep + (raw reachable count)`` — every
  downstream dependent counts once, fully;
- with ``decay < 1`` ⇒ nearer dependents dominate (a dependent at depth ``d``
  contributes ``decay ** d``), so a deep tail is discounted;
- a **wider / deeper** reachable set ⇒ strictly larger ``n_dep_eff`` than a
  narrower / shallower one (monotonicity — the property the integrator feeds back
  into the L3 cascade term as ``round(n_dep_eff)``).

Traversal is breadth-first from the root, **cycle-safe** (a ``visited`` set means
each node is counted at most once, at its *shallowest* depth), and capped at
``max_depth`` so a pathological graph cannot blow up the walk. A missing / empty
graph or an unknown root degrades to the flat ``base_n_dep`` (DESIGN §8
"degradation": the advisor must never block a dispatch).

Stdlib-only (``collections``). Pure function of its arguments; no I/O. The
integrator wires the result into ``recommend(..., cascade=...)`` (hook-spec
below); this module edits nothing in the shared files.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass
class CascadeResult:
    """The DAG-propagated effective blast radius for one root bead (DESIGN §1.3 L3).

    ``n_dep_eff``
        The effective ``N_dep`` to feed the §1.3 cascade term — ``base_n_dep``
        plus the ``decay``-weighted count of downstream-reachable dependents. The
        integrator uses ``round(n_dep_eff)`` (min ``1``) as ``n_dep`` in
        ``_expected_loss``.
    ``depth``
        The deepest dependent level actually reached (``0`` for a leaf / degenerate
        root), bounded by ``max_depth``.
    ``n_nodes``
        Total distinct beads visited *including the root* (so a leaf is ``1``).
    ``loss_terms``
        Audit detail: ``{reachable, by_depth: {d: count}}`` — the raw reachable
        dependent count and the per-depth histogram that built ``n_dep_eff``.
    ``rationale``
        One-line human summary of the propagation.
    """

    n_dep_eff: float
    depth: int
    n_nodes: int
    loss_terms: dict = field(default_factory=dict)
    rationale: str = ""


# --------------------------------------------------------------------------- #
# Effective cascade (DESIGN §1.3 Layer 3 — N_dep propagated over the DAG)       #
# --------------------------------------------------------------------------- #


def effective_cascade(
    graph: Mapping[str, Sequence[str]] | None,
    root: str,
    *,
    base_n_dep: float = 1,
    decay: float = 1.0,
    max_depth: int = 6,
) -> CascadeResult:
    """Compute the DAG-propagated effective blast radius ``N_dep`` for ``root``.

    Faithful, tractable core of DESIGN §7.3's deferred "critical-path-aware
    cascade modelling": rather than the flat ``N_dep`` scalar of §1.3 Layer 3, we
    count the dependents *transitively reachable* from ``root`` in the blast-radius
    graph and weight each by its depth.

    Parameters
    ----------
    graph:
        Adjacency map ``{bead_id: [downstream dependent bead_ids]}`` — the beads
        each bead **blocks** (its blast radius), i.e. an edge ``u -> v`` means "u
        blocks v / v depends on u". Built by :func:`build_graph_from_dep_json` from
        ``gc bd dep tree --json``. ``None`` / empty ⇒ degrade to ``base_n_dep``.
    root:
        The dispatched bead whose effective blast radius we want. If absent from
        ``graph`` ⇒ degrade to ``base_n_dep`` (a leaf / unknown bead).
    base_n_dep:
        The root's own-dispatch floor — the §1.3 "default ``N_dep = 1`` when
        unknown". Added to the weighted dependent count so a leaf returns exactly
        ``base_n_dep`` (the flat-scalar behaviour). Default ``1``.
    decay:
        Per-depth weight base in ``(0, 1]``. ``1.0`` (default) ⇒ every reachable
        dependent counts once (raw reachable count); ``< 1`` ⇒ a dependent at
        depth ``d`` contributes ``decay ** d``, so nearer dependents dominate.
        Clamped to ``(0, 1]`` (a value ``≤ 0`` would erase the graph signal; ``> 1``
        would make distant dependents matter *more*, which inverts the intent).
    max_depth:
        Hard cap on traversal depth (``≥ 0``). Dependents deeper than this are not
        visited or counted — a pathological / very deep graph cannot blow up the
        walk. Default ``6``.

    Returns
    -------
    :class:`CascadeResult`. Degenerate inputs (``None`` / empty graph, unknown
    ``root``, ``max_depth < 1``) return
    ``CascadeResult(n_dep_eff=base_n_dep, depth=0, n_nodes=1, …)`` — the flat
    ``N_dep`` fallback (DESIGN §8 degradation: never block a dispatch).

    Notes
    -----
    Breadth-first from ``root`` with a ``visited`` set, so the traversal is
    **cycle-safe** and each node is counted **once**, at its *shallowest* depth
    (BFS reaches a node by a shortest path first). Self-loops and back-edges are
    therefore harmless. Edges pointing at beads not present as graph keys are still
    counted as reachable leaves (they are real dependents with no known children).
    """
    floor = float(base_n_dep)
    # Clamp decay into (0, 1]: <=0 would erase the graph; >1 would up-weight the
    # far tail (inverting "nearer dependents matter more").
    d = float(decay)
    if d <= 0.0:
        d = 1e-9
    elif d > 1.0:
        d = 1.0

    # Degenerate fallbacks -> flat base_n_dep (DESIGN §8). An unknown/leaf root has
    # no outgoing edges to walk; max_depth < 1 means we may not even count children.
    if not graph or root not in graph or max_depth < 1:
        return CascadeResult(
            n_dep_eff=floor,
            depth=0,
            n_nodes=1,
            loss_terms={"reachable": 0, "by_depth": {}},
            rationale=(
                f"leaf/flat: {root!r} has no reachable dependents "
                f"(N_dep_eff={floor:g}, base floor)"
            ),
        )

    # BFS from the root. ``visited`` makes the walk cycle-safe and counts each
    # bead once (at its shallowest depth). The root is visited at depth 0 and is
    # NOT a dependent (it is the dispatch itself -> the base_n_dep floor).
    visited: set[str] = {root}
    queue: deque[tuple[str, int]] = deque([(root, 0)])
    by_depth: dict[int, int] = {}
    weighted = 0.0
    max_reached = 0

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            # Do not expand past the cap; this node's children (depth+1) are pruned.
            continue
        for child in graph.get(node, ()):  # tolerate absent keys -> leaf, no children
            if child in visited:
                continue  # cycle / re-convergence: count once, at shallowest depth
            visited.add(child)
            child_depth = depth + 1
            by_depth[child_depth] = by_depth.get(child_depth, 0) + 1
            weighted += d ** child_depth
            if child_depth > max_reached:
                max_reached = child_depth
            queue.append((child, child_depth))

    reachable = len(visited) - 1  # exclude the root itself
    n_dep_eff = floor + weighted

    if reachable == 0:
        rationale = (
            f"leaf/flat: {root!r} has no reachable dependents "
            f"(N_dep_eff={n_dep_eff:g}, base floor)"
        )
    else:
        decay_note = "raw count" if d >= 1.0 else f"decay={d:g} (nearer dependents weighted up)"
        rationale = (
            f"{root!r} blocks {reachable} reachable dependent(s) over "
            f"{max_reached} level(s) [{decay_note}] -> effective N_dep "
            f"{n_dep_eff:g} (floor {floor:g} + weighted {weighted:g})"
        )

    return CascadeResult(
        n_dep_eff=n_dep_eff,
        depth=max_reached,
        n_nodes=len(visited),
        loss_terms={"reachable": reachable, "by_depth": dict(sorted(by_depth.items()))},
        rationale=rationale,
    )


# --------------------------------------------------------------------------- #
# Graph builder — best-effort parse of `gc bd dep tree --json` shapes           #
# --------------------------------------------------------------------------- #


def build_graph_from_dep_json(dep_tree_json: object) -> dict[str, list[str]]:
    """Parse ``gc bd dep tree --json``-shaped data into the blast-radius adjacency map.

    Builds ``{bead_id: [downstream dependent bead_ids]}`` — the edges
    :func:`effective_cascade` walks, where ``u -> v`` means "u blocks v / v depends
    on u". **Best-effort and total**: it never throws on a missing/odd key (it
    skips), so a malformed tree degrades to a partial (or empty) graph rather than
    failing a dispatch (DESIGN §8 degradation).

    Two input shapes are tolerated (gc's ``dep tree`` has shipped both):

    1. **Nested tree** — a dict (or list of dict roots) ``{id, dependents|children:
       [ …same shape… ]}``. Each node's id maps to the ids of its child nodes; the
       walk recurses, accumulating an edge ``parent -> child`` per nesting level.
       Alternate id keys (``id`` / ``bead_id`` / ``bead`` / ``name``) and alternate
       child keys (``dependents`` / ``children`` / ``blocks`` / ``downstream`` /
       ``deps``) are all accepted.
    2. **Flat list** — ``[{id, blocks:[child_id, …]}, …]`` (or a single such dict).
       Each record contributes edges ``id -> b`` for every ``b`` it ``blocks``
       (alternate edge keys ``blocks`` / ``dependents`` / ``children`` /
       ``downstream`` / ``deps`` accepted). List members may themselves be the
       *nested* shape, in which case they are recursed into as well.

    **Assumptions / conventions** (documented per the brief):

    - Edges always point **downstream** (root → dependents = blast radius). The
      caller's ``root`` is the dispatched bead; its reachable set is what it
      blocks. If a producer emits the *inverse* (``depends_on`` / ``parents``)
      those keys are intentionally **not** followed — they are upstream and not the
      blast radius.
    - Child entries may be **plain id strings** *or* nested **dicts**; both are
      handled (a string child is a leaf edge; a dict child is an edge *and*
      recursed).
    - A node may appear multiple times (re-convergent DAG); edges are **de-duped**
      per source (a child is listed once per parent) and every seen id gets a key
      (so leaves appear as ``id: []``). Re-visiting a node during recursion does
      not re-expand it (guards against cycles in the source data).
    - Anything that is not a dict/list, or a node with no usable id, is skipped.

    Returns a plain ``dict[str, list[str]]`` adjacency map (possibly empty).
    """
    graph: dict[str, list[str]] = {}
    if dep_tree_json is None:
        return graph

    # Accepted aliases for the id field and the downstream-edge field. Order is
    # irrelevant; first present wins for the id.
    id_keys = ("id", "bead_id", "bead", "name")
    edge_keys = ("dependents", "children", "blocks", "downstream", "deps")

    def _node_id(node: Mapping) -> str | None:
        for k in id_keys:
            v = node.get(k)
            if isinstance(v, str) and v:
                return v
        return None

    def _edges(node: Mapping) -> list:
        for k in edge_keys:
            v = node.get(k)
            if isinstance(v, list):
                return v
        return []

    def _add_edge(src: str, dst: str) -> None:
        bucket = graph.setdefault(src, [])
        if dst not in bucket:
            bucket.append(dst)
        graph.setdefault(dst, graph.get(dst, []))  # ensure the child has a key too

    # ``recursing`` guards against cycles in malformed source data: a node already
    # being expanded is not re-expanded (its edges were/are recorded once).
    recursing: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if not isinstance(node, Mapping):
            return  # scalar / unknown at the top level: nothing to extract

        src = _node_id(node)
        if src is None:
            # No usable id on this node, but its edge-list children might still be
            # well-formed nested nodes worth walking for their own edges.
            for child in _edges(node):
                if isinstance(child, Mapping):
                    _walk(child)
            return

        graph.setdefault(src, [])
        if src in recursing:
            return  # already expanding this node (cycle): edges recorded once
        recursing.add(src)

        for child in _edges(node):
            if isinstance(child, str) and child:
                _add_edge(src, child)
            elif isinstance(child, Mapping):
                cid = _node_id(child)
                if cid is not None:
                    _add_edge(src, cid)
                _walk(child)  # recurse for the child's own downstream edges
            # any other child type (int/None/list) is skipped

        recursing.discard(src)

    _walk(dep_tree_json)
    return graph
