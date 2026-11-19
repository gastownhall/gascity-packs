"""The harness as shipped: its entry refuses off the VM, its units and
scripts are well-formed, the drills' pure parts hold, and a drill whose
fault does not land never passes."""

from __future__ import annotations

import configparser
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple

import pytest
from .soaktestkit import ProcTree

import soakdrill
from soakanalysis import Incarnation
from soakcli import NOTE_COVERS, compare_snapshots, demand_sessions, parser
from soakdrill import DRILLS, PIN_0_1_20, Before, Drill, DrillError, drill_main, is_always_on, is_dispatcher, new_dispatcher_box, take_lock
from soakhc import CoreStatus, CoreTuple
from soaklib import GUARD_FILE, City, CmdResult, ProcFS, SoakPaths

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


# --- a fault that does not land ---------------------------------------------------------------
#
# Every process a drill may signal in these tests is a child the test started,
# and a synthetic /proc entry a drill may signal carries such a child's pid: a
# drill whose guard is broken can only ever hit that child, never the host's.

Spawn = Callable[[], "subprocess.Popen[bytes]"]
CITY_CORE = CoreTuple("gc-c", "/sock", "/R", "/R/hc-config")
MINE = {"XDG_STATE_HOME": "/R", "HC_SESSION": "gc-c", "HC_RUNTIME": "1"}
AFTER_HOLDER_KILL = ("c2_c3", "f1_store_kept", "c1", "settle", "c4", "c5", "c6")
AFTER_CORE_KILL = ("boxes_unchanged", "c1", "settle", "c4", "c6")


@pytest.fixture
def spawn() -> Iterator[Spawn]:
    """Starts sleeping children; each is killed and reaped at the end."""
    children: List[subprocess.Popen[bytes]] = []

    def one() -> subprocess.Popen[bytes]:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        children.append(child)
        return child

    try:
        yield one
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait()


class FakeClock:
    """A drill's ``time``: ``sleep`` moves the clock on at once and runs what falls due."""

    def __init__(self, now: float) -> None:
        self.now = now
        self.due: List[Tuple[float, Callable[[], None]]] = []

    def at(self, t: float, action: Callable[[], None]) -> None:
        self.due.append((t, action))

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        ready = [d for d in self.due if d[0] <= self.now]
        self.due = [d for d in self.due if d[0] > self.now]
        for _t, action in ready:
            action()


def a_before(
    core: Optional[CoreStatus] = None,
    *,
    boxes: Optional[Dict[int, Tuple[int, str]]] = None,
    sessions: Optional[Dict[str, str]] = None,
    alive_incs: Optional[Set[str]] = None,
) -> Before:
    return Before(1000.0, core, boxes or {}, sessions or {}, [], 1, alive_incs or set(), [], set())


def stub(monkeypatch: pytest.MonkeyPatch, *steps: str) -> None:
    """The named drill steps do nothing (and the controller keeps pid 1): a
    drill that wrongly went on past its fault ends at once, failing its test,
    instead of waiting on a city that is not there."""
    for step in steps:
        monkeypatch.setattr(Drill, step, lambda self, *args, **kwargs: None)
    monkeypatch.setattr(Drill, "supervisor_pid", lambda self: 1)


def test_a_refused_fault_ends_the_drill_in_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn) -> None:
    # The ownership check refuses the core (the pid runs no hc serve): the drill
    # ends in error where it stands, so a core that answers is never read as the
    # recovery from a kill that did not happen.
    core = spawn()
    monkeypatch.setattr(Drill, "core_tuple", lambda self: CITY_CORE)
    monkeypatch.setattr(Drill, "before", lambda self: a_before(CoreStatus(core.pid, "0.1.19", (), 1)))
    monkeypatch.setattr(soakdrill, "wait_answers", lambda rpc, timeout: 0.5)
    monkeypatch.setattr(soakdrill, "GONE_WAIT_S", 0.0)
    stub(monkeypatch, *AFTER_CORE_KILL)
    city = City("c", tmp_path / "city", tmp_path, "warn")
    assert drill_main(city, SoakPaths(tmp_path), "core-kill") == 1
    [out] = (tmp_path / "drills").glob("core-kill-*.json")
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["verdict"] == "error" and rec["criteria"] == []
    assert rec["notes"][-1] == f"core not signalled: pid {core.pid}: not an hc serve process"
    assert core.poll() is None and not city.file("DRILL").exists()


