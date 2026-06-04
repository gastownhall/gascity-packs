"""Tests for per-agent auto-apply (``modeladvisor.autoapply`` + the CLI surface).

These exercise the **real** engine/store/config (auto-apply is defined in terms
of the engine's gate, so the realistic contract is the point) against a
multi-agent TEMP ``advisor.toml`` + synthetic ``invocations.jsonl``.

Safety: NOTHING here touches live ``/Users/jayse/Code`` config. Every config /
telemetry / city file is created under ``tmp_path``; the resolver is pointed at
the temp ``city.toml`` via ``$ADVISOR_AGENT_TOML`` (the same hook the apply tests
use) and the engine state via ``$ADVISOR_TOML`` / ``$ADVISOR_TELEMETRY_DIR``.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

PACK_DIR = Path(__file__).resolve().parents[1]

# Import the real engine modules. If the sibling bead isn't present, skip the
# whole file (mirrors test_cli's real-engine gate) — auto-apply has no meaning
# without the engine.
try:
    from modeladvisor import autoapply
    from modeladvisor import config as madconfig
    from modeladvisor import engine as madengine
    from modeladvisor import store as madstore
    _HAVE = True
except Exception:  # pragma: no cover - engine not landed
    _HAVE = False

pytestmark = pytest.mark.skipif(not _HAVE, reason="sibling engine/store/config not present")


# Load cli.py standalone (bypassing package __init__ re-exports), as test_cli does.
def _load_cli_module():
    spec = importlib.util.spec_from_file_location(
        "mad_cli_under_test_aa", PACK_DIR / "modeladvisor" / "cli.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mad_cli_under_test_aa"] = mod
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli_module() if _HAVE else None


# --------------------------------------------------------------------------- #
# Fixtures: a multi-agent temp config + synthetic telemetry
# --------------------------------------------------------------------------- #

# A self-contained advisor.toml. Roster haiku ≺ sonnet ≺ opus, baseline opus.
# refinery/judge is pinned Critical; mayor/judge has a force_baseline cell so we
# can exercise BOTH block paths. polecat → {implement, lookup}.
ADVISOR_TOML = """
[advisor]
default_provider = "claude"
baseline_tier = "opus"

[[tier]]
id = "haiku"
provider = "claude"
model = "claude-haiku-4-5"
run_target = "claude-haiku"
rank = 1
in_cost = 0.80
out_cost = 4.00

[[tier]]
id = "sonnet"
provider = "claude"
model = "claude-sonnet-4-5"
run_target = "claude-sonnet"
rank = 2
in_cost = 3.00
out_cost = 15.00

[[tier]]
id = "opus"
provider = "claude"
model = "claude-opus-4-8"
run_target = "claude-opus"
rank = 3
in_cost = 15.00
out_cost = 75.00

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

[[shape]]
name = "lookup"
tol_class = "Lenient"
[[shape]]
name = "implement"
tol_class = "Moderate"
[[shape]]
name = "judge"
tol_class = "Moderate"
[[shape]]
name = "review"
tol_class = "Strict"
[[shape]]
name = "patrol"
tol_class = "Lenient"

[[agent]]
name = "polecat"
shapes = ["implement", "lookup"]

[[agent]]
name = "refinery"
shapes = ["review", "judge"]
  [[agent.cell]]
  shape = "judge"
  tol_class = "Critical"

[[agent]]
name = "mayor"
shapes = ["judge", "implement", "lookup"]
  [[agent.cell]]
  shape = "judge"
  force_baseline = true

[[agent]]
name = "witness"
shapes = ["patrol", "judge"]

[[agent]]
name = "boot"
shapes = ["patrol", "judge"]

