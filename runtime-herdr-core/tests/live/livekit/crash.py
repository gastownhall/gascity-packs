"""Holder kills and the checks around them, shared by the crash suites."""

from __future__ import annotations

import signal
import subprocess
import time
from typing import Callable, Dict, List, Optional

from .cases import Kill
from .hcrpc import CoreStatus, HcRpc
from .scratch import Scratch
from .units import k2_argv, unit_of

SETTLE_S = 5.0
"""hc's sweep signals HUP, TERM and KILL 0.5 s apart and waits up to 2 s more."""


def core_status(scratch: Scratch) -> CoreStatus:
    """The scratch city's core, its holders adopted as the run's own: a core
    answering on the run's socket under its fresh state root was started by
    the run's ops, and so were the holders it lists."""
    status = HcRpc(scratch.paths().socket).status()
    if not scratch.ownership.owns(status.pid, runtime_only=True):
        raise AssertionError(f"the core on the scratch socket (pid {status.pid}) is not hc runtime of the scratch root")
    scratch.ownership.note_unit(status.pid)
    for pid in status.holders:
        scratch.ownership.record(pid)
        scratch.ownership.note_unit(pid)
    if not status.holders:
        raise AssertionError("the core lists no holder")
    return status


def holder_units(scratch: Scratch, status: CoreStatus) -> Dict[int, str]:
    """Each holder's systemd unit (systemd lane), read from its own cgroup."""
    out: Dict[int, str] = {}
    for pid in status.holders:
        cgroup = scratch.ownership.procs.cgroup(pid)
        unit = None if cgroup is None else unit_of(cgroup)
        if unit is None:
            raise AssertionError(f"holder {pid} runs in no unit (cgroup {cgroup!r})")
        out[pid] = unit
    return out


def kill_holders(scratch: Scratch, kill: Kill) -> List[str]:
    """K1: SIGKILL every holder process of the scratch core. K2: a cgroup-wide
    SIGKILL of every holder's ``hc-hold-*`` unit (found from that holder)."""
    status = core_status(scratch)
    if kill == "K1":
        for pid in status.holders:
            scratch.ownership.signal(pid, signal.SIGKILL)
        return [f"pid {pid}" for pid in status.holders]
    killed: List[str] = []
    for pid, unit in sorted(holder_units(scratch, status).items()):
        if not scratch.ownership.owns(pid):
            raise AssertionError(f"holder {pid} is no longer the run's")
        done = subprocess.run(k2_argv(unit), env=scratch.systemd_env(), capture_output=True, text=True, timeout=30, check=False)
        if done.returncode != 0:
            raise AssertionError(f"{' '.join(k2_argv(unit))} failed: {done.stderr.strip()}")
        killed.append(unit)
    return killed


def wait_until(predicate: Callable[[], bool], timeout_s: float, *, step_s: float = 0.25) -> bool:
    end = time.monotonic() + timeout_s
    while True:
        if predicate():
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(step_s)


def environ_of(scratch: Scratch, pid: int) -> Dict[str, str]:
    env = scratch.ownership.procs.environ(pid)
    if env is None:
        raise AssertionError(f"pid {pid} is gone")
    return env


def cgroup_of(scratch: Scratch, pid: int) -> str:
    cgroup = scratch.ownership.procs.cgroup(pid)
    if cgroup is None:
        raise AssertionError(f"cannot read the cgroup of pid {pid}")
    return cgroup


def alive(scratch: Scratch, pids: Dict[str, int]) -> Dict[str, bool]:
    return {role: scratch.ownership.alive(pid) for role, pid in pids.items()}


def unit_or_none(scratch: Scratch, pid: int) -> Optional[str]:
    return unit_of(cgroup_of(scratch, pid))