@pytest.mark.parametrize("second", ["not running", "another core's"])
def test_holder_kill_signals_nothing_unless_every_listed_holder_is_the_citys(
    second: str, proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn
) -> None:
    first, other = spawn(), spawn()
    proc_tree.add(first.pid, "herdr-core", argv=["/hc/herdr-core", "hold"], env=MINE)
    if second == "another core's":
        proc_tree.add(other.pid, "herdr-core", argv=["/hc/herdr-core", "hold"], env=dict(MINE, HC_SESSION="gc-other"))
    monkeypatch.setattr(soakdrill, "GONE_WAIT_S", 0.0)
    stub(monkeypatch, *AFTER_HOLDER_KILL)
    drill = Drill("holder-kill", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path), procfs=ProcFS(str(proc_tree.root)), core=CITY_CORE)
    why = "that the core lists is not running" if second == "not running" else "is not this city's: hc runtime of another core"
    with pytest.raises(DrillError, match=f"holder {other.pid} {why}"):
        drill.drill_holder_kill(a_before(CoreStatus(9, "0.1.19", (first.pid, other.pid), 2)))
    # The city's own holder, listed first, is not killed either.
    assert first.poll() is None and other.poll() is None
    assert drill.t_inject == 0.0 and not (tmp_path / "faults.jsonl").exists()


def test_a_holder_refused_when_the_signal_goes_out_ends_the_drill(
    proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn
) -> None:
    # The holder passes the check before the fault and is refused when the
    # signal goes out (it changed hands in between): the drill ends in error.
    holder = spawn()
    proc_tree.add(holder.pid, "herdr-core", argv=["/hc/herdr-core", "hold"], env=MINE)
    asked: List[int] = []

    def owner(pid: int) -> Optional[str]:
        asked.append(pid)
        return None if len(asked) == 1 else "changed hands"

    monkeypatch.setattr(Drill, "hc_owner", lambda self, role: owner)
    monkeypatch.setattr(soakdrill, "GONE_WAIT_S", 0.0)
    stub(monkeypatch, *AFTER_HOLDER_KILL)
    drill = Drill("holder-kill", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path), procfs=ProcFS(str(proc_tree.root)), core=CITY_CORE)
    with pytest.raises(DrillError, match=f"holder {holder.pid} not signalled: pid {holder.pid}: changed hands"):
        drill.drill_holder_kill(a_before(CoreStatus(9, "0.1.19", (holder.pid,), 1)))
    assert asked == [holder.pid, holder.pid] and holder.poll() is None and drill.criteria == []


def test_a_failed_systemctl_kill_ends_the_unit_drill(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn) -> None:
    holder = spawn()
    cgroup = "/user.slice/user-1000.slice/user@1000.service/app.slice/hc-hold-gc-c.service"
    proc_tree.add(holder.pid, "herdr-core", argv=["/hc/herdr-core", "hold"], env=MINE, cgroup=cgroup)
    calls: List[List[str]] = []

    def refused(argv: Sequence[str], **_kwargs: Any) -> CmdResult:
        calls.append(list(argv))
        return CmdResult(tuple(argv), 1, "", "Failed to kill unit hc-hold-gc-c.service: Access denied", 0.1)

    monkeypatch.setattr(soakdrill, "run", refused)
    monkeypatch.setattr(soakdrill, "GONE_WAIT_S", 0.0)
    stub(monkeypatch, *AFTER_HOLDER_KILL)
    drill = Drill("holder-unit-kill", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path), procfs=ProcFS(str(proc_tree.root)), core=CITY_CORE)
    with pytest.raises(DrillError, match=r"systemctl kill hc-hold-gc-c\.service exited 1: Failed to kill unit"):
        drill.drill_holder_unit_kill(a_before(CoreStatus(9, "0.1.19", (holder.pid,), 1)))
    assert calls == [["systemctl", "--user", "kill", "--kill-whom=all", "--signal=SIGKILL", "--", "hc-hold-gc-c.service"]]
    assert drill.notes == ["systemctl kill hc-hold-gc-c.service: exit 1"] and drill.criteria == []
    assert holder.poll() is None


