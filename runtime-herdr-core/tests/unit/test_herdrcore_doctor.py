"""The doctor checks, run as gc runs them: ``doctor/<check>/run.sh`` with the
pack directory as cwd and gc's ``PackScriptCheck`` environment
(``GC_CITY_PATH`` and its siblings, ``GC_PACK_DIR``, ``GC_PACK_STATE_DIR``),
against an in-process fake-hc and a fake ``/proc``. Nothing here installs or
runs a real herdr-core."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import pytest
from fakehc import FakeHc
from fakehc.procfs import add_proc, add_unix_socket

from gc_runtime_herdr_core.hc.paths import HcPaths, ensure_dirs, resolve_paths
from gc_runtime_herdr_core.herdrcore import doctor
from gc_runtime_herdr_core.herdrcore.admin import admin_context, admin_host, controller_socket
from gc_runtime_herdr_core.herdrcore.core import core_env
from gc_runtime_herdr_core.herdrcore.pin import host_target, load_pin
from gc_runtime_herdr_core.rpp.cancel import CancelToken
from gc_runtime_herdr_core.rpp.statedir import DOCTOR_CITY_ENV, OP_CITY_ENV

PACK = Path(__file__).resolve().parents[2]
STUB = b"#!/bin/sh\nexit 0\n"
CORE_PID = os.getpid()
"""The in-process fake core's pid, as ``server.status`` reports it."""


def pack_script_env(city: Path, extra: Mapping[str, str]) -> Dict[str, str]:
    """gc's ``PackScriptCheck.Run`` environment: the caller's, plus
    ``citylayout.PackRuntimeEnv`` and ``GC_PACK_DIR``."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    runtime = city / ".gc" / "runtime"
    env.update(
        {
            "GC_CITY": str(city),
            "GC_CITY_PATH": str(city),
            "GC_CITY_RUNTIME_DIR": str(runtime),
            "GC_CONTROL_DISPATCHER_TRACE_DEFAULT": str(runtime / "control-dispatcher-trace.log"),
            "GC_PACK_STATE_DIR": str(runtime / "packs" / "runtime-herdr-core"),
            "GC_PACK_DIR": str(PACK),
        }
    )
    env.update(extra)
    return env


@dataclass
class DoctorCity:
    tmp: Path
    city: Path
    home: Path
    proc: Path
    env: Dict[str, str]
    paths: HcPaths
    fake: Optional[FakeHc] = None
    listeners: List[socket.socket] = field(default_factory=list)

    @property
    def install_root(self) -> Path:
        return self.home / ".local/share/gc-runtime-herdr-core/hc"

    @property
    def hc_bin(self) -> Path:
        return self.install_root / str(load_pin().version) / "herdr-core"

    def run(self, check: str) -> Tuple[int, List[str]]:
        done = subprocess.run(
            [str(PACK / "doctor" / check / "run.sh")],
            cwd=str(PACK),
            env=self.env,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert done.stderr == b"", done.stderr.decode()
        return done.returncode, done.stdout.decode().splitlines()

    def install_pinned(self, *, record: bool = True, mode: int = 0o555) -> None:
        """Lay out the pinned install as ``gc herdr-core install`` leaves it."""
        pin = load_pin()
        binary = self.hc_bin
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.parent.chmod(0o755)
        for leftover in binary.parent.iterdir():
            leftover.chmod(0o644)
            leftover.unlink()
        binary.write_bytes(STUB)
        if record:
            doc = {
                "version": str(pin.version),
                "target": host_target(),
                "archive_sha256": pin.target(host_target()).sha256,
                "binary_sha256": hashlib.sha256(STUB).hexdigest(),
                "installed_ms": 1,
            }
            (binary.parent / "install.json").write_text(json.dumps(doc))
            (binary.parent / "install.json").chmod(0o444)
        binary.chmod(mode)
        binary.parent.chmod(mode)

    def expected_core_env(self) -> Dict[str, str]:
        ctx = admin_context(self.env, admin_host(self.env, sys.executable), name="t", deadline_s=5, cancel=CancelToken())
        return core_env(ctx, str(self.hc_bin))

    def start_core(self, *, version: str = "0.1.19", environ: Optional[Dict[str, str]] = None, exe: Optional[str] = None, cgroup: Optional[str] = None) -> FakeHc:
        """Serve the city's socket with a core of ``version`` that runs, by
        default, the pack's install of that version."""
        ensure_dirs(self.paths)
        self.fake = FakeHc(self.paths.socket, version=version)
        self.fake.start()
        add_proc(
            self.proc,
            CORE_PID,
            ppid=1,
            argv=[str(self.hc_bin), "serve"],
            env=self.expected_core_env() if environ is None else environ,
            exe=exe or str(self.install_root / version / "herdr-core"),
            cgroup=cgroup,
        )
        return self.fake

    def run_city(self) -> None:
        """Answer on the city's controller socket, as a running city does."""
        path = controller_socket(str(self.city))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path)
        listener.listen(4)
        self.listeners.append(listener)