[[agent]]
name = "deacon"
shapes = ["patrol", "judge"]
"""

# The base agents the config declares (auto-apply sweeps all of these).
ALL_AGENTS = ("boot", "deacon", "mayor", "polecat", "refinery", "witness")


def _city_toml(agents=ALL_AGENTS) -> str:
    """A city.toml with an [[agent]] block per agent so every one resolves."""
    out = ['[workspace]', 'provider = "claude"', ""]
    for a in agents:
        out += [f'[[agent]]', f'name = "{a}"', 'scope = "rig"', ""]
    return "\n".join(out)


def _wins(cell_key: str, n: int, channel: str = "close") -> list:
    return [
        {"kind": "quality", "cell_key": cell_key, "q": 1, "channel": channel, "ts": "2026-01-01T00:00:00Z"}
        for _ in range(n)
    ]


def _build_store(cfg, records):
    st = madstore.CellStore.cold_start(cfg)
    st.apply_records(records)
    return st


def _cfg():
    import tomllib
    return madconfig.from_mapping(tomllib.loads(ADVISOR_TOML))


@pytest.fixture
def cfg():
    return _cfg()


@pytest.fixture
def city(tmp_path):
    p = tmp_path / "city.toml"
    p.write_text(_city_toml(), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Policy unit tests (decide_agent — pure, no file I/O)
# --------------------------------------------------------------------------- #

def test_safest_across_shapes_takes_most_capable(cfg):
    """polecat: implement→sonnet but lookup still cold → conservative tier = opus."""
    st = _build_store(cfg, _wins("claude::polecat::implement::sonnet", 60))
    d = autoapply.decide_agent("polecat", cfg, st, madengine, provider="claude")
    assert d.per_shape["implement"] == "sonnet"
    assert d.per_shape["lookup"] == "opus"  # cold
    # safest (most-capable) across shapes is opus — no shape may be under-served.
    assert d.chosen_tier == "opus"
    assert d.binding_shape == "lookup"


def test_safest_across_shapes_downgrades_when_all_clear(cfg):
    """polecat: BOTH shapes strong on sonnet → conservative tier = sonnet."""
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    st = _build_store(cfg, recs)
    d = autoapply.decide_agent("polecat", cfg, st, madengine, provider="claude")
    assert d.per_shape == {"implement": "sonnet", "lookup": "sonnet"}
    assert d.chosen_tier == "sonnet"


def test_critical_agent_blocked(cfg):
    """refinery has a Critical judge shape → blocked even with huge sonnet evidence."""
    recs = _wins("claude::refinery::review::sonnet", 80, channel="review") + _wins(
        "claude::refinery::judge::sonnet", 80, channel="eval"
    )
    st = _build_store(cfg, recs)
    d = autoapply.decide_agent("refinery", cfg, st, madengine, provider="claude")
    assert d.status == autoapply.STATUS_BLOCKED
    assert d.critical is True
    assert "judge" in d.reason


def test_force_baseline_agent_blocked(cfg):
    """mayor has a force_baseline judge cell → blocked from auto-apply."""
    st = _build_store(cfg, [])
    d = autoapply.decide_agent("mayor", cfg, st, madengine, provider="claude")
    assert d.status == autoapply.STATUS_BLOCKED
    assert d.critical is True


# --------------------------------------------------------------------------- #
# Sweep: dry-run writes nothing
# --------------------------------------------------------------------------- #

def test_dry_run_writes_nothing(monkeypatch, cfg, city, tmp_path):
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(city))
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    st = _build_store(cfg, recs)
    before = city.read_text()

    rep = autoapply.auto_apply(cfg, st, dry_run=True, engine=madengine)

    # polecat would change to sonnet; refinery+mayor blocked; cold ones no-op.
    pole = next(d for d in rep.decisions if d.agent == "polecat")
    assert pole.status == autoapply.STATUS_DRYRUN
    assert pole.chosen_model == "claude-sonnet-4-5"
    assert {d.agent for d in rep.decisions if d.status == autoapply.STATUS_BLOCKED} == {
        "refinery",
        "mayor",
    }
    # NOTHING written, no backup.
    assert city.read_text() == before
    assert not list(tmp_path.glob("*advisor-bak*"))
    assert rep.dry_run is True


# --------------------------------------------------------------------------- #
# Sweep: only evidence-strong changes are applied; thin + Critical untouched
# --------------------------------------------------------------------------- #

def test_apply_only_evidence_strong(monkeypatch, cfg, city, tmp_path):
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(city))
    # Strong on BOTH polecat shapes (→ sonnet). refinery review strong but judge
    # Critical (→ blocked). Everyone else cold (→ no-op on baseline).
    recs = (
        _wins("claude::polecat::implement::sonnet", 60)
        + _wins("claude::polecat::lookup::sonnet", 60)
        + _wins("claude::refinery::review::sonnet", 60, channel="review")
    )
    st = _build_store(cfg, recs)

    rep = autoapply.auto_apply(cfg, st, dry_run=False, engine=madengine)

    by = {d.agent: d for d in rep.decisions}
    # Exactly one applied: polecat → sonnet.
    assert by["polecat"].status == autoapply.STATUS_APPLIED
    assert by["polecat"].chosen_model == "claude-sonnet-4-5"
    assert by["polecat"].direction in (None, "set", "down")
    # Critical / force_baseline agents blocked, never written.
    assert by["refinery"].status == autoapply.STATUS_BLOCKED
    assert by["mayor"].status == autoapply.STATUS_BLOCKED
    # Cold agents: no-op (conservative tier is the baseline, nothing to write).
    for a in ("boot", "deacon", "witness"):
        assert by[a].status == autoapply.STATUS_NOOP

    # Only one applied across the whole sweep.
    assert rep.count(autoapply.STATUS_APPLIED) == 1
    # The city.toml gained exactly one model line (polecat's), inside its block.
    text = city.read_text()
    assert text.count("model = ") == 1
    assert 'model = "claude-sonnet-4-5"' in text
    pol_idx = text.index('name = "polecat"')
    model_idx = text.index('model = "claude-sonnet-4-5"')
    ref_idx = text.index('name = "refinery"')
    assert model_idx > pol_idx and model_idx < ref_idx  # inside polecat's block


def test_thin_evidence_is_not_downgraded(monkeypatch, cfg, city):
    """A few wins on one shape must NOT downgrade the agent (gate withholds)."""
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(city))
    # Only 3 sonnet wins on implement; lookup cold. Far below the gate.
    st = _build_store(cfg, _wins("claude::polecat::implement::sonnet", 3))
    rep = autoapply.auto_apply(cfg, st, dry_run=False, engine=madengine)
    pole = next(d for d in rep.decisions if d.agent == "polecat")
    # Conservative tier stays opus (baseline); reported as a no-op, nothing written.
    assert pole.chosen_tier == "opus"
    assert pole.status == autoapply.STATUS_NOOP
    assert city.read_text().count("model = ") == 0


# --------------------------------------------------------------------------- #
# Real apply: byte-preserving edit + single backup; idempotence
# --------------------------------------------------------------------------- #

def test_real_apply_is_byte_preserving_and_backs_up(monkeypatch, cfg, tmp_path):
    """A flat per-agent agent.toml: the routing triple is surgically inserted.

    Applying a tier now sets the full cross-provider routing target — provider +
    model + run_target — so a Codex tier actually runs on Codex.  The edit stays
    byte-preserving: the three lines are inserted and the rest of the file is
    untouched.
    """
    flat = (
        'scope = "rig"\n'
        'wake_mode = "fresh"\n'
        "idle_timeout = \"2h\"\n"
        "max_active_sessions = 5\n"
    )
    agent_toml = tmp_path / "agent.toml"
    agent_toml.write_text(flat, encoding="utf-8")
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(agent_toml))

    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    st = _build_store(cfg, recs)

    rep = autoapply.auto_apply(
        cfg, st, dry_run=False, agents=["polecat"], engine=madengine
    )
    d = rep.decisions[0]
    assert d.status == autoapply.STATUS_APPLIED
    assert d.backup_path is not None

    updated = agent_toml.read_text()
    # Surgical insert: original lines byte-for-byte present; the full sonnet
    # routing triple written exactly once each.
    assert 'scope = "rig"' in updated
    assert 'wake_mode = "fresh"' in updated
    assert "max_active_sessions = 5" in updated
    assert updated.count("model = ") == 1
    assert updated.count("provider = ") == 1
    assert updated.count("run_target = ") == 1
    assert 'model = "claude-sonnet-4-5"' in updated
    assert 'provider = "claude"' in updated
    assert 'run_target = "claude-sonnet"' in updated
    # The only added content is the routing triple; stripping the three inserted
    # lines yields the original byte-for-byte.
    stripped = updated
    for line in (
        'provider = "claude"\n',
        'model = "claude-sonnet-4-5"\n',
        'run_target = "claude-sonnet"\n',
    ):
        stripped = stripped.replace(line, "")
    assert stripped == flat

    # Backup holds the ORIGINAL content, exactly once.
    baks = list(tmp_path.glob("*advisor-bak*"))
    assert len(baks) == 1
    assert baks[0].read_text() == flat


def test_single_backup_per_run_for_shared_file(monkeypatch, cfg, city, tmp_path):
    """All agents share one city.toml → it is backed up ONCE per run."""
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(city))
    # Make TWO agents apply in one run: polecat→sonnet and witness via a forced
    # upgrade (hand-set witness to haiku so the safe direction pulls it up).
    city.write_text(
        city.read_text().replace(
            '[[agent]]\nname = "witness"\nscope = "rig"\n',
            '[[agent]]\nname = "witness"\nmodel = "claude-haiku-4-5"\nscope = "rig"\n',
        ),
        encoding="utf-8",
    )
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    st = _build_store(cfg, recs)

    rep = autoapply.auto_apply(cfg, st, dry_run=False, engine=madengine)
    applied = {d.agent for d in rep.decisions if d.status == autoapply.STATUS_APPLIED}
    # polecat downgrades to sonnet; witness (haiku, cold) is pulled UP to baseline.
    assert "polecat" in applied
    assert "witness" in applied
    wit = next(d for d in rep.decisions if d.agent == "witness")
    assert wit.direction == "up" and wit.chosen_tier == "opus"
    # Despite two writes into the same file, exactly ONE backup exists.
    assert len(list(tmp_path.glob("*advisor-bak*"))) == 1


def test_idempotent_second_run(monkeypatch, cfg, city, tmp_path):
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(city))
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    st = _build_store(cfg, recs)

    rep1 = autoapply.auto_apply(cfg, st, dry_run=False, engine=madengine)
    assert rep1.count(autoapply.STATUS_APPLIED) == 1
    after = city.read_text()

    rep2 = autoapply.auto_apply(cfg, st, dry_run=False, engine=madengine)
    # Second run: polecat is now a no-op; nothing applied; file unchanged.
    assert rep2.count(autoapply.STATUS_APPLIED) == 0
    pole2 = next(d for d in rep2.decisions if d.agent == "polecat")
    assert pole2.status == autoapply.STATUS_NOOP
    assert city.read_text() == after
    # No second backup created.
    assert len(list(tmp_path.glob("*advisor-bak*"))) == 1


# --------------------------------------------------------------------------- #
# Error isolation: one unresolvable agent doesn't abort the sweep
# --------------------------------------------------------------------------- #

def test_unresolvable_agent_isolated(monkeypatch, cfg, tmp_path):
    # city.toml WITHOUT a polecat block and no [agent_defaults] → polecat errors,
    # but agents that do resolve are still processed.
    city = tmp_path / "city.toml"
    city.write_text(_city_toml(agents=("mayor", "refinery")), encoding="utf-8")
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(city))
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    st = _build_store(cfg, recs)

    rep = autoapply.auto_apply(cfg, st, dry_run=False, engine=madengine)
    by = {d.agent: d for d in rep.decisions}
    # polecat can't resolve a config home → error (isolated), not a crash.
    assert by["polecat"].status == autoapply.STATUS_ERROR
    assert "config not resolvable" in by["polecat"].reason
    # refinery still blocked, mayor still blocked — the sweep continued.
    assert by["refinery"].status == autoapply.STATUS_BLOCKED
    assert by["mayor"].status == autoapply.STATUS_BLOCKED


# --------------------------------------------------------------------------- #
# CLI surface: auto-apply subcommand (dry-run default, --apply, --json)
# --------------------------------------------------------------------------- #

def _run_cli(*argv):
    buf = io.StringIO()
    rc = cli.main(list(argv), out=buf)
    return rc, buf.getvalue()


def _setup_cli_env(monkeypatch, tmp_path, records):
    """Write advisor.toml + telemetry + city.toml and point the CLI env at them."""
    adv = tmp_path / "advisor.toml"
    adv.write_text(ADVISOR_TOML, encoding="utf-8")
    teldir = tmp_path / ".beads" / "telemetry"
    teldir.mkdir(parents=True)
    with (teldir / "invocations.jsonl").open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    city = tmp_path / "city.toml"
    city.write_text(_city_toml(), encoding="utf-8")
    monkeypatch.setenv("ADVISOR_TOML", str(adv))
    monkeypatch.setenv("ADVISOR_TELEMETRY_DIR", str(teldir))
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(city))
    return city


def test_cli_dry_run_by_default(monkeypatch, tmp_path):
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    city = _setup_cli_env(monkeypatch, tmp_path, recs)

    rc, text = _run_cli("auto-apply")  # no --apply
    assert rc == 0 or rc == 1  # 1 only if some agent errored; both are "ran ok"
    assert "DRY-RUN" in text
    assert "SUMMARY" in text
    assert "WOULD" in text  # polecat planned change
    assert "BLOCKED" in text  # refinery / mayor
    # Default is dry-run → nothing written.
    assert city.read_text().count("model = ") == 0
    assert not list(tmp_path.glob("*advisor-bak*"))


def test_cli_apply_writes(monkeypatch, tmp_path):
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    city = _setup_cli_env(monkeypatch, tmp_path, recs)

    rc, text = _run_cli("auto-apply", "--apply")
    assert "APPLY" in text and "APPLIED" in text
    updated = city.read_text()
    assert updated.count("model = ") == 1
    assert 'model = "claude-sonnet-4-5"' in updated
    assert len(list(tmp_path.glob("*advisor-bak*"))) == 1


def test_cli_json_report(monkeypatch, tmp_path):
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    _setup_cli_env(monkeypatch, tmp_path, recs)

    rc, text = _run_cli("auto-apply", "--json")
    obj = json.loads(text)  # valid JSON
    assert obj["dry_run"] is True
    assert obj["scope"] == "town"
    assert "summary" in obj and "decisions" in obj
    by = {d["agent"]: d for d in obj["decisions"]}
    assert by["polecat"]["chosen_tier"] == "sonnet"
    assert by["polecat"]["per_shape"] == {"implement": "sonnet", "lookup": "sonnet"}
    assert by["refinery"]["status"] == "blocked"
    assert by["mayor"]["status"] == "blocked"


# --------------------------------------------------------------------------- #
# Cross-provider routing: applying a tier sets provider + model + run_target
# so a Codex tier actually runs on Codex (not just a renamed model).
# --------------------------------------------------------------------------- #

# A cross-provider roster (Codex + Claude), cost-ordered: Codex `gpt54` is the
# CHEAPEST tier and `sonnet` (Claude) is the most-capable baseline (tier*).  With
# strong gpt54 evidence on every shape, the agent's conservative tier becomes a
# genuine gate-admitted cross-provider DOWNGRADE to gpt54 — the honest path that
# proves auto-apply routes the whole Codex triple, not just the model.
XPROV_TOML = """
[advisor]
default_provider = "codex"
baseline_tier = "sonnet"

