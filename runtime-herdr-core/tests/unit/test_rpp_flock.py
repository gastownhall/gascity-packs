"""Per-name flock(2) locks: exclusive mutations, shared bounded reads."""

from __future__ import annotations

import os
import stat
import threading
import time
from pathlib import Path
from typing import Optional

import pytest

from gc_runtime_herdr_core.rpp.cancel import CancelToken, Cancelled
from gc_runtime_herdr_core.rpp.flock import FileLock, LockFileError, LockTimeout


def lock(path: Path, *, shared: bool, wait_s: float = 0.2, cancel: Optional[CancelToken] = None) -> FileLock:
    return FileLock(str(path), shared=shared, wait_s=wait_s, cancel=cancel or CancelToken())


def test_exclusive_excludes_exclusive_within_the_bounded_wait(tmp_path: Path) -> None:
    path = tmp_path / "mc-mayor.lock"
    with lock(path, shared=False):
        started = time.monotonic()
        with pytest.raises(LockTimeout):
            with lock(path, shared=False, wait_s=0.2):
                pass
        waited = time.monotonic() - started
    assert 0.15 <= waited < 1.0


def test_shared_holders_coexist(tmp_path: Path) -> None:
    path = tmp_path / "n.lock"
    with lock(path, shared=True), lock(path, shared=True):
        pass


def test_shared_blocks_exclusive_and_exclusive_blocks_shared(tmp_path: Path) -> None:
    path = tmp_path / "n.lock"
    with lock(path, shared=True):
        with pytest.raises(LockTimeout):
            with lock(path, shared=False):
                pass
    with lock(path, shared=False):
        with pytest.raises(LockTimeout):
            with lock(path, shared=True):
                pass


def test_release_lets_a_waiter_in(tmp_path: Path) -> None:
    path = tmp_path / "n.lock"
    holder = lock(path, shared=False)
    holder.__enter__()
    threading.Timer(0.1, holder.__exit__, args=(None, None, None)).start()
    with lock(path, shared=False, wait_s=2.0):
        pass


def test_lock_file_is_private(tmp_path: Path) -> None:
    path = tmp_path / "n.lock"
    with lock(path, shared=False):
        pass
    assert stat.S_IMODE(os.lstat(path).st_mode) == 0o600


def test_refuses_a_symlinked_lock_file(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.write_text("")
    link = tmp_path / "n.lock"
    link.symlink_to(target)
    with pytest.raises(LockFileError):
        with lock(link, shared=False):
            pass


def test_refuses_a_lock_path_that_is_not_a_regular_file(tmp_path: Path) -> None:
    path = tmp_path / "n.lock"
    path.mkdir()
    with pytest.raises(LockFileError):
        with lock(path, shared=True):
            pass


def test_cancel_interrupts_a_waiter(tmp_path: Path) -> None:
    path = tmp_path / "n.lock"
    token = CancelToken()
    with lock(path, shared=False):
        threading.Timer(0.1, token.cancel, args=("terminated",)).start()
        started = time.monotonic()
        with pytest.raises(Cancelled):
            with lock(path, shared=False, wait_s=10.0, cancel=token):
                pass
    assert time.monotonic() - started < 1.0
