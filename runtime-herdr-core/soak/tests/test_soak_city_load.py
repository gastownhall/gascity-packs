from __future__ import annotations

import json
import random
import stat
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

import pytest

from soakcity import (
    CITY_FILES,
    TomlEditError,
    city_keys,
    edit_file,
    load_config,
    render,
    set_phase,
    toml_check,
    toml_del,
    toml_set,
)
from soakload import LoadConfig, LoadGen, due_actions, next_round_robin, pick_mode, running_sessions
from soaklib import City, read_jsonl

SOAK = Path(__file__).resolve().parents[1]
HAVE_TOMLLIB = sys.version_info >= (3, 11)

CITY_TOML = """# written by gc init
[workspace]
name = "hc-soak"

[[agent]]
name = "x"

[daemon]
patrol_interval = "30s"
session_reconciler = "v2"

[storage.bindings.infra]
provider = "sqlite-beads"
"""


def test_toml_set_inserts_replaces_and_appends() -> None:
    text = toml_set(CITY_TOML, "workspace", "provider", '"soak"')
    assert '[workspace]\nname = "hc-soak"\nprovider = "soak"\n\n[[agent]]' in text
    text = toml_set(text, "daemon", "session_reconciler", '"legacy"')
    assert 'session_reconciler = "legacy"' in text and 'session_reconciler = "v2"' not in text
    text = toml_set(text, "events.mirror", "path", '"/d/events.jsonl"')
    assert text.endswith('[events.mirror]\npath = "/d/events.jsonl"\n')
    text = toml_set(text, "events.mirror", "max_size_bytes", "0")
    assert text.endswith('path = "/d/events.jsonl"\nmax_size_bytes = 0\n')
    assert text.startswith("# written by gc init\n")


def test_toml_set_does_not_cross_an_array_of_tables() -> None:
    text = toml_set("[a]\nk = 1\n[[a.list]]\nk = 2\n", "a", "k", "3")
    assert text == "[a]\nk = 3\n[[a.list]]\nk = 2\n"


def test_toml_del() -> None:
    text = toml_del(CITY_TOML, "daemon", "session_reconciler")
    assert "session_reconciler" not in text and 'patrol_interval = "30s"' in text
    with pytest.raises(TomlEditError):
        toml_del(text, "daemon", "session_reconciler")
    with pytest.raises(TomlEditError):
        toml_del(text, "nope", "x")


@pytest.mark.skipif(not HAVE_TOMLLIB, reason="tomllib is 3.11+")
def test_edit_file_checks_the_result(tmp_path: Path) -> None:
    path = tmp_path / "city.toml"
    path.write_text(CITY_TOML, encoding="utf-8")
    for table, key, value in city_keys(tmp_path / "data"):
        edit_file(path, table, key, value)
    doc = toml_check(path.read_text(encoding="utf-8"))
    assert doc is not None
    assert doc["session"]["provider"] == "herdr-core" and doc["workspace"]["provider"] == "soak"
    assert doc["daemon"] == {"patrol_interval": "30s", "session_reconciler": "legacy", "max_wakes_per_tick": 25}
    assert doc["beads"]["proxied_idle_timeout"] == "0"
    assert doc["events"]["mirror"] == {"path": str(tmp_path / "data" / "gc-events" / "events.jsonl"), "mode": "0600", "max_size_bytes": 0}
    edit_file(path, "daemon", "session_reconciler", None)
    assert "session_reconciler" not in path.read_text(encoding="utf-8")
    with pytest.raises(TomlEditError):
        edit_file(path, "daemon", "bad", "not a literal")


def test_city_templates_render_completely() -> None:
    values = {"DATA": "/home/soak/soak-data/hc-soak", "CANARY": "soakcanary" + "0" * 32, "STEADY": "6", "BURST": "10", "PACK": "/home/soak/packs/runtime-herdr-core", "AGENT": "/home/soak/soak/bin/soak-agent"}
    rendered = {item.path: render(SOAK / "city", item.template, values) for item in CITY_FILES}
    rendered["pack.toml"] = render(SOAK / "city", "pack.append.toml", values)
    assert "min_active_sessions = 6" in rendered["agents/soak-steady/agent.toml"]
    assert "max_active_sessions = 10" in rendered["agents/soak-burst/agent.toml"]
    assert 'SOAK_DRAIN_IDLE_S = "60"' in rendered["agents/soak-burst/agent.toml"]
    assert 'work_dir = ".gc/agents/{{.AgentBase}}"' in rendered["agents/soak-steady/agent.toml"]
    assert rendered["assets/prompts/soak.template.md"] == "SOAK-FIRST-TURN {{ .AgentName }}\n"
    assert 'process_names = ["soak-agent"]' in rendered["pack.toml"]
    for text in rendered.values():
        assert "${" not in text
    if HAVE_TOMLLIB:
        for path, text in rendered.items():
            if path.endswith(".toml"):
                assert toml_check(text) is not None, path
        run = toml_check(rendered["formulas/soak-run.toml"])
        assert run is not None and [s["id"] for s in run["steps"]] == ["prepare", "work-a", "work-b", "work-c", "collect"]


