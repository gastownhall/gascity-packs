"""The RPP entry point gc execs directly, with no shell, so its shebang is the
interpreter (gascity docs/reference/exec-session-provider.md "Calling Convention")."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import pytest

from gc_runtime_herdr_core import PACK_NAME, PACK_VERSION

PACK_ROOT = Path(__file__).resolve().parents[2]
ENTRY = PACK_ROOT / "assets" / "bin" / "gc-runtime-herdr-core"
SHEBANG = "#!/usr/bin/env -S python3 -I -S"


def invoke(
    *args: str,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    stdin: Optional[bytes] = None,
) -> "subprocess.CompletedProcess[bytes]":
    """Run the entry point under this interpreter with the shebang's flags."""
    return subprocess.run(
        [sys.executable, "-I", "-S", str(ENTRY), *args],
        cwd=str(cwd) if cwd else None,
        env=env if env is not None else {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_entry_point_is_an_executable_python_script() -> None:
    mode = stat.S_IMODE(os.stat(ENTRY).st_mode)
    assert mode & 0o555 == 0o555, oct(mode)  # anyone running gc may read and exec it
    assert not mode & 0o002, oct(mode)
    assert ENTRY.read_text(encoding="utf-8").splitlines()[0] == SHEBANG


def test_entry_point_ships_executable() -> None:
    # git keeps only 644 or 755, so the index mode is what every checkout gets.
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-s", "--", str(ENTRY)],
            cwd=str(PACK_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("git is not installed")
    if listed.returncode != 0 or not listed.stdout.strip():
        pytest.skip("not a git checkout of the pack")
    assert listed.stdout.split()[0] == "100755"


HANDSHAKE = {
    "version": 0,
    "capabilities": [
        "observe.v1",
        "report-attachment",
        "report-activity",
        "city-scoped",
        "conformance-faults",
        "server-lifecycle",
        "carrier.ops",
        "idle-boundary",
        "input-outcome",
        "fs.host",
    ],
    "locality": "local",
}


def test_protocol_answers_the_v2_ready_handshake(tmp_path: Path) -> None:
    done = invoke("protocol", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == HANDSHAKE
    assert done.stderr == b""


def test_fs_host_is_declared_with_local_locality(tmp_path: Path) -> None:
    # gc ignores fs.host without locality local. With it gc does the host work
    # and scans the process table for this pack; that scan fences tmux
    # subtrees only because proc.exec stays undeclared (the agent runs outside
    # tmux), which the next test pins.
    doc = json.loads(invoke("protocol", cwd=tmp_path).stdout)
    assert "fs.host" in doc["capabilities"]
    assert doc["locality"] == "local"


def test_the_handshake_never_declares_exec_or_provision(tmp_path: Path) -> None:
    # Under proc.exec gc would pipe tmux commands to `exec`; this runtime
    # declares only what it implements.
    caps = set(json.loads(invoke("protocol", cwd=tmp_path).stdout)["capabilities"])
    assert not caps & {"proc.exec", "proc.provision", "input-fence", "tty.attach", "proc.stream"}


def test_carrier_ops_never_routes_tmux_text(tmp_path: Path) -> None:
    # carrier.ops selects the pack's own driving ops, so gc never pipes tmux
    # commands to `exec`; and `exec` is unknown (exit 2) without reading
    # stdin, so even a gc that had not read the handshake runs nothing.
    caps = set(json.loads(invoke("protocol", cwd=tmp_path).stdout)["capabilities"])
    assert {"carrier.ops", "idle-boundary", "input-outcome"} <= caps
    assert "proc.exec" not in caps
    done = invoke("exec", "mc-a", cwd=tmp_path, stdin=b"tmux send-keys -t main 'echo pwned' Enter\n")
    assert done.returncode == 2 and done.stdout == b""


def test_protocol_reads_no_state_and_ignores_the_callers_python_environment(tmp_path: Path) -> None:
    poison = tmp_path / "poison"
    poison.mkdir()
    (poison / "json.py").write_text("raise SystemExit('shadowed stdlib json')\n")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(poison),
        "PYTHONSTARTUP": str(poison / "json.py"),
        "GC_EXEC_STATE_DIR": "relative-and-invalid",
        "HOME": "/nonexistent",
    }
    done = invoke("protocol", cwd=poison, env=env)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["version"] == 0
    assert sorted(p.name for p in poison.iterdir()) == ["json.py"]


def test_x_version_reports_the_pack(tmp_path: Path) -> None:
    done = invoke("x-version", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    doc = json.loads(done.stdout)
    assert doc["pack"] == PACK_NAME == "runtime-herdr-core"
    assert doc["version"] == PACK_VERSION
    assert doc["python"] == ".".join(str(n) for n in sys.version_info[:3])


@pytest.mark.parametrize("op", ["exec", "provision", "check-image", "frobnicate"])
def test_never_declared_ops_exit_2_unread_and_spawn_nothing(tmp_path: Path, op: str) -> None:
    # The default-tmux-server hazard: gc's tmux carrier drives input by piping
    # tmux commands to `exec` (exec-session-provider.md "Operations"); a pack
    # that ran them would drive whatever tmux server it reaches. The only tmux
    # on PATH here records any call.
    bindir = tmp_path / "bin"
    bindir.mkdir()
    sentinel = tmp_path / "tmux-was-run"
    fake_tmux = bindir / "tmux"
    fake_tmux.write_text(f"#!/bin/sh\ntouch {sentinel}\n")
    fake_tmux.chmod(0o755)
    payload = tmp_path / "stdin"
    payload.write_bytes(b"tmux send-keys -t main 'echo pwned' Enter\n")
    env = {"PATH": str(bindir), "TMUX_TMPDIR": str(tmp_path), "HOME": str(tmp_path)}
    with open(payload, "rb") as stdin:
        done = subprocess.run(
            [sys.executable, "-I", "-S", str(ENTRY), op, "mc-mayor"],
            cwd=str(tmp_path),
            env=env,
            stdin=stdin,
            capture_output=True,
            timeout=30,
            check=False,
        )
        offset = os.lseek(stdin.fileno(), 0, os.SEEK_CUR)
    assert done.returncode == 2
    assert offset == 0, "stdin was read"
    assert not sentinel.exists()
    assert done.stdout == b""


def test_the_shebang_runs_without_an_explicit_interpreter(tmp_path: Path) -> None:
    # gc execs the command itself: the kernel reads the shebang and env -S
    # splits it. Needs python3 on PATH, as on any host running the pack.
    python_dir = Path(sys.executable).parent
    done = subprocess.run(
        [str(ENTRY), "protocol"],
        cwd=str(tmp_path),
        env={"PATH": f"{python_dir}:/usr/bin:/bin"},
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == HANDSHAKE


def test_usage_without_an_op(tmp_path: Path) -> None:
    done = invoke(cwd=tmp_path)
    assert done.returncode == 2
    assert b"usage" in done.stderr


def test_protocol_loads_no_backend_code(tmp_path: Path) -> None:
    # Every op pays Python's start-up, so the static handshake must not pay
    # for the hc client, sockets or the schema tooling too.
    probe = (
        "import sys, time\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from gc_runtime_herdr_core.main import main\n"
        "rc = main(['gc-runtime-herdr-core', 'protocol'], started=time.monotonic())\n"
        "heavy = sorted(m for m in sys.modules if m.startswith('gc_runtime_herdr_core.hc') "
        "or m in ('socket', 'jsonschema', 'subprocess', 'threading'))\n"
        "print(rc, heavy, file=sys.stderr)\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-S", "-c", probe, str(PACK_ROOT / "assets")],
        cwd=str(tmp_path),
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert done.stderr.decode().strip() == "0 []"
