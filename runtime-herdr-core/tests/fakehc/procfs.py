"""A fake ``/proc`` tree for process-table tests: ``stat``, ``cmdline`` and
``environ`` per pid, owned by the test's user."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional, Sequence


def add_proc(
    root: Path,
    pid: int,
    *,
    ppid: int,
    argv: Sequence[str],
    comm: Optional[str] = None,
    start: int = 1000,
    env: Optional[Mapping[str, str]] = None,
) -> None:
    """Write pid's entries; ``start`` is the starttime field (stat field 22)."""
    proc = root / str(pid)
    proc.mkdir(parents=True, exist_ok=True)
    name = comm if comm is not None else os.path.basename(argv[0])[:15]
    # Fields after "(comm)": state ppid pgrp session tty tpgid flags minflt
    # cminflt majflt cmajflt utime stime cutime cstime priority nice
    # num_threads itrealvalue starttime ...
    rest = ["S", str(ppid)] + ["0"] * 17 + [str(start)] + ["0"] * 10
    (proc / "stat").write_text(f"{pid} ({name}) " + " ".join(rest) + "\n")
    (proc / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    env_items = env or {}
    (proc / "environ").write_bytes(b"".join(f"{k}={v}".encode() + b"\0" for k, v in env_items.items()))