@pytest.fixture
def dc(short_tmp: Path, home_dir: Path) -> Iterator[DoctorCity]:
    city = short_tmp / "city"
    city.mkdir()
    proc = short_tmp / "proc"
    proc.mkdir()
    add_proc(proc, 1, ppid=0, argv=["/sbin/init"])
    run_dir = short_tmp / "run"
    run_dir.mkdir()
    linger = short_tmp / "linger"
    linger.mkdir()
    (linger / pwd.getpwuid(os.getuid()).pw_name).write_text("")
    env = pack_script_env(
        city,
        {
            "GC_EXEC_STATE_DIR": str(short_tmp / "R"),
            "GC_HC_TEST": "1",
            "GC_HC_TEST_HOME": str(home_dir),
            "GC_HC_TEST_PROC_ROOT": str(proc),
            "GC_HC_TEST_RUNTIME_DIR": str(run_dir),
            "GC_HC_TEST_LINGER_DIR": str(linger),
        },
    )
    paths = resolve_paths(env, home=lambda: str(home_dir), city_var=DOCTOR_CITY_ENV)
    made = DoctorCity(tmp=short_tmp, city=city, home=home_dir, proc=proc, env=env, paths=paths)
    try:
        yield made
    finally:
        for listener in made.listeners:
            listener.close()
        if made.fake is not None:
            made.fake.close()
            assert made.fake.schema_violations == []
        for path in made.home.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)


def test_doctor_and_ops_resolve_one_core_for_one_city(dc: DoctorCity) -> None:
    as_op = resolve_paths({**dc.env, OP_CITY_ENV: str(dc.city)}, home=lambda: str(dc.home))
    assert as_op == dc.paths


def test_every_check_is_a_two_line_wrapper_gc_discovers(dc: DoctorCity) -> None:
    for check in ("hc-binary", "hc-core", "hc-scope-hygiene", "hc-state-perms"):
        script = PACK / "doctor" / check / "run.sh"
        assert os.access(script, os.X_OK)
        assert script.read_text().splitlines()[1].endswith(f"x-doctor {check}")
        assert (PACK / "doctor" / check / "doctor.toml").read_text().startswith("description = ")
    assert "hc-serve" not in os.listdir(PACK / "doctor")


def test_hc_python_answers_without_loading_the_pack(dc: DoctorCity) -> None:
    code, lines = dc.run("hc-python")
    assert code == 0 and lines[0].startswith("python3 3.")


# --- hc-binary ----------------------------------------------------------------------


def test_hc_binary_errors_when_hc_is_not_installed(dc: DoctorCity) -> None:
    code, lines = dc.run("hc-binary")
    assert code == 2
    assert lines[0].startswith("hc not installed") and "gc herdr-core install" in lines[0]
    assert str(dc.home) in lines[0]


def test_hc_binary_passes_for_the_verified_pinned_install(dc: DoctorCity) -> None:
    dc.install_pinned()
    code, lines = dc.run("hc-binary")
    assert (code, lines[0]) == (0, f"herdr-core 0.1.19 installed and matching the pin ({host_target()})")


