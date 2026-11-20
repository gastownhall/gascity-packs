"""Synthetic inputs for the soak harness's unit tests: a ``/proc`` tree and agent records."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence


class ProcTree:
    """A synthetic ``/proc``: ``add`` writes one process's files."""

    def __init__(self, root: Path, uptime: float = 10_000.0, boot_id: str = "b00tb00t-0000") -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / "uptime").write_text(f"{uptime:.2f} 1.00\n", encoding="utf-8")
        boot = root / "sys" / "kernel" / "random"
        boot.mkdir(parents=True, exist_ok=True)
        (boot / "boot_id").write_text(boot_id + "\n", encoding="utf-8")

    def add(
        self,
        pid: int,
        comm: str,
        *,
        ppid: int = 1,
        start: int = 100,
        argv: Sequence[str] = (),
        env: Optional[Mapping[str, str]] = None,
        cgroup: str = "/user.slice/user-1000.slice/user@1000.service/app.slice/x.scope",
        uid: Optional[int] = None,
        state: str = "S",
        utime: int = 5,
        stime: int = 3,
        rss_pages: int = 256,
    ) -> None:
        d = self.root / str(pid)
        d.mkdir(parents=True, exist_ok=True)
        fields = [state, str(ppid)] + ["0"] * 9 + [str(utime), str(stime), "1", "2"] + ["0"] * 4 + [str(start), "1000", str(rss_pages)] + ["0"] * 20
        (d / "stat").write_text(f"{pid} ({comm}) {' '.join(fields)}\n", encoding="utf-8")
        (d / "cmdline").write_bytes(b"".join(a.encode() + b"\0" for a in (argv or [comm])))
        (d / "environ").write_bytes(b"".join(f"{k}={v}".encode() + b"\0" for k, v in (env or {}).items()))
        (d / "cgroup").write_text(f"0::{cgroup}\n", encoding="utf-8")
        me = os.getuid() if uid is None else uid
        (d / "status").write_text(f"Name:\t{comm}\nUid:\t{me}\t{me}\t{me}\t{me}\n", encoding="utf-8")


def rec(ev: str, t: float, inc: str, **fields: object) -> Dict[str, object]:
    out: Dict[str, object] = {"ev": ev, "t": t, "mono": t, "inc": inc}
    out.update(fields)
    return out
