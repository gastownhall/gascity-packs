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
from typing import TYPE_CHECKING, Callable, Iterator, Optional

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
        await_kicks(made)
        stop_cores(made.root / "R")
        if made.fake is not None:
            made.fake.close()
            assert made.fake.schema_violations == [], "fake-hc schema guard:\n" + "\n".join(made.fake.schema_violations)


def await_kicks(made: "City", timeout: float = 20.0) -> None:
    """Wait until no background core start a test's read kicked is in flight:
    one leaves its lock file before it writes its record."""
    import time

    from gc_runtime_herdr_core.herdrcore.attach import lock_held
    from gc_runtime_herdr_core.herdrcore.core import KICK_FILE

    ctx = made.context()
    lock_path = ctx.lock_path("misc", "kick")
    record = os.path.join(ctx.pack_state, KICK_FILE)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not os.path.exists(lock_path) or (os.path.exists(record) and not lock_held(lock_path)):
            return
        time.sleep(0.05)


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