def test_a_refused_store_kill_ends_the_placement_drill(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn) -> None:
    proxy = spawn()
    proc_tree.add(proxy.pid, "bd", argv=["/usr/local/bin/bd", "db-proxy-child"], env={"GC_CITY_PATH": "/other"})
    monkeypatch.setattr(soakdrill, "time", FakeClock(1000.0))
    stub(monkeypatch, "c1", "settle", "c4", "c6")
    drill = Drill("place-store", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path), procfs=ProcFS(str(proc_tree.root)))
    with pytest.raises(DrillError, match=f"store proxy not signalled: pid {proxy.pid}: not this city's store"):
        drill.drill_place_store(a_before(sessions={"s1": "soak-steady"}))
    assert proxy.poll() is None and drill.criteria == []


def test_a_holder_the_drill_killed_is_judged_gone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn) -> None:
    # The host's /proc, with an ownership check that accepts only the test's child.
    holder = spawn()
    monkeypatch.setattr(Drill, "hc_owner", lambda self, role: lambda pid: None if pid == holder.pid else "not the test's child")
    stub(monkeypatch, *AFTER_HOLDER_KILL)
    drill = Drill("holder-kill", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path), core=CITY_CORE)
    drill.drill_holder_kill(a_before(CoreStatus(9, "0.1.19", (holder.pid,), 1)))
    assert holder.wait(timeout=10) == -signal.SIGKILL
    killed = drill.criteria[0]
    assert (killed.id, killed.passed, killed.measured["left"]) == ("F2-killed", True, [])


def test_a_core_that_outlives_its_kill_fails_the_drill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn) -> None:
    # Whatever leaves the old core running (here: the signal never goes out),
    # the core that answers is that old core, not a recovery.
    core = spawn()
    monkeypatch.setattr(Drill, "core_tuple", lambda self: CITY_CORE)
    monkeypatch.setattr(Drill, "before", lambda self: a_before(CoreStatus(core.pid, "0.1.19", (), 1)))
    monkeypatch.setattr(Drill, "inject", lambda self, *args: None)
    monkeypatch.setattr(soakdrill, "wait_answers", lambda rpc, timeout: 0.5)
    monkeypatch.setattr(soakdrill, "GONE_WAIT_S", 0.0)
    stub(monkeypatch, *AFTER_CORE_KILL)
    rec = Drill("core-kill", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path)).run()
    assert {c["id"]: c["pass"] for c in rec["criteria"]} == {"F4-answer": True, "F4-killed": False}
    assert rec["verdict"] == "fail" and core.poll() is None


def test_an_interrupted_wedged_stop_still_resumes_the_core(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn) -> None:
    core = spawn()
    monkeypatch.setattr(Drill, "hc_owner", lambda self, role: lambda pid: None if pid == core.pid else "not the test's child")

    def state() -> str:
        st = ProcFS().stat(core.pid)
        return st.state if st else ""

    def interrupted(argv: Sequence[str], **_kwargs: Any) -> CmdResult:
        # The first gc stop is interrupted once the core is stopped.
        deadline = time.time() + 10.0
        while state() != "T" and time.time() < deadline:
            time.sleep(0.05)
        assert state() == "T"
        raise KeyboardInterrupt

    monkeypatch.setattr(soakdrill, "run", interrupted)
    drill = Drill("stop-wedged", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path))
    with pytest.raises(KeyboardInterrupt):
        drill.drill_stop_wedged(a_before(CoreStatus(core.pid, "0.1.19", (), 1)))
    assert state() not in ("T", "") and core.poll() is None


