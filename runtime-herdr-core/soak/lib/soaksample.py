"""``soak sample``: one ``samples.jsonl`` record every 60 s (supervisor, core,
holders, boxes, store, this user's CPU and, every five minutes, sizes,
memory and disk)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from soakanalysis import boxes, store_procs
from soakhc import CoreTuple, HcError, HcRpc, core_tuple
from soaklib import City, ProcFS, Rec, SoakPaths, append_jsonl, run, unit_of

SAMPLE_PERIOD_S = 60.0
SIZE_PERIOD_S = 300.0
SUPERVISOR_UNIT = "gascity-supervisor.service"


def parse_systemctl_show(text: str) -> Dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def parse_cpu_stat(text: str) -> Optional[int]:
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "usage_usec":
            return int(parts[1])
    return None


def parse_meminfo(text: str) -> Optional[int]:
    """MemAvailable in KiB."""
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    return None


def tree_bytes(path: Path) -> Optional[int]:
    """Apparent bytes of the regular files under ``path``, or of ``path``
    itself when it is a file (None when it is missing)."""
    if not path.exists():
        return None
    if path.is_file():
        return path.stat().st_size
    total = 0
    for dirpath, _dirs, files in os.walk(str(path)):
        for name in files:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            total += st.st_size
    return total


def supervisor_state() -> Dict[str, Any]:
    res = run(["systemctl", "--user", "show", SUPERVISOR_UNIT, "-p", "MainPID", "-p", "NRestarts", "-p", "ActiveState"], timeout=30.0)
    values = parse_systemctl_show(res.out) if res.ok else {}
    try:
        pid = int(values.get("MainPID", "0") or 0)
    except ValueError:
        pid = 0
    try:
        restarts = int(values.get("NRestarts", "0") or 0)
    except ValueError:
        restarts = 0
    return {"pid": pid, "nrestarts": restarts, "active": values.get("ActiveState", "")}


def user_usage_usec(uid: int) -> Optional[int]:
    path = Path(f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/cpu.stat")
    try:
        return parse_cpu_stat(path.read_text(encoding="utf-8"))
    except OSError:
        return None


@dataclass
class Sampler:
    city: City
    paths: SoakPaths
    procfs: ProcFS = field(default_factory=ProcFS)
    gc: str = "gc"
    core: Optional[CoreTuple] = None
    core_checked: float = 0.0
    last_sizes: float = 0.0

    def core_tuple(self, now: float) -> Optional[CoreTuple]:
        if self.core is None and now - self.core_checked >= 600:
            self.core_checked = now
            try:
                self.core = core_tuple(str(self.city.path), self.gc)
            except HcError:
                self.core = None
        return self.core

    def sample(self, now: float) -> Rec:
        uid = os.getuid()
        snap = self.procfs.snapshot(uid)
        phase = ""
        try:
            phase = self.city.file("phase").read_text(encoding="utf-8").strip()
        except OSError:
            pass
        rec: Rec = {"t": now, "mono_ns": time.monotonic_ns(), "phase": phase}
        sup = supervisor_state()
        info = snap.get(sup["pid"]) if sup["pid"] else None
        stat = self.procfs.stat(sup["pid"]) if sup["pid"] else None
        if info is not None and stat is not None:
            sup.update(
                start=info.start,
                ticks=stat.utime + stat.stime + stat.cutime + stat.cstime,
                rss_kib=info.rss_kib,
            )
        rec["supervisor"] = sup
        holders: List[int] = []
        core = self.core_tuple(now)
        if core is not None:
            try:
                status = HcRpc(core.socket, timeout_s=10.0).status()
            except HcError as err:
                rec["core"] = {"error": str(err)[:300]}
            else:
                holders = list(status.holders)
                rec["core"] = self.proc_view(snap, status.pid, version=status.version, live=status.live)
                rec["holders"] = [self.proc_view(snap, h) for h in holders]
        else:
            rec["core"] = {"error": "no core tuple"}
        rec["boxes"] = [{"pid": b.pid, "start": b.start, "comm": b.comm} for b in boxes(snap, holders)]
        rec["store"] = [
            {
                "pid": p.pid,
                "start": p.start,
                "comm": p.comm,
                "argv1": p.argv1,
                "unit": unit_of(p.cgroup),
                "cgroup": p.cgroup,
                "rss_kib": p.rss_kib,
                "hc_scope": "HC_SCOPE" in p.env,
            }
            for p in store_procs(snap, uid)
        ]
        rec["user_usage_usec"] = user_usage_usec(uid)
        if now - self.last_sizes >= SIZE_PERIOD_S:
            self.last_sizes = now
            rec["sizes"] = self.sizes(core)
            try:
                rec["mem_avail_kib"] = parse_meminfo(Path("/proc/meminfo").read_text(encoding="utf-8"))
            except OSError:
                rec["mem_avail_kib"] = None
            st = os.statvfs(str(self.paths.home))
            rec["disk_free_bytes"] = st.f_bavail * st.f_frsize
        return rec

    def proc_view(self, snap: Mapping[int, Any], pid: int, **extra: Any) -> Rec:
        info = snap.get(pid)
        view: Rec = {"pid": pid}
        view.update(extra)
        if info is not None:
            view.update(start=info.start, rss_kib=info.rss_kib, cpu_ticks=info.cpu_ticks, unit=unit_of(info.cgroup))
        return view

    def sizes(self, core: Optional[CoreTuple]) -> Rec:
        return {
            "R": tree_bytes(self.paths.state_root),
            "hc_state": None if core is None else tree_bytes(Path(core.state_dir)),
            "gc_dir": tree_bytes(self.city.path / ".gc"),
            "beads_dir": tree_bytes(self.city.path / ".beads"),
            "events": tree_bytes(self.city.events),
        }

    def forever(self) -> None:
        while True:
            started = time.time()
            append_jsonl(self.city.file("samples.jsonl"), self.sample(started))
            time.sleep(max(1.0, SAMPLE_PERIOD_S - (time.time() - started)))
