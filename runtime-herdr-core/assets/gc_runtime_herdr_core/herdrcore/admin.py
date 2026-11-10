"""What the doctor checks and the ``gc herdr-core`` commands share: their
city, their host, and how they look at the city's core.

gc runs both with ``GC_CITY_PATH`` (never ``GC_EXEC_CITY_PATH``), the pack
directory as cwd for doctor checks, and its own environment, so
``GC_EXEC_STATE_DIR`` is seen when the operator set it. They resolve the
city's core exactly as the ops do, with ``GC_CITY_PATH`` as the city key: an
op and a doctor check of one city name one core.
"""

from __future__ import annotations

import hashlib
import os
import socket
from dataclasses import dataclass, replace
from typing import Final, List, Mapping, Optional

from ..hc.client import CallTimeouts, CoreEndpoint, HcClient
from ..hc.errors import HcError, HcUnreachable
from ..hc.types import StatusResult, Terminal
from ..hc.version import Version, VersionPolicy
from ..rpp.cancel import CancelToken, Deadline
from ..rpp.ops import OpRequest
from ..rpp.redact import Redactor
from ..rpp.statedir import DOCTOR_CITY_ENV, StateDirError
from .config import TEST_HOME_ENV, pin_policy, read_private_file, test_mode
from .context import Host, OpContext, live_host
from .naming import LABEL_CITY, city_label
from .procs import LinuxProcs, ProcError

TEST_PROC_ROOT_ENV: Final = "GC_HC_TEST_PROC_ROOT"
"""Test-only (``GC_HC_TEST=1``): a fake ``/proc`` the checks and commands read."""

CONTROLLER_SOCKET_LIMIT: Final = 100
"""gc's ``controllerSocketPathLimit`` (``cmd/gc/controller.go``)."""


def admin_host(env: Mapping[str, str], python: str) -> Host:
    """The live host, with the test-only process table and home under ``GC_HC_TEST=1``."""
    host = live_host(python)
    if not test_mode(env):
        return host
    proc_root = env.get(TEST_PROC_ROOT_ENV, "")
    if proc_root:
        host = replace(host, procs=LinuxProcs(proc_root))
    home = env.get(TEST_HOME_ENV, "")
    if home:
        host = replace(host, home=lambda: home)
    return host


def admin_context(env: Mapping[str, str], host: Host, *, name: str, deadline_s: float, cancel: CancelToken) -> OpContext:
    """The city named by ``GC_CITY_PATH``, as an op of ``deadline_s`` seconds sees it."""
    redactor = Redactor()
    redactor.add_process_env(env)
    request = OpRequest(
        op=name,
        args=(),
        stdin=b"",
        env=env,
        cancel=cancel,
        deadline=Deadline.after(deadline_s),
        redactor=redactor,
    )
    return OpContext(request, host, city_var=DOCTOR_CITY_ENV)


def controller_socket(city_path: str) -> str:
    """Where gc's controller (or the supervisor, for this city) listens:
    gc's ``controllerSocketPath``."""
    canonical = os.path.realpath(city_path)
    legacy = os.path.join(canonical, ".gc", "controller.sock")
    if len(legacy) <= CONTROLLER_SOCKET_LIMIT:
        return legacy
    digest = hashlib.sha256(canonical.encode("utf-8", "surrogateescape")).hexdigest()[:32]
    return os.path.join("/tmp", "gascity-controller", f"{digest}.sock")


def answers(path: str, *, timeout_s: float = 0.5) -> bool:
    """Whether something accepts a connection on Unix socket ``path``."""
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(timeout_s)
        probe.connect(path)
    except OSError:
        return False
    finally:
        probe.close()
    return True


def city_running(env: Mapping[str, str]) -> bool:
    """Whether the city's controller answers (live state, never a status file)."""
    city = env.get(DOCTOR_CITY_ENV, "")
    return bool(city) and answers(controller_socket(city))


def lock_socket(ctx: OpContext) -> Optional[str]:
    """The socket ``core.lock`` names when it is not ours and something listens
    there (a core of this session on another socket, herdr-core #200)."""
    try:
        raw = read_private_file(ctx.paths.core_lock)
    except StateDirError:  # an unreadable lock names nothing we can act on
        return None
    if not raw:
        return None
    listening = os.fsdecode(raw.strip())
    if listening == ctx.paths.socket or not answers(listening):
        return None
    return listening


ANY_VERSION: Final = VersionPolicy(min_version=Version(0, 0, 0), tested=())
"""A gate that admits any release of the protocol generation: for looking
at a core the pack is about to replace, which may be older than the pin's
minimum."""


def client_for(ctx: OpContext, socket_path: str, *, any_version: bool = False) -> HcClient:
    """An hc client for the core at ``socket_path`` within the context's deadline."""
    return HcClient(
        CoreEndpoint(socket_path, policy=ANY_VERSION if any_version else pin_policy()),
        deadline=ctx.request.deadline,
        cancel=ctx.request.cancel,
        timeouts=CallTimeouts.for_op(read=False, probe=False),
    )


@dataclass(frozen=True)
class Ownership:
    """Whose core answers on a socket."""

    own: bool
    """It is this city's core: this user's, with this city's hc session and state root."""
    reason: str
    """Why it is not (empty when it is)."""


def ownership(ctx: OpContext, status: StatusResult) -> Ownership:
    """Whether the core behind ``status`` is this city's own: run by this user,
    with the city's ``HC_SESSION`` and ``XDG_STATE_HOME``. A core of the city
    started with the wrong environment otherwise is still the city's (that is
    what ``restart-core`` fixes); one that is not cannot be told apart from a
    person's or another city's core, and is never stopped by the pack."""
    try:
        snapshot = ctx.host.procs.snapshot()
        env = ctx.host.procs.environ(status.pid)
    except ProcError as err:
        return Ownership(False, f"its process cannot be read ({err})")
    proc = snapshot.get(status.pid)
    if proc is None or env is None:
        return Ownership(False, f"its process (pid {status.pid}) cannot be found")
    if proc.uid != os.getuid():
        return Ownership(False, f"it runs as uid {proc.uid}")
    for key, want in (("HC_SESSION", ctx.paths.session), ("XDG_STATE_HOME", ctx.paths.state_root)):
        if env.get(key) != want:
            return Ownership(False, f"its {key} is not this city's")
    return Ownership(True, "")


def live_terminals(client: HcClient) -> List[Terminal]:
    """Every live terminal on the core."""
    return [t for t in client.list_terminals(include_finished=False).terminals if t.is_live]


def city_terminals(ctx: OpContext, terminals: List[Terminal]) -> List[Terminal]:
    """The ones the city's sessions run in."""
    mine = city_label(ctx.paths.city_id)
    return [t for t in terminals if t.labels.get(LABEL_CITY) == mine]


def core_reachable(client: HcClient) -> bool:
    """Whether a core answers the client's socket (a gate failure answers too)."""
    try:
        client.hello()
    except HcUnreachable:
        return False
    except HcError:
        return True
    return True
