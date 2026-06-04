"""Tests for Layer-4 auto-scheduled eval (``modeladvisor.evalsched``, DESIGN §5.4).

Covers bead ``bh-0r9``'s acceptance:

- ``schedule_evals`` ranks a wide, high-savings gating cell above a wide but
  low-savings one (``score = ci_halfwidth × unlock_value``);
- it respects ``max_evals`` (the eval budget);
- it skips cells whose CI half-width is at or below ``theta_eval``;
- ``unlock_value`` is the *real* tier-cost differential at the shape budget;
- a fully-admitted / tight cell produces NO eval request;
- ``emit_eval_beads(dry_run=True)`` returns command strings and creates NOTHING
  (asserted by making ``subprocess.run`` explode if it is ever called);
- determinism: identical inputs → byte-identical schedules.

Fixtures are built exactly as ``test_engine.py`` builds them (a ``from_mapping``
config + a cold-start ``CellStore`` fed synthetic ``kind=quality`` records). The
two shapes share an identical cold-start posterior shape but very different
representative token budgets, so their gating cells have the SAME CI half-width
and differ ONLY in unlock-value — isolating the ranking signal.
"""

from __future__ import annotations

import os
import sys

import pytest

# Make the pack root importable when pytest is run from anywhere (as test_engine).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modeladvisor import config as C  # noqa: E402
from modeladvisor import engine as E  # noqa: E402
from modeladvisor import evalsched as V  # noqa: E402
from modeladvisor import store as S  # noqa: E402
from modeladvisor.store import cell_key  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures + helpers                                                            #
# --------------------------------------------------------------------------- #

# One agent, two shapes. Roster haiku ≺ sonnet ≺ opus, baseline opus.
#   implement: HUGE representative budget  -> big unlock-value
#   lookup:    TINY representative budget  -> tiny unlock-value
# Both cold-start cheaper tiers gate on uncertainty with the SAME CI half-width
# (posterior shape is budget-independent), so the schedule's ordering is driven
# purely by unlock-value -> this is the clean ranking test.
_RAW = {
    "advisor": {"baseline_tier": "opus", "default_provider": "claude"},
    "tier": [
        {"id": "haiku", "rank": 1, "in_cost": 0.80, "out_cost": 4.00,
         "model": "claude-haiku-4-5"},
        {"id": "sonnet", "rank": 2, "in_cost": 3.00, "out_cost": 15.00,
         "model": "claude-sonnet-4-5"},
        {"id": "opus", "rank": 3, "in_cost": 15.00, "out_cost": 75.00,
         "model": "claude-opus-4-8"},
    ],
    "shape": [
        {"name": "implement", "tol_class": "Moderate",
         "tok_in": 100_000, "tok_out": 40_000},
        {"name": "lookup", "tol_class": "Lenient", "tok_in": 100, "tok_out": 50},
    ],
    "agent": [{"name": "polecat", "shapes": ["implement", "lookup"]}],
}


@pytest.fixture
def cfg() -> C.AdvisorConfig:
    """Single-agent (polecat) config; the only agent_shapes entry we assert on.

    NB: ``from_mapping`` re-injects the documented default agents for any agent it
    didn't mention, so ``cfg.agent_shapes`` also contains mayor/witness/etc. The
    scheduler sweeps all of them; tests filter to the polecat cells they pin.
    """
    return C.from_mapping(_RAW)


def q_record(cfg, agent, shape, tier, q, *, channel="close", i=0):
    """One synthetic ``kind=quality`` telemetry record (as in test_engine)."""
    return {
        "schema_version": "advisor.v1",
        "kind": "quality",
        "ts": f"2026-06-01T00:{i // 60:02d}:{i % 60:02d}Z",
        "bead_id": f"bh-{agent}-{shape}-{tier}-{i}",
        "cell_key": cell_key(cfg.default_provider, agent, shape, tier),
        "q": q,
        "channel": channel,
    }