def test_a_slow_reap_never_delays_when_a_session_counts_as_back(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The ended session's new box runs 20 s after the fault; the background
    # child of its dead incarnation is gone only after 100 s. C2 measures 20 s
    # and passes; C3 measures 100 s and fails. Nothing here is signalled.
    clock = FakeClock(1000.0)
    proc_tree.add(20, "sleep")
    clock.at(1020.0, lambda: proc_tree.add(11, "sh", ppid=5, env={"GC_SESSION_ID": "s1"}))
    clock.at(1100.0, lambda: proc_tree.add(20, "sleep", state="Z"))
    monkeypatch.setattr(soakdrill, "time", clock)
    monkeypatch.setattr(Drill, "status", lambda self: CoreStatus(4, "0.1.19", (5,), 1))
    dead = Incarnation(
        inc="i1", session_id="s1", session_name="s1", template="soak-steady", pid=10, start=100, boot_t=900.0, last_t=990.0, alive=False, bg=[(20, 100)]
    )
    monkeypatch.setattr(Drill, "incs", lambda self: [dead])
    drill = Drill("agent-kill", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path), procfs=ProcFS(str(proc_tree.root)), t_inject=1000.0)
    drill.c2_c3(a_before(boxes={10: (100, "s1")}, sessions={"s1": "soak-steady"}, alive_incs={"i1"}))
    c2, c3 = drill.criteria
    assert (c2.id, c2.measured["sessions"], c2.passed) == ("C2", {"s1": 20.0}, True)
    assert (c3.id, c3.measured["reaped_s"], c3.passed) == ("C3", 100.0, False)


# C5 through the real criterion: the agent logs are stubbed (Drill.incs), the
# clock is fake, and /proc is synthetic. C5 starts at 2000; the fault was at 1000.


def an_inc(sid: str, pid: int, boot_t: float, beacons: Sequence[float] = (), alive: bool = True) -> Incarnation:
    """A scripted agent's incarnation (start ticks 100, the synthetic host's
    boot) with one beacon line at each time in ``beacons``."""
    inputs: List[Dict[str, Any]] = [{"ev": "in", "t": t, "mono": t, "beacon": True} for t in beacons]
    return Incarnation(f"b00tb00t:{pid}:100", sid, sid, "soak-steady", pid, 100, boot_t, max([boot_t, *beacons]), alive, inputs=inputs)


def c5_drill(tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch, clock: FakeClock, incs: Callable[[], List[Incarnation]]) -> Drill:
    monkeypatch.setattr(soakdrill, "time", clock)
    monkeypatch.setattr(Drill, "incs", lambda self: incs())
    return Drill("holder-kill", City("c", tmp_path / "city", tmp_path, "warn"), SoakPaths(tmp_path), procfs=ProcFS(str(proc_tree.root)), t_inject=1000.0)


