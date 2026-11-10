"""The pack's ``gc doctor`` checks: ``gc-runtime-herdr-core x-doctor <check>``.

gc runs each ``doctor/<check>/run.sh`` with the pack directory as cwd and
``GC_CITY_PATH`` naming the city, and reads the answer as the pack doctor
protocol: exit 0 OK, 1 warning, 2 error; the first stdout line is the
message, the rest are details. gc gives a check no timeout, so each one
here has a :data:`CHECK_BUDGET_S` total budget (a check that runs out
reports a warning) and 1 to 1.5 s per hc call.

* ``hc-binary``: the pinned build is installed and matches the pin.
* ``hc-core``: the running core's version gate, the foreign-core check, the
  core's binary, a crash-looping start, and the user-manager and lingering
  hints that apply to a running core.
* ``hc-scope-hygiene``: no city infrastructure runs under herdr-core.
* ``hc-state-perms``: hc's state for the city is private.

``hc-python`` is a shell check (``doctor/hc-python/run.sh``): it must answer
on a Python too old to load this package.
"""

from __future__ import annotations

import os
import pwd
import signal
import stat
from enum import IntEnum
from types import FrameType
from typing import Callable, Dict, Final, List, Mapping, Optional, Sequence, Set, TextIO, Tuple

from ..hc.errors import HcError, HcGateError, HcUnreachable
from ..hc.version import Version
from ..rpp.cancel import CancelToken
from ..rpp.statedir import DOCTOR_CITY_ENV, StateDirError
from .admin import admin_context, admin_host, city_running, controller_socket, lock_socket
from .config import ConfigError, install_root, pinned_binary, read_pack_config
from .context import Host, OpContext
from .core import FOREIGN_FIX, KICK_BACKOFF_MS, core_env, foreign_reason, read_kick
from .infra_argv import BD_PROXY_CHILD_VERB, MANAGED_DOLT_SCOPE_WATCHDOG_VERB, infrastructure_prefix
from .install import verify_installed, writable
from .pin import PinError, host_target, load_pin
from .procs import Proc, ProcError, ProcSource, Snapshot

CHECK_BUDGET_S: Final = 10.0

LINGER_DIR: Final = "/var/lib/systemd/linger"
TEST_LINGER_DIR_ENV: Final = "GC_HC_TEST_LINGER_DIR"
"""Test-only (``GC_HC_TEST=1``): where systemd keeps its linger flags."""

UPGRADE_FIX: Final = "run `gc herdr-core upgrade`"
INSTALL_FIX: Final = "run `gc herdr-core install`"
RESTART_FIX: Final = "run `gc herdr-core restart-core`"


class Status(IntEnum):
    OK = 0
    WARNING = 1
    ERROR = 2


class Report:
    """A check's answer: its findings, worst first in the message, and notes."""

    def __init__(self, status: Status = Status.OK, message: str = "") -> None:
        self.findings: List[Tuple[Status, str]] = [(status, message)] if message else []
        self.notes: List[str] = []
        self.headline = ""
        """Replaces the worst finding as the message (which then leads the details)."""

    def note(self, status: Status, message: str) -> None:
        self.findings.append((status, message))

    @property
    def status(self) -> Status:
        return max((status for status, _ in self.findings), default=Status.OK)

    @property
    def message(self) -> str:
        worst = self.status
        if self.headline and worst > Status.OK:
            return self.headline
        return next((text for status, text in self.findings if status == worst), "ok")

    @property
    def details(self) -> List[str]:
        message = self.message
        rest = [text for _, text in self.findings]
        if message in rest:
            rest.remove(message)
        return rest + self.notes

    def render(self) -> str:
        return "\n".join([self.message, *self.details]) + "\n"


# --- hc-binary ---------------------------------------------------------------------


