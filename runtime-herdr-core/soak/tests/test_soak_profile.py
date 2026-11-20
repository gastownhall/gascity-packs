"""Soak 2: the profiles and their VM timers, and gc's runtime checks run in
a scratch city the harness removes after."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import List, Sequence

import pytest

from soakcli import parser
from soakconf import CONF_CITY_NAME, ConfScratch, conf_env, conf_run
from soakhc import Teardown
from soaklib import SoakPaths, append_jsonl
from soakprofile import PROFILES, profile, schedule_argv, timer_units
from soakreport import compute, load_inputs, render_markdown

SOAK = Path(__file__).resolve().parents[1]
BIN = SOAK / "bin"
HOUR = 3600


# --- (a) the conformance run's scratch city ------------------------------------------


def test_conf_env_names_a_scratch_city_under_the_scratch_dir(tmp_path: Path) -> None:
    scratch = ConfScratch(tmp_path / "hcconf.x")
    env = conf_env({"HOME": "/home/soak", "PATH": "/usr/bin", "GC_EXEC_CITY_PATH": "/home/soak/cities/hc-soak2"}, scratch)
    assert env["GC_EXEC_CITY_NAME"] == CONF_CITY_NAME
    assert env["GC_EXEC_CITY_PATH"] == str(tmp_path / "hcconf.x" / "city")
    assert env["GC_EXEC_STATE_DIR"] == str(tmp_path / "hcconf.x" / "state")
    assert env["HOME"] == "/home/soak" and env["PATH"] == "/usr/bin"
    # never a live city's name
    assert not CONF_CITY_NAME.startswith("hc-")


FAKE_GC = """#!/bin/sh
# records each call: argv, cwd and the scratch variables
printf '%s|%s|%s|%s|%s\\n' "$*" "$PWD" "${GC_EXEC_CITY_NAME-}" "${GC_EXEC_CITY_PATH-}" "${GC_EXEC_STATE_DIR-}" >> "$FAKE_GC_LOG"
case "$2" in
  check) echo "check ok"; exit "${FAKE_CHECK_EXIT:-0}" ;;
  conformance) echo '{"ok": true, "v2_ready": true, "results": []}'; echo "conf err" >&2; exit 0 ;;
