"""The per-op benchmark (``tests/bench_ops.py``) runs end to end on a scratch
root and leaves nothing behind: no scratch directory, no core answering."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import pytest

PACK_ROOT = Path(__file__).resolve().parents[2]
BENCH = PACK_ROOT / "tests" / "bench_ops.py"


def _answers(path: str) -> bool:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2.0)
        try:
            sock.connect(path)
        except OSError:
            return False
    return True


def _processes_under(root: str) -> List[int]:
    """Pids of processes whose environment points at scratch root ``root``."""
    found: List[int] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            env = Path(f"/proc/{entry}/environ").read_bytes().split(b"\0")
        except OSError:
            continue
        if any(item.startswith(b"GC_EXEC_STATE_DIR=" + root.encode()) or item.startswith(b"XDG_STATE_HOME=" + root.encode()) for item in env):
            found.append(int(entry))
    return found


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")
def test_bench_runs_on_a_scratch_root_and_cleans_up() -> None:
    done = subprocess.run(
        [sys.executable, str(BENCH), "--runs", "1", "--sessions", "1", "--ops", "protocol,get-meta", "--json", "--python", sys.executable],
        capture_output=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    report = json.loads(done.stdout)
    results: Dict[str, List[Dict[str, float]]] = report["results"]
    assert sorted(results) == ["get-meta", "protocol"]
    for label in ("protocol", "get-meta"):
        assert results[label][0]["runs"] == 1
        assert results[label][0]["cpu_ms_median"] > 0
    scratch = str(report["scratch"])
    assert scratch.startswith("/tmp/hcbench-")
    assert not os.path.exists(scratch)
    assert report["sockets"], "the bench's sessions started a core"
    assert not any(_answers(path) for path in report["sockets"])
    end = time.monotonic() + 30.0
    while _processes_under(scratch) and time.monotonic() < end:
        time.sleep(0.1)  # a stopped core may take a moment to exit
    assert _processes_under(scratch) == []