def successes(cfg, agent, shape, tier, n, *, channel="close"):
    return [q_record(cfg, agent, shape, tier, 1, channel=channel, i=i) for i in range(n)]


def store_with(cfg, records):
    st = S.CellStore.cold_start(cfg)
    st.apply_records(records)
    return st


def polecat_reqs(reqs):
    """Just the polecat requests, keyed by shape (drops defaulted sibling agents)."""
    return {r.shape: r for r in reqs if r.agent == "polecat"}


# --------------------------------------------------------------------------- #
# Ranking: wide + high-savings beats wide + low-savings                        #
# --------------------------------------------------------------------------- #


def test_ranks_wide_high_savings_cell_first(cfg):
    """At cold start both shapes gate with equal CI half-width; the big-budget
    (high unlock-value) cell must rank strictly above the tiny-budget one."""
    st = S.CellStore.cold_start(cfg)
    reqs = V.schedule_evals(cfg, st, max_evals=99)
    by_shape = polecat_reqs(reqs)

    assert {"implement", "lookup"} <= set(by_shape)
    impl, look = by_shape["implement"], by_shape["lookup"]

    # Same posterior shape -> same CI half-width; ranking is pure unlock-value.
    assert impl.ci_halfwidth == pytest.approx(look.ci_halfwidth)
    assert impl.unlock_value > look.unlock_value
    assert impl.score > look.score

    # And the global ordering puts the implement cell ahead of the lookup cell.
    order = [r.cell_key for r in reqs]
    assert order.index(impl.cell_key) < order.index(look.cell_key)
    # The single highest-scoring request overall is an `implement` cell.
    assert reqs[0].shape == "implement"


def test_schedule_sorted_by_score_descending(cfg):
    """The returned list is monotone non-increasing in score (the ranking key)."""
    st = S.CellStore.cold_start(cfg)
    reqs = V.schedule_evals(cfg, st, max_evals=99)
    scores = [r.score for r in reqs]
    assert scores == sorted(scores, reverse=True)
    assert len(reqs) >= 2  # several gating cells exist at cold start


# --------------------------------------------------------------------------- #
# unlock_value is the real tier-cost differential at the shape budget          #
# --------------------------------------------------------------------------- #


def test_unlock_value_from_real_tier_costs(cfg):
    """unlock_value == cost(baseline) − cost(candidate) at the shape budget."""
    st = S.CellStore.cold_start(cfg)
    reqs = polecat_reqs(V.schedule_evals(cfg, st, max_evals=99))
    impl = reqs["implement"]

    # Cheapest tier (haiku) is the widest cold-start gating candidate.
    assert impl.tier_id == "haiku"
    tin, tout = cfg.budget_for("implement")
    expect = cfg.tier("opus").cost(tin, tout) - cfg.tier("haiku").cost(tin, tout)
    assert impl.unlock_value == pytest.approx(expect)
    assert impl.score == pytest.approx(impl.ci_halfwidth * expect)
    assert impl.unlock_value > 0.0  # a downgrade always saves


def test_cell_key_and_fields_consistent(cfg):
    """The request's cell_key matches its (provider, agent, shape, tier) fields."""
    st = S.CellStore.cold_start(cfg)
    impl = polecat_reqs(V.schedule_evals(cfg, st, max_evals=99))["implement"]
    assert impl.cell_key == cell_key(impl.provider, impl.agent, impl.shape, impl.tier_id)
    assert impl.provider == "claude"


# --------------------------------------------------------------------------- #
# max_evals (the eval budget)                                                  #
# --------------------------------------------------------------------------- #


def test_respects_max_evals(cfg):
    st = S.CellStore.cold_start(cfg)
    full = V.schedule_evals(cfg, st, max_evals=99)
    assert len(full) > 1  # there are several gating cells across the roster

    top1 = V.schedule_evals(cfg, st, max_evals=1)
    assert len(top1) == 1
    # max_evals keeps the HIGHEST-scoring request (a high-unlock implement cell).
    assert top1[0].cell_key == full[0].cell_key
    assert top1[0].score == max(r.score for r in full)

    top3 = V.schedule_evals(cfg, st, max_evals=3)
    assert len(top3) == 3
    assert [r.cell_key for r in top3] == [r.cell_key for r in full[:3]]


