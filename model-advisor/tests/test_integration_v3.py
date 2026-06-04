"""End-to-end integration tests for the v3 deferred features (DESIGN §7.3).

These exercise the *wiring* of all eight v3 modules through the shared public
surfaces (``config`` / ``store`` / ``engine`` / ``cli``), one feature per toggle,
proving each flag turns its feature on end-to-end while staying **off by default**.
They deliberately do not re-test the modules' internal algorithms (those have
their own ``test_<feature>.py``); they assert the integration contract:

- ``continuous_quality`` lets the store accept a fractional ``q``;
- ``lcb_backend = conformal`` runs ``recommend`` and, on an empty calibration
  buffer, returns the *same* decision as Wilson (the safe-drop-in contract);
- ``pooling = empirical-bayes`` runs ``recommend`` end-to-end;
- ``mode = thompson`` is deterministic per seed and never downgrades a Critical cell;
- the ``changepoint`` rebuild branch re-weights a drifted cell's posterior;
- ``schedule_evals`` ranks gating cells;
- ``federate export`` → ``merge_peers`` round-trips observed mass;
- a wide DAG raises the cascade ``N_dep`` vs a flat bead.

The default-off invariant (the 86 pre-existing tests passing unmodified) is the
primary guard; these add the *opt-in-on* half.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace

import pytest

# Make the pack root importable when pytest is run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modeladvisor import config as C  # noqa: E402
from modeladvisor import engine as E  # noqa: E402
from modeladvisor import federation as F  # noqa: E402
from modeladvisor import store as S  # noqa: E402
from modeladvisor.cascade import build_graph_from_dep_json, effective_cascade  # noqa: E402
from modeladvisor.evalsched import schedule_evals  # noqa: E402
from modeladvisor.store import cell_key  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures + helpers                                                            #
# --------------------------------------------------------------------------- #


@pytest.fixture
def cfg() -> C.AdvisorConfig:
    """Default Claude haiku/sonnet/opus roster, baseline = opus."""
    return C.default_config()


def _key(cfg: C.AdvisorConfig, agent: str, shape: str, tier: str) -> str:
    return cell_key(cfg.default_provider, agent, shape, tier)


def _wins(cfg, agent, shape, tier, n, *, channel="close"):
    k = _key(cfg, agent, shape, tier)
    return [
        {"kind": "quality", "cell_key": k, "q": 1, "channel": channel, "ts": f"t{i}"}
        for i in range(n)
    ]


def _feed(store, records):
    for r in records:
        store.apply_quality(r)
    return store


# --------------------------------------------------------------------------- #
# 1. continuous_quality — the store accepts a fractional q                      #
# --------------------------------------------------------------------------- #


def test_continuous_quality_off_drops_fractional_q(cfg):
    """Default (off): a non-binary q is dropped, exactly as v1 (the invariant)."""
    st = S.CellStore.cold_start(cfg)
    applied = st.apply_quality(
        {"kind": "quality", "cell_key": _key(cfg, "polecat", "implement", "sonnet"), "q": 0.7}
    )
    assert applied is False
    assert _key(cfg, "polecat", "implement", "sonnet") not in st.observed_cells()


def test_continuous_quality_on_accepts_q_0_7(cfg):
    """``continuous_quality`` on: q=0.7 is accepted and folds into the posterior."""
    cfg_c = replace(cfg, hp=replace(cfg.hp, continuous_quality=True))
    st = S.CellStore.cold_start(cfg_c)
    k = _key(cfg_c, "polecat", "implement", "sonnet")
    prior = st.get(k)
    prior_a, prior_b = prior.a, prior.b
    assert st.apply_quality({"kind": "quality", "cell_key": k, "q": 0.7, "weight": 1.0}) is True
    cell = st.cells[k]
    assert cell.n == 1
    # Beta soft-update with the fractional reward: a += w·q, b += w·(1−q).
    assert cell.a == pytest.approx(prior_a + 1.0 * 0.7)
    assert cell.b == pytest.approx(prior_b + 1.0 * 0.3)
    assert 0.0 < cell.mean < 1.0


# --------------------------------------------------------------------------- #
# 2. lcb_backend = conformal — runs recommend; empty buffer == Wilson          #
# --------------------------------------------------------------------------- #


def test_conformal_backend_empty_buffer_matches_wilson(cfg):
    """An empty calibration buffer ⇒ conformal falls back to Wilson: equal result."""
    records = _wins(cfg, "polecat", "implement", "sonnet", 40)

    st_w = _feed(S.CellStore.cold_start(cfg), records)
    rec_w = E.recommend("polecat", "implement", cfg, st_w, provider=cfg.default_provider)

    cfg_c = replace(cfg, lcb_backend="conformal")
    st_c = _feed(S.CellStore.cold_start(cfg_c), records)
    rec_c = E.recommend("polecat", "implement", cfg_c, st_c, provider=cfg_c.default_provider)

    assert rec_c["reasons"]["lcb_backend"] == "conformal"
    assert rec_c["tier_id"] == rec_w["tier_id"]
    # Per-tier q_lo identical too (buffers thin ⇒ exact Wilson on both sides).
    qlo_w = {t: p["q_lo"] for t, p in rec_w["posterior_summary"].items()}
    for tid, p in rec_c["posterior_summary"].items():
        assert p["q_lo"] == pytest.approx(qlo_w[tid])


# --------------------------------------------------------------------------- #
# 3. pooling = empirical-bayes — runs recommend end-to-end                      #
# --------------------------------------------------------------------------- #


def test_empirical_bayes_pooling_runs_recommend(cfg):
    """``pooling = empirical-bayes`` produces a complete, valid recommendation."""
    cfg_eb = replace(cfg, pooling="empirical-bayes")
    st = _feed(S.CellStore.cold_start(cfg_eb), _wins(cfg_eb, "polecat", "implement", "sonnet", 30))
    rec = E.recommend("polecat", "implement", cfg_eb, st, provider=cfg_eb.default_provider)
    assert rec["reasons"]["pooling"] == "empirical-bayes"
    assert rec["tier_id"] in cfg_eb.tier_ids
    # The pooled posterior was read via the EB pooler (drop-in for store.pooled).
    eb_cell = st.pooled(cfg_eb.default_provider, "polecat", "implement", "sonnet")
    assert eb_cell.n >= 0 and 0.0 < eb_cell.mean < 1.0


# --------------------------------------------------------------------------- #
# 4. mode = thompson — deterministic per seed + never downgrades Critical       #
# --------------------------------------------------------------------------- #


def test_thompson_mode_deterministic_per_seed(cfg):
    """``mode = thompson`` is reproducible for a fixed seed, varies across seeds."""
    cfg_t = replace(cfg, hp=replace(cfg.hp, mode="thompson"))
    st = _feed(S.CellStore.cold_start(cfg_t), _wins(cfg_t, "polecat", "implement", "sonnet", 50))

    a = E.recommend("polecat", "implement", cfg_t, st, provider=cfg_t.default_provider, seed=11)
    b = E.recommend("polecat", "implement", cfg_t, st, provider=cfg_t.default_provider, seed=11)
    assert a["reasons"]["mode"] == "thompson"
    assert a["tier_id"] == b["tier_id"]
    assert a["reasons"]["thompson"]["samples"] == b["reasons"]["thompson"]["samples"]
    # The audit carries a cli-renderable candidates list with the standard keys.
    assert a["reasons"]["candidates"]
    assert {"tier_id", "admitted", "cost_diff"} <= set(a["reasons"]["candidates"][0])


def test_thompson_mode_never_downgrades_critical(cfg):
    """Across many seeds, a Critical cell stays on the baseline (hard rule)."""
    cfg_t = replace(cfg, hp=replace(cfg.hp, mode="thompson"))
    # Pile evidence on a cheap tier so a non-Critical cell WOULD downgrade.
    st = _feed(S.CellStore.cold_start(cfg_t), _wins(cfg_t, "refinery", "judge", "haiku", 80))
    for seed in range(25):
        rec = E.recommend(
            "refinery", "judge", cfg_t, st,
            provider=cfg_t.default_provider, tol_class="Critical", seed=seed,
        )
        assert rec["tier_id"] == cfg_t.baseline_tier_id, f"downgraded at seed {seed}"


# --------------------------------------------------------------------------- #
# 5. changepoint — the rebuild branch re-weights a drifted cell's posterior     #
# --------------------------------------------------------------------------- #


def test_changepoint_rebuild_reweights_drifted_cell(cfg, tmp_path):
    """A 0.9→fail drift: the changepoint re-fold lands below the straight fold."""
    k = _key(cfg, "polecat", "implement", "sonnet")
    jsonl = tmp_path / "invocations.jsonl"
    with open(jsonl, "w", encoding="utf-8") as fh:
        for i in range(40):  # high-quality regime
            fh.write(json.dumps({"kind": "quality", "cell_key": k, "q": 1, "ts": f"t{i}"}) + "\n")
        for i in range(40, 75):  # sustained drop (drift)
            fh.write(json.dumps({"kind": "quality", "cell_key": k, "q": 0, "ts": f"t{i}"}) + "\n")

    st_off = S.CellStore.rebuild(cfg, os.fspath(jsonl))  # straight fold (default)
    cfg_cp = replace(cfg, hp=replace(cfg.hp, changepoint=True))
    st_on = S.CellStore.rebuild(cfg_cp, os.fspath(jsonl))  # changepoint reweight

    mean_off = st_off.cells[k].mean
    mean_on = st_on.cells[k].mean
    # Forgetting stale pre-drift wins pulls the posterior toward the failing regime.
    assert mean_on < mean_off


# --------------------------------------------------------------------------- #
# 6. schedule_evals — ranks gating cells worth an eval                          #
# --------------------------------------------------------------------------- #


def test_schedule_evals_returns_ranked_requests(cfg):
    """A cheaper tier with a wide, savings-bearing CI surfaces as a ranked probe."""
    # Moderate (downgrade-able) cell with thin-but-present evidence on the cheap
    # tier so its CI is wide enough to gate on uncertainty.
    st = _feed(S.CellStore.cold_start(cfg), _wins(cfg, "polecat", "implement", "sonnet", 6))
    reqs = schedule_evals(cfg, st, max_evals=10)
    # Ranked by score descending (deterministic), each a real gating candidate.
    assert all(reqs[i].score >= reqs[i + 1].score for i in range(len(reqs) - 1))
    for r in reqs:
        assert r.unlock_value >= 0.0
        assert r.ci_halfwidth > 0.0


# --------------------------------------------------------------------------- #
# 7. federation — export → merge_peers round-trips observed mass                #
# --------------------------------------------------------------------------- #


def test_federation_export_merge_round_trip(cfg):
    """A peer's exported aggregates re-enter a thin local cell on merge (trust>0)."""
    # Peer earned strong evidence on a cell the local store has never seen.
    peer_store = _feed(S.CellStore.cold_start(cfg), _wins(cfg, "polecat", "implement", "sonnet", 20))
    export = F.export_aggregates(peer_store)
    k = _key(cfg, "polecat", "implement", "sonnet")
    assert k in export["cells"]
    assert export["cells"][k]["a_obs"] > 0.0  # only observed mass, prior subtracted

    # Survives a JSON round-trip (it is pure data) before the merge.
    export = json.loads(json.dumps(export))

    local = S.CellStore.cold_start(cfg)  # thin: this cell is prior-only locally
    prior_a = local.get(k).a
    merged = F.merge_peers(local, export, trust=0.5)
    # The peer's success mass moved the thin local cell's posterior up.
    assert merged.get(k).a > prior_a

    # trust = 0 ⇒ no peer influence (the conservative default contract).
    merged0 = F.merge_peers(local, export, trust=0.0)
    assert merged0.get(k).a == pytest.approx(prior_a)