def check_binary(ctx: OpContext) -> Report:
    """The pinned build is installed and matches the pin, or the operator's
    unpinned choice is allowed."""
    report = Report()
    try:
        pin = load_pin()
        target = host_target()
        config = read_pack_config(ctx.pack_state)
    except (PinError, ConfigError) as err:
        report.note(Status.ERROR, str(err))
        return report
    if config.hc_bin:
        if not config.allow_unpinned:
            report.note(Status.ERROR, f"hc_bin names an unpinned hc ({config.hc_bin}) without allow_unpinned: remove it and {INSTALL_FIX}")
            return report
        if not (os.path.isfile(config.hc_bin) and os.access(config.hc_bin, os.X_OK)):
            report.note(Status.ERROR, f"hc_bin {config.hc_bin} is not an executable file")
            return report
        report.note(Status.WARNING, f"drives an unpinned hc ({config.hc_bin}, allow_unpinned): the pin is {pin.version}")
        return report
    root = install_root(ctx.host.home)
    binary = pinned_binary(ctx.host.home, str(pin.version))
    problem = verify_installed(pin, root, target)
    if problem is not None:
        if not os.path.isfile(binary):
            report.note(Status.ERROR, f"hc not installed: no herdr-core {pin.version} at {binary}: {INSTALL_FIX}")
        elif "no install.json" in problem:
            report.note(Status.WARNING, f"{problem}; {INSTALL_FIX} to replace it with the verified build")
        else:
            report.note(Status.ERROR, f"{problem}: {INSTALL_FIX}")
        return report
    report.note(Status.OK, f"herdr-core {pin.version} installed and matching the pin ({target})")
    if writable(binary):
        report.note(Status.WARNING, f"{binary} or its directory is writable: `hc update` could replace it; {INSTALL_FIX}")
    return report


# --- hc-core -------------------------------------------------------------------------


def _user_name() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return str(os.getuid())


def _supervisor_cgroup(procs: ProcSource, snapshot: Snapshot) -> Optional[str]:
    uid = os.getuid()
    for proc in snapshot.values():
        if proc.uid == uid and _has_sequence(proc.argv[1:], ("supervisor", "run")):
            group = procs.cgroup(proc.pid)
            if group and group.rstrip("/").endswith(".service"):
                return group.rstrip("/")
    return None


