"""Tests for the CC-TS engine (DESIGN.md §1, §3, §5).

Covers the load-bearing properties from the design + the explicit acceptance
checklist for this bead:

- cold-start recommends the baseline (no silent downgrade);
- a cheaper tier is admitted only after enough successful observations push its
  one-sided lower bound past ``mu* − q_tol``;
- a single failure on a thin cell keeps the baseline;
- a ``Critical`` cell never downgrades regardless of evidence;
- ``cost_delta`` + structured ``reasons`` are populated on every call;
- determinism: identical inputs -> identical output.

Plus store/cache round-trip, pooling, gate-threshold arithmetic, the safety
hatch, and the ``inspect`` surface. Fixtures are built from synthetic
``invocations.jsonl`` records keyed exactly as the engine expects.
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
from modeladvisor import engine as E  # noqa: E402
from modeladvisor import store as S  # noqa: E402
from modeladvisor.store import cell_key  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures + helpers                                                            #
# --------------------------------------------------------------------------- #


@pytest.fixture
def cfg() -> C.AdvisorConfig:
    """Default Claude haiku/sonnet/opus roster, baseline = opus."""
    return C.default_config()


def q_record(cfg, agent, shape, tier, q, *, channel="close", i=0, provider=None):
    """One synthetic ``kind=quality`` telemetry record for a cell."""
    provider = provider or cfg.default_provider
    return {
        "schema_version": "advisor.v1",
        "kind": "quality",
        "ts": f"2026-06-01T00:{i // 60:02d}:{i % 60:02d}Z",
        "bead_id": f"bh-{agent}-{shape}-{tier}-{i}",
        "cell_key": cell_key(provider, agent, shape, tier),
        "q": q,
        "channel": channel,
        "signal": "closed" if q == 1 else "reopened",
    }


def store_with(cfg, records):
    """Cold-start store with the given quality records applied."""
    st = S.CellStore.cold_start(cfg)
    st.apply_records(records)
    return st


def successes(cfg, agent, shape, tier, n, *, channel="close"):
    return [q_record(cfg, agent, shape, tier, 1, channel=channel, i=i) for i in range(n)]


def failures(cfg, agent, shape, tier, n, *, channel="close"):
    return [q_record(cfg, agent, shape, tier, 0, channel=channel, i=i) for i in range(n)]


# --------------------------------------------------------------------------- #
# Cold start: no silent downgrade                                              #
# --------------------------------------------------------------------------- #


def test_cold_start_recommends_baseline(cfg):
    st = S.CellStore.cold_start(cfg)
    rec = E.recommend("polecat", "implement", cfg, st)
    assert rec["tier_id"] == cfg.baseline_tier_id == "opus"
    assert rec["cost_delta"] == 0.0
    # No cheaper tier admitted at cold start.
    cands = {c["tier_id"]: c for c in rec["reasons"]["candidates"]}
    assert cands["haiku"]["admitted"] is False
    assert cands["sonnet"]["admitted"] is False
    assert cands["opus"]["admitted"] is True
    assert "no cheaper tier" in rec["rationale"].lower()


def test_cold_start_prior_means_are_cost_ordered(cfg):
    """DESIGN §3.2: baseline optimistic (0.8); cheaper tiers depressed & monotone."""
    a_h, b_h = S.cold_start_prior(cfg, "haiku", "opus")
    a_s, b_s = S.cold_start_prior(cfg, "sonnet", "opus")
    a_o, b_o = S.cold_start_prior(cfg, "opus", "opus")
    m_h, m_s, m_o = a_h / (a_h + b_h), a_s / (a_s + b_s), a_o / (a_o + b_o)
    assert m_h < m_s < m_o
    assert m_o == pytest.approx(0.8)
    assert m_h == pytest.approx(cfg.hp.cold_m_lo)


# --------------------------------------------------------------------------- #
# Earned admission: enough successes push q_lo past the threshold              #
# --------------------------------------------------------------------------- #


def test_cheaper_tier_admitted_only_after_enough_successes(cfg):
    # A handful of successes is NOT enough (LCB still below mu* - q_tol).
    thin = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 3))
    rec_thin = E.recommend("polecat", "implement", cfg, thin)
    assert rec_thin["tier_id"] == "opus", "thin evidence must keep baseline"

    # Many successes DO admit the cheaper tier.
    rich = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 40))
    rec_rich = E.recommend("polecat", "implement", cfg, rich)
    assert rec_rich["tier_id"] == "sonnet", "sufficient evidence must admit the cheaper tier"

    # And the admission is exactly the gate rule: q_lo >= mu* - q_tol.
    sonnet = rec_rich["reasons"]["candidates"]
    srow = next(c for c in sonnet if c["tier_id"] == "sonnet")
    thr = rec_rich["reasons"]["gate_threshold"]
    assert srow["admitted"] is True
    assert srow["q_lo"] >= thr
    # Savings recorded (cheaper than baseline -> negative cost_delta).
    assert rec_rich["cost_delta"] < 0.0


def test_admission_is_monotone_in_evidence(cfg):
    """q_lo for a tier should rise monotonically as successes accumulate."""
    prev = -1.0
    for n in (0, 5, 10, 20, 40, 80):
        st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", n))
        ins = E.inspect("polecat", "implement", cfg, st)
        srow = next(t for t in ins["tiers"] if t["tier_id"] == "sonnet")
        assert srow["q_lo"] >= prev - 1e-9
        prev = srow["q_lo"]


def test_picks_cheapest_among_admitted(cfg):
    """When both haiku and sonnet clear the gate, pick the cheapest (haiku)."""
    recs = (
        successes(cfg, "polecat", "implement", "haiku", 60)
        + successes(cfg, "polecat", "implement", "sonnet", 60)
    )
    st = store_with(cfg, recs)
    rec = E.recommend("polecat", "implement", cfg, st)
    assert rec["tier_id"] == "haiku"
    cands = {c["tier_id"]: c for c in rec["reasons"]["candidates"]}
    assert cands["haiku"]["admitted"] and cands["sonnet"]["admitted"]
    # haiku saves the most vs baseline.
    assert rec["cost_delta"] == cands["haiku"]["cost_diff"] < 0.0


# --------------------------------------------------------------------------- #
# A single failure on a thin cell keeps the baseline                          #
# --------------------------------------------------------------------------- #


def test_single_failure_on_thin_cell_keeps_baseline(cfg):
    st = store_with(cfg, failures(cfg, "polecat", "implement", "haiku", 1))
    rec = E.recommend("polecat", "implement", cfg, st)
    assert rec["tier_id"] == "opus"


def test_one_failure_after_some_successes_can_revoke_admission(cfg):
    """A late failure lowers q_lo; near the boundary it can flip back to baseline."""
    base = successes(cfg, "polecat", "implement", "sonnet", 12)
    # Without the failure, with 12 successes sonnet may or may not be admitted;
    # assert the *direction*: adding a failure never increases the recommended
    # aggressiveness (cost can only go up or stay, never further down).
    st_ok = store_with(cfg, base)
    st_bad = store_with(cfg, base + failures(cfg, "polecat", "implement", "sonnet", 1))
    rec_ok = E.recommend("polecat", "implement", cfg, st_ok)
    rec_bad = E.recommend("polecat", "implement", cfg, st_bad)
    order = list(cfg.tier_ids)
    assert order.index(rec_bad["tier_id"]) >= order.index(rec_ok["tier_id"])


# --------------------------------------------------------------------------- #
# Critical class never downgrades                                             #
# --------------------------------------------------------------------------- #


def test_critical_never_downgrades_even_with_overwhelming_evidence(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "haiku", 200))
    rec = E.recommend("polecat", "implement", cfg, st, tol_class="Critical")
    assert rec["tier_id"] == cfg.baseline_tier_id
    assert rec["reasons"]["critical"] is True
    # Every cheaper candidate is rejected with the Critical reason.
    for c in rec["reasons"]["candidates"]:
        if c["action"] == "down":
            assert c["admitted"] is False
            assert "critical" in c["reason"].lower()


def test_critical_via_config_override(cfg):
    """A per-cell [[agent.cell]] tol_class=Critical override is honoured."""
    raw = {
        "advisor": {"baseline_tier": "opus", "default_provider": "claude"},
        "tier": [
            {"id": "haiku", "rank": 1, "in_cost": 0.8, "out_cost": 4.0},
            {"id": "sonnet", "rank": 2, "in_cost": 3.0, "out_cost": 15.0},
            {"id": "opus", "rank": 3, "in_cost": 15.0, "out_cost": 75.0},
        ],
        "agent": [
            {"name": "refinery", "shapes": ["judge"],
             "cell": [{"shape": "judge", "tol_class": "Critical"}]},
        ],
    }
    cfg2 = C.from_mapping(raw)
    assert cfg2.tol_class_for("refinery", "judge").is_critical
    st = store_with(cfg2, successes(cfg2, "refinery", "judge", "haiku", 200))
    rec = E.recommend("refinery", "judge", cfg2, st)
    assert rec["tier_id"] == "opus"


# --------------------------------------------------------------------------- #
# Structured reasons + cost_delta populated on every call                     #
# --------------------------------------------------------------------------- #


def test_reasons_and_cost_delta_populated(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 40))
    rec = E.recommend("polecat", "implement", cfg, st)
    # top-level shape
    for key in ("tier_id", "model", "rationale", "cost_delta", "reasons", "posterior_summary"):
        assert key in rec
    assert isinstance(rec["rationale"], str) and rec["rationale"]
    assert isinstance(rec["cost_delta"], float)
    r = rec["reasons"]
    # the audit contract surface (DESIGN §1.4 property 3)
    for key in (
        "candidates", "advised_tier", "eval_flag", "baseline_mean",
        "gate_threshold", "class", "q_tol", "n_dep", "cell",
    ):
        assert key in r
    assert r["advised_tier"] == rec["tier_id"]
    # every candidate carries q_lo, exp_loss (or inf flag), cost_diff
    for c in r["candidates"]:
        assert "q_lo" in c and "cost_diff" in c
        assert ("exp_loss" in c) and ("exp_loss_inf" in c)
    # posterior_summary spans the whole roster
    assert set(rec["posterior_summary"]) == set(cfg.tier_ids)


def test_cost_delta_matches_rate_sheet(cfg):
    """cost_delta = -(cost(opus) - cost(sonnet)) at the implement budget."""
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 40))
    rec = E.recommend("polecat", "implement", cfg, st)
    assert rec["tier_id"] == "sonnet"
    tin, tout = cfg.budget_for("implement")
    expect = -(cfg.tier("opus").cost(tin, tout) - cfg.tier("sonnet").cost(tin, tout))
    assert rec["cost_delta"] == pytest.approx(expect, abs=1e-9)


def test_realised_token_counts_override_budget(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 40))
    rec = E.recommend("polecat", "implement", cfg, st, tok_in=10000, tok_out=5000)
    assert rec["reasons"]["representative_budget"] is False
    expect = -(cfg.tier("opus").cost(10000, 5000) - cfg.tier("sonnet").cost(10000, 5000))
    assert rec["cost_delta"] == pytest.approx(expect, abs=1e-9)


# --------------------------------------------------------------------------- #
# Determinism                                                                  #
# --------------------------------------------------------------------------- #


def test_determinism_same_inputs_same_output(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 25))
    a = E.recommend("polecat", "implement", cfg, st, seed=7)
    b = E.recommend("polecat", "implement", cfg, st, seed=7)
    assert a == b
    # Even a different seed yields the same result (v1 rule is LCB-deterministic).
    c = E.recommend("polecat", "implement", cfg, st, seed=99)
    assert a["tier_id"] == c["tier_id"]
    assert a["cost_delta"] == c["cost_delta"]


def test_inspect_is_deterministic(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 25))
    assert E.inspect("polecat", "implement", cfg, st) == E.inspect("polecat", "implement", cfg, st)


# --------------------------------------------------------------------------- #
# Gate arithmetic + LCB                                                       #
# --------------------------------------------------------------------------- #


def test_wilson_lcb_formula():
    cell = S.Cell(a=8.0, b=2.0)  # mean 0.8
    z = 1.645
    expected = max(0.0, cell.mean - z * cell.stderr)
    assert E.wilson_lcb(cell, z) == pytest.approx(expected)


def test_wilson_lcb_floored_at_zero():
    cell = S.Cell(a=1.0, b=1.0)  # mean 0.5, big sd
    assert E.wilson_lcb(cell, 5.0) == 0.0


def test_gate_threshold_is_mu_star_minus_qtol(cfg):
    st = S.CellStore.cold_start(cfg)
    rec = E.recommend("polecat", "implement", cfg, st)
    mu_star = rec["reasons"]["baseline_mean"]
    q_tol = rec["reasons"]["q_tol"]
    assert rec["reasons"]["gate_threshold"] == pytest.approx(mu_star - q_tol)


# --------------------------------------------------------------------------- #
# Safety hatch (force_baseline)                                               #
# --------------------------------------------------------------------------- #


def test_force_baseline_disables_downgrade(cfg):
    raw = {
        "advisor": {"baseline_tier": "opus"},
        "tier": [
            {"id": "haiku", "rank": 1, "in_cost": 0.8, "out_cost": 4.0},
            {"id": "sonnet", "rank": 2, "in_cost": 3.0, "out_cost": 15.0},
            {"id": "opus", "rank": 3, "in_cost": 15.0, "out_cost": 75.0},
        ],
        "agent": [
            {"name": "polecat", "shapes": ["implement"],
             "cell": [{"shape": "implement", "force_baseline": True}]},
        ],
    }
    cfg2 = C.from_mapping(raw)
    st = store_with(cfg2, successes(cfg2, "polecat", "implement", "haiku", 200))
    rec = E.recommend("polecat", "implement", cfg2, st)
    assert rec["tier_id"] == "opus"
    assert rec["reasons"]["forced_baseline"] is True
    assert "safety hatch" in rec["rationale"].lower()


# --------------------------------------------------------------------------- #
# inspect surface                                                             #
# --------------------------------------------------------------------------- #


def test_inspect_reports_per_tier_and_drop_ci(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 5))
    ins = E.inspect("polecat", "implement", cfg, st)
    assert {t["tier_id"] for t in ins["tiers"]} == set(cfg.tier_ids)
    for t in ins["tiers"]:
        for k in ("a", "b", "mean", "q_lo", "n", "ci_halfwidth", "admitted"):
            assert k in t
        if t["role"] == "candidate":
            assert t["quality_drop_ci"] is not None
            assert {"lo", "mean", "hi", "q_tol", "exceeds_tol"} <= set(t["quality_drop_ci"])
        else:
            assert t["quality_drop_ci"] is None


def test_inspect_widest_gating_cell_points_at_widest_rejected(cfg):
    # A few sonnet obs -> both cheaper cells gating; haiku (no data) is widest.
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 3))
    ins = E.inspect("polecat", "implement", cfg, st)
    wg = ins["widest_gating_cell"]
    assert wg is not None
    # It must be a rejected candidate with the widest CI half-width.
    cand_hw = {
        t["tier_id"]: t["ci_halfwidth"]
        for t in ins["tiers"]
        if t["role"] == "candidate" and not t["admitted"] and t["ci_halfwidth"] > cfg.hp.theta_eval
    }
    assert wg["tier_id"] == max(cand_hw, key=cand_hw.get)
    assert "run an eval" in wg["rationale"]


def test_inspect_no_gating_cell_when_admitted(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "haiku", 80))
    ins = E.inspect("polecat", "implement", cfg, st)
    # haiku admitted (lots of evidence) -> it is not "gating".
    assert ins["widest_gating_cell"] is None or ins["widest_gating_cell"]["tier_id"] != "haiku"


# --------------------------------------------------------------------------- #
# Store: cache round-trip == rebuild from JSONL                               #
# --------------------------------------------------------------------------- #


def test_cache_rebuild_equivalence(cfg, tmp_path):
    recs = (
        successes(cfg, "polecat", "implement", "sonnet", 30)
        + failures(cfg, "polecat", "implement", "haiku", 4)
        + successes(cfg, "mayor", "judge", "sonnet", 10)
    )
    jsonl = tmp_path / "invocations.jsonl"
    jsonl.write_text("".join(json.dumps(r) + "\n" for r in recs))

    rebuilt = S.CellStore.rebuild(cfg, str(jsonl))
    cache = tmp_path / "advisor-cells.json"
    rebuilt.save(str(cache))
    loaded = S.CellStore.load(cfg, str(cache))

    def snap(st):
        return {
            k: (round(v.a, 9), round(v.b, 9), v.n)
            for k, v in st.observed_cells().items()
        }

    assert snap(rebuilt) == snap(loaded)
    # recommendations identical from either store
    assert (
        E.recommend("polecat", "implement", cfg, rebuilt)["tier_id"]
        == E.recommend("polecat", "implement", cfg, loaded)["tier_id"]
    )


def test_cache_is_byte_stable(cfg, tmp_path):
    recs = successes(cfg, "polecat", "implement", "sonnet", 12)
    st = store_with(cfg, recs)
    c1 = tmp_path / "a.json"
    c2 = tmp_path / "b.json"
    st.save(str(c1))
    S.CellStore.load(cfg, str(c1)).save(str(c2))
    assert c1.read_text() == c2.read_text()


def test_replay_order_independence_of_final_posterior(cfg, tmp_path):
    """Beta updates are additive -> final (a,b) is order-independent."""
    recs = (
        successes(cfg, "polecat", "implement", "sonnet", 7)
        + failures(cfg, "polecat", "implement", "sonnet", 3)
    )
    fwd = store_with(cfg, recs)
    rev = store_with(cfg, list(reversed(recs)))
    k = cell_key(cfg.default_provider, "polecat", "implement", "sonnet")
    assert (fwd.get(k).a, fwd.get(k).b, fwd.get(k).n) == (rev.get(k).a, rev.get(k).b, rev.get(k).n)


# --------------------------------------------------------------------------- #
# Channel weights                                                             #
# --------------------------------------------------------------------------- #


def test_review_channel_weighted_higher_than_close(cfg):
    """A review success (w=3) moves the posterior ~3x a close success (w=1)."""
    one_review = store_with(cfg, [q_record(cfg, "polecat", "implement", "sonnet", 1, channel="review")])
    k = cell_key(cfg.default_provider, "polecat", "implement", "sonnet")
    a0, b0 = S.cold_start_prior(cfg, "sonnet", "opus")
    cell = one_review.get(k)
    # a increased by w_review (=3); b unchanged.
    assert cell.a == pytest.approx(a0 + cfg.hp.w_review)
    assert cell.b == pytest.approx(b0)


def test_explicit_weight_overrides_channel(cfg):
    rec = {"kind": "quality", "cell_key": cell_key(cfg.default_provider, "polecat", "implement", "sonnet"),
           "q": 1, "channel": "close", "weight": 5, "ts": "2026-06-01T00:00:00Z"}
    st = store_with(cfg, [rec])
    a0, _ = S.cold_start_prior(cfg, "sonnet", "opus")
    assert st.get(rec["cell_key"]).a == pytest.approx(a0 + 5)


def test_non_binary_q_is_dropped(cfg):
    bad = {"kind": "quality", "cell_key": cell_key(cfg.default_provider, "polecat", "implement", "sonnet"),
           "q": 0.5, "ts": "2026-06-01T00:00:00Z"}
    st = store_with(cfg, [bad])
    assert st.get(bad["cell_key"]).n == 0


# --------------------------------------------------------------------------- #
# Config validation                                                           #
# --------------------------------------------------------------------------- #


def test_config_rejects_duplicate_tier_ids():
    raw = {"tier": [
        {"id": "x", "rank": 1, "in_cost": 1, "out_cost": 1},
        {"id": "x", "rank": 2, "in_cost": 2, "out_cost": 2},
    ]}
    with pytest.raises(C.ConfigError):
        C.from_mapping(raw)


def test_config_rejects_unknown_baseline():
    raw = {"advisor": {"baseline_tier": "nope"},
           "tier": [{"id": "x", "rank": 1, "in_cost": 1, "out_cost": 1}]}
    with pytest.raises(C.ConfigError):
        C.from_mapping(raw)


def test_config_sorts_roster_by_cost_order():
    raw = {"tier": [
        {"id": "opus", "rank": 3, "in_cost": 15, "out_cost": 75},
        {"id": "haiku", "rank": 1, "in_cost": 0.8, "out_cost": 4},
        {"id": "sonnet", "rank": 2, "in_cost": 3, "out_cost": 15},
    ]}
    cfg = C.from_mapping(raw)
    assert cfg.tier_ids == ("haiku", "sonnet", "opus")
    assert cfg.baseline_tier_id == "opus"  # default = most-capable


def test_arbitrary_k_tiers():
    """Nothing assumes K=3: a 2-tier and a 5-tier roster both work."""
    two = C.from_mapping({"tier": [
        {"id": "cheap", "rank": 1, "in_cost": 1, "out_cost": 1},
        {"id": "dear", "rank": 2, "in_cost": 9, "out_cost": 9},
    ]})
    assert two.tier_ids == ("cheap", "dear")
    st = S.CellStore.cold_start(two)
    rec = E.recommend("polecat", "implement", two, st)
    assert rec["tier_id"] == "dear"  # baseline

    five = C.from_mapping({"tier": [
        {"id": f"t{i}", "rank": i, "in_cost": float(i), "out_cost": float(i)} for i in range(1, 6)
    ]})
    assert len(five.tier_ids) == 5
    st5 = S.CellStore.cold_start(five)
    rec5 = E.recommend("polecat", "implement", five, st5)
    assert rec5["tier_id"] == "t5"


def test_sample_toml_parses_and_is_consistent(tmp_path):
    p = tmp_path / "advisor.toml"
    C.write_sample_toml(str(p))
    cfg = C.load_config(str(p))
    assert cfg.tier_ids == ("haiku", "sonnet", "opus")
    assert cfg.baseline_tier_id == "opus"
    assert cfg.tol_class_for("refinery", "judge").is_critical  # pinned in the sample
    assert cfg.budget_for("implement") == (4000.0, 1500.0)
