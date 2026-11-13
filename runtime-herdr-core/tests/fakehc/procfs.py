"""A fake ``/proc`` tree for process-table tests: ``stat``, ``cmdline`` and
``environ`` per pid, its main thread's ``children`` list, its ``exe`` link,
``cgroup`` and socket fds when given, ``net/unix`` and the boot id; owned by
the test's user."""

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
    children: Optional[Sequence[int]] = None,
    state: str = "S",
    exe: Optional[str] = None,
    cgroup: Optional[str] = None,
    sockets: Sequence[int] = (),
) -> None:
    """Write pid's entries; ``start`` is the starttime field (stat field 22),
    ``children`` what ``task/<pid>/children`` lists (no such file when None,
    as a kernel without ``CONFIG_PROC_CHILDREN`` has)."""
    proc = root / str(pid)
    proc.mkdir(parents=True, exist_ok=True)
    name = comm if comm is not None else os.path.basename(argv[0])[:15]
    # Fields after "(comm)": state ppid pgrp session tty tpgid flags minflt
    # cminflt majflt cmajflt utime stime cutime cstime priority nice
    # num_threads itrealvalue starttime ...
    rest = [state, str(ppid)] + ["0"] * 17 + [str(start)] + ["0"] * 10
    (proc / "stat").write_text(f"{pid} ({name}) " + " ".join(rest) + "\n")
    (proc / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    env_items = env or {}
    (proc / "environ").write_bytes(b"".join(f"{k}={v}".encode() + b"\0" for k, v in env_items.items()))
    if children is not None:
        add_thread(root, pid, pid, children)
    if exe is not None:
        (proc / "exe").symlink_to(exe)
    if cgroup is not None:
        (proc / "cgroup").write_text(f"0::{cgroup}\n")
    if sockets:
        fd = proc / "fd"
        fd.mkdir(exist_ok=True)
        for index, inode in enumerate(sockets):
            (fd / str(10 + index)).symlink_to(f"socket:[{inode}]")


def add_unix_socket(root: Path, inode: int, path: str) -> None:
    """List a bound Unix socket in ``net/unix``, as the kernel does."""
    table = root / "net" / "unix"
    table.parent.mkdir(parents=True, exist_ok=True)
    if not table.exists():
        table.write_text("Num       RefCount Protocol Flags    Type St Inode Path\n")
    with table.open("a") as handle:
        handle.write(f"0000000000000000: 00000002 00000000 00010000 0001 01 {inode} {path}\n")


def add_boot(root: Path, boot_id: str) -> None:
    """Write ``sys/kernel/random/boot_id``, as the kernel does: the boot the
    start times count from."""
    path = root / "sys" / "kernel" / "random" / "boot_id"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(boot_id + "\n")


def add_thread(root: Path, pid: int, tid: int, children: Sequence[int]) -> None:
    """Write ``task/<tid>/children`` of ``pid``: the kernel's "1 2 " form."""
    task = root / str(pid) / "task" / str(tid)
    task.mkdir(parents=True, exist_ok=True)
    (task / "children").write_text("".join(f"{kid} " for kid in children))