def check_core(ctx: OpContext, *, linger_dir: str = LINGER_DIR) -> Report:
    """The city's core: reachable while the city runs, gated, the pack's own."""
    report = Report()
    try:
        pin = load_pin()
    except PinError as err:
        report.note(Status.ERROR, str(err))
        return report
    try:
        hc_bin: Optional[str] = ctx.hc_binary()
    except ConfigError:
        hc_bin = None
    running = city_running(ctx.env)
    other = lock_socket(ctx)
    if other is not None:
        report.note(Status.ERROR, f"a core of this city's session listens at {other}, not at {ctx.paths.socket}: {RESTART_FIX}")
        return report
    client = ctx.client(read=True, probe=True)
    try:
        hello = client.hello()
    except HcUnreachable:
        kick = read_kick(ctx)
        if kick is not None and not kick.ok and ctx.host.now_ms() - kick.at_ms < KICK_BACKOFF_MS:
            report.note(Status.ERROR, f"the city's core failed to start in the last 5 minutes: {kick.detail}")
        elif running and kick is not None:
            # A read of one of the city's herdr-core sessions found the core
            # down and kicked a start (kick.json), and it is still down.
            report.note(Status.ERROR, f"the city runs but its core does not answer at {ctx.paths.socket} (last start: {kick.detail or 'unknown'})")
        elif running:
            report.note(Status.OK, "no core runs (no session of the city has needed one)")
        else:
            report.note(Status.OK, "no core runs (the city is stopped)")
        return report
    except HcGateError as err:
        message = str(err)
        report.note(Status.ERROR, f"{message}: {UPGRADE_FIX}" if "older" in message else message)
        return report
    except HcError as err:
        report.note(Status.WARNING, f"the city's core did not answer: {err}")
        return report
    version = Version.parse(hello.version)
    report.note(Status.OK, f"the city's core runs herdr-core {version}")
    if version != pin.version:
        report.note(Status.WARNING, f"the city's core runs hc {version}, the pin is {pin.version}: {UPGRADE_FIX}")
    for warning in client.gate_warnings:
        report.note(Status.WARNING, warning)
    try:
        status = client.server_status()
    except HcError as err:
        report.note(Status.WARNING, f"cannot read the core's status: {err}")
        return report
    if status.installed_by:
        report.note(Status.WARNING, f"the core's hc came from {status.installed_by}, which updates it outside the pin")
    expected = core_env(ctx, hc_bin or pinned_binary(ctx.host.home, str(pin.version)))
    procs = ctx.host.procs
    try:
        actual = procs.environ(status.pid)
    except ProcError as err:
        actual = None
        report.note(Status.ERROR, f"cannot read the core's environment ({err}); {FOREIGN_FIX}")
    if actual is not None:
        reason = foreign_reason(actual, expected)
        if reason is not None:
            report.note(Status.ERROR, f"{FOREIGN_FIX} ({reason})")
    elif report.status < Status.ERROR:
        report.note(Status.ERROR, f"cannot read the core's environment (pid {status.pid}); {FOREIGN_FIX}")
    exe = procs.exe(status.pid)
    if exe and hc_bin and os.path.realpath(exe.replace(" (deleted)", "")) != os.path.realpath(hc_bin):
        report.note(Status.ERROR, f"the core runs {exe}, not the pack's {hc_bin} (updated or started outside the pack): {RESTART_FIX}")
    runtime_dir = expected.get("XDG_RUNTIME_DIR", "")
    if not runtime_dir:
        report.note(
            Status.WARNING,
            "no systemd user manager: the core lives only as long as whoever started it, and agents are not re-scoped out of hc's holders",
        )
    elif not os.path.exists(os.path.join(linger_dir, _user_name())):
        report.note(
            Status.WARNING,
            "lingering is off: the user manager, the core and every agent stop when your last login ends (`loginctl enable-linger`)",
        )
    try:
        snapshot = procs.snapshot()
    except ProcError:
        snapshot = {}
    service = _supervisor_cgroup(procs, snapshot)
    core_group = procs.cgroup(status.pid)
    if service and core_group and (core_group == service or core_group.startswith(service + "/")):
        report.note(Status.WARNING, f"the core runs inside gc's service cgroup ({service}): restarting that service ends every agent")
    if not running:
        report.notes.append("the city is stopped; its core stays up until it is stopped")
    return report


# --- hc-scope-hygiene ---------------------------------------------------------------------

HC_BINARY_NAMES: Final = frozenset({"herdr-core", "hc"})
HC_HOLDER_VERBS: Final = frozenset({"hold", "serve"})
HC_UNIT_PREFIXES: Final = ("hc-hold-", "hc-serve-")
CITY_ENV_KEYS: Final = ("GC_CITY", "GC_CITY_PATH", "GC_CITY_ROOT")


def _has_sequence(words: Sequence[str], seq: Tuple[str, ...]) -> bool:
    return any(tuple(words[i : i + len(seq)]) == seq for i in range(len(words) - len(seq) + 1))


def _option(argv: Sequence[str], name: str) -> List[str]:
    """Values of ``--name value`` and ``--name=value`` in ``argv``."""
    out: List[str] = []
    for i, word in enumerate(argv):
        if word == name and i + 1 < len(argv):
            out.append(argv[i + 1])
        elif word.startswith(name + "="):
            out.append(word[len(name) + 1 :])
    return out


def infrastructure_kind(proc: Proc) -> Optional[str]:
    """What city infrastructure ``proc`` is, or None. gc's nudge poller is
    not: it is session-scoped and spawned from agents by design."""
    argv = proc.argv
    if len(argv) < 2:
        return None
    prefix = infrastructure_prefix(argv)
    if prefix == (MANAGED_DOLT_SCOPE_WATCHDOG_VERB,):
        return "managed Dolt watchdog"
    if prefix == (BD_PROXY_CHILD_VERB,):
        return "bd database proxy"
    if prefix:
        return None  # the nudge poller
    if os.path.basename(argv[0]) == "dolt" and argv[1] == "sql-server":
        return "Dolt server"
    if _has_sequence(argv[1:], ("supervisor", "run")):
        return "gc supervisor"
    if argv[1] == "start" and ("--foreground" in argv or "--controller" in argv):
        return "gc controller"
    return None