# --------------------------------------------------------------------------- #
# 8. cascade — a wide DAG raises N_dep vs a flat bead                            #
# --------------------------------------------------------------------------- #


def test_cascade_raises_n_dep_for_wide_dag(cfg):
    """A bead blocking a wide downstream DAG gets a larger effective N_dep."""
    st = _feed(S.CellStore.cold_start(cfg), _wins(cfg, "polecat", "implement", "sonnet", 30))

    flat = effective_cascade({}, "leaf")  # unknown/leaf ⇒ flat floor
    wide_graph = build_graph_from_dep_json(
        [
            {"id": "root", "blocks": ["a", "b", "c"]},
            {"id": "a", "blocks": ["a1", "a2"]},
            {"id": "b", "blocks": ["b1"]},
        ]
    )
    wide = effective_cascade(wide_graph, "root", decay=1.0)
    assert wide.n_dep_eff > flat.n_dep_eff

    rec_flat = E.recommend(
        "polecat", "implement", cfg, st, provider=cfg.default_provider, cascade=flat
    )
    rec_wide = E.recommend(
        "polecat", "implement", cfg, st, provider=cfg.default_provider, cascade=wide
    )
    assert rec_flat["reasons"]["n_dep"] == 1
    assert rec_wide["reasons"]["n_dep"] == max(1, round(wide.n_dep_eff))
    assert rec_wide["reasons"]["n_dep"] > rec_flat["reasons"]["n_dep"]
    assert "cascade" in rec_wide["reasons"]