def test_hc_binary_warns_on_an_install_it_cannot_verify_or_a_writable_one(dc: DoctorCity) -> None:
    dc.install_pinned(record=False)
    code, lines = dc.run("hc-binary")
    assert code == 1 and "cannot be checked against the pin" in lines[0]
    dc.install_pinned(record=True, mode=0o755)
    code, lines = dc.run("hc-binary")
    assert code == 1 and "writable" in " ".join(lines)


def test_hc_binary_errors_on_a_changed_binary(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.hc_bin.chmod(0o755)
    dc.hc_bin.write_bytes(b"#!/bin/sh\nexit 1\n")
    dc.hc_bin.chmod(0o555)
    code, lines = dc.run("hc-binary")
    assert code == 2 and "changed since it was installed" in lines[0]


def pack_config(dc: DoctorCity, doc: Dict[str, object]) -> None:
    state = Path(dc.paths.state_root) / "pack" / dc.paths.city_id
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    for part in (Path(dc.paths.state_root), Path(dc.paths.state_root) / "pack", state):
        part.chmod(0o700)
    (state / "config.json").write_text(json.dumps(doc))
    (state / "config.json").chmod(0o600)


def test_hc_binary_errors_on_an_unpinned_binary_unless_allowed(dc: DoctorCity) -> None:
    chosen = dc.tmp / "my-hc"
    chosen.write_bytes(STUB)
    chosen.chmod(0o755)
    pack_config(dc, {"hc_bin": str(chosen)})
    code, lines = dc.run("hc-binary")
    assert code == 2 and "unpinned" in lines[0] and "allow_unpinned" in lines[0]
    pack_config(dc, {"hc_bin": str(chosen), "allow_unpinned": True})
    code, lines = dc.run("hc-binary")
    assert code == 1 and "drives an unpinned hc" in lines[0]


# --- hc-core --------------------------------------------------------------------------


def test_hc_core_is_ok_without_a_core_for_a_stopped_city(dc: DoctorCity) -> None:
    assert dc.run("hc-core") == (0, ["no core runs (the city is stopped)"])
    dc.run_city()
    assert dc.run("hc-core") == (0, ["no core runs (no session of the city has needed one)"])
    assert not Path(dc.paths.state_root).exists(), "doctor wrote state"


def write_kick(dc: DoctorCity, *, ok: bool, age_ms: int, detail: str) -> None:
    state = Path(dc.paths.state_root) / "pack" / dc.paths.city_id
    pack_config(dc, {})
    (state / "kick.json").write_text(json.dumps({"at_ms": int(time.time() * 1000) - age_ms, "ok": ok, "detail": detail}))
    (state / "kick.json").chmod(0o600)


def test_hc_core_errors_when_a_running_citys_core_is_down(dc: DoctorCity) -> None:
    dc.run_city()
    write_kick(dc, ok=True, age_ms=20 * 60 * 1000, detail="started")
    code, lines = dc.run("hc-core")
    assert code == 2 and lines[0].startswith("the city runs but its core does not answer")


def test_hc_core_is_ok_for_a_city_server_stop_parked(dc: DoctorCity) -> None:
    """`gc stop` runs server-stop, which parks the city and stops its core; a
    `gc start` with no herdr-core session due leaves it down on purpose, and
    no read kicks it, so an old kick record is no sign of a core that fails."""
    dc.run_city()
    write_kick(dc, ok=True, age_ms=3 * 24 * 3600 * 1000, detail="started")
    state = Path(dc.paths.state_root) / "pack" / dc.paths.city_id
    (state / "parked.json").write_text(json.dumps({"at_ms": int(time.time() * 1000)}) + "\n")
    (state / "parked.json").chmod(0o600)
    code, lines = dc.run("hc-core")
    assert (code, lines) == (0, ["no core runs (stopped by server-stop; the next session start brings it back)"])


def test_hc_core_errors_on_a_crash_looping_core(dc: DoctorCity) -> None:
    write_kick(dc, ok=False, age_ms=1000, detail="hc server start exited 1")
    code, lines = dc.run("hc-core")
    assert code == 2 and "failed to start in the last 5 minutes" in lines[0] and "exited 1" in lines[0]


def test_hc_core_passes_for_the_packs_own_pinned_core(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.run_city()
    dc.start_core()
    code, lines = dc.run("hc-core")
    assert (code, lines[0]) == (0, "the city's core runs herdr-core 0.1.19"), lines


def test_hc_core_warns_when_the_core_differs_from_the_pin(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.run_city()
    dc.start_core(version="0.1.20")
    code, lines = dc.run("hc-core")
    assert code == 1
    assert lines[0] == "the city's core runs hc 0.1.20, the pin is 0.1.19: run `gc herdr-core upgrade`"
    assert any("not a tested version" in line for line in lines)


def test_hc_core_warns_on_a_core_still_running_a_previous_install(dc: DoctorCity) -> None:
    # Between `install` of a new pin and `upgrade`, the core runs the build
    # the pack installed before: a warning naming upgrade, never an error.
    dc.install_pinned()
    dc.run_city()
    dc.start_core(version="0.1.20", exe=str(dc.install_root / "0.1.20" / "herdr-core") + " (deleted)")
    code, lines = dc.run("hc-core")
    assert code == 1, lines
    assert "gc herdr-core upgrade" in lines[0]
    assert not any("not the pack's" in line for line in lines)


def test_hc_core_errors_on_a_core_running_from_outside_the_install_root(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.run_city()
    dc.start_core(exe=str(dc.tmp / "elsewhere" / "0.1.19" / "herdr-core"))
    code, lines = dc.run("hc-core")
    assert code == 2 and "not the pack's" in lines[0] and "restart-core" in lines[0]


def test_hc_core_warns_on_a_core_running_for_a_stopped_city(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.start_core()
    code, lines = dc.run("hc-core")
    assert code == 1
    assert lines[0].startswith(f"the city is stopped but its core still runs (pid {CORE_PID}, ")


def test_hc_core_names_the_user_manager_only_on_linux(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.run_city()
    dc.env["GC_HC_TEST_RUNTIME_DIR"] = str(dc.tmp / "no-such-run-dir")
    dc.start_core()
    ctx = admin_context(dc.env, admin_host(dc.env, sys.executable), name="t", deadline_s=5, cancel=CancelToken())
    linux = doctor.check_core(ctx, linger_dir=dc.env["GC_HC_TEST_LINGER_DIR"], platform="linux")
    assert linux.status == doctor.Status.WARNING and linux.message.startswith("no systemd user manager")
    darwin = doctor.check_core(ctx, linger_dir=dc.env["GC_HC_TEST_LINGER_DIR"], platform="darwin")
    assert darwin.status == doctor.Status.OK, darwin.render()


def test_hc_core_errors_on_a_core_older_than_the_minimum(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.run_city()
    dc.start_core(version="0.1.18")
    code, lines = dc.run("hc-core")
    assert code == 2 and "older than the minimum" in lines[0] and "gc herdr-core upgrade" in lines[0]


def test_hc_core_errors_on_a_foreign_core(dc: DoctorCity) -> None:
    dc.install_pinned()
    foreign = dict(dc.expected_core_env())
    foreign["OPENAI_API_KEY"] = "sk-secret-value"
    dc.start_core(environ=foreign)
    code, lines = dc.run("hc-core")
    assert code == 2
    assert lines[0].startswith("city core was started outside the pack: run `gc herdr-core restart-core`")
    assert "OPENAI_API_KEY" in lines[0] and "sk-secret-value" not in "\n".join(lines)


def test_hc_core_errors_on_a_core_running_another_binary(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.start_core(exe="/home/someone/.local/bin/herdr-core")
    code, lines = dc.run("hc-core")
    assert code == 2 and "not the pack's" in lines[0] and "restart-core" in lines[0]


def test_hc_core_hints_at_lingering_and_the_user_manager(dc: DoctorCity) -> None:
    dc.install_pinned()
    dc.run_city()
    for flag in Path(dc.env["GC_HC_TEST_LINGER_DIR"]).iterdir():
        flag.unlink()
    dc.start_core()
    code, lines = dc.run("hc-core")
    assert code == 1 and "lingering is off" in lines[0]
    dc.fake.close() if dc.fake else None
    dc.env["GC_HC_TEST_RUNTIME_DIR"] = str(dc.tmp / "no-such-run-dir")
    for leaf in ("environ", "exe", "cgroup", "cmdline", "stat"):
        (dc.proc / str(CORE_PID) / leaf).unlink(missing_ok=True)
    dc.start_core()
    code, lines = dc.run("hc-core")
    assert code == 1 and lines[0].startswith("no systemd user manager")


def test_hc_core_errors_on_a_core_of_the_session_on_another_socket(dc: DoctorCity) -> None:
    ensure_dirs(dc.paths)
    other = dc.tmp / "other.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(other))
    listener.listen(1)
    dc.listeners.append(listener)
    Path(dc.paths.core_lock).write_text(str(other))
    code, lines = dc.run("hc-core")
    assert code == 2 and str(other) in lines[0] and "restart-core" in lines[0]


# --- hc-scope-hygiene --------------------------------------------------------------------

DOLT = "/usr/local/bin/dolt"
GC = "/opt/gc/bin/gc"
BD = "/usr/local/bin/bd"


def infra(dc: DoctorCity, pid: int, argv: Sequence[str], *, ppid: int = 1, env: Optional[Dict[str, str]] = None, cgroup: Optional[str] = None, sockets: Sequence[int] = ()) -> None:
    add_proc(dc.proc, pid, ppid=ppid, argv=list(argv), env=env or {"PATH": "/usr/bin"}, cgroup=cgroup, sockets=sockets)


def test_scope_hygiene_is_ok_when_infrastructure_runs_outside_hc(dc: DoctorCity) -> None:
    infra(dc, 100, [DOLT, "sql-server", "--config", f"{dc.city}/.gc/runtime/packs/dolt/dolt-config.yaml"])
    infra(dc, 101, [GC, "__gc-managed-dolt-scope-watchdog", "cfg", "log", str(dc.city)])
    code, lines = dc.run("hc-scope-hygiene")
    assert (code, lines) == (0, ["no city infrastructure runs under herdr-core (2 checked)"])


def test_scope_hygiene_flags_hc_scope_attributed_by_config_path(dc: DoctorCity) -> None:
    infra(dc, 100, [DOLT, "sql-server", "--config", f"{dc.city}/.gc/runtime/packs/dolt/dolt-config.yaml"], env={"HC_SCOPE": "t3"})
    code, lines = dc.run("hc-scope-hygiene")
    assert code == 2 and lines[0].startswith("city infrastructure runs under herdr-core")
    assert "Dolt server (pid 100) carries HC_SCOPE" in lines[1]


def test_scope_hygiene_flags_an_hc_holder_ancestor(dc: DoctorCity) -> None:
    infra(dc, 50, ["/home/u/.local/bin/herdr-core", "hold", "x"])
    infra(dc, 60, ["/bin/sh"], ppid=50)
    infra(dc, 101, [GC, "__gc-managed-dolt-scope-watchdog", "cfg", "log", str(dc.city)], ppid=60)
    code, lines = dc.run("hc-scope-hygiene")
    assert code == 2 and "managed Dolt watchdog (pid 101) runs under herdr-core (pid 50, " in "\n".join(lines)


def test_scope_hygiene_flags_an_hc_holder_cgroup(dc: DoctorCity) -> None:
    infra(dc, 102, [BD, "db-proxy-child", "--root", f"{dc.city}/.beads/dolt"], cgroup="/user.slice/user-1000.slice/user@1000.service/app.slice/hc-hold-ab12.service")
    code, lines = dc.run("hc-scope-hygiene")
    assert code == 2 and "bd database proxy (pid 102) runs in herdr-core's cgroup hc-hold-ab12.service" in "\n".join(lines)


def test_scope_hygiene_attributes_by_gc_city_environment(dc: DoctorCity) -> None:
    infra(dc, 102, [BD, "db-proxy-child", "--root", "/srv/shared"], env={"GC_CITY_PATH": str(dc.city), "HC_SCOPE": "t9"})
    code, _ = dc.run("hc-scope-hygiene")
    assert code == 2


def test_scope_hygiene_ignores_other_cities_and_nudge_pollers(dc: DoctorCity) -> None:
    infra(dc, 100, [DOLT, "sql-server", "--config", "/other/city/.gc/dolt.yaml"], env={"HC_SCOPE": "t1"})
    infra(dc, 103, [GC, "nudge", "poll", str(dc.city), "s"], env={"HC_SCOPE": "t2", "GC_CITY_PATH": str(dc.city)})
    infra(dc, 104, [GC, "supervisor", "run"], env={"HC_SCOPE": "t3"})
    code, lines = dc.run("hc-scope-hygiene")
    assert (code, lines) == (0, ["no city infrastructure runs under herdr-core (0 checked)"])


def test_scope_hygiene_attributes_the_supervisor_holding_the_citys_controller_socket(dc: DoctorCity) -> None:
    add_unix_socket(dc.proc, 7777, controller_socket(str(dc.city)))
    infra(dc, 104, [GC, "supervisor", "run"], env={"HC_SCOPE": "t3"}, sockets=[7777])
    infra(dc, 105, [GC, "supervisor", "run"], env={"HC_SCOPE": "t4"})
    code, lines = dc.run("hc-scope-hygiene")
    assert code == 2 and "gc supervisor (pid 104) carries HC_SCOPE" in "\n".join(lines)
    assert "pid 105" not in "\n".join(lines)


# --- hc-state-perms ---------------------------------------------------------------------


def write_terminals(dc: DoctorCity, mode: int) -> Path:
    """terminals.json as hc writes it (``std::fs::write``: 0666 less the umask)."""
    path = Path(dc.paths.state_dir) / "terminals.json"
    path.write_text("{}")
    path.chmod(mode)
    return path


def test_state_perms_flags_a_readable_hc_state_directory(dc: DoctorCity) -> None:
    assert dc.run("hc-state-perms")[0] == 0
    ensure_dirs(dc.paths)
    write_terminals(dc, 0o644)
    os.chmod(dc.paths.state_dir, 0o755)
    code, lines = dc.run("hc-state-perms")
    assert code == 2 and "open to others" in lines[0]
    # R itself is still 0700: nobody else reaches the file.
    assert not any("terminals.json" in line for line in lines)
    for part in (dc.paths.state_root, os.path.dirname(dc.paths.state_dir)):
        os.chmod(part, 0o755)
    code, lines = dc.run("hc-state-perms")
    assert code == 2 and any("terminals.json is readable by others (mode 644)" in line for line in lines)


def test_state_perms_accepts_hcs_umask_file_inside_private_directories(dc: DoctorCity) -> None:
    ensure_dirs(dc.paths)
    write_terminals(dc, 0o644)
    code, lines = dc.run("hc-state-perms")
    assert (code, lines[0]) == (0, "hc's state is private"), lines


def test_state_perms_flags_a_state_directory_others_can_traverse(dc: DoctorCity) -> None:
    ensure_dirs(dc.paths)
    write_terminals(dc, 0o600)
    os.chmod(os.path.dirname(dc.paths.state_dir), 0o711)
    code, lines = dc.run("hc-state-perms")
    assert code == 2 and "open to others (mode 711)" in lines[0]


# --- the budget ------------------------------------------------------------------------


def test_a_check_that_runs_out_of_its_budget_warns(dc: DoctorCity, monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(ctx: object) -> doctor.Report:
        time.sleep(5)
        return doctor.Report()

    monkeypatch.setitem(doctor.CHECKS, "hc-binary", hang)
    started = time.monotonic()
    report = doctor.run_check("hc-binary", dc.env, admin_host(dc.env, sys.executable), budget_s=0.3)
    assert time.monotonic() - started < 2
    assert (report.status, report.message) == (doctor.Status.WARNING, "timed out after 0.3 s")


def test_every_check_finishes_within_its_budget_against_a_silent_core(dc: DoctorCity) -> None:
    dc.install_pinned()
    fake = dc.start_core()
    fake.delay_reply("hello", 30.0, count=100)
    started = time.monotonic()
    code, lines = dc.run("hc-core")
    assert time.monotonic() - started < doctor.CHECK_BUDGET_S + 2
    assert code == 1 and "did not answer" in lines[0]
