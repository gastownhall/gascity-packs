"""Running a helper command within an op's deadline and cancel token.

The per-op runner turns gc's SIGTERM into a cancel flag, so a blocking
``subprocess.run`` would sit out a cancel. :func:`run_bounded` polls the
child instead, and on a cancel or timeout kills the child's whole process
group (it runs in its own session).
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Final, Mapping, Optional, Sequence

from ..rpp.cancel import POLL_INTERVAL_S, CancelToken

OUTPUT_TAIL_BYTES: Final = 4 << 10


@dataclass(frozen=True)
class Completed:
    returncode: Optional[int]
    """None when the command was killed at its timeout."""
    output: str
    """The tail of its combined stdout and stderr."""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_bounded(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: str,
    timeout_s: float,
    cancel: CancelToken,
) -> Completed:
    """Run ``argv`` to completion or for at most ``timeout_s``; stdin is empty."""
    with tempfile.TemporaryFile() as output:
        proc = subprocess.Popen(
            list(argv),
            env=dict(env),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        waited = 0.0
        code: Optional[int] = None
        try:
            while True:
                code = proc.poll()
                if code is not None:
                    break
                if waited >= timeout_s:
                    break
                cancel.check()
                try:
                    code = proc.wait(timeout=POLL_INTERVAL_S)
                    break
                except subprocess.TimeoutExpired:
                    waited += POLL_INTERVAL_S
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                proc.wait()
        size = output.seek(0, os.SEEK_END)
        output.seek(max(0, size - OUTPUT_TAIL_BYTES))
        tail = output.read().decode("utf-8", "replace")
    return Completed(returncode=code, output=tail.strip())
