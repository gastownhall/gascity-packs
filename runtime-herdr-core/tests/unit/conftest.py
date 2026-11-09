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

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable, Iterator, Optional

import pytest

PACK_ROOT = Path(__file__).resolve().parents[2]
for _entry in (PACK_ROOT / "assets", PACK_ROOT / "tests"):
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
    path = tempfile.mkdtemp(prefix="hcrt-", dir="/tmp")
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