class CityPaths:
    """The city's path, raw and resolved, for attribution."""

    def __init__(self, city: str) -> None:
        self.roots = {os.path.normpath(city), os.path.realpath(city)} if city else set()

    def holds(self, path: str) -> bool:
        if not path or not os.path.isabs(path):
            return False
        for candidate in {os.path.normpath(path), os.path.realpath(path)}:
            for root in self.roots:
                if candidate == root or candidate.startswith(root.rstrip("/") + "/"):
                    return True
        return False


def attributed(kind: str, proc: Proc, env: Optional[Mapping[str, str]], city: CityPaths, controllers: Set[int]) -> bool:
    """Whether ``proc`` serves this city: by its argv or config path, by gc's
    city variables in its environment, or (a supervisor or controller) by
    holding the city's controller socket."""
    if proc.pid in controllers:
        return True
    if env is not None and any(city.holds(env.get(key, "")) for key in CITY_ENV_KEYS):
        return True
    argv = proc.argv
    if kind == "Dolt server":
        return any(city.holds(path) for path in _option(argv, "--config"))
    if kind == "gc supervisor":
        return False  # it serves many cities; only the socket ties it to this one
    paths: List[str] = []
    for word in argv[1:]:
        paths.append(word.split("=", 1)[1] if word.startswith("--") and "=" in word else word)
    return any(city.holds(path) for path in paths)


def _hc_ancestor(proc: Proc, snapshot: Snapshot) -> Optional[Proc]:
    seen: Set[int] = set()
    current = snapshot.get(proc.ppid)
    while current is not None and current.pid not in seen and current.pid > 1:
        seen.add(current.pid)
        head = os.path.basename(current.argv[0]) if current.argv else os.path.basename(current.comm)
        if head in HC_BINARY_NAMES and len(current.argv) > 1 and current.argv[1] in HC_HOLDER_VERBS:
            return current
        current = snapshot.get(current.ppid)
    return None


def check_scope_hygiene(ctx: OpContext) -> Report:
    """City infrastructure must not run under herdr-core: its holder-loss sweep
    kills every process carrying ``HC_SCOPE``, and an oomd or ``systemctl
    kill`` of a holder's cgroup kills everything in it."""
    report = Report()
    procs = ctx.host.procs
    try:
        snapshot = procs.snapshot()
    except ProcError as err:
        report.note(Status.WARNING, f"cannot read the process table: {err}")
        return report
    city_path = ctx.env.get(DOCTOR_CITY_ENV, "")
    city = CityPaths(city_path)
    uid = os.getuid()
    candidates = {
        pid: kind
        for pid, kind in ((p.pid, infrastructure_kind(p)) for p in snapshot.values() if p.uid == uid and not p.opaque)
        if kind is not None
    }
    managers = [pid for pid, kind in candidates.items() if kind in ("gc supervisor", "gc controller")]
    holders = procs.socket_holders(controller_socket(city_path), managers) if city_path and managers else set()
    controllers: Set[int] = holders or set()
    checked = 0
    for pid in sorted(candidates):
        proc = snapshot[pid]
        kind = candidates[pid]
        try:
            env = procs.environ(proc.pid)
        except ProcError:
            env = None
        if not attributed(kind, proc, env, city, controllers):
            continue
        checked += 1
        label = f"{kind} (pid {proc.pid})"
        if env is None:
            report.note(Status.WARNING, f"{label}: its environment cannot be read")
        elif "HC_SCOPE" in env:
            report.note(Status.ERROR, f"{label} carries HC_SCOPE: a herdr-core holder loss kills it")
        holder = _hc_ancestor(proc, snapshot)
        if holder is not None:
            report.note(Status.ERROR, f"{label} runs under herdr-core (pid {holder.pid}, {' '.join(holder.argv[:2])})")
        group = procs.cgroup(proc.pid)
        if group:
            unit = next((part for part in group.split("/") if part.startswith(HC_UNIT_PREFIXES)), None)
            if unit is not None:
                report.note(Status.ERROR, f"{label} runs in herdr-core's cgroup {unit}: killing that unit kills it")
    if report.status == Status.ERROR:
        report.headline = (
            "city infrastructure runs under herdr-core: restart it outside hc "
            "(`gc dolt restart`, or the supervisor from a login shell)"
        )
    elif report.status == Status.OK:
        report.note(Status.OK, f"no city infrastructure runs under herdr-core ({checked} checked)")
    return report


