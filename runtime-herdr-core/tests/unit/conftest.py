"""Shared fixtures for the runtime-herdr-core unit tier.

The pack's package lives under ``assets/`` (pack-spec: private support files)
and the fake-hc under ``tests/fakehc``; both go on ``sys.path`` here so the
tier runs the same from the pack root (the pack's CI job) and from the
repository root (the shared pytest step).

No test in this tier builds, installs or runs a real herdr-core binary: every
hc conversation is with the in-process fake-hc, whose every result and every
client request is checked against the vendored hc schema.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterator, List, Optional

import pytest

PACK_ROOT = Path(__file__).resolve().parents[2]
for _entry in (PACK_ROOT / "assets", PACK_ROOT / "tests", PACK_ROOT / "tests" / "unit"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from fakehc import FakeHc  # noqa: E402
from gc_runtime_herdr_core.hc.client import CallTimeouts, CoreEndpoint, HcClient  # noqa: E402
from gc_runtime_herdr_core.hc.version import Version, VersionPolicy  # noqa: E402
from gc_runtime_herdr_core.rpp.cancel import CancelToken, Deadline  # noqa: E402

TEST_POLICY = VersionPolicy(min_version=Version.parse("0.1.19"), tested=(Version.parse("0.1.19"),))

ClientFactory = Callable[..., HcClient]


@pytest.fixture
def short_tmp() -> Iterator[Path]:
    """A short private directory: a Unix socket path must fit in sun_path."""
    path = os.path.realpath(tempfile.mkdtemp(prefix="hcrt-", dir="/tmp"))  # /tmp is a symlink on macOS
    try:
        yield Path(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def fake_hc(short_tmp: Path) -> Iterator[FakeHc]:
    """A running fake-hc; the test fails if any reply or request left the schema."""
    fake = FakeHc(str(short_tmp / "hc.sock"))
    fake.start()
    try:
        yield fake
    finally:
        fake.close()
    assert fake.schema_violations == [], "fake-hc schema guard:\n" + "\n".join(fake.schema_violations)


@pytest.fixture
def gate_policy() -> VersionPolicy:
    """The gate policy matching fake-hc's default version."""
    return TEST_POLICY


@pytest.fixture
def make_client(fake_hc: FakeHc) -> ClientFactory:
    """Build an HcClient for one op against the fake (fresh endpoint per call)."""

    def factory(
        *,
        deadline_s: float = 30.0,
        read: bool = False,
        probe: bool = False,
        cancel: Optional[CancelToken] = None,
        endpoint: Optional[CoreEndpoint] = None,
        inject_unavailable: bool = False,
    ) -> HcClient:
        return HcClient(
            endpoint or CoreEndpoint(fake_hc.socket_path, policy=TEST_POLICY),
            deadline=Deadline.after(deadline_s),
            cancel=cancel or CancelToken(),
            timeouts=CallTimeouts.for_op(read=read, probe=probe),
            inject_unavailable=inject_unavailable,
        )

    return factory


@pytest.fixture
def home_dir(tmp_path: Path) -> Path:
    """Stands in for the password-database home: tests never write the real one."""
    home = tmp_path / "pwhome"
    home.mkdir(mode=0o755)
    return home


@pytest.fixture
def city(short_tmp: Path, home_dir: Path) -> Iterator["City"]:
    """An in-process city with its fake-hc core running (see cityharness)."""
    from cityharness import make_city

    made = make_city(short_tmp, home_dir)
    made.start_core()
    try:
        yield made
    finally:
        teardown_cores(made.root / "R")
        if made.fake is not None:
            made.fake.close()
            assert made.fake.schema_violations == [], "fake-hc schema guard:\n" + "\n".join(made.fake.schema_violations)


def _processes_for(root: Path, marker: str) -> List[int]:
    """Pids of this user's processes whose argv holds ``marker`` and whose
    environment points at state root ``root`` (``GC_EXEC_STATE_DIR`` or ``XDG_STATE_HOME``)."""
    found: List[int] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            argv = Path(f"/proc/{entry}/cmdline").read_bytes()
            if marker.encode() not in argv:
                continue
            env = Path(f"/proc/{entry}/environ").read_bytes().split(b"\0")
        except OSError:
            continue
        wanted = {f"GC_EXEC_STATE_DIR={root}".encode(), f"XDG_STATE_HOME={root}".encode()}
        if wanted & set(env):
            found.append(int(entry))
    return found


def teardown_cores(root: Path, timeout: float = 30.0) -> None:
    """Wait out every background core start a test's ops kicked, stop every
    core under ``root``, and fail the test if one survives (killing it)."""
    import signal
    import time

    if not sys.platform.startswith("linux"):
        stop_cores(root)
        return
    end = time.monotonic() + timeout
    while _processes_for(root, "x-kick-core") and time.monotonic() < end:
        time.sleep(0.05)
    stop_cores(root)
    while _processes_for(root, "cli.py") and time.monotonic() < end:
        time.sleep(0.05)
    leaked = _processes_for(root, "cli.py") + _processes_for(root, "x-kick-core")
    for pid in leaked:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    assert not leaked, f"standalone fake cores or kicks outlived the test: {leaked}"


def stop_cores(root: Path) -> None:
    """Stop every standalone core a test's ops started under state root ``root``."""
    from fakehc.rawclient import raw_call

    for lock in root.glob("herdr-core/*/core.lock"):
        try:
            raw_call(lock.read_text(), "server.stop", {}, timeout=10.0)
        except (OSError, ValueError):
            continue


if TYPE_CHECKING:
    from cityharness import City
