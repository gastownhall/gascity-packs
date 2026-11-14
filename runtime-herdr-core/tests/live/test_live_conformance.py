"""gc's own checks of the runtime, against the pinned hc instead of fake-hc:
``gc runtime check`` and ``gc runtime conformance --json``, which must report
v2-ready with no failed requirement. gc is built at the pinned gascity
commit, the same one the fake-hc conformance job uses."""

from __future__ import annotations

import json
import subprocess
from typing import Dict, List

from livekit.pack import ENTRY
from livekit.scratch import Scratch

TIMEOUT_S = 900


def _gc_env(scratch: Scratch) -> Dict[str, str]:
    env = scratch.pack_env(rescope=scratch.lane == "systemd")
    del env["GC_EXEC_CITY_PATH"]  # the kit names its own cities
    return env


def test_gc_runtime_check_passes(scratch: Scratch, gc_bin: str) -> None:
    done = subprocess.run(
        [gc_bin, "runtime", "check", str(ENTRY)],
        env=_gc_env(scratch),
        cwd=scratch.work,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_gc_runtime_conformance_is_v2_ready(scratch: Scratch, gc_bin: str) -> None:
    done = subprocess.run(
        [gc_bin, "runtime", "conformance", "--json", str(ENTRY)],
        env=_gc_env(scratch),
        cwd=scratch.work,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )
    try:
        report = json.loads(done.stdout)
    except ValueError:
        raise AssertionError(f"gc wrote no JSON report (exit {done.returncode}):\n{done.stderr[-4000:]}") from None
    results: List[Dict[str, str]] = report["results"]
    counts: Dict[str, int] = {}
    for result in results:
        status = result["status"].lower()
        counts[status] = counts.get(status, 0) + 1
    failed = [r["code"] for r in results if r["status"].lower() == "fail"]
    scratch.note("conformance", {"v2_ready": report.get("v2_ready"), "counts": counts, "failed": failed})
    assert not failed, f"failed requirements: {failed}\n{done.stderr[-4000:]}"
    assert report["v2_ready"] is True, "not v2-ready"
    assert done.returncode == 0, done.stderr[-4000:]