@pytest.mark.parametrize(
    "ended, logs",
    [
        ({"steady-1"}, []),
        # Only the incarnation the drill ended: the session never came back with a log.
        ({"steady-1"}, [an_inc("steady-1", 20, 900.0, [905.0], alive=False)]),
        # A drill that ended no session has nothing to judge, even with a good new incarnation.
        (set(), [an_inc("steady-1", 30, 1030.0, [1035.0])]),
    ],
)
def test_c5_fails_without_a_new_incarnation_of_each_ended_session(
    ended: Set[str], logs: List[Incarnation], proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock(2000.0)
    drill = c5_drill(tmp_path, proc_tree, monkeypatch, clock, lambda: logs)
    drill.c5(a_before(alive_incs={"b00tb00t:20:100"}), ended)
    [c5] = drill.criteria
    assert (c5.id, c5.passed, c5.measured["missing"]) == ("C5", False, sorted(ended))
    # It waited out its bound for a missing incarnation before failing.
    assert clock.now == (2000.0 + soakdrill.FIRST_TURN_WAIT_S if ended else 2000.0)


def test_c5_fails_on_a_first_turn_still_pending_at_its_bound(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The replacement is alive and never older than a second, so it is pending
    # at every read: C5 does not wait for it forever and does not pass it.
    clock = FakeClock(2000.0)
    drill = c5_drill(tmp_path, proc_tree, monkeypatch, clock, lambda: [an_inc("steady-1", 30, clock.now - 1.0)])
    drill.c5(a_before(), {"steady-1"}, {"steady-1"})
    [c5] = drill.criteria
    assert (c5.passed, c5.measured["pending"], c5.measured["missing"], c5.measured["new"]) == (False, ["steady-1"], [], 1)
    assert c5.measured["waited_s"] == soakdrill.FIRST_TURN_WAIT_S


def test_c5_fails_on_a_live_agent_without_its_log(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    city = str(tmp_path / "city")
    proc_tree.add(30, "soak-agent", env={"GC_CITY_PATH": city, "GC_SESSION_ID": "steady-1"})
    proc_tree.add(31, "soak-agent", env={"GC_CITY_PATH": city, "GC_SESSION_ID": "steady-2"})
    drill = c5_drill(tmp_path, proc_tree, monkeypatch, FakeClock(2000.0), lambda: [an_inc("steady-1", 30, 1030.0, [1035.0])])
    drill.c5(a_before(), {"steady-1"})
    [c5] = drill.criteria
    assert (c5.passed, c5.measured["unlogged"], c5.measured["missing"]) == (False, ["steady-2 pid 31"], [])


def test_c5_passes_on_an_exact_replacement_of_each_ended_session(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # steady-1 came back exact; steady-2 came back late and gets its first turn
    # 12 s into C5, which waits for it; a burst session that load started after
    # C5 began is still pending and is not judged; a survivor kept its one turn.
    # Each live agent has its log.
    city = str(tmp_path / "city")
    for pid, sid in ((30, "steady-1"), (31, "steady-2"), (32, "burst-1"), (40, "steady-3")):
        proc_tree.add(pid, "soak-agent", env={"GC_CITY_PATH": city, "GC_SESSION_ID": sid})
    clock = FakeClock(2000.0)

    def logs() -> List[Incarnation]:
        late = [2012.0] if clock.now >= 2012.0 else []
        return [
            an_inc("steady-3", 40, 900.0, [905.0]),
            an_inc("steady-1", 30, 1030.0, [1035.0]),
            an_inc("steady-2", 31, 1995.0, late),
            an_inc("burst-1", 32, 2001.0),
        ]

    drill = c5_drill(tmp_path, proc_tree, monkeypatch, clock, logs)
    drill.c5(a_before(alive_incs={"b00tb00t:40:100"}), {"steady-1", "steady-2"})
    [c5] = drill.criteria
    assert c5.passed is True, c5.measured
    assert c5.measured == {
        "expected": ["steady-1", "steady-2"],
        "new": 2,
        "missing": [],
        "pending": [],
        "bad_new": [],
        "survivors_duplicated": [],
        "unlogged": [],
        "waited_s": 15.0,
    }


def test_c5_fails_on_a_survivor_typed_its_first_turn_again(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The drill ended steady-1, which came back exact; steady-3 lived through
    # the drill and got its first turn a second time after it, which is how a
    # reconciler that adopts a session and types it again shows. Only the
    # survivor fails C5.
    city = str(tmp_path / "city")
    for pid, sid in ((30, "steady-1"), (40, "steady-3")):
        proc_tree.add(pid, "soak-agent", env={"GC_CITY_PATH": city, "GC_SESSION_ID": sid})
    logs = [an_inc("steady-3", 40, 900.0, [905.0, 1500.0]), an_inc("steady-1", 30, 1030.0, [1035.0])]
    drill = c5_drill(tmp_path, proc_tree, monkeypatch, FakeClock(2000.0), lambda: logs)
    drill.c5(a_before(alive_incs={"b00tb00t:40:100"}), {"steady-1"}, {"steady-1"})
    [c5] = drill.criteria
    assert (c5.passed, c5.measured["survivors_duplicated"]) == (False, ["steady-3"]), c5.measured
    assert [c5.measured[k] for k in ("missing", "pending", "bad_new", "unlogged")] == [[], [], [], []]


C5Call = Tuple[Before, Set[str], Optional[Set[str]]]


def record_c5(monkeypatch: pytest.MonkeyPatch) -> List[C5Call]:
    calls: List[C5Call] = []

    def c5(self: Drill, before: Before, expected: Any, sessions: Optional[Set[str]] = None) -> None:
        calls.append((before, set(expected), sessions))

    monkeypatch.setattr(Drill, "c5", c5)
    return calls


def test_the_drills_hand_c5_what_they_ended(proc_tree: ProcTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn: Spawn) -> None:
    calls = record_c5(monkeypatch)
    stub(monkeypatch, "f1_store_kept", "c1", "settle", "c4", "c6", "restore_pin", "kill")
    monkeypatch.setattr(Drill, "c2_c3", lambda self, before: {"steady-1": 10, "steady-2": 11})
    city = City("c", tmp_path / "city", tmp_path, "warn")
    # agent-kill: the one session it killed, and only its incarnations.
    monkeypatch.setattr(Drill, "inject_agent_kill", lambda self, before: "steady-1")
    Drill("agent-kill", city, SoakPaths(tmp_path)).drill_agent_kill(a_before())
    # holder-kill: every always-on session C2 found ended.
    holder = spawn()
    monkeypatch.setattr(Drill, "hc_owner", lambda self, role: lambda pid: None if pid == holder.pid else "not the test's child")
    monkeypatch.setattr(soakdrill, "GONE_WAIT_S", 0.0)
    Drill("holder-kill", city, SoakPaths(tmp_path), core=CITY_CORE).drill_holder_kill(a_before(CoreStatus(9, "0.1.19", (holder.pid,), 1)))
    assert holder.wait(timeout=10) == -signal.SIGKILL
    # stop-wedged: every always-on session that ran a box before the stop.
    core = spawn()
    monkeypatch.setattr(Drill, "inject", lambda self, *args: None)
    monkeypatch.setattr(soakdrill, "run", lambda argv, **_kwargs: CmdResult(tuple(argv), 0, "City stopped.", "", 0.1))
    monkeypatch.setattr(soakdrill, "remains", lambda *args: [])
    monkeypatch.setattr(Drill, "measure_recovery", lambda self, before, ended, pairs=(), dispatcher=False: ({s: 1.0 for s in ended}, None, 0.0))
    monkeypatch.setattr(Drill, "herdr_status", lambda self: "")
    boxes = {20: (100, "steady-3"), 21: (100, "burst-1")}
    Drill("stop-wedged", city, SoakPaths(tmp_path)).drill_stop_wedged(
        a_before(CoreStatus(core.pid, "0.1.19", (), 1), boxes=boxes, sessions={"steady-3": "soak-steady", "burst-1": "soak-burst"})
    )
    assert core.poll() is None
    # upgrade: the session its agent kill under the upgraded core ended, judged
    # against the state taken after the upgrade, not the drill's first one.
    upgraded = a_before()
    monkeypatch.setattr(Drill, "before", lambda self: upgraded)
    monkeypatch.setattr(Drill, "inject_agent_kill", lambda self, before: "steady-4" if before is upgraded else "not the upgraded state")
    monkeypatch.setattr(Drill, "gc_run", lambda self, argv, timeout=300.0: CmdResult(("gc", *argv), 0, soakdrill.UPGRADE_LINE, "", 0.1))
    stub(monkeypatch, "boxes_unchanged")
    paths = SoakPaths(tmp_path)
    (paths.pack / "assets").mkdir(parents=True)
    (paths.pack / "assets" / "hc-pin.json").write_text('{"version": "0.1.19"}\n', encoding="utf-8")
    Drill("upgrade", city, paths).drill_upgrade(a_before())
    assert [(expected, sessions) for _, expected, sessions in calls] == [
        ({"steady-1"}, {"steady-1"}),
        ({"steady-1", "steady-2"}, None),
        ({"steady-3"}, None),
        ({"steady-4"}, {"steady-4"}),
    ]
    assert calls[-1][0] is upgraded


def test_python_entry_points_compile() -> None:
    for name in ("soak", "soak-agent"):
        source = (SOAK / "bin" / name).read_text(encoding="utf-8")
        compile(source, name, "exec")
    assert sys.version_info >= (3, 9)
