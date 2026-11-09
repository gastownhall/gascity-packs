"""One op's view of its city: the core's paths, the pack's private state, an
hc client, the per-name locks, and the host it runs on.

What the ops touch outside their request (the process table, the machine's
identity, the password-database home, where spawn files go, whether a
systemd user manager can re-scope agents, the clock) is a :class:`Host`, so
the unit tier runs the ops in process against fake-hc and a fake process
table. The test-only overrides (``GC_HC_TEST_*``) are honoured only under
``GC_HC_TEST=1``.

The pack's state for a city lives in ``R/pack/<city id>/``: ``meta/`` (one
file per incarnation), ``locks/``, ``outbox/``, ``activity.json`` and
``kick.json``, all private to the user.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Final, Mapping, Optional

from ..hc.client import CallTimeouts, CoreEndpoint, HcClient
from ..hc.paths import HcPaths, resolve_paths
from ..rpp.cancel import CancelToken, Deadline
from ..rpp.flock import FileLock
from ..rpp.ops import OpRequest
from ..rpp.statedir import ensure_private_dir, user_home
from .config import POLICY, resolve_hc_binary, test_mode
from .procs import ProcSource, default_source

FAULT_ENV: Final = "GC_RPP_FAULT"
"""``conformance-faults``: ``unavailable`` fails every backend call at its call site."""

READ_LOCK_WAIT_S: Final = 1.0
"""Reads wait at most this long for a name's lock, then answer unknown."""
MUTATION_LOCK_WAIT_S: Final = 30.0

PACK_SUBDIR: Final = "pack"
SHIM_SUBDIR: Final = os.path.join("shim", "bin")


def _pack_dir() -> str:
    # assets/gc_runtime_herdr_core/herdrcore/context.py -> the pack directory
    here = os.path.dirname(os.path.realpath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


@dataclass(frozen=True)
class Host:
    """The host an op runs on. :func:`live_host` is the real one."""

    procs: ProcSource
    pack_dir: str
    python: str
    machine: Optional[str] = None
    """The machine identity; None reads the real one."""
    home: Callable[[], str] = user_home
    now_ms: Callable[[], int] = field(default=lambda: int(time.time() * 1000))


def live_host(python: str) -> Host:
    """The host this process runs on; ``python`` runs the pack's helpers."""
    return Host(procs=default_source(), pack_dir=_pack_dir(), python=python)


class OpContext:
    """An op's city, core, private state and clients."""

    def __init__(self, request: OpRequest, host: Host) -> None:
        self.request = request
        self.host = host
        self.env: Mapping[str, str] = request.env
        self.test = test_mode(self.env)
        self.paths: HcPaths = resolve_paths(self.env, machine=host.machine, home=host.home)
        self.pack_state = os.path.join(self.paths.state_root, PACK_SUBDIR, self.paths.city_id)
        self.fault = self.env.get(FAULT_ENV, "") == "unavailable"
        self._endpoint = CoreEndpoint(self.paths.socket, policy=POLICY)

    # --- private state ---------------------------------------------------------

    def state_dir(self, *parts: str) -> str:
        """A private directory under the city's pack state, created on demand."""
        ensure_private_dir(self.paths.state_root)
        ensure_private_dir(os.path.join(self.paths.state_root, PACK_SUBDIR))
        ensure_private_dir(self.pack_state)
        path = self.pack_state
        for part in parts:
            path = os.path.join(path, part)
            ensure_private_dir(path)
        return path

    def state_file(self, name: str) -> str:
        return os.path.join(self.state_dir(), name)

    @property
    def shim_dir(self) -> str:
        return os.path.join(self.paths.state_root, SHIM_SUBDIR)

    def hc_binary(self) -> str:
        return resolve_hc_binary(self.env, self.pack_state, home=self.host.home)

    # --- hc ------------------------------------------------------------------------

    def client(self, *, read: bool = False, probe: bool = False) -> HcClient:
        """An hc client for this op, within its deadline and cancel token."""
        return HcClient(
            self._endpoint,
            deadline=self.request.deadline,
            cancel=self.request.cancel,
            timeouts=CallTimeouts.for_op(read=read, probe=probe),
            inject_unavailable=self.fault,
        )

    def rollback_client(self, seconds: float) -> HcClient:
        """A client that still works once the op is canceled, for a bounded cleanup."""
        return HcClient(
            self._endpoint,
            deadline=Deadline.after(seconds),
            cancel=CancelToken(),
            timeouts=CallTimeouts.for_op(read=False, probe=True),
        )

    # --- locks ---------------------------------------------------------------------

    def lock_path(self, kind: str, key: str) -> str:
        """The lock file of ``key`` (one per name, incarnation or purpose)."""
        digest = hashlib.sha256(os.fsencode(key)).hexdigest()[:32]
        return os.path.join(self.state_dir("locks"), f"{kind}-{digest}")

    def name_lock(self, name: str, *, shared: bool) -> FileLock:
        """The per-name lock: exclusive for mutations, shared with a short wait for reads."""
        return FileLock(
            self.lock_path("name", name),
            shared=shared,
            wait_s=READ_LOCK_WAIT_S if shared else min(MUTATION_LOCK_WAIT_S, max(0.1, self.request.deadline.budget(MUTATION_LOCK_WAIT_S))),
            cancel=self.request.cancel,
        )

    def attach_lock_path(self, obj: str) -> str:
        """The lock an ``attach`` holds for as long as it runs (incarnation ``obj``)."""
        return self.lock_path("attach", obj)

    def lock(self, key: str, *, shared: bool, wait_s: float) -> FileLock:
        return FileLock(self.lock_path("misc", key), shared=shared, wait_s=wait_s, cancel=self.request.cancel)
