"""``soak capture``: an evidence bundle (``captures/<time>.tar.gz``), and the
check that nothing of a stopped city remains."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from soakanalysis import hc_runtime
from soakhc import CoreTuple, HcError, HcRpc, core_tuple
from soaklib import City, ProcFS, SoakPaths, read_jsonl, run

COMMANDS: Tuple[Tuple[str, Sequence[str], bool], ...] = (
    ("gc-trace-status.txt", ("trace", "status"), True),
    ("gc-trace-reasons.txt", ("trace", "reasons", "--since", "30m"), True),
    ("gc-trace-cycle-results.json", ("trace", "show", "--since", "30m", "--type", "cycle_result", "--json"), True),
    ("gc-trace-show.json", ("trace", "show", "--since", "30m", "--json"), True),
    ("gc-supervisor-logs.txt", ("supervisor", "logs", "-n", "2000"), False),
    ("gc-status.json", ("status", "--json"), True),
    ("gc-session-list.json", ("session", "list", "--json", "--state", "all"), True),
    ("gc-doctor.json", ("doctor", "--json"), True),
    ("gc-herdr-core-status.txt", ("herdr-core", "status"), True),
)
"""``(file, gc argv, run in the city directory)``."""

HOST_COMMANDS: Tuple[Tuple[str, Sequence[str]], ...] = (
    ("ps.txt", ("ps", "-eo", "pid,ppid,lstart,args")),
    ("cgls-supervisor.txt", ("systemd-cgls", "--no-pager", "--user-unit", "gascity-supervisor.service")),
    ("hc-units.txt", ("systemctl", "--user", "list-units", "hc-*", "--all", "--no-pager")),
)

DATA_FILES = ("load.jsonl", "faults.jsonl", "samples.jsonl", "check.jsonl", "check.log", "phases.jsonl", "ABORTED")


def _copy(src: Path, dst: Path) -> None:
    try:
        if src.is_dir():
            shutil.copytree(str(src), str(dst), symlinks=True, ignore_dangling_symlinks=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
    except (OSError, shutil.Error) as err:
        dst.parent.mkdir(parents=True, exist_ok=True)
        (dst.parent / (dst.name + ".error")).write_text(str(err), encoding="utf-8")


def _core(city: City, gc: str) -> Optional[CoreTuple]:
    try:
        return core_tuple(str(city.path), gc)
    except HcError:
        return None


def capture(city: City, paths: SoakPaths, gc: str, procfs: ProcFS) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = city.data / "captures"
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f"soak-capture-{stamp}-", dir=str(out_dir)))
    root = work / stamp
    root.mkdir()
    for name, argv, in_city in COMMANDS:
        res = run([gc, *argv], cwd=str(city.path) if in_city else None, timeout=300.0)
        (root / name).write_text(res.out + ("\n--- stderr (exit %d)\n" % res.code) + res.err, encoding="utf-8")
    for name, argv in HOST_COMMANDS:
        res = run(list(argv), timeout=120.0)
        (root / name).write_text(res.out + res.err, encoding="utf-8")
    core = _core(city, gc)
    if core is not None:
        try:
            status = HcRpc(core.socket).status()
            (root / "server-status.txt").write_text(repr(status.raw), encoding="utf-8")
        except HcError as err:
            (root / "server-status.txt").write_text(f"error: {err}", encoding="utf-8")
        state_dir = Path(core.state_dir)
        for log in sorted(state_dir.rglob("*.log")) if state_dir.is_dir() else []:
            _copy(log, root / "hc-logs" / log.relative_to(state_dir))
    _copy(city.path / ".gc" / "runtime" / "session-reconciler-trace", root / "session-reconciler-trace")
    _copy(city.agents, root / "agents")
    _copy(city.events, root / "events.jsonl")
    for name in DATA_FILES:
        _copy(city.file(name), root / name)
    _copy(paths.optrace, root / "optrace.log")
    bundle = out_dir / f"{stamp}.tar.gz"
    with tarfile.open(str(bundle), "w:gz") as tar:
        tar.add(str(root), arcname=stamp)
    shutil.rmtree(str(work), ignore_errors=True)
    os.chmod(bundle, 0o600)
    return bundle


def remains(city: City, procfs: ProcFS, gc: str = "gc", core: Optional[CoreTuple] = None) -> List[str]:
    """What of a stopped city still runs: a core or holder of its core tuple,
    or any process of any of its sessions -- one that carries the city's
    ``GC_CITY_PATH`` and a non-empty ``GC_SESSION_ID``. That takes in every
    session's boxes and their descendants whether or not the session wrote a
    log: ``agents/*.jsonl`` lists only the scripted agents that logged, not the
    control-dispatcher nor an agent that has written no line.

    ``core`` is the core tuple when the caller already knows it; otherwise
    ``gc herdr-core status --env`` names it. When that fails, the scan cannot
    see a core or holder (the pack starts the core with no ``GC_*`` in its
    environment), so it reports ``core tuple unknown: <error>``: a scan that
    could not look never reads as nothing remaining."""
    left: List[str] = []
    snap = procfs.snapshot(os.getuid())
    if core is None:
        try:
            core = core_tuple(str(city.path), gc)
        except HcError as err:
            left.append(f"core tuple unknown: {err}")
    if core is not None:
        for h in hc_runtime(snap):
            if h.state_home == core.state_home and h.session == core.session:
                left.append(f"hc {h.role} pid {h.pid}")
    for proc in snap.values():
        session = proc.env.get("GC_SESSION_ID", "")
        if session and proc.env.get("GC_CITY_PATH") == str(city.path):
            left.append(f"session {session} pid {proc.pid} {proc.comm}")
    return left


def faults_since(city: City, t: float) -> int:
    return sum(1 for f in read_jsonl(city.file("faults.jsonl")) if float(f.get("t", 0)) >= t)