def test_max_evals_zero_or_negative_returns_empty(cfg):
    st = S.CellStore.cold_start(cfg)
    assert V.schedule_evals(cfg, st, max_evals=0) == []
    assert V.schedule_evals(cfg, st, max_evals=-5) == []


# --------------------------------------------------------------------------- #
# theta_eval: sub-threshold cells are skipped                                  #
# --------------------------------------------------------------------------- #


def test_skips_cells_at_or_below_theta_eval(cfg):
    """A theta_eval above every gating cell's CI half-width schedules nothing."""
    st = S.CellStore.cold_start(cfg)
    # Cold-start gating cells have CI half-width ~0.37; a theta_eval of 1.0 is
    # above any possible half-width (the CI half-width is bounded by ~0.5).
    assert V.schedule_evals(cfg, st, theta_eval=1.0) == []

    # The default (cfg.hp.theta_eval = 0.10) does schedule them.
    assert len(V.schedule_evals(cfg, st)) > 0


def test_stricter_theta_eval_prunes_narrow_cells(cfg):
    """Raising theta_eval can only shrink (never grow) the scheduled set."""
    st = S.CellStore.cold_start(cfg)
    base = V.schedule_evals(cfg, st, max_evals=99, theta_eval=cfg.hp.theta_eval)
    strict = V.schedule_evals(cfg, st, max_evals=99, theta_eval=0.30)
    base_keys = {r.cell_key for r in base}
    strict_keys = {r.cell_key for r in strict}
    assert strict_keys <= base_keys
    # Every surviving cell is strictly wider than the (stricter) threshold.
    assert all(r.ci_halfwidth > 0.30 for r in strict)


def test_theta_eval_defaults_to_config(cfg):
    """Passing theta_eval=None is identical to passing cfg.hp.theta_eval."""
    st = S.CellStore.cold_start(cfg)
    a = V.schedule_evals(cfg, st, max_evals=99, theta_eval=None)
    b = V.schedule_evals(cfg, st, max_evals=99, theta_eval=cfg.hp.theta_eval)
    assert [r.to_dict() for r in a] == [r.to_dict() for r in b]


# --------------------------------------------------------------------------- #
# A tight / fully-admitted cell schedules no eval                             #
# --------------------------------------------------------------------------- #


def test_admitted_tight_cell_produces_no_request(cfg):
    """When every cheaper tier on a shape is admitted (tight CIs), that shape is
    not gating and yields no eval request."""
    # Admit BOTH haiku and sonnet on lookup -> no candidate is gating.
    recs = (
        successes(cfg, "polecat", "lookup", "haiku", 120)
        + successes(cfg, "polecat", "lookup", "sonnet", 120)
    )
    st = store_with(cfg, recs)

    # Sanity: the engine itself reports no widest-gating cell for that pair.
    assert E.inspect("polecat", "lookup", cfg, st)["widest_gating_cell"] is None

    reqs = V.schedule_evals(cfg, st, max_evals=99)
    assert "lookup" not in polecat_reqs(reqs)
    # polecat/implement is still cold -> still gating, still scheduled.
    assert "implement" in polecat_reqs(reqs)


# --------------------------------------------------------------------------- #
# emit_eval_beads: dry-run returns commands and creates NOTHING                 #
# --------------------------------------------------------------------------- #


