"""flock(2) locks on private lock files.

Mutations take a name's lock exclusively; reads take it shared with a short
bounded wait and answer "unknown" when it does not come, because gc gives
``observe`` and ``is-attached`` 4 s in all (exec-session-provider.md
"observe.v1", rule 11). A lock belongs to an
open file description, so it ends with its process: a lock file existing
means nothing, and no cleanup is ever needed.
"""

from __future__ import annotations

import errno
import fcntl
import os
import stat
import time
from types import TracebackType
from typing import Final, Optional, Type

from .cancel import POLL_INTERVAL_S, CancelToken

_FIRST_RETRY_S: Final = 0.005
_LAST_RETRY_S: Final = 0.05


class LockTimeout(Exception):
    """The lock did not come within the wait."""


class LockFileError(Exception):
    """The lock file is a symlink, not a regular file, or not this user's."""


def _open_lock_file(path: str) -> int:
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError as err:
        if err.errno == errno.ELOOP:
            raise LockFileError(f"lock file {path} is a symlink") from None
        if err.errno == errno.EISDIR:
            raise LockFileError(f"lock file {path} is not a regular file") from None
        raise LockFileError(f"cannot open lock file {path}: {err.strerror}") from None
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
        os.close(fd)
        raise LockFileError(f"lock file {path} is not a regular file owned by this user")
    return fd


class FileLock:
    """A shared or exclusive flock on ``path``, held for a ``with`` block."""

    def __init__(self, path: str, *, shared: bool, wait_s: float, cancel: CancelToken) -> None:
        self._path = path
        self._shared = shared
        self._wait_s = wait_s
        self._cancel = cancel
        self._fd: Optional[int] = None

    def __enter__(self) -> FileLock:
        fd = _open_lock_file(self._path)
        try:
            self._acquire(fd)
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _acquire(self, fd: int) -> None:
        mode = fcntl.LOCK_SH if self._shared else fcntl.LOCK_EX
        end = time.monotonic() + self._wait_s
        retry = _FIRST_RETRY_S
        while True:
            self._cancel.check()
            try:
                fcntl.flock(fd, mode | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                pass
            left = end - time.monotonic()
            if left <= 0:
                kind = "shared" if self._shared else "exclusive"
                raise LockTimeout(f"{kind} lock {self._path} still held after {self._wait_s:.1f}s")
            time.sleep(min(retry, left, POLL_INTERVAL_S))
            retry = min(retry * 2, _LAST_RETRY_S)
