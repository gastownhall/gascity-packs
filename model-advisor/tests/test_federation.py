"""Tests for multi-tenant posterior federation (DESIGN §7.3).

Federation shares per-cell **aggregates** — never raw telemetry — so thin cells
converge faster by borrowing a peer repo's evidence, while a trust scaling +
per-cell mass cap keep a peer from ever dominating local evidence. The
load-bearing properties we assert:

- **privacy** — an export carries ONLY ``a_obs``/``b_obs``/``n`` per cell (no
  ``ts``/``last_update``/``bead_id``/rationale/extra keys) and round-trips through
  JSON;
- **prior subtraction** — a cell carrying only prior mass is excluded (or exports
  ``a_obs ≈ 0``); the exporter's prior never leaks and is never double-counted;
- **thin vs rich (THE key test)** — a confident peer moves a *thin* local cell's
  mean materially but barely moves a *rich* local cell (the trust cap);
- **trust = 0** ⇒ no peer influence; **empty peers** ⇒ store unchanged;
- **fail closed** — a bad peer schema (and other malformed peers) raise;
- determinism.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# Make the pack root importable when pytest is run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modeladvisor import config as C  # noqa: E402
from modeladvisor import federation as F  # noqa: E402
from modeladvisor import store as S  # noqa: E402
from modeladvisor.store import cell_key, cold_start_prior  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures + helpers                                                            #
# --------------------------------------------------------------------------- #


@pytest.fixture
def cfg() -> C.AdvisorConfig:
    """Default Claude haiku/sonnet/opus roster, baseline = opus."""
    return C.default_config()


def _q(agent, shape, tier, q, i, *, provider="claude"):
    return {
        "kind": "quality",
        "ts": f"2026-06-01T00:00:{i % 60:02d}Z",
        "bead_id": f"bh-{agent}-{shape}-{tier}-{i}",
        "cell_key": cell_key(provider, agent, shape, tier),
        "q": q,
        "channel": "close",
    }


def _wins(agent, shape, tier, n):
    return [_q(agent, shape, tier, 1, i) for i in range(n)]


def _losses(agent, shape, tier, n):
    return [_q(agent, shape, tier, 0, i) for i in range(n)]


def _store_with(cfg, records) -> S.CellStore:
    st = S.CellStore.cold_start(cfg)
    st.apply_records(records)
    return st


def _mean(cell) -> float:
    return cell.a / (cell.a + cell.b)


# --------------------------------------------------------------------------- #
# export — privacy contract: only a_obs/b_obs/n, JSON round-trip                #
# --------------------------------------------------------------------------- #


def test_export_carries_only_aggregate_fields_and_round_trips(cfg):
    # A cell with real, heterogeneous evidence (so a_obs != b_obs and n > 0).
    st = _store_with(cfg, _wins("polecat", "implement", "sonnet", 7)
                     + _losses("polecat", "implement", "sonnet", 3))
    doc = F.export_aggregates(st)

    assert doc["schema"] == F.SCHEMA
    assert set(doc.keys()) == {"schema", "cells"}
    key = cell_key("claude", "polecat", "implement", "sonnet")
    assert key in doc["cells"]
    agg = doc["cells"][key]
    # EXACTLY the three numbers — nothing else may ride along.
    assert set(agg.keys()) == {"a_obs", "b_obs", "n"}
    assert agg["n"] == 10
    # No telemetry/audit field leaks anywhere in the document text.
    blob = json.dumps(doc)
    for forbidden in ("ts", "last_update", "bead_id", "signal", "rationale",
                      "channel", "weight", "2026-06-01"):
        assert forbidden not in blob
    # Survives a JSON round-trip unchanged (it is pure data).
    assert json.loads(json.dumps(doc)) == doc


def test_export_observed_only_excludes_untouched_cells(cfg):
    st = _store_with(cfg, _wins("polecat", "implement", "sonnet", 4))
    # Materialise an unrelated prior-only cell (n == 0) by reading it.
    st.get(cell_key("claude", "polecat", "implement", "haiku"))
    obs = F.export_aggregates(st, observed_only=True)
    assert cell_key("claude", "polecat", "implement", "haiku") not in obs["cells"]
    assert cell_key("claude", "polecat", "implement", "sonnet") in obs["cells"]
    # With observed_only=False the prior-only cell appears, but prior-subtracted.
    allc = F.export_aggregates(st, observed_only=False)
    haiku = allc["cells"][cell_key("claude", "polecat", "implement", "haiku")]
    assert haiku["a_obs"] == pytest.approx(0.0, abs=1e-9)
    assert haiku["b_obs"] == pytest.approx(0.0, abs=1e-9)
    assert haiku["n"] == 0


# --------------------------------------------------------------------------- #
# export — prior subtraction (no prior baked in, none leaked)                   #
# --------------------------------------------------------------------------- #


def test_export_subtracts_prior_so_aggregates_are_pure_evidence(cfg):
    # 6 wins, 2 losses (all weight 1 via the close channel) => observed mass is
    # exactly a_obs=6, b_obs=2 regardless of what the cold-start prior was.
    st = _store_with(cfg, _wins("mayor", "judge", "sonnet", 6)
                     + _losses("mayor", "judge", "sonnet", 2))
    key = cell_key("claude", "mayor", "judge", "sonnet")
    agg = F.export_aggregates(st)["cells"][key]
    assert agg["a_obs"] == pytest.approx(6.0)
    assert agg["b_obs"] == pytest.approx(2.0)

    # And the posterior really did include a (non-zero) prior we subtracted off.
    prior_a, prior_b = cold_start_prior(cfg, "sonnet",
                                        cfg.baseline_tier_id_for("mayor", "judge"))
    cell = st.get(key)
    assert cell.a == pytest.approx(prior_a + 6.0)
    assert cell.b == pytest.approx(prior_b + 2.0)


def test_export_prior_only_baseline_cell_is_excluded(cfg):
    # The baseline tier (opus) seeds Beta(8,2) — pure prior, no observations.
    st = S.CellStore.cold_start(cfg)
    st.get(cell_key("claude", "mayor", "judge", "opus"))  # materialise prior-only
    doc = F.export_aggregates(st)  # observed_only default
    assert doc["cells"] == {}


# --------------------------------------------------------------------------- #
# load_peer — validation, fail closed                                          #
# --------------------------------------------------------------------------- #


def test_load_peer_round_trips_from_dict_and_file(cfg, tmp_path):
    st = _store_with(cfg, _wins("polecat", "implement", "sonnet", 5)
                     + _losses("polecat", "implement", "sonnet", 1))
    doc = F.export_aggregates(st)

    from_dict = F.load_peer(doc)
    assert from_dict["schema"] == F.SCHEMA
    assert from_dict["cells"].keys() == doc["cells"].keys()

    p = tmp_path / "peer.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    from_file = F.load_peer(str(p))
    assert from_file == from_dict


def test_load_peer_rejects_bad_schema_and_garbage(cfg, tmp_path):
    # Wrong schema tag.
    with pytest.raises(F.FederationError):
        F.load_peer({"schema": "advisor.federation.v0", "cells": {}})
    # Missing schema.
    with pytest.raises(F.FederationError):
        F.load_peer({"cells": {}})
    # Not an object at all.
    with pytest.raises(F.FederationError):
        F.load_peer([1, 2, 3])  # type: ignore[arg-type]
    # Missing file.
    with pytest.raises(F.FederationError):
        F.load_peer(str(tmp_path / "nope.json"))
    # Non-JSON file content.
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(F.FederationError):
        F.load_peer(str(bad))
    # Malformed cell key.
    with pytest.raises(F.FederationError):
        F.load_peer({"schema": F.SCHEMA, "cells": {"bad-key": {"a_obs": 1, "b_obs": 1, "n": 2}}})
    # Negative pseudocount (observed mass can never be negative).
    good_key = cell_key("claude", "polecat", "implement", "sonnet")
    with pytest.raises(F.FederationError):
        F.load_peer({"schema": F.SCHEMA, "cells": {good_key: {"a_obs": -3.0, "b_obs": 1, "n": 2}}})
    # Missing aggregate field.
    with pytest.raises(F.FederationError):
        F.load_peer({"schema": F.SCHEMA, "cells": {good_key: {"a_obs": 1.0, "n": 2}}})


# --------------------------------------------------------------------------- #
# merge — THE key test: thin moves, rich doesn't                               #
# --------------------------------------------------------------------------- #


def test_merge_moves_thin_cell_but_barely_moves_rich_cell(cfg):
    key = cell_key("claude", "polecat", "implement", "sonnet")

    # A confident peer: lots of successful observed mass on this cell.
    peer_st = _store_with(cfg, _wins("polecat", "implement", "sonnet", 200))
    peer = F.export_aggregates(peer_st)
    peer_mean = peer["cells"][key]["a_obs"] / (
        peer["cells"][key]["a_obs"] + peer["cells"][key]["b_obs"])
    assert peer_mean > 0.95  # the peer is strongly positive

    # THIN local cell: 2 wins, 2 losses (own mean 0.5).
    thin = _store_with(cfg, _wins("polecat", "implement", "sonnet", 2)
                       + _losses("polecat", "implement", "sonnet", 2))
    thin_before = _mean(thin.get(key))
    thin_after = _mean(merge := F.merge_peers(thin, [peer], trust=0.3).get(key))
    assert thin_after > thin_before + 0.1  # peer pulls the thin cell up materially

    # RICH local cell: same own mean (0.5) but 500 wins + 500 losses. With own
    # mass (~1000) >> the trust-scaled peer mass (0.3 * 200 = 60), local evidence
    # dominates and the peer can barely move it.
    rich = _store_with(cfg, _wins("polecat", "implement", "sonnet", 500)
                       + _losses("polecat", "implement", "sonnet", 500))
    rich_before = _mean(rich.get(key))
    rich_after = _mean(F.merge_peers(rich, [peer], trust=0.3).get(key))
    rich_shift = rich_after - rich_before
    thin_shift = thin_after - thin_before
    assert rich_shift < 0.05                 # rich cell barely budges
    assert thin_shift > 5.0 * rich_shift     # thin moves far more than rich (the cap)

    # merge returned a NEW store; the local one was not mutated.
    assert _mean(thin.get(key)) == pytest.approx(thin_before)


def test_merge_max_peer_mass_caps_peer_injection(cfg):
    key = cell_key("claude", "polecat", "implement", "sonnet")
    peer_st = _store_with(cfg, _wins("polecat", "implement", "sonnet", 500))
    peer = F.export_aggregates(peer_st)

    thin = _store_with(cfg, _wins("polecat", "implement", "sonnet", 1)
                       + _losses("polecat", "implement", "sonnet", 1))
    uncapped = _mean(F.merge_peers(thin, [peer], trust=1.0).get(key))
    capped = _mean(F.merge_peers(thin, [peer], trust=1.0, max_peer_mass=2.0).get(key))
    thin_before = _mean(thin.get(key))
    # The cap keeps the thin cell closer to its own mean than uncapped does.
    assert thin_before < capped < uncapped


# --------------------------------------------------------------------------- #
# merge — no-influence / idempotence guarantees                                #
# --------------------------------------------------------------------------- #


def test_merge_trust_zero_has_no_peer_influence(cfg):
    key = cell_key("claude", "polecat", "implement", "sonnet")
    peer_st = _store_with(cfg, _wins("polecat", "implement", "sonnet", 300))
    peer = F.export_aggregates(peer_st)

    local = _store_with(cfg, _wins("polecat", "implement", "sonnet", 2)
                        + _losses("polecat", "implement", "sonnet", 2))
    merged = F.merge_peers(local, [peer], trust=0.0)
    a, b = merged.get(key).a, merged.get(key).b
    base = local.get(key)
    assert (a, b) == pytest.approx((base.a, base.b))


def test_merge_empty_peers_reproduces_local_store(cfg):
    key = cell_key("claude", "polecat", "implement", "sonnet")
    local = _store_with(cfg, _wins("polecat", "implement", "sonnet", 9)
                        + _losses("polecat", "implement", "sonnet", 4))
    for peers in ([], None):
        merged = F.merge_peers(local, peers, trust=0.3)
        # Same observed cells, same posteriors as the local store.
        assert set(merged.observed_cells()) == set(local.observed_cells())
        m, l = merged.get(key), local.get(key)
        assert (m.a, m.b, m.n) == pytest.approx((l.a, l.b, l.n))
        assert m.last_update == l.last_update


def test_merge_does_not_invent_local_only_cells_for_absent_peers(cfg):
    # A peer that only knows about a DIFFERENT cell must not touch a local cell,
    # and must not fabricate the local cell out of thin air.
    local_key = cell_key("claude", "polecat", "implement", "sonnet")
    other_key = cell_key("claude", "refinery", "review", "haiku")
    peer_st = _store_with(cfg, _wins("refinery", "review", "haiku", 50))
    peer = F.export_aggregates(peer_st)

    local = _store_with(cfg, _wins("polecat", "implement", "sonnet", 3)
                        + _losses("polecat", "implement", "sonnet", 3))
    merged = F.merge_peers(local, [peer], trust=0.5)
    # Local cell unchanged (no peer evidence for it).
    l, m = local.get(local_key), merged.get(local_key)
    assert (m.a, m.b) == pytest.approx((l.a, l.b))
    # The peer-only cell exists in the merge (its prior + peer mass) but carries
    # n == 0 locally — it is borrowed prior, not local observation.
    assert merged.get(other_key).n == 0
    assert merged.get(other_key).a > local.get(other_key).a  # peer mass added


def test_merge_accepts_raw_paths_and_is_deterministic(cfg, tmp_path):
    key = cell_key("claude", "polecat", "implement", "sonnet")
    peer_st = _store_with(cfg, _wins("polecat", "implement", "sonnet", 80)
                          + _losses("polecat", "implement", "sonnet", 20))
    p = tmp_path / "peer.json"
    p.write_text(json.dumps(F.export_aggregates(peer_st)), encoding="utf-8")

    local = _store_with(cfg, _wins("polecat", "implement", "sonnet", 2)
                        + _losses("polecat", "implement", "sonnet", 1))
    # Pass a raw path (string) — load_peer is invoked internally.
    m1 = F.merge_peers(local, str(p), trust=0.4).get(key)
    m2 = F.merge_peers(local, [str(p)], trust=0.4).get(key)
    assert (m1.a, m1.b, m1.n) == pytest.approx((m2.a, m2.b, m2.n))


def test_merge_sums_multiple_peers(cfg):
    key = cell_key("claude", "polecat", "implement", "sonnet")
    peer_a = F.export_aggregates(_store_with(cfg, _wins("polecat", "implement", "sonnet", 40)))
    peer_b = F.export_aggregates(_store_with(cfg, _wins("polecat", "implement", "sonnet", 40)))
    thin = _store_with(cfg, _wins("polecat", "implement", "sonnet", 1)
                       + _losses("polecat", "implement", "sonnet", 1))

    one = _mean(F.merge_peers(thin, [peer_a], trust=0.3).get(key))
    two = _mean(F.merge_peers(thin, [peer_a, peer_b], trust=0.3).get(key))
    # Two agreeing positive peers pull the thin cell higher than one alone.
    assert two > one
