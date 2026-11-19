"""The harness as shipped: its entry refuses off the VM, its units and
scripts are well-formed, and the drills' pure parts hold."""

from __future__ import annotations

import configparser
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import pytest
from .soaktestkit import ProcTree

from soakcli import NOTE_COVERS, compare_snapshots, demand_sessions, parser
from soakdrill import DRILLS, PIN_0_1_20, Drill, DrillError, is_always_on, is_dispatcher, new_dispatcher_box, take_lock
from soakhc import CoreTuple
from soaklib import GUARD_FILE, City, ProcFS, SoakPaths

SOAK = Path(__file__).resolve().parents[1]
PACK = SOAK.parent
BASH_SCRIPTS = sorted(p for p in (SOAK / "bin").iterdir() if p.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash"))


@pytest.mark.skipif(Path(GUARD_FILE).exists(), reason="this host is provisioned as the soak VM")
@pytest.mark.parametrize("argv", [["guard"], ["check"], ["drill", "core-kill"], ["report", "--city", "x"]])
def test_every_subcommand_refuses_off_the_soak_vm(argv: list) -> None:  # type: ignore[type-arg]
    res = subprocess.run([str(SOAK / "bin" / "soak"), *argv], capture_output=True, text=True, timeout=60)
    assert res.returncode == 3 and "refused" in res.stderr


@pytest.mark.skipif(Path(GUARD_FILE).exists(), reason="this host is provisioned as the soak VM")
def test_bash_phase_scripts_refuse_off_the_soak_vm(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / "soak").mkdir(parents=True)
    os.symlink(str(SOAK / "bin"), str(home / "soak" / "bin"))
    for script in BASH_SCRIPTS:
        res = subprocess.run([str(script), "hc-bringup", "v2-switch"], env={"HOME": str(home), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=60)
        assert res.returncode == 3, (script.name, res.stderr)


def test_the_parser_knows_every_runbook_subcommand() -> None:
    wanted = (
        "city-init toml-set toml-del phase note wait snapshot hc-status store placement load probe sample check "
        "capture conf-teardown orphans drill report guard final-scan"
    ).split()
    sub = next(a for a in parser()._actions if a.dest == "cmd")
    assert sorted(sub.choices) == sorted(wanted)  # type: ignore[arg-type]


def test_shellcheck_is_clean() -> None:
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck is not installed")
    assert BASH_SCRIPTS
    res = subprocess.run(["shellcheck", *map(str, BASH_SCRIPTS)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout


def units() -> Dict[str, configparser.ConfigParser]:
    out: Dict[str, configparser.ConfigParser] = {}
    for path in sorted((SOAK / "systemd").rglob("*.*")):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str  # type: ignore[assignment,method-assign]
        cp.read_string(path.read_text(encoding="utf-8"))
        out[path.name] = cp
    return out


def test_systemd_units() -> None:
    u = units()
    assert sorted(u) == sorted(
        ["soak-check.service", "soak-check.timer", "soak-load.service", "soak-probe.service", "soak-probe.timer", "soak-sample.service", "soak-optrace.service"]
    )
    for name in ("soak-check", "soak-load", "soak-probe", "soak-sample"):
        svc = u[f"{name}.service"]["Service"]
        assert svc["EnvironmentFile"] == "%h/soak-data/current/soak.env"
        assert svc["ExecStart"] == f"%h/soak/bin/soak {name.split('-')[1]}"
    assert u["soak-check.service"]["Service"]["Type"] == "oneshot"
    assert u["soak-check.timer"]["Timer"]["OnUnitActiveSec"] == "5min"
    assert u["soak-probe.timer"]["Timer"]["OnUnitActiveSec"] == "30min"
    assert u["soak-sample.service"]["Service"]["Restart"] == "always"
    assert u["soak-load.service"]["Service"]["Restart"] == "on-failure"
    optrace = u["soak-optrace.service"]["Service"]
    assert optrace["ExecStart"].split() == [
        "/usr/bin/bpftrace",
        "/home/soak/soak/bin/soak-optrace.bt",
        "/home/soak/packs/runtime-herdr-core/assets/bin/gc-runtime-herdr-core",
    ]


def test_optrace_script_matches_the_runbook() -> None:
    script = (SOAK / "bin" / "soak-optrace.bt").read_text(encoding="utf-8")
    runbook = (SOAK / "RUNBOOK.md").read_text(encoding="utf-8")
    block = runbook.split("```text\n#!/usr/bin/env bpftrace\n", 1)[1].split("```", 1)[0]
    assert script == "#!/usr/bin/env bpftrace\n" + block


def test_entries_are_python_isolated() -> None:
    for name in ("soak", "soak-agent"):
        path = SOAK / "bin" / name
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/python3 -I\n")
        assert os.access(path, os.X_OK)


def test_compare_snapshots() -> None:
    before = {"core": {"pid": 5, "start": 1, "version": "0.1.19"}, "boxes": [[10, 1, "s1"], [11, 2, "s2"]]}
    same = compare_snapshots(before, before)
    assert same["core_same"] and same["boxes_kept"] == 2 and not same["boxes_ended"] and not same["boxes_new"]
    after = {"core": {"pid": 5, "start": 1, "version": "0.1.19"}, "boxes": [[10, 1, "s1"], [12, 3, "s2"]]}
    diff = compare_snapshots(before, after)
    assert diff["boxes_ended"] == [[11, 2, "s2"]] and diff["boxes_new"] == [[12, 3, "s2"]]
    assert diff["demand_churn"] == {"ended": [], "new": []}


def test_compare_snapshots_sets_demand_churn_apart() -> None:
    before = {"core": {"pid": 5, "start": 1, "version": "0.1.19"}, "boxes": [[10, 1, "s1"], [11, 2, "b1"], [13, 4, "b2"]]}
    after = {"core": {"pid": 5, "start": 1, "version": "0.1.19"}, "boxes": [[10, 1, "s1"], [13, 4, "b2"], [14, 5, "b3"]]}
    diff = compare_snapshots(before, after, demand={"b1", "b2", "b3"})
    assert not diff["boxes_ended"] and not diff["boxes_new"] and diff["boxes_kept"] == 2
    assert diff["demand_churn"] == {"ended": [[11, 2, "b1"]], "new": [[14, 5, "b3"]]}
    killed = {"core": before["core"], "boxes": [[13, 4, "b2"], [14, 5, "b3"]]}
    diff = compare_snapshots(before, killed, demand={"b1", "b2", "b3"})
    assert diff["boxes_ended"] == [[10, 1, "s1"]]


def test_demand_sessions_are_every_session_but_the_always_on_pools() -> None:
    doc = {
        "sessions": [
            {"id": "s1", "template": "soak-steady", "state": "active"},
            {"id": "b1", "template": "soak-burst", "state": "closed", "closed": True},
            {"id": "c1", "template": "core.control-dispatcher", "state": "active"},
            {"id": "d1", "template": "bd.dog", "state": "closed"},
            {"template": "soak-burst"},
        ]
    }
    assert demand_sessions(doc) == {"b1", "c1", "d1"}
    assert demand_sessions(None) == set()


def test_note_covers() -> None:
    assert set(NOTE_COVERS["supervisor-restart"]) == {"supervisor", "controller", "store"}
    assert NOTE_COVERS["city-stop"] == ["all"]


def test_upgrade_pin_is_the_runbooks() -> None:
    runbook = (SOAK / "RUNBOOK.md").read_text(encoding="utf-8")
    block = runbook.split("```json\n", 1)[1].split("```", 1)[0]
    assert json.loads(block) == PIN_0_1_20
    current = json.loads((PACK / "assets" / "hc-pin.json").read_text(encoding="utf-8"))
    assert set(current) == set(PIN_0_1_20) and set(current["targets"]) == set(PIN_0_1_20["targets"])


def test_the_report_template_is_the_runbooks() -> None:
    runbook = (SOAK / "RUNBOOK.md").read_text(encoding="utf-8")
    block = runbook.split("```markdown\n", 1)[1].split("\n```\n\n## 16. Teardown", 1)[0] + "\n"
    doc = (PACK / "docs" / "soak-report.md").read_text(encoding="utf-8")

    def sections(text: str) -> List[str]:
        return [line for line in text.splitlines() if line.startswith(("# ", "## "))]

    def row_keys(text: str) -> List[str]:
        return [line.split("|")[1].strip() for line in text.splitlines() if line.startswith("| ")]

    # A filled report keeps the template's sections and every row the template
    # asks for, in order; it may add subsections and rows.
    assert sections(doc) == sections(block)
    keys = iter(row_keys(doc))
    missing = [k for k in row_keys(block) if not any(k == d for d in keys)]
    assert missing == []


def test_drill_names_and_always_on_templates() -> None:
    assert "core-kill" in DRILLS and "reboot-verify" in DRILLS and len(DRILLS) == 11
    assert is_always_on("soak-steady")
    # The dispatcher is a demand session (max 1, no minimum): its return is recorded, not judged.
    assert not is_always_on("core.control-dispatcher") and not is_always_on("core/control-dispatcher")
    assert not is_always_on("soak-burst") and not is_always_on("bd/dog")
    assert is_dispatcher("core.control-dispatcher") and is_dispatcher("core/control-dispatcher") and not is_dispatcher("soak-steady")


def test_a_new_dispatcher_box_counts_under_any_session_id(proc_tree: ProcTree, tmp_path: Path) -> None:
    proc_tree.add(10, "sh", env={"GC_TEMPLATE": "core.control-dispatcher", "GC_SESSION_ID": "old"})
    proc_tree.add(11, "sh", env={"GC_TEMPLATE": "soak-steady", "GC_SESSION_ID": "s1"})
    procfs = ProcFS(str(proc_tree.root))
    snap = procfs.snapshot(os.getuid())
    boxes = [snap[10], snap[11]]
    before = {10: (snap[10].start, "old"), 11: (snap[11].start, "s1")}
    assert new_dispatcher_box(boxes, before) is None
    proc_tree.add(12, "sh", env={"GC_TEMPLATE": "core.control-dispatcher", "GC_SESSION_ID": "new"})
    snap = procfs.snapshot(os.getuid())
    assert new_dispatcher_box([snap[11], snap[12]], before) == 12


def test_the_pin_restores_from_the_upgrade_drills_copy_without_a_clone(tmp_path: Path) -> None:
    paths = SoakPaths(tmp_path)
    pin = paths.pack / "assets" / "hc-pin.json"
    pin.parent.mkdir(parents=True)
    original = '{"version": "0.1.19"}\n'
    pin.write_text(original, encoding="utf-8")
    subprocess.run("sha256sum ./assets/hc-pin.json > ../runtime-herdr-core.SHA256SUMS", shell=True, cwd=str(paths.pack), check=True)
    drill = Drill("stop-wedged", City("c", tmp_path / "city", tmp_path, "warn"), paths)
    with pytest.raises(DrillError, match="cannot restore the pin"):
        drill.restore_pin()
    paths.pin_backup.write_text(original, encoding="utf-8")
    pin.write_text(json.dumps(PIN_0_1_20), encoding="utf-8")
    drill.restore_pin()
    assert pin.read_text(encoding="utf-8") == original
    assert [c.id for c in drill.criteria] == ["pack-restored"] and drill.criteria[0].passed


def test_the_drill_lock_is_exclusive(tmp_path: Path) -> None:
    city = City("c", tmp_path / "city", tmp_path, "warn")
    lock = take_lock(city, "core-kill")
    with pytest.raises(DrillError, match="core-kill"):
        take_lock(city, "agent-kill")
    lock.unlink()
    take_lock(city, "agent-kill")


def test_drill_ownership_checks(proc_tree: ProcTree, tmp_path: Path) -> None:
    city_path = str(tmp_path / "cities" / "c")
    core = CoreTuple("gc-c", "/sock", "/R", "/R/hc-config")
    mine = {"XDG_STATE_HOME": "/R", "HC_SESSION": "gc-c", "HC_RUNTIME": "1"}
    proc_tree.add(1, "herdr-core", argv=["/hc/herdr-core", "hold"], env=mine)
    proc_tree.add(2, "herdr-core", argv=["/hc/herdr-core", "serve"], env=mine)
    proc_tree.add(3, "herdr-core", argv=["/hc/herdr-core", "hold"], env=dict(mine, XDG_STATE_HOME="/tmp/hcconf/state"))
    proc_tree.add(4, "herdr-core", argv=["/hc/herdr-core", "hold"], env=mine, uid=0)
    proc_tree.add(5, "bd", argv=["/usr/local/bin/bd", "db-proxy-child"], env={"GC_CITY_PATH": city_path})
    proc_tree.add(6, "bd", argv=["/usr/local/bin/bd", "db-proxy-child", f"{city_path}/.beads"])
    proc_tree.add(7, "bd", argv=["/usr/local/bin/bd", "db-proxy-child"], env={"GC_CITY_PATH": "/other"})
    proc_tree.add(8, "sleep", env={"GC_CITY_PATH": city_path})
    drill = Drill("holder-kill", City("c", Path(city_path), tmp_path, "warn"), SoakPaths(tmp_path), procfs=ProcFS(str(proc_tree.root)), core=core)
    hold = drill.hc_owner("hold")
    assert hold(1) is None
    assert hold(2) == "not an hc hold process"
    assert hold(3) == "hc runtime of another core"
    assert hold(4) == "another user's process"
    assert hold(99) == "gone"
    assert drill.hc_owner("serve")(2) is None
    store = drill.store_owner()
    assert store(5) is None and store(6) is None
    assert store(7) == "not this city's store" and store(8) == "not a store proxy or its Dolt"


def test_python_entry_points_compile() -> None:
    for name in ("soak", "soak-agent"):
        source = (SOAK / "bin" / name).read_text(encoding="utf-8")
        compile(source, name, "exec")
    assert sys.version_info >= (3, 9)
