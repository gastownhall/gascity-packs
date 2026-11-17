"""Unit tests of the soak harness: synthetic logs, a synthetic ``/proc`` tree,
and fake-hc. Nothing here runs gc, bd or a real herdr-core, and no harness
subcommand runs on this host (they refuse without the soak VM's marker).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest

SOAK = Path(__file__).resolve().parents[1]
PACK = SOAK.parent
for _entry in (SOAK / "lib", PACK / "tests", PACK / "assets"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))


from .soaktestkit import ProcTree  # noqa: E402


@pytest.fixture
def proc_tree(tmp_path: Path) -> ProcTree:
    return ProcTree(tmp_path / "proc")


@pytest.fixture
def short_tmp() -> Iterator[Path]:
    """A short directory for AF_UNIX sockets (108-byte limit)."""
    import shutil
    import tempfile

    path = Path(tempfile.mkdtemp(prefix="sk", dir="/tmp"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