# --- hc-state-perms --------------------------------------------------------------------


def check_state_perms(ctx: OpContext) -> Report:
    """hc's state for the city (terminal records, saved screens) is private."""
    report = Report()
    targets = [ctx.paths.state_root, os.path.dirname(ctx.paths.state_dir), ctx.paths.state_dir, os.path.join(ctx.paths.state_dir, "terminals.json")]
    found = False
    for path in targets:
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as err:
            report.note(Status.ERROR, f"cannot read {path}: {err.strerror}")
            continue
        found = True
        if stat.S_ISLNK(st.st_mode):
            report.note(Status.ERROR, f"{path} is a symlink")
        elif st.st_uid != os.getuid():
            report.note(Status.ERROR, f"{path} is owned by uid {st.st_uid}")
        elif stat.S_IMODE(st.st_mode) & 0o077:
            report.note(Status.ERROR, f"{path} is readable by others (mode {stat.S_IMODE(st.st_mode):o})")
    if report.status == Status.OK:
        report.note(Status.OK, "hc's state is private" if found else "no hc state yet")
        report.notes.append(f"hc keeps terminal records and screens in plaintext under {ctx.paths.state_dir}")
    return report


# --- dispatch ----------------------------------------------------------------------------

Check = Callable[[OpContext], Report]


def _core(ctx: OpContext) -> Report:
    linger = ctx.env.get(TEST_LINGER_DIR_ENV, "") if ctx.test else ""
    return check_core(ctx, linger_dir=linger or LINGER_DIR)


CHECKS: Final[Dict[str, Check]] = {
    "hc-binary": check_binary,
    "hc-core": _core,
    "hc-scope-hygiene": check_scope_hygiene,
    "hc-state-perms": check_state_perms,
}


class _Expired(Exception):
    pass


def _expire(signum: int, frame: Optional[FrameType]) -> None:
    raise _Expired()


def run_check(name: str, env: Mapping[str, str], host: Host, *, budget_s: float = CHECK_BUDGET_S) -> Report:
    """Run check ``name`` within ``budget_s`` seconds."""
    check = CHECKS.get(name)
    if check is None:
        return Report(Status.ERROR, f"unknown check {name!r} (known: {', '.join(sorted(CHECKS))})")
    cancel = CancelToken()
    previous = signal.signal(signal.SIGALRM, _expire)
    signal.setitimer(signal.ITIMER_REAL, budget_s)
    try:
        ctx = admin_context(env, host, name=f"doctor {name}", deadline_s=budget_s, cancel=cancel)
        return check(ctx)
    except _Expired:
        return Report(Status.WARNING, f"timed out after {budget_s:g} s")
    except (ConfigError, StateDirError, PinError) as err:
        return Report(Status.ERROR, str(err))
    except (HcError, ProcError, OSError) as err:
        return Report(Status.ERROR, f"the check could not finish: {err}")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def main(argv: Sequence[str], env: Mapping[str, str], python: str, out: TextIO) -> int:
    """``x-doctor <check>``: print the report and exit with its status."""
    if len(argv) != 1:
        out.write(f"usage: x-doctor <{'|'.join(sorted(CHECKS))}>\n")
        return int(Status.ERROR)
    report = run_check(argv[0], env, admin_host(env, python))
    out.write(report.render())
    out.flush()
    return int(report.status)

