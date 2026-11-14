"""The live tier's pytest plugin (``tests/live/conftest.py`` loads it); see
that file for what the tier needs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import pytest

from . import guard
from .cases import Lane
from .scratch import Scratch, open_scratch, write_summary

HERE = Path(__file__).resolve().parents[1]

__all__ = [
    "clearance",
    "gc_bin",
    "hc_bin",
    "lane",
    "pytest_collection_modifyitems",
    "pytest_configure",
    "pytest_runtest_logreport",
    "pytest_sessionfinish",
    "scratch",
    "user_manager_missing",
]

_RESULTS: List[Tuple[str, str, str]] = []
_NOTES: Dict[str, object] = {}


def pytest_configure(config: pytest.Config) -> None:
    if not guard.live_requested(os.environ):
        return
    try:
        guard.clearance(os.environ)
    except guard.Refused as err:
        sys.stderr.write(f"{err}\n")
        pytest.exit(str(err), returncode=guard.REFUSED_EXIT)


def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    if guard.live_requested(os.environ):
        return
    skip = pytest.mark.skip(reason=f"live tier: set {guard.LIVE_ENV}=1 on a CI runner")
    for item in items:
        if HERE in Path(str(item.fspath)).parents:
            item.add_marker(skip)


def _summary_path() -> Optional[str]:
    return os.environ.get("GITHUB_STEP_SUMMARY") or None


def _summarize(text: str) -> None:
    path = _summary_path()
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


@pytest.fixture(scope="session")
def clearance() -> guard.Clearance:
    return guard.clearance(os.environ)


@pytest.fixture(scope="session")
def lane(clearance: guard.Clearance) -> Lane:
    value = os.environ.get(guard.LANE_ENV, "")
    if value == "plain":
        return "plain"
    if value == "systemd":
        why = user_manager_missing()
        if why is not None:
            message = f"the systemd lane has no user manager: {why}"
            _summarize(f"\n> [!CAUTION]\n> **{message}.** The systemd placement was NOT exercised.\n\n")
            pytest.exit(message, returncode=1)
        return "systemd"
    pytest.exit(f"{guard.LANE_ENV} must be plain or systemd, not {value!r}", returncode=2)
    raise AssertionError("unreachable")


def user_manager_missing() -> Optional[str]:
    """Why this user has no running systemd user manager, or None."""
    runtime = f"/run/user/{os.getuid()}"
    if not os.path.exists(os.path.join(runtime, "systemd", "private")):
        return f"{runtime}/systemd/private does not exist (enable lingering for this user)"
    env = dict(os.environ, XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS=f"unix:path={runtime}/bus")
    try:
        done = subprocess.run(
            ["systemctl", "--user", "is-system-running"], env=env, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return f"systemctl --user is-system-running failed: {err}"
    state = done.stdout.strip()
    if state not in ("running", "degraded"):
        return f"systemctl --user is-system-running says {state or done.stderr.strip()!r}"
    return None


@pytest.fixture(scope="session")
def hc_bin(clearance: guard.Clearance) -> str:
    path = os.environ.get(guard.HC_BIN_ENV, "")
    if not path or not os.path.isfile(path) or not os.access(path, os.X_OK):
        pytest.exit(f"{guard.HC_BIN_ENV} must name the pinned hc fetched by tests/live/fetch_hc.py", returncode=2)
    return path


@pytest.fixture(scope="session")
def gc_bin(clearance: guard.Clearance) -> str:
    path = os.environ.get(guard.GC_BIN_ENV, "")
    if not path or not os.access(path, os.X_OK):
        pytest.fail(f"{guard.GC_BIN_ENV} must name gc built at the pinned gascity commit")
    return path


@pytest.fixture
def scratch(request: pytest.FixtureRequest, clearance: guard.Clearance, lane: Lane, hc_bin: str) -> Iterator[Scratch]:
    made = open_scratch(clearance, lane, hc_bin)
    try:
        yield made
    finally:
        problems = made.close()
        for key, value in made.notes.items():
            _NOTES[f"{request.node.name}: {key}"] = value
        if made.teardown_notes:
            _NOTES[f"{request.node.name}: teardown"] = made.teardown_notes
        assert not problems, "teardown left the run's processes or units behind:\n" + "\n".join(problems)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        detail = ""
        if report.skipped and isinstance(report.longrepr, tuple):
            detail = str(report.longrepr[2])
        elif report.failed:
            detail = str(report.longreprtext).strip().splitlines()[-1][:300] if report.longreprtext else ""
        _RESULTS.append((report.nodeid.split("::", 1)[-1], report.outcome, detail))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not guard.live_requested(os.environ) or not _RESULTS:
        return
    lane = os.environ.get(guard.LANE_ENV, "?")
    lines = [f"\n### herdr-core live tier: {lane} lane\n\n", "| test | outcome | detail |\n", "|---|---|---|\n"]
    for name, outcome, detail in _RESULTS:
        lines.append(f"| `{name}` | {outcome} | {detail.replace('|', '/')} |\n")
    _summarize("".join(lines) + "\n")
    write_summary(_NOTES, _summary_path())