esac
exit 9
"""


def fake_gc(tmp_path: Path) -> Path:
    gc = tmp_path / "gc"
    gc.write_text(FAKE_GC, encoding="utf-8")
    gc.chmod(0o755)
    return gc


def test_conf_run_runs_check_and_conformance_in_a_scratch_city_and_removes_it(tmp_path: Path) -> None:
    out = tmp_path / "data"
    out.mkdir()
    log = tmp_path / "calls.log"
    torn: List[str] = []
    seen_mode: List[int] = []

    def teardown(root: str) -> Teardown:
        torn.append(root)
        seen_mode.append(stat.S_IMODE(os.stat(root).st_mode))
        return Teardown(root=root)

    tmp = tmp_path / "tmp"
    tmp.mkdir()
    result = conf_run(
        "/p/gc-runtime-herdr-core", out, {"FAKE_GC_LOG": str(log), "PATH": "/usr/bin:/bin"},
        gc_bin=str(fake_gc(tmp_path)), teardown=teardown, tmp_dir=str(tmp),
    )
    calls = [line.split("|") for line in log.read_text(encoding="utf-8").splitlines()]
    assert [c[0] for c in calls] == ["runtime check /p/gc-runtime-herdr-core", "runtime conformance --json /p/gc-runtime-herdr-core"]
    scratch = Path(calls[0][1])
    assert scratch.parent == tmp and scratch.name.startswith("hcconf.")
    for _argv, cwd, name, city, state in calls:
        assert cwd == str(scratch)
        assert name == CONF_CITY_NAME and city == str(scratch / "city") and state == str(scratch / "state")
    assert torn == [str(scratch / "state")] and seen_mode == [0o700]
    assert not scratch.exists() and list(tmp.iterdir()) == []
    assert (out / "runtime-check.txt").read_text(encoding="utf-8") == "check ok\n"
    assert json.loads((out / "conformance.json").read_text(encoding="utf-8"))["v2_ready"] is True
    assert (out / "conformance.err").read_text(encoding="utf-8") == "conf err\n"
    assert json.loads((out / "conf-teardown.json").read_text(encoding="utf-8"))["ok"] is True
    rec = result.as_rec()
    assert rec == {"check": 0, "conformance": 0, "teardown": 0, "scratch_removed": True, "scratch": str(scratch)}
    assert result.ok


def test_conf_run_removes_the_scratch_dir_when_a_step_fails(tmp_path: Path) -> None:
    out = tmp_path / "data"
    out.mkdir()
    tmp = tmp_path / "tmp"
    tmp.mkdir()

    def teardown(root: str) -> Teardown:
        return Teardown(root=root, held_locks=[root + "/herdr-core/x/core.lock"])

    result = conf_run(
        "/p/e", out, {"FAKE_GC_LOG": str(tmp_path / "log"), "FAKE_CHECK_EXIT": "3"},
        gc_bin=str(fake_gc(tmp_path)), teardown=teardown, tmp_dir=str(tmp),
    )
    assert result.check == 3 and result.teardown == 1 and not result.ok
    assert list(tmp.iterdir()) == []

    def broken(root: str) -> Teardown:
        raise RuntimeError("teardown blew up")

    with pytest.raises(RuntimeError):
        conf_run("/p/e", out, {"FAKE_GC_LOG": str(tmp_path / "log")}, gc_bin=str(fake_gc(tmp_path)), teardown=broken, tmp_dir=str(tmp))
    assert list(tmp.iterdir()) == []


def test_conf_run_stops_the_scratch_cores_when_an_output_write_fails(tmp_path: Path) -> None:
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    torn: List[str] = []

    def teardown(root: str) -> Teardown:
        torn.append(root)
        return Teardown(root=root)

    with pytest.raises(OSError):
        conf_run(
            "/p/e", tmp_path / "missing-out", {"FAKE_GC_LOG": str(tmp_path / "log")},
            gc_bin=str(fake_gc(tmp_path)), teardown=teardown, tmp_dir=str(tmp),
        )
    assert len(torn) == 1 and torn[0].endswith("/state")
    assert list(tmp.iterdir()) == []


GC_RUNTIME = re.compile(r"\bgc runtime (check|conformance)\b")


def test_no_phase_script_runs_gcs_runtime_checks_outside_a_scratch_city() -> None:
    for script in sorted(BIN.iterdir()):
        text = script.read_text(encoding="utf-8")
        assert not GC_RUNTIME.search(text), f"{script.name} runs gc runtime directly; use `soak conf-run`"
    assert '"$SOAK" conf-run "$ENTRY" "$DATA"' in (BIN / "soak-phase1").read_text(encoding="utf-8")


def test_every_runbook_runtime_check_names_a_scratch_city() -> None:
    runbook = (SOAK / "RUNBOOK.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", runbook, flags=re.S)
    lines = [line for block in blocks for line in block.splitlines() if GC_RUNTIME.search(line)]
    assert lines, "the runbook shows the conformance run by hand"
    for line in lines:
        assert "GC_EXEC_CITY_PATH=" in line and "GC_EXEC_CITY_NAME=" in line and "GC_EXEC_STATE_DIR=" in line, line


# --- (b) the Soak 2 profile and its timers -------------------------------------------


def test_soak2_is_soak1s_city_and_load_with_six_hour_halves() -> None:
    one, two = PROFILES["soak1"], PROFILES["soak2"]
    assert two.city == "hc-soak2" and one.city == "hc-soak"
    assert (two.legacy_s, two.v2_s) == (6 * HOUR, 6 * HOUR)
    assert (one.legacy_s, one.v2_s) == (12 * HOUR, 12 * HOUR)
    assert (two.steady, two.burst, two.load, two.mode) == (one.steady, one.burst, one.load, one.mode) == (6, 10, "soak", "abort")
    assert profile("soak2") is two
    with pytest.raises(LookupError, match="soak3"):
        profile("soak3")


def test_soak2s_data_dir() -> None:
    paths = SoakPaths(Path("/home/soak"))
    assert PROFILES["soak2"].data(paths) == Path("/home/soak/soak-data/hc-soak2")
    assert PROFILES["soak2"].as_rec(paths)["data"] == "/home/soak/soak-data/hc-soak2"


def test_schedule_runs_the_switch_and_the_end_as_vm_timers() -> None:
    paths = SoakPaths(Path("/home/soak"))
    switch, end = schedule_argv(PROFILES["soak2"], paths, {"PATH": "/usr/local/bin:/usr/bin"})
    common = ["systemd-run", "--user"]
    assert switch[:2] == end[:2] == common
    assert "--unit=soak-hc-soak2-v2-switch" in switch and "--on-active=21600s" in switch
    assert "--unit=soak-hc-soak2-end" in end and "--on-active=43200s" in end
    for argv in (switch, end):
        assert "--setenv=PATH=/usr/local/bin:/usr/bin" in argv
    assert switch[switch.index("--") + 1 :] == ["/home/soak/soak/bin/soak-phase2", "hc-soak2", "soak-v2"]
    assert end[end.index("--") + 1 :] == ["/home/soak/soak/bin/soak-phase4", "end", "soak2"]
    assert timer_units("hc-soak2") == ("soak-hc-soak2-v2-switch.timer", "soak-hc-soak2-end.timer")


def test_the_parser_knows_the_soak2_subcommands() -> None:
    args = parser().parse_args(["conf-run", "/p/e", "/d"])
    assert (args.entry, args.out) == ("/p/e", "/d")
    assert parser().parse_args(["profile", "soak2"]).name == "soak2"
    args = parser().parse_args(["schedule", "soak2", "--dry-run"])
    assert args.name == "soak2" and args.dry_run


def test_phase4_takes_a_profile_and_schedules_the_timers() -> None:
    text = (BIN / "soak-phase4").read_text(encoding="utf-8")
    assert 'PROFILE="${2:-soak1}"' in text
    assert '"$SOAK" profile "$PROFILE"' in text
    assert '"$SOAK" schedule "$PROFILE"' in text
    assert "hc-soak" not in text


def test_an_abort_stops_the_scheduled_timers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import soakcapture
    import soakcheck
    from soaklib import City, CmdResult, ProcFS

    calls: List[List[str]] = []

    def fake_run(argv: Sequence[str], **_kw: object) -> CmdResult:
        calls.append(list(argv))
        return CmdResult(tuple(argv), 0, "", "", 0.0)

    monkeypatch.setattr(soakcheck, "run", fake_run)
    monkeypatch.setattr(soakcapture, "capture", lambda *a, **k: tmp_path / "capture")
    monkeypatch.setattr(soakcapture, "remains", lambda *a, **k: [])
    city = City("hc-soak2", tmp_path / "city", tmp_path, "abort")
    outcome = soakcheck.Outcome(t=0.0, phase="soak-legacy", mode="abort", hits=[soakcheck.Finding("AP1", "x")])
    soakcheck.abort(city, outcome, SoakPaths(tmp_path), "gc", ProcFS(str(tmp_path)))
    stopped = {unit for c in calls if c[:3] == ["systemctl", "--user", "stop"] for unit in c[3:]}
    assert {"soak-load.service", "soak-probe.timer", "soak-hc-soak2-v2-switch.timer", "soak-hc-soak2-end.timer"} <= stopped
    assert (tmp_path / "ABORTED").exists()


ABORT_STUBS = {
    "soak": """#!/usr/bin/env bash