def test_load_config_and_phase(tmp_path: Path) -> None:
    cfg = LoadConfig.from_json(load_config("soak", 7))
    assert (cfg.burst_s, cfg.steady_s, cfg.nudge_s, cfg.seed) == (30.0, 60.0, 120.0, 7)
    assert LoadConfig.from_json(load_config("bringup", 1)).periods() == {"burst": 180.0, "steady": 180.0, "nudge": 300.0}
    with pytest.raises(ValueError):
        load_config("heavy", 1)
    rec = set_phase(tmp_path, "soak-v2")
    assert rec["reconciler"] == "v2" and (tmp_path / "phase").read_text(encoding="utf-8") == "soak-v2\n"
    set_phase(tmp_path, "custom", "legacy")
    assert [r["phase"] for r in read_jsonl(tmp_path / "phases.jsonl")] == ["soak-v2", "custom"]


def test_due_actions_skip_missed_periods() -> None:
    due: Dict[str, float] = {}
    periods = {"burst": 30.0, "nudge": 120.0}
    assert due_actions(0.0, periods, due) == ["burst", "nudge"]
    assert due_actions(10.0, periods, due) == []
    assert due_actions(30.0, periods, due) == ["burst"]
    assert due_actions(200.0, periods, due) == ["burst", "nudge"]
    assert due["burst"] == 210.0 and due["nudge"] == 240.0


def test_pick_mode_follows_the_weights() -> None:
    rng = random.Random(1)
    modes = (("wait-idle", 80), ("immediate", 10), ("queue", 10))
    counts = Counter(pick_mode(rng, modes) for _ in range(10_000))
    assert 7700 < counts["wait-idle"] < 8300 and 800 < counts["immediate"] < 1200 and 800 < counts["queue"] < 1200


def test_running_sessions_and_round_robin() -> None:
    doc = {
        "sessions": [
            {"id": "s3", "template": "soak-steady", "state": "active"},
            {"id": "s1", "template": "soak-steady", "state": "awake"},
            {"id": "s2", "template": "soak-steady", "state": "asleep"},
            {"id": "s4", "template": "soak-steady", "state": "active", "closed": True},
            {"id": "s5", "template": "soak-steady", "state": "active", "running": False},
        ]
    }
    assert running_sessions(doc, "soak-steady") == ["s1", "s3"]
    assert running_sessions(None, "soak-steady") == []
    assert next_round_robin(["s3", "s1"], None) == "s1"
    assert next_round_robin(["s3", "s1"], "s1") == "s3"
    assert next_round_robin(["s3", "s1"], "s3") == "s1"
    assert next_round_robin([], "s3") is None


FAKE_GC = """#!{python}
import json, sys
args = sys.argv[1:]
with open({log!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["status", "--json"]:
    print(json.dumps({{"running": True}}))
elif args[:2] == ["session", "list"]:
    print(json.dumps({{"sessions": [{{"id": "gc-1", "template": "soak-steady", "state": "active"}}]}}))
elif args[0] == "sling":
    print(json.dumps({{"ok": True, "workflow_id": "wf-" + args[1]}}))
elif args[:2] == ["session", "nudge"]:
    print(json.dumps({{"ok": True, "outcome": "submitted", "queued": False}}))
else:
    sys.exit(2)
"""


def test_load_generator_tick_runs_every_due_action_against_a_fake_gc(tmp_path: Path) -> None:
    log = tmp_path / "gc-calls.jsonl"
    gc = tmp_path / "gc"
    gc.write_text(FAKE_GC.format(python=sys.executable, log=str(log)), encoding="utf-8")
    gc.chmod(gc.stat().st_mode | stat.S_IXUSR)
    data = tmp_path / "data"
    data.mkdir()
    city = City("hc-soak", tmp_path, data, "warn")
    gen = LoadGen(city, LoadConfig.from_json(load_config("soak", 3)), gc=str(gc), rng=random.Random(3))
    assert gen.tick(1000.0) == ["burst", "nudge", "steady"]
    records = read_jsonl(data / "load.jsonl")
    actions = [r["action"] for r in records]
    assert actions == ["sling-burst", "nudge", "sling-steady"]
    assert records[0]["workflow_id"] == "wf-soak-burst" and records[2]["workflow_id"] == "wf-soak-steady"
    nudge = records[1]
    assert nudge["session_id"] == "gc-1" and len(nudge["nonce"]) == 32 and nudge["mode"] in ("wait-idle", "immediate", "queue")
    assert nudge["argv"][-4:-2] == [f"SOAK-NUDGE {nudge['nonce']}", "--delivery"]
    assert gen.tick(1001.0) == []
    (data / "PAUSE").touch()
    assert gen.tick(5000.0) == []
    calls: List[List[str]] = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls[1][:2] == ["sling", "soak-burst"] and "--formula" in calls[1]


def test_running_sessions_without_a_template_and_with_qualified_names() -> None:
    doc = {
        "sessions": [
            {"id": "a", "template": "hc-soak/soak-steady", "state": "active"},
            {"id": "b", "template": "core.control-dispatcher", "state": "active"},
            {"id": "c", "template": "soak-steady-extra", "state": "active"},
        ]
    }
    assert running_sessions(doc, "soak-steady") == ["a"]
    assert running_sessions(doc, "") == ["a", "b", "c"]
