"""Tests for the DAG-propagated effective blast radius (DESIGN §1.3 L3, §7.3).

The deferred-feature contract (V3 build brief, bead bh-1rd):

- **leaf ⇒ flat** — a root that blocks nothing returns ``n_dep_eff == base_n_dep``
  (the v1 flat-scalar behaviour, recovered exactly);
- **width monotonicity** — a wider DAG yields a strictly larger ``n_dep_eff`` than
  a narrower one;
- **depth monotonicity** — a deeper chain yields a strictly larger ``n_dep_eff``
  than a shallow one;
- **decay** — ``decay < 1`` down-weights deeper dependents (so a deep tail counts
  for less than the same nodes placed shallow);
- **cycle-safety** — a cyclic graph terminates and counts each node once;
- **max_depth** — caps how far the walk reaches;
- **parser tolerance** — ``build_graph_from_dep_json`` parses both a nested tree
  and a flat ``blocks`` list, and never throws on missing keys;
- **degradation** — an empty / ``None`` graph or unknown root falls back to base.

The module is a pure function of ``(graph, root)``, so these tests drive it with
hand-built adjacency maps (no store / config / engine needed).
"""

from __future__ import annotations

import os
import sys

import pytest

# Make the pack root importable when pytest is run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modeladvisor import cascade as C  # noqa: E402
from modeladvisor.cascade import CascadeResult  # noqa: E402


# --------------------------------------------------------------------------- #
# Leaf / degradation -> flat base_n_dep (DESIGN §8 degradation)                 #
# --------------------------------------------------------------------------- #


def test_leaf_returns_base_n_dep():
    """A root present in the graph but blocking nothing ⇒ n_dep_eff == base."""
    graph = {"root": []}
    res = C.effective_cascade(graph, "root")
    assert isinstance(res, CascadeResult)
    assert res.n_dep_eff == 1  # default base_n_dep
    assert res.depth == 0
    assert res.n_nodes == 1
    assert res.loss_terms == {"reachable": 0, "by_depth": {}}


def test_leaf_honours_custom_base_n_dep():
    res = C.effective_cascade({"root": []}, "root", base_n_dep=3)
    assert res.n_dep_eff == 3
    assert res.n_nodes == 1


def test_empty_and_none_graph_fall_back_to_base():
    for g in (None, {}):
        res = C.effective_cascade(g, "root", base_n_dep=2)
        assert res.n_dep_eff == 2
        assert res.depth == 0
        assert res.n_nodes == 1


def test_unknown_root_falls_back_to_base():
    graph = {"a": ["b"], "b": []}
    res = C.effective_cascade(graph, "does-not-exist")
    assert res.n_dep_eff == 1
    assert res.n_nodes == 1
    assert res.loss_terms["reachable"] == 0


# --------------------------------------------------------------------------- #
# Width & depth monotonicity (the core property fed into the L3 cascade term)   #
# --------------------------------------------------------------------------- #


def test_wider_dag_has_strictly_larger_n_dep_eff():
    """An ADR blocking 3 dependents outweighs one blocking 1 (both depth 1)."""
    narrow = {"adr": ["x"], "x": []}
    wide = {"adr": ["x", "y", "z"], "x": [], "y": [], "z": []}
    n = C.effective_cascade(narrow, "adr")
    w = C.effective_cascade(wide, "adr")
    assert w.n_dep_eff > n.n_dep_eff
    # decay=1.0 default => raw reachable count + base floor.
    assert n.n_dep_eff == 1 + 1
    assert w.n_dep_eff == 1 + 3


def test_deeper_chain_has_strictly_larger_n_dep_eff():
    """A chain root->a->b->c outweighs a shallow root->a (monotone in depth)."""
    shallow = {"root": ["a"], "a": []}
    deep = {"root": ["a"], "a": ["b"], "b": ["c"], "c": []}
    s = C.effective_cascade(shallow, "root")
    dd = C.effective_cascade(deep, "root")
    assert dd.n_dep_eff > s.n_dep_eff
    assert dd.depth == 3 and s.depth == 1
    assert dd.n_nodes == 4 and s.n_nodes == 2


def test_layered_blast_radius_counts_full_transitive_closure():
    """ADR blocks 3 ADRs that each block 4 builders => 3 + 12 = 15 reachable."""
    graph: dict[str, list[str]] = {"root": ["a", "b", "c"]}
    for mid in ("a", "b", "c"):
        kids = [f"{mid}{i}" for i in range(4)]
        graph[mid] = kids
        for k in kids:
            graph[k] = []
    res = C.effective_cascade(graph, "root")  # decay=1.0 default
    assert res.loss_terms["reachable"] == 15
    assert res.loss_terms["by_depth"] == {1: 3, 2: 12}
    assert res.n_dep_eff == 1 + 15  # base floor + raw reachable
    assert res.depth == 2
    assert res.n_nodes == 16  # 15 dependents + the root