echo "soak $*" >> "$STUB_LOG"
if [ "$1" = profile ]; then
  printf '{"city":"hc-soak2","steady":6,"burst":10,"load":"soak","mode":"abort","data":"%s"}\\n' "$HOME/soak-data/hc-soak2"
fi
exit 0
""",
    "gc": """#!/usr/bin/env bash
echo "gc $*" >> "$STUB_LOG"
exit 0
""",
    "systemctl": """#!/usr/bin/env bash
echo "systemctl $*" >> "$STUB_LOG"
exit 0
""",
}


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq is not installed")
@pytest.mark.parametrize("argv", [["soak-phase2", "hc-soak2", "soak-v2"], ["soak-phase4", "end", "soak2"]])
def test_the_scheduled_scripts_refuse_after_an_abort(argv: List[str], tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / "soak" / "bin").mkdir(parents=True)
    (home / "cities" / "hc-soak2").mkdir(parents=True)
    data = home / "soak-data" / "hc-soak2"
    data.mkdir(parents=True)
    (data / "ABORTED").write_text("AP1 x\n", encoding="utf-8")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in ABORT_STUBS.items():
        path = home / "soak" / "bin" / "soak" if name == "soak" else stubs / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    log = tmp_path / "calls.log"
    log.touch()
    env = {"HOME": str(home), "PATH": f"{stubs}:{os.environ.get('PATH', '/usr/bin:/bin')}", "STUB_LOG": str(log)}
    res = subprocess.run(["bash", str(BIN / argv[0]), *argv[1:]], env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 1, res.stderr
    assert "aborted" in res.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    # Only the guard and the profile read ran: no phase, no gc, no systemctl.
    assert all(c in ("soak guard", "soak profile soak2") for c in calls), calls


# --- (c) the report on a Soak 2 data directory ---------------------------------------


def test_the_report_reads_a_soak2_data_dir(tmp_path: Path) -> None:
    t0 = 1_800_000_000.0
    data = tmp_path / "hc-soak2"
    (data / "agents").mkdir(parents=True)
    for phase, t in (("soak-legacy", t0), ("soak-v2", t0 + 6 * HOUR), ("soak-end", t0 + 12 * HOUR)):
        append_jsonl(data / "phases.jsonl", {"t": t, "phase": phase, "reconciler": "v2" if phase != "soak-legacy" else "legacy"})
    trace = tmp_path / "optrace.log"
    trace.write_text("B 0\n", encoding="utf-8")
    report = compute(load_inputs(data, trace, lambda inc: False, t0 + 12 * HOUR + 900))
    assert report.city == "hc-soak2"
    legacy, v2 = [p for p in report.phases if p.window.name in ("soak-legacy", "soak-v2")]
    assert legacy.window.t1 - legacy.window.t0 == 6 * HOUR and v2.window.t1 - v2.window.t0 == 6 * HOUR
    assert render_markdown(report).startswith("# soak data: hc-soak2\n")
