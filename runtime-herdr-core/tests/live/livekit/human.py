"""A person at a terminal: ``hc attach`` on a pseudo-terminal the harness
types into. hc holds a ``send`` until the person has been quiet for a while,
so this is how the suites hold a nudge the way a human does."""

from __future__ import annotations

import fcntl
import os
import pty
import signal
import struct
import subprocess
import termios
import threading
import time
from typing import List, Optional

from .owned import NotOwned
from .scratch import Scratch


class Human:
    def __init__(self, scratch: Scratch, address: str) -> None:
        self.scratch = scratch
        self.keys: List[float] = []
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        paths = scratch.paths()
        env = dict(scratch.hc_cli_env(paths.session, paths.socket), TERM="xterm-256color")
        self.proc = subprocess.Popen(
            [scratch.hc_bin, "attach", address],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            cwd=scratch.work,
            start_new_session=True,
        )
        os.close(slave)
        self.master = master
        scratch.ownership.record(self.proc.pid)
        self._drain = threading.Thread(target=self._read, daemon=True)
        self._drain.start()

    def _read(self) -> None:
        while True:
            try:
                if not os.read(self.master, 1 << 16):
                    return
            except OSError:
                return

    def type(self, data: bytes) -> None:
        os.write(self.master, data)
        self.keys.append(time.time())

    def type_for(self, seconds: float, *, every_s: float = 1.0, key: bytes = b"x") -> None:
        """Type ``key`` every ``every_s`` for ``seconds``."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.type(key)
            time.sleep(every_s)

    @property
    def last_key(self) -> Optional[float]:
        return self.keys[-1] if self.keys else None

    def attached(self) -> bool:
        return self.proc.poll() is None

    def leave(self) -> None:
        if self.proc.poll() is None:
            try:
                self.scratch.ownership.signal(self.proc.pid, signal.SIGKILL)
            except NotOwned:
                pass
        self.proc.wait(timeout=10)
        os.close(self.master)