# --------------------------------------------------------------------------- #
# Decay: nearer dependents weighted more (DESIGN §1.3 L3 propagation)           #
# --------------------------------------------------------------------------- #


def test_decay_downweights_deep_nodes():
    """The same 3-node chain weighs less under decay<1 than under decay==1."""
    chain = {"root": ["a"], "a": ["b"], "b": ["c"], "c": []}
    full = C.effective_cascade(chain, "root", decay=1.0)
    decayed = C.effective_cascade(chain, "root", decay=0.5)
    assert full.n_dep_eff == 1 + 3  # 1 + (1 + 1 + 1)
    # 1 + (0.5^1 + 0.5^2 + 0.5^3) = 1 + 0.875
    assert decayed.n_dep_eff == pytest.approx(1 + (0.5 + 0.25 + 0.125))
    assert decayed.n_dep_eff < full.n_dep_eff


def test_decay_makes_shallow_outweigh_deep_for_equal_node_counts():
    """Two dependents at depth 1 beat two stacked at depths 1+2 under decay<1."""
    shallow = {"root": ["a", "b"], "a": [], "b": []}  # both at depth 1
    deep = {"root": ["a"], "a": ["b"], "b": []}        # depths 1 and 2
    s = C.effective_cascade(shallow, "root", decay=0.5)
    d = C.effective_cascade(deep, "root", decay=0.5)
    # shallow: 1 + (0.5 + 0.5) = 2.0 ; deep: 1 + (0.5 + 0.25) = 1.75
    assert s.n_dep_eff > d.n_dep_eff