[[tier]]
id = "gpt54"
provider = "codex"
model = "gpt-5.4"
run_target = "codex-gpt54"
rank = 1
in_cost = 2.50
out_cost = 10.00

[[tier]]
id = "sonnet"
provider = "claude"
model = "claude-sonnet-4-5"
run_target = "claude-sonnet"
rank = 2
in_cost = 3.00
out_cost = 15.00

[[tolerance]]
name = "Lenient"
q_tol = 0.10
multiplier = 1

[[shape]]
name = "implement"
tol_class = "Lenient"
[[shape]]
name = "lookup"
tol_class = "Lenient"

[[agent]]
name = "polecat"
shapes = ["implement", "lookup"]
"""


def _xprov_cfg():
    import tomllib
    return madconfig.from_mapping(tomllib.loads(XPROV_TOML))


def _xprov_codex_store(cfg):
    """A store where polecat has earned gpt54 on BOTH shapes (gate-admitted)."""
    recs = _wins("codex::polecat::implement::gpt54", 80) + _wins(
        "codex::polecat::lookup::gpt54", 80
    )
    return _build_store(cfg, recs)


def test_apply_codex_tier_sets_provider_model_run_target(monkeypatch, tmp_path):
    """A gate-admitted downgrade to Codex gpt54 writes the FULL routing triple."""
    cfg = _xprov_cfg()
    flat = (
        'scope = "rig"\n'
        'model = "claude-sonnet-4-5"\n'  # current = the Claude baseline
        'max_active_sessions = 5\n'
    )
    agent_toml = tmp_path / "agent.toml"
    agent_toml.write_text(flat, encoding="utf-8")
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(agent_toml))

    st = _xprov_codex_store(cfg)
    rep = autoapply.auto_apply(
        cfg, st, dry_run=False, agents=["polecat"], provider="codex", engine=madengine
    )
    d = rep.decisions[0]
    assert d.status == autoapply.STATUS_APPLIED
    assert d.chosen_tier == "gpt54"

    updated = agent_toml.read_text()
    assert 'provider = "codex"' in updated
    assert 'model = "gpt-5.4"' in updated
    assert 'run_target = "codex-gpt54"' in updated
    # Each field written exactly once (replace-or-insert, no dupes).
    assert updated.count("provider = ") == 1
    assert updated.count("model = ") == 1
    assert updated.count("run_target = ") == 1
    # Surrounding lines untouched (byte-preserving).
    assert 'scope = "rig"' in updated
    assert "max_active_sessions = 5" in updated
    # The old Claude model is gone (replaced in place, not duplicated).
    assert "claude-sonnet-4-5" not in updated


def test_apply_claude_tier_sets_provider_model_run_target(monkeypatch, tmp_path):
    """A Claude tier write carries provider=claude + model + run_target too."""
    cfg = _cfg()  # the main ADVISOR_TOML roster (now with run_targets)
    flat = 'scope = "rig"\nmodel = "claude-haiku-4-5"\n'
    agent_toml = tmp_path / "agent.toml"
    agent_toml.write_text(flat, encoding="utf-8")
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(agent_toml))

    # polecat strong on BOTH shapes for sonnet → conservative tier sonnet (claude).
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    st = _build_store(cfg, recs)
    rep = autoapply.auto_apply(
        cfg, st, dry_run=False, agents=["polecat"], engine=madengine
    )
    d = rep.decisions[0]
    assert d.status == autoapply.STATUS_APPLIED
    assert d.chosen_tier == "sonnet"

    updated = agent_toml.read_text()
    assert 'provider = "claude"' in updated
    assert 'model = "claude-sonnet-4-5"' in updated
    assert 'run_target = "claude-sonnet"' in updated
    assert updated.count("provider = ") == 1
    assert updated.count("run_target = ") == 1


def test_apply_codex_tier_idempotent_no_dupes(monkeypatch, tmp_path):
    """Re-applying the same Codex tier is a no-op: no duplicated routing lines."""
    cfg = _xprov_cfg()
    agent_toml = tmp_path / "agent.toml"
    # Start on the Claude baseline so the first run is a real gpt54 downgrade.
    agent_toml.write_text(
        'scope = "rig"\nmodel = "claude-sonnet-4-5"\n', encoding="utf-8"
    )
    monkeypatch.setenv("ADVISOR_AGENT_TOML", str(agent_toml))

    st = _xprov_codex_store(cfg)
    rep1 = autoapply.auto_apply(
        cfg, st, dry_run=False, agents=["polecat"], provider="codex", engine=madengine
    )
    assert rep1.decisions[0].status == autoapply.STATUS_APPLIED
    after = agent_toml.read_text()
    assert after.count("provider = ") == 1
    assert after.count("model = ") == 1
    assert after.count("run_target = ") == 1

    # Second run: chosen model already set → no-op; file byte-identical.
    rep2 = autoapply.auto_apply(
        cfg, st, dry_run=False, agents=["polecat"], provider="codex", engine=madengine
    )
    assert rep2.decisions[0].status == autoapply.STATUS_NOOP
    assert agent_toml.read_text() == after  # no dupes, no churn


def test_dispatch_metadata_returns_routing_triple():
    """cli.dispatch_metadata(cfg, tier) → the per-DISPATCH gc.* routing triple."""
    cfg = _xprov_cfg()
    assert cli.dispatch_metadata(cfg, "gpt54") == {
        "gc.provider": "codex",
        "gc.model": "gpt-5.4",
        "gc.run_target": "codex-gpt54",
    }
    assert cli.dispatch_metadata(cfg, "sonnet") == {
        "gc.provider": "claude",
        "gc.model": "claude-sonnet-4-5",
        "gc.run_target": "claude-sonnet",
    }


def test_cli_rig_scope_label(monkeypatch, tmp_path):
    recs = _wins("claude::polecat::implement::sonnet", 60) + _wins(
        "claude::polecat::lookup::sonnet", 60
    )
    _setup_cli_env(monkeypatch, tmp_path, recs)
    rc, text = _run_cli("auto-apply", "--rig", "demo-repo", "--json")
    obj = json.loads(text)
    assert obj["scope"] == "rig:demo-repo"