def test_emit_dry_run_returns_commands_and_runs_nothing(cfg, monkeypatch):
    """dry_run=True must return command strings and never invoke subprocess."""
    # Make ANY subprocess call explode — proves the dry-run path shells out to
    # nothing (creates no beads).
    def _boom(*a, **k):  # pragma: no cover - asserted not to run
        raise AssertionError("emit_eval_beads(dry_run=True) must not run subprocess")

    monkeypatch.setattr(V.subprocess, "run", _boom)

    st = S.CellStore.cold_start(cfg)
    reqs = V.schedule_evals(cfg, st, max_evals=3)
    cmds = V.emit_eval_beads(reqs, dry_run=True)

    assert len(cmds) == len(reqs)
    for cmd, req in zip(cmds, reqs):
        assert isinstance(cmd, str)
        assert cmd.startswith("gc bd create ")
        assert "-t task" in cmd
        assert f"-l {V.EVAL_LABEL}" in cmd
        assert "--silent" in cmd
        # The title embeds the cell + the unlock economics.
        assert req.cell_key in cmd
        assert "CI hw" in cmd and "unlocks $" in cmd


def test_emit_dry_run_is_default(cfg, monkeypatch):
    """dry_run defaults to True (safe): no subprocess even without the kwarg."""
    monkeypatch.setattr(
        V.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    st = S.CellStore.cold_start(cfg)
    cmds = V.emit_eval_beads(V.schedule_evals(cfg, st, max_evals=2))
    assert all(c.startswith("gc bd create ") for c in cmds)


def test_emit_dry_run_threads_rig(cfg):
    """A rig is threaded into the command as `--rig <rig>`."""
    st = S.CellStore.cold_start(cfg)
    reqs = V.schedule_evals(cfg, st, max_evals=1)
    cmds = V.emit_eval_beads(reqs, dry_run=True, rig="frontend")
    assert "--rig frontend" in cmds[0]
    # No rig -> no --rig flag.
    assert "--rig" not in V.emit_eval_beads(reqs, dry_run=True)[0]


def test_emit_empty_requests_is_noop(cfg, monkeypatch):
    monkeypatch.setattr(
        V.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert V.emit_eval_beads([], dry_run=True) == []
    assert V.emit_eval_beads([], dry_run=False) == []


def test_emit_apply_parses_bead_ids(cfg, monkeypatch):
    """dry_run=False shells out once per request and returns the created ids."""
    calls = []

    class _Proc:
        def __init__(self, out):
            self.stdout = out
            self.stderr = ""

    def _fake_run(argv, **kw):
        calls.append(argv)
        # gc bd create --silent prints just the new id.
        return _Proc(f"bh-eval-{len(calls)}\n")

    monkeypatch.setattr(V.subprocess, "run", _fake_run)

    st = S.CellStore.cold_start(cfg)
    reqs = V.schedule_evals(cfg, st, max_evals=2)
    ids = V.emit_eval_beads(reqs, dry_run=False)

    assert ids == ["bh-eval-1", "bh-eval-2"]
    assert len(calls) == 2
    # Each call is a real gc bd create argv (list form, not a shell string).
    for argv in calls:
        assert argv[:3] == ["gc", "bd", "create"]
        assert "--silent" in argv


# --------------------------------------------------------------------------- #
# Determinism                                                                  #
# --------------------------------------------------------------------------- #


def test_schedule_is_deterministic(cfg):
    st = store_with(cfg, successes(cfg, "polecat", "implement", "sonnet", 7))
    a = V.schedule_evals(cfg, st, max_evals=99)
    b = V.schedule_evals(cfg, st, max_evals=99)
    assert [r.to_dict() for r in a] == [r.to_dict() for r in b]
    # Stable order even across the tie-break (sorted by (-score, cell_key)).
    keys = [r.cell_key for r in a]
    assert keys == sorted(set(keys), key=lambda k: ([-r.score for r in a if r.cell_key == k][0], k))


def test_emit_dry_run_is_deterministic(cfg):
    st = S.CellStore.cold_start(cfg)
    reqs = V.schedule_evals(cfg, st, max_evals=4)
    assert V.emit_eval_beads(reqs, dry_run=True) == V.emit_eval_beads(reqs, dry_run=True)