def test_decay_clamped_into_unit_interval():
    """decay<=0 is clamped (still counts) and decay>1 collapses to raw-count (==1)."""
    chain = {"root": ["a"], "a": ["b"], "b": []}
    # decay > 1 must not up-weight the far tail -> behaves like decay==1.0.
    over = C.effective_cascade(chain, "root", decay=2.0)
    one = C.effective_cascade(chain, "root", decay=1.0)
    assert over.n_dep_eff == one.n_dep_eff == 1 + 2
    # decay <= 0 is nudged to ~0 (deep nodes contribute ~nothing) but never crashes.
    zero = C.effective_cascade(chain, "root", decay=0.0)
    assert zero.n_dep_eff == pytest.approx(1.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# Cycle-safety & max_depth (robustness of the traversal)                       #
# --------------------------------------------------------------------------- #


def test_cycle_terminates_and_counts_each_node_once():
    """A graph with a cycle terminates; each distinct node is counted once."""
    graph = {"a": ["b"], "b": ["c"], "c": ["a"]}  # a->b->c->a (cycle)
    res = C.effective_cascade(graph, "a")
    # From a: reachable = {b, c} (a is the root, not a dependent of itself).
    assert res.loss_terms["reachable"] == 2
    assert res.n_nodes == 3
    assert res.n_dep_eff == 1 + 2
    # by_depth counts b at 1, c at 2 (shallowest path); the back-edge c->a is dropped.
    assert res.loss_terms["by_depth"] == {1: 1, 2: 1}


def test_self_loop_is_harmless():
    graph = {"root": ["root", "a"], "a": []}
    res = C.effective_cascade(graph, "root")
    assert res.loss_terms["reachable"] == 1  # only 'a'; the self-edge is ignored
    assert res.n_dep_eff == 1 + 1


def test_reconvergent_dag_counts_shared_child_once():
    """A diamond root->{a,b}->c counts the shared sink c exactly once."""
    graph = {"root": ["a", "b"], "a": ["c"], "b": ["c"], "c": []}
    res = C.effective_cascade(graph, "root")
    assert res.loss_terms["reachable"] == 3  # a, b, c (c shared, once)
    # c is reached at depth 2 via the shortest path; counted a single time.
    assert res.loss_terms["by_depth"] == {1: 2, 2: 1}
    assert res.n_dep_eff == 1 + 3


def test_max_depth_caps_traversal():
    """max_depth bounds how deep the walk reaches (deeper dependents are pruned)."""
    chain = {"root": ["a"], "a": ["b"], "b": ["c"], "c": ["d"], "d": []}
    capped = C.effective_cascade(chain, "root", max_depth=2)
    full = C.effective_cascade(chain, "root", max_depth=6)
    assert capped.depth == 2
    assert capped.loss_terms["reachable"] == 2  # a (d1), b (d2); c, d pruned
    assert full.loss_terms["reachable"] == 4
    assert capped.n_dep_eff < full.n_dep_eff


def test_max_depth_zero_degrades_to_base():
    """max_depth<1 means even direct children aren't counted -> flat base."""
    graph = {"root": ["a", "b"], "a": [], "b": []}
    res = C.effective_cascade(graph, "root", max_depth=0)
    assert res.n_dep_eff == 1
    assert res.n_nodes == 1


# --------------------------------------------------------------------------- #
# Determinism & audit completeness (DESIGN §1.4 property 3 spirit)             #
# --------------------------------------------------------------------------- #


def test_deterministic_repeated_calls():
    graph = {"root": ["a", "b"], "a": ["c"], "b": ["c"], "c": []}
    r1 = C.effective_cascade(graph, "root", decay=0.7)
    r2 = C.effective_cascade(graph, "root", decay=0.7)
    assert r1 == r2


def test_result_has_rationale_and_loss_terms():
    graph = {"root": ["a", "b"], "a": [], "b": []}
    res = C.effective_cascade(graph, "root")
    assert isinstance(res.rationale, str) and res.rationale
    assert "reachable" in res.loss_terms and "by_depth" in res.loss_terms
    assert "root" in res.rationale


# --------------------------------------------------------------------------- #
# build_graph_from_dep_json — nested tree shape                                 #
# --------------------------------------------------------------------------- #


def test_parse_nested_tree_with_dependents_key():
    """A nested {id, dependents:[...]} tree becomes the right adjacency map."""
    tree = {
        "id": "root",
        "dependents": [
            {"id": "a", "dependents": [{"id": "c", "dependents": []}]},
            {"id": "b", "dependents": []},
        ],
    }
    graph = C.build_graph_from_dep_json(tree)
    assert graph["root"] == ["a", "b"]
    assert graph["a"] == ["c"]
    assert graph["b"] == []
    assert graph["c"] == []
    # And it drives effective_cascade end-to-end.
    res = C.effective_cascade(graph, "root")
    assert res.loss_terms["reachable"] == 3  # a, b, c


def test_parse_nested_tree_with_children_key_and_string_leaves():
    """Alternate 'children' key and plain-string leaf children are both handled."""
    tree = {
        "bead_id": "root",
        "children": [
            {"bead_id": "a", "children": ["leaf1", "leaf2"]},
            "b",  # a bare string child of root
        ],
    }
    graph = C.build_graph_from_dep_json(tree)
    assert set(graph["root"]) == {"a", "b"}
    assert graph["a"] == ["leaf1", "leaf2"]
    assert graph["leaf1"] == [] and graph["leaf2"] == [] and graph["b"] == []


# --------------------------------------------------------------------------- #
# build_graph_from_dep_json — flat-list shape                                   #
# --------------------------------------------------------------------------- #


def test_parse_flat_list_with_blocks_key():
    """A flat [{id, blocks:[...]}] list becomes the right adjacency map."""
    flat = [
        {"id": "root", "blocks": ["a", "b"]},
        {"id": "a", "blocks": ["c"]},
        {"id": "b", "blocks": []},
        {"id": "c", "blocks": []},
    ]
    graph = C.build_graph_from_dep_json(flat)
    assert graph["root"] == ["a", "b"]
    assert graph["a"] == ["c"]
    res = C.effective_cascade(graph, "root")
    assert res.loss_terms["reachable"] == 3
    assert res.loss_terms["by_depth"] == {1: 2, 2: 1}


def test_parse_is_total_and_skips_bad_entries():
    """Missing keys / non-dict members / no-id nodes never throw; they're skipped."""
    messy = [
        {"id": "root", "blocks": ["a"]},
        {"blocks": ["orphan"]},        # no id -> skipped as a source
        "not-a-dict",                  # scalar member -> skipped
        {"id": "a"},                   # no edge key -> leaf
        {"id": "b", "blocks": [42, None, "c"]},  # non-str edges skipped, 'c' kept
    ]
    graph = C.build_graph_from_dep_json(messy)  # must not raise
    assert graph["root"] == ["a"]
    assert graph["a"] == []
    assert graph["b"] == ["c"]
    assert "orphan" not in graph  # came only from a source with no id
    # None input is tolerated too.
    assert C.build_graph_from_dep_json(None) == {}


def test_parse_dedupes_edges_per_source():
    """Repeated edges from one source are de-duplicated."""
    flat = [{"id": "root", "blocks": ["a", "a", "b"]}]
    graph = C.build_graph_from_dep_json(flat)
    assert graph["root"] == ["a", "b"]


def test_parse_cyclic_source_does_not_recurse_forever():
    """A nested source that references a node already being expanded terminates."""
    # 'a' nests 'b', and 'b' nests 'a' again (cyclic source data).
    tree = {
        "id": "a",
        "children": [{"id": "b", "children": [{"id": "a", "children": []}]}],
    }
    graph = C.build_graph_from_dep_json(tree)  # must terminate
    assert "a" in graph and "b" in graph
    assert "b" in graph["a"]
    # effective_cascade is cycle-safe over whatever edges resulted.
    res = C.effective_cascade(graph, "a")
    assert res.n_nodes >= 2
