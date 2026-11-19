"""The city's core: starting it, refusing one started by anyone else, and
kicking a start when a read finds it down.

hc's raw socket API never starts a core (only its CLI does), and every
program a core runs inherits the environment of whoever started it
(herdr-core #86). So the pack starts the core itself, with ``hc server
start`` under a minimal explicit environment (:func:`core_env`): the
password-database user, a fixed ``PATH``, the locale, the discovery tuple
and the pack-owned config, and the systemd user manager's runtime directory
and bus when they exist (which keeps hc's systemd placement). No gc token or
provider credential reaches the core or its programs.

A core whose environment differs from that is **foreign** (a person's ``hc``,
an in-agent CLI during a restart window, the Herdr app's autostart):
``start`` refuses to put sessions on it and names the fix. Reads stay
permissive: they report what the core holds. A core hc placed under
systemd is judged by its unit's environment file, found through
``RUNTIME_DIRECTORY`` (when the core runs in that unit) or, before systemd
244, through the core's control group (:func:`foreign_reason`); a file a
holder wrote when it restarted the core is the pack's by the lineage the
pack recorded when it accepted that holder's core. A core hc placed under
launchd (macOS) runs with launchd's environment, so it is judged by who
started it: the pack's own hc, which the pack names before it waits on it,
or a holder of the city restarting a crashed core (:mod:`.coreid`). Only a
start records what it accepts (:func:`check_foreign`). Before its own ``hc
server start`` the pack removes hc's restart handoff
(:func:`clear_restart_env`).

A read that finds the core down answers unknown and **kicks** a detached
start, at most one at a time per city and none for five minutes after a
failed one; ``kick.json`` records the last attempt and its outcome, never
liveness (always probed live). No read kicks a start for a city **at
rest**: one ``server-stop`` parked, or one no core has ever run for
(:func:`never_started`: hc keeps every record, live or finished, under the
session's state directory, which it creates before any core or holder of
the session runs), while nothing of the core runs (:func:`at_rest`). Such a
city reads empty, which is the truth, and its first session start brings
the core up, so ``gc doctor`` before ``gc start`` starts nothing. No core
is ever started for a call that names no city (the fixed bucket only
identifies): :func:`run_starter` and :func:`kick_due` refuse it.

A core ``server-stop`` stopped is **parked**: ``parked.json`` records that
the pack ended every record of the city and then the core, on purpose. While
it is there no read kicks a start (a stopped city stays stopped), and a read
that finds nothing of the core running answers an empty city. A
``server-stop`` that finds the core already down parks the city too, so
gc's confirming read after its stop does not start it again; while the pack
keeps an incarnation's metadata it first starts the core to remove the
records hc keeps across a restart (:mod:`.server`). A start
(:func:`ensure_core`) clears the mark, first, before it tries the core and
before any record is created: one whose core start then fails (a core lock
naming another socket) leaves the city unparked, and reads kick again as
for any core that is down. The mark holds only while nothing of the core
runs: ``server-stop`` clears it at its end when a holder or a core still
runs, and a read that finds a parked city with a holder or core still
running (a ``server-stop`` killed at its deadline) answers unknown and
kicks, since gc never sends a start for a session it reads unknown, so
the city is never stranded. ``server-stop`` holds the kick lock
(:data:`KICK_LOCK`) throughout, so no kick starts the core while it
sweeps. A core that ends any other way (a crash, a reboot) is kicked as
before.
"""

from __future__ import annotations

import os
import pwd
import subprocess
import time
from typing import Callable, Dict, Final, FrozenSet, List, Mapping, Optional, Sequence, Set

from ..hc.errors import HcError, HcUnreachable
from ..hc.paths import ensure_dirs
from ..hc.types import StatusResult
from ..rpp.flock import LockTimeout
from ..rpp.frozen import frozen
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.ops import OpError
from ..rpp.statedir import StateDirError
from . import coreid
from .attach import ATTACH_TERMINAL_KEYS
from .command import Completed, run_bounded
from .config import ConfigError, read_private_file, write_hc_config, write_private_file
from .context import OpContext
from .corescan import holder_prefix, is_holder_of, listener_elsewhere, nothing_runs
from .naming import KICK_OP
from .procs import ProcError

CORE_START_WAIT_S: Final = 15.0
"""hc's own wait for a starting core (``client.rs`` START_WAIT)."""

KICK_FILE: Final = "kick.json"
PARK_FILE: Final = "parked.json"
KICK_BACKOFF_MS: Final = 5 * 60 * 1000
KICK_LOCK: Final = "kick"
"""Held by a kick while it starts the core, and by ``server-stop`` throughout."""

BASE_PATH: Final = "/usr/local/bin:/usr/bin:/bin"

DISCOVERY_KEYS: Final = ("HC_SESSION", "HC_SOCKET", "XDG_STATE_HOME", "XDG_CONFIG_HOME")

SERVICE_KEYS: Final[FrozenSet[str]] = frozenset(
    {
        "INVOCATION_ID",
        "RUNTIME_DIRECTORY",
        "JOURNAL_STREAM",
        "SYSTEMD_EXEC_PID",
        "MANAGERPID",
        "MANAGERPIDFDID",
        "MEMORY_PRESSURE_WATCH",
        "MEMORY_PRESSURE_WRITE",
        "NOTIFY_SOCKET",
        "WATCHDOG_PID",
        "WATCHDOG_USEC",
        "LISTEN_PID",
        "LISTEN_FDS",
        "LISTEN_FDNAMES",
    }
)
"""What systemd sets for a service (hc ``platform/systemd.rs`` ``SERVICE``)."""

UNIT_ENVIRONMENT_FILE: Final = "environment"
"""hc writes the starter's environment, 0600, to ``$RUNTIME_DIRECTORY/environment``
and starts its unit with ``EnvironmentFile=`` it (``platform/systemd.rs``)."""

HC_RUNTIME_KEY: Final = "HC_RUNTIME"
"""hc marks its own cores and holders with ``HC_RUNTIME=1`` (sweep exemption)."""

HC_MARK_KEYS: Final[FrozenSet[str]] = frozenset({HC_RUNTIME_KEY, "XPC_SERVICE_NAME", "_HC_RESPONSIBLE_PID", "HC_LAUNCHD_DIRECT"})
"""What hc itself sets in a core's or holder's environment: ``HC_RUNTIME``;
on macOS ``XPC_SERVICE_NAME=0`` in the environment a launchd core restores
(``platform/macos_launchd.rs``), ``HC_LAUNCHD_DIRECT`` on a core it serves
directly when it cannot use launchd (the same file), and
``_HC_RESPONSIBLE_PID`` in the one a holder re-execs itself with
(``platform/macos_responsibility.rs``)."""

HC_CORE_UNIT_PREFIX: Final = "hc-serve-"
SYSTEMD_SERVICE_SUFFIX: Final = ".service"
UNIT_ID_LEN: Final = 8
"""hc names a core's unit ``hc-serve-<8 hex>.service`` and gives it the
runtime directory ``$XDG_RUNTIME_DIR/hc-serve-<8 hex>`` (``platform/systemd.rs``)."""

TEST_RUNTIME_DIR_ENV: Final = "GC_HC_TEST_RUNTIME_DIR"
"""Test-only (``GC_HC_TEST=1``): the runtime directory handed to the core
instead of ``/run/user/<uid>``."""

RESTART_ENV_FILE: Final = "restart-env.json"
"""hc's restart handoff in the city's state directory: the environment an
``hc server restart`` saved, which the next core hc starts restores when it
is under three minutes old (``restart.rs``)."""

FOREIGN_FIX: Final = "city core was started outside the pack: run `gc herdr-core restart-core`"


def _locale(env: Mapping[str, str]) -> Dict[str, str]:
    return {k: v for k, v in env.items() if (k == "LANG" or k.startswith("LC_")) and v}


def core_env(
    ctx: OpContext,
    hc_bin: str,
    *,
    run_user: Optional[str] = None,
) -> Dict[str, str]:
    """The whole environment ``hc server start`` runs with (the allowlist)."""
    uid = os.getuid()
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = str(uid)
    env = {
        "HOME": ctx.host.home(),
        "USER": user,
        "LOGNAME": user,
        "PATH": os.path.dirname(hc_bin) + ":" + BASE_PATH,
    }
    env.update(_locale(ctx.env))
    env.update(ctx.paths.discovery_env())
    if run_user is not None:
        runtime_dir = run_user
    elif ctx.test and ctx.env.get(TEST_RUNTIME_DIR_ENV, ""):
        runtime_dir = ctx.env[TEST_RUNTIME_DIR_ENV]
    else:
        runtime_dir = f"/run/user/{uid}"
    if os.path.isdir(runtime_dir):
        env["XDG_RUNTIME_DIR"] = runtime_dir
        bus = os.path.join(runtime_dir, "bus")
        if os.path.exists(bus):
            env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + bus
    return env


def allowed_core_keys(env: Mapping[str, str]) -> FrozenSet[str]:
    """The variables a core started with ``env`` may carry. A core hc's CLI
    starts while ``attach`` races a core's exit has the viewer's terminal
    settings too (:data:`.attach.ATTACH_TERMINAL_KEYS`), and hc's own marks
    (:data:`HC_MARK_KEYS`)."""
    return frozenset(env) | {"LANG", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", *HC_MARK_KEYS, *ATTACH_TERMINAL_KEYS}


def format_environment_file(env: Mapping[str, str]) -> str:
    """``env`` as hc writes a unit's EnvironmentFile: ``KEY="value"`` lines,
    with backslash, double quote, dollar and backtick escaped."""
    out = []
    for key in sorted(env):
        value = "".join("\\" + ch if ch in '\\"$`' else ch for ch in env[key])
        out.append(f'{key}="{value}"\n')
    return "".join(out)


def parse_environment_file(text: str) -> Optional[Dict[str, str]]:
    """A unit EnvironmentFile as hc writes it; None when it is not that shape."""
    env: Dict[str, str] = {}
    at = 0
    while at < len(text):
        if text[at] == "\n":
            at += 1
            continue
        eq = text.find('="', at)
        if eq <= at:
            return None
        key = text[at:eq]
        if not (key[0].isalpha() or key[0] == "_") or not all(c.isalnum() or c == "_" for c in key):
            return None
        at = eq + 2
        value = []
        while True:
            if at >= len(text):
                return None
            ch = text[at]
            if ch == "\\" and at + 1 < len(text):
                value.append(text[at + 1])
                at += 2
            elif ch == '"':
                at += 1
                break
            else:
                value.append(ch)
                at += 1
        env[key] = "".join(value)
    return env


def read_unit_environment(runtime_directory: str) -> Optional[Dict[str, str]]:
    """The environment a systemd-placed core's unit was started with; None when unreadable."""
    try:
        raw = read_private_file(os.path.join(runtime_directory, UNIT_ENVIRONMENT_FILE))
    except StateDirError:
        return None
    if raw is None:
        return None
    return parse_environment_file(raw.decode("utf-8", "surrogateescape"))


def is_core_unit_name(unit: str) -> bool:
    """Whether ``unit`` is an hc core unit's name, ``hc-serve-<8 hex>``."""
    unit_id = unit[len(HC_CORE_UNIT_PREFIX) :]
    return (
        unit.startswith(HC_CORE_UNIT_PREFIX)
        and len(unit_id) == UNIT_ID_LEN
        and all(c in "0123456789abcdef" for c in unit_id)
    )


def core_unit(cgroup: Optional[str], uid: int) -> Optional[str]:
    """The name of the hc core unit (``hc-serve-<8 hex>``) of this user's
    systemd manager that control group path ``cgroup`` is, or None."""
    if not cgroup:
        return None
    if f"/user@{uid}.service/" not in cgroup:
        return None
    leaf = cgroup.rstrip("/").rsplit("/", 1)[-1]
    if not leaf.endswith(SYSTEMD_SERVICE_SUFFIX):
        return None
    unit = leaf[: -len(SYSTEMD_SERVICE_SUFFIX)]
    return unit if is_core_unit_name(unit) else None


def unit_directory(actual: Mapping[str, str], cgroup: Optional[str], run_user: str) -> Optional[str]:
    """The runtime directory of the hc core unit a core with environment
    ``actual`` and control group ``cgroup`` (None: unreadable) runs as, or
    None when it runs as none, or when ``RUNTIME_DIRECTORY`` names no hc
    core unit or not the one its control group is: that is only a variable,
    and its environment is then judged. Before systemd 244, which sets no
    ``RUNTIME_DIRECTORY``, the unit is the control group's, in ``run_user``
    (empty when the user has no runtime directory)."""
    running_in = core_unit(cgroup, os.getuid())
    named = actual.get("RUNTIME_DIRECTORY")
    if named is not None:
        unit = os.path.basename(os.path.normpath(named))
        if not is_core_unit_name(unit) or (cgroup is not None and running_in != unit):
            return None
        return named
    if running_in is None:
        return None
    return os.path.join(run_user, running_in) if run_user else running_in


def foreign_reason(
    actual: Mapping[str, str],
    expected: Mapping[str, str],
    *,
    cgroup: Optional[str] = None,
    unit_environment: Callable[[str], Optional[Dict[str, str]]] = read_unit_environment,
    lineage: Optional[coreid.Lineage] = None,
) -> Optional[str]:
    """Why a core running with environment ``actual`` is not the pack's, or None.

    What is judged, by placement:

    * **No service manager:** ``actual``, the core's live environment.
    * **systemd:** the unit's EnvironmentFile, where hc writes the starter's
      environment; the manager's block and systemd's service variables in
      ``actual`` are not the starter's. The file is read only when the core
      runs as an hc core unit (:func:`unit_directory`): ``RUNTIME_DIRECTORY``
      names ``hc-serve-<8 hex>`` and the readable control group ``cgroup``
      is that unit, or, under systemd older than 244, which sets no
      ``RUNTIME_DIRECTORY``, the control group alone names it. Otherwise
      ``actual`` is judged.
    * **launchd** (macOS): judged by its starter (:func:`launchd_reason`),
      which judges a holder's environment here.

    In what is judged, the discovery tuple must equal the pack's by value.
    Every other variable is judged **by name only**: it must be one
    :func:`allowed_core_keys` allows (the allowlist, the locale, the user's
    runtime directory and bus, hc's marks, ``attach``'s terminal settings),
    or, in a live environment, a systemd service variable. In a unit file,
    another name passes only with the value ``lineage`` records for it:
    what every holder of a systemd core the pack accepted carries, which a
    holder writes into the file of the core it restarts (:mod:`.coreid`).
    No live holder is asked, so the holders a foreign core started never
    vouch for it. Only key names are reported, never values.
    """
    for key in DISCOVERY_KEYS:
        if actual.get(key) != expected.get(key):
            return f"its {key} differs from the pack's"
    run_user = expected.get("XDG_RUNTIME_DIR", "")
    runtime_directory = unit_directory(actual, cgroup, run_user)
    if runtime_directory is None:
        stray = _stray(actual, set(allowed_core_keys(expected)) | SERVICE_KEYS)
    else:
        if not run_user or os.path.dirname(os.path.normpath(runtime_directory)) != os.path.normpath(run_user):
            return "it runs as a systemd unit outside the user's runtime directory"
        unit_env = unit_environment(runtime_directory)
        if unit_env is None:
            return "it runs as a systemd unit whose environment file cannot be read"
        for key in DISCOVERY_KEYS:
            if unit_env.get(key) != expected.get(key):
                return f"its unit was started with another {key}"
        stray = [
            key
            for key in _stray(unit_env, set(allowed_core_keys(expected)))
            if lineage is None or not lineage.carries(key, unit_env[key])
        ]
    if stray:
        return "it carries variables the pack never sets: " + ", ".join(stray[:8])
    return None


def _stray(env: Mapping[str, str], allowed: Set[str]) -> List[str]:
    return sorted(key for key in env if key not in allowed and not key.startswith("LC_"))


def check_discovery_paths(env: Mapping[str, str], *, lossy: bool) -> None:
    """Where a core's environment can only be read cut at whitespace (macOS
    ``ps -E``), a discovery value with whitespace could never be matched, and
    the pack would refuse its own core: refuse that state root up front."""
    if not lossy:
        return
    for key in DISCOVERY_KEYS:
        if any(ch.isspace() for ch in env.get(key, "")):
            raise OpError(f"{key} holds whitespace, which this host's process table cannot read back: choose a GC_EXEC_STATE_DIR without it")


def check_core_lock(ctx: OpContext) -> None:
    """Refuse a core of this session that listens on another socket (herdr-core #200)."""
    listening = listener_elsewhere(ctx)
    if listening is None:
        return
    raise OpError(
        f"the city's core listens at {listening}, not at {ctx.paths.socket}: "
        "run `gc herdr-core restart-core`"
    )


@frozen
class StarterRun:
    """An hc the pack ran to start the core (:func:`run_starter`)."""

    done: Completed
    since_ms: int
    """Wall clock before the pack ran it."""


def require_city(ctx: OpContext) -> None:
    """Refuse a call that names no city: no core is started for one."""
    if not ctx.paths.scoped:
        raise OpError(ctx.no_city)


def run_starter(ctx: OpContext, argv: Sequence[str], *, env: Mapping[str, str], timeout_s: float) -> StarterRun:
    """Run the hc command ``argv`` that starts the core (``server start`` or
    ``server restart``), adding it to the pending starts before it is
    waited on and closing its entry once it ends (:mod:`.coreid`). Refused
    for a call that names no city."""
    require_city(ctx)
    since_ms = coreid.wall_ms()
    noted: List[int] = []

    def pending(pid: int) -> None:
        try:
            coreid.begin_start(ctx, starter_pid=pid, since_ms=since_ms)
        except coreid.PENDING_ERRORS as err:
            raise OpError(f"cannot note the start of the city's core: {err}") from None
        noted.append(pid)

    try:
        done = run_bounded(argv, env=env, cwd=ctx.paths.state_root, timeout_s=timeout_s, cancel=ctx.request.cancel, on_spawn=pending)
    except OSError as err:
        raise OpError(f"cannot run {argv[0]} {' '.join(argv[1:])}: {err.strerror or err}") from None
    finally:
        if noted:
            _close_start(ctx, noted[0], since_ms)
    return StarterRun(done=done, since_ms=since_ms)


def _close_start(ctx: OpContext, starter_pid: int, since_ms: int) -> None:
    try:
        coreid.close_start(ctx, starter_pid=starter_pid, since_ms=since_ms, until_ms=coreid.wall_ms())
    except coreid.PENDING_ERRORS as err:
        raise OpError(f"cannot note the end of the city's core start: {err}") from None


def clear_restart_env(ctx: OpContext) -> None:
    """Remove hc's restart handoff before the pack's own ``hc server
    start``: a restart someone else asked for in the last three minutes
    would otherwise hand its environment to the core the pack starts. Never
    before an ``hc server restart``, whose handoff it is."""
    try:
        os.unlink(os.path.join(ctx.paths.state_dir, RESTART_ENV_FILE))
    except FileNotFoundError:
        return
    except OSError as err:
        raise OpError(f"cannot clear hc's restart environment before starting the city's core: {err.strerror}") from None


def start_core(ctx: OpContext, hc_bin: str) -> None:
    """``hc server start`` under the allowlist, with hc's restart handoff
    cleared (:func:`clear_restart_env`), wait for the core's hello, then
    record the core that answers when that hc started it under launchd
    (:mod:`.coreid`). Refused for a call that names no city, before
    anything is created."""
    require_city(ctx)
    ensure_dirs(ctx.paths)
    write_hc_config(ctx.paths)
    budget = ctx.request.deadline.budget(CORE_START_WAIT_S)
    if budget <= 0:
        raise OpError("no time left to start the city's core")
    clear_restart_env(ctx)
    run = run_starter(ctx, [hc_bin, "server", "start"], env=core_env(ctx, hc_bin), timeout_s=budget)
    done = run.done
    if not done.ok:
        detail = done.output.splitlines()[-1] if done.output else "no output"
        state = "timed out" if done.returncode is None else f"exited {done.returncode}"
        raise OpError(f"cannot start the city's core: hc server start {state}: {detail}")
    end = time.monotonic() + ctx.request.deadline.budget(CORE_START_WAIT_S)
    while True:
        try:
            ctx.client().hello()
            break
        except HcUnreachable:
            if time.monotonic() >= end:
                raise OpError("the city's core did not answer after hc server start") from None
            ctx.request.cancel.pause(0.05)
    record_started_core(ctx, run)


def record_started_core(ctx: OpContext, run: StarterRun) -> None:
    """Record the core that answers now as the one the pack started, when the
    hc the pack ran asked launchd for it, and drop that start's pending
    entry: it finished. Any other core is not recorded (:mod:`.coreid`)."""
    try:
        status = ctx.client().server_status()
    except HcError:
        return
    coreid.record(ctx, status, starter_pid=run.done.pid, since_ms=run.since_ms)
    try:
        coreid.finish_start(ctx, starter_pid=run.done.pid, since_ms=run.since_ms)
    except coreid.PENDING_ERRORS as err:
        raise OpError(f"cannot note the end of the city's core start: {err}") from None


# --- parking ---------------------------------------------------------------------------


def parked(ctx: OpContext) -> bool:
    """Whether ``server-stop`` stopped the city's core and no start has come
    since. An unreadable mark reads as not parked: reads kick, as before.
    It creates no state (doctor reads it too), as :func:`read_kick` does."""
    try:
        return read_private_file(os.path.join(ctx.pack_state, PARK_FILE)) is not None
    except StateDirError:
        return False


def never_started(ctx: OpContext) -> bool:
    """Whether no core or holder has ever run for the city's session: hc's
    state directory for it does not exist. hc creates it before either runs
    (``Paths::create_dirs``), and the pack before its own first ``hc server
    start``. False when it cannot be told (an lstat that fails otherwise)."""
    try:
        os.lstat(ctx.paths.state_dir)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def at_rest(ctx: OpContext) -> bool:
    """Whether the city holds no session and nothing of its core runs: it
    is parked or never started, and :func:`.corescan.nothing_runs`. Such a
    city reads empty, and no read kicks its core."""
    return (parked(ctx) or never_started(ctx)) and nothing_runs(ctx)


def park(ctx: OpContext) -> None:
    """Mark the city's core as stopped on purpose (raises StateDirError or OSError)."""
    doc = {"at_ms": ctx.host.now_ms()}
    write_private_file(ctx.state_file(PARK_FILE), (dumps(doc) + "\n").encode("ascii"))


def unpark(ctx: OpContext) -> None:
    """Clear the mark: the city's core is started again."""
    try:
        os.unlink(ctx.state_file(PARK_FILE))
    except FileNotFoundError:
        return
    except (OSError, StateDirError) as err:
        raise OpError(f"cannot clear the city's stopped mark: {err}") from None


@frozen
class Foreign:
    """Why the city's core is not taken as the pack's (:func:`foreign_core`)."""

    reason: str
    unknown: bool = False
    """Its process or environment cannot be read, so who started it cannot
    be told; a start refuses it all the same."""


def foreign_core(ctx: OpContext, status: StatusResult, hc_bin: str, *, record: bool = False) -> Optional[Foreign]:
    """Why the core behind ``status`` is not the pack's, or None. A core hc
    placed under launchd is judged by who started it (:func:`launchd_reason`);
    any other core by its environment (:func:`foreign_reason`), a systemd
    core's unit file against the lineage the pack recorded. One whose
    process or environment cannot be read is not the pack's either
    (:attr:`Foreign.unknown`). ``record``: a start checks the core, and
    records the one it accepts (:mod:`.coreid`); ``status``, doctor and
    ``upgrade`` only read."""
    expected = core_env(ctx, hc_bin)
    try:
        proc = ctx.host.procs.process(status.pid)
    except ProcError as err:
        return Foreign(f"its process cannot be read: {err}", unknown=True)
    if proc is None:
        return Foreign("its process cannot be found", unknown=True)
    started = coreid.launchd_start(proc.argv)
    if started is not None:
        reason = launchd_reason(ctx, status, started, expected, record=record)
        return None if reason is None else Foreign(reason)
    try:
        actual = ctx.host.procs.environ(status.pid)
    except ProcError as err:
        return Foreign(f"its environment cannot be read: {err}", unknown=True)
    if actual is None:
        return Foreign("its environment cannot be read", unknown=True)
    cgroup = ctx.host.procs.cgroup(status.pid)
    reason = foreign_reason(actual, expected, cgroup=cgroup, lineage=coreid.read_lineage(ctx))
    if reason is not None:
        return Foreign(reason)
    if record and unit_directory(actual, cgroup, expected.get("XDG_RUNTIME_DIR", "")) is not None:
        record_lineage(ctx, actual)
    return None


def record_lineage(ctx: OpContext, actual: Mapping[str, str]) -> None:
    """Record, for the systemd core a start accepted, running with
    ``actual``, what every holder of that core carries: its environment less
    systemd's service variables (hc writes that into a holder's unit file,
    and the holder's whole environment into the file of a core it restarts).
    Best effort: with no record, a core one of those holders restarts is
    refused, and ``restart-core`` mends that."""
    try:
        coreid.write_lineage(ctx, coreid.Lineage.of({k: v for k, v in actual.items() if k not in SERVICE_KEYS}))
    except (OSError, StateDirError):
        return


def launchd_reason(
    ctx: OpContext, status: StatusResult, started: coreid.LaunchdStart, expected: Mapping[str, str], *, record: bool = False
) -> Optional[str]:
    """Why a core hc placed under launchd is not the pack's, or None: it is
    the core the pack's own hc started (its recorded identity, or a pending
    start that names its starter), or one a holder of the city restarted,
    judged by that holder's environment (:func:`holder_reason`). ``record``:
    a start accepts it, and records it (:func:`.coreid.pin`), so it stays
    the pack's once that start's entry, or that holder, is gone."""
    if coreid.started_by_pack(ctx, status):
        return None
    pending = coreid.pending_start(ctx, started)
    reason = None if pending is not None else holder_reason(ctx, started, expected)
    if reason is None and record:
        coreid.pin(ctx, status, superseding=pending)
    return reason


def holder_reason(ctx: OpContext, started: coreid.LaunchdStart, expected: Mapping[str, str]) -> Optional[str]:
    """Why the launchd core ``started`` names was not restarted by a holder
    of the city whose environment is the pack's, or None."""
    starter = coreid.live(ctx, started.starter_pid)
    if starter is None or starter.uid != os.getuid() or not is_holder_of(starter, holder_prefix(ctx.paths)):
        return "it was started through launchd by an hc the pack did not run"
    holder_started_ms = ctx.host.procs.started_ms(starter)
    if holder_started_ms is None or holder_started_ms > started.asked_ns // 1_000_000:
        return "it was asked for before the holder its start names began: that pid was another process's"
    try:
        holder_env = ctx.host.procs.environ(starter.pid)
    except ProcError as err:
        return f"the environment of the holder that started it cannot be read: {err}"
    if holder_env is None:
        return f"the holder that started it (pid {starter.pid}) is gone"
    reason = foreign_reason(holder_env, expected)
    return None if reason is None else f"the holder that started it was not the pack's: {reason}"


def check_foreign(ctx: OpContext, hc_bin: str) -> None:
    """Refuse the running core unless the pack started it; record the one it
    accepts where its environment cannot show that (:func:`foreign_core`)."""
    found = foreign_core(ctx, ctx.client().server_status(), hc_bin, record=True)
    if found is not None:
        raise OpError(f"{FOREIGN_FIX} ({found.reason})")


def ensure_core(ctx: OpContext) -> str:
    """The city's core, started if down and checked as the pack's own.
    Returns the hc binary. It clears the stopped mark first, whatever then
    becomes of the start: a start is the way out of a parked city. Once the
    core is the pack's own, it rewrites the pack-owned hc config where it
    differs: hc reads that file on every ``terminal.run``, so the start runs
    on the current file even under a core an earlier release started."""
    unpark(ctx)  # before any record: a parked city holds none
    try:
        hc_bin = ctx.hc_binary()
    except ConfigError as err:
        raise OpError(str(err)) from None
    check_discovery_paths(ctx.paths.discovery_env(), lossy=ctx.host.procs.lossy_environ)
    check_core_lock(ctx)
    try:
        ctx.client().hello()
    except HcUnreachable:
        if ctx.backend_unavailable:
            raise OpError("the backend is unavailable (GC_RPP_FAULT=unavailable)") from None
        start_core(ctx, hc_bin)
    check_foreign(ctx, hc_bin)
    write_hc_config(ctx.paths)
    return hc_bin


# --- kick ------------------------------------------------------------------------------


@frozen
class KickRecord:
    at_ms: int
    ok: bool
    detail: str


def read_kick(ctx: OpContext) -> Optional[KickRecord]:
    try:
        raw = read_private_file(os.path.join(ctx.pack_state, KICK_FILE))
        if raw is None:
            return None
        doc = JsonObject.of(loads(raw))
        return KickRecord(at_ms=doc.req_int("at_ms"), ok=doc.req_bool("ok"), detail=doc.str_or("detail", ""))
    except (JsonShapeError, OSError, ValueError, StateDirError):
        return None


def write_kick(ctx: OpContext, record: KickRecord) -> None:
    doc = {"at_ms": record.at_ms, "ok": record.ok, "detail": record.detail}
    write_private_file(ctx.state_file(KICK_FILE), (dumps(doc) + "\n").encode("ascii"))


def kick_due(ctx: OpContext) -> bool:
    """Whether a kick may start the core: never for a call that names no
    city, never while the city is at rest (:func:`at_rest`), nor within the
    backoff after a failed one. A parked or never-started city whose holder
    or core still runs is kicked: gc reads unknown while it runs and never
    sends the start that unparks, so the core comes back to adopt what runs
    (``server-stop`` holds the kick lock, so none starts while it sweeps)."""
    if not ctx.paths.scoped or at_rest(ctx):
        return False
    record = read_kick(ctx)
    return record is None or record.ok or ctx.host.now_ms() - record.at_ms >= KICK_BACKOFF_MS


def kick(ctx: OpContext) -> bool:
    """Start the city's core in the background for the next pass. Returns
    whether a start was launched."""
    if ctx.backend_unavailable or not kick_due(ctx):
        return False
    try:
        ctx.hc_binary()
        with ctx.lock(KICK_LOCK, shared=False, wait_s=0.0):
            pass  # a kick in flight holds it
    except (ConfigError, LockTimeout, OSError):
        return False
    entry = os.path.join(ctx.host.pack_dir, "assets", "bin", "gc-runtime-herdr-core")
    env = {k: v for k, v in ctx.env.items() if k != "GC_EXEC_DEADLINE_MS"}
    subprocess.Popen(
        [ctx.host.python, "-I", "-S", entry, KICK_OP],
        env=env,
        cwd="/",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True


def run_kick(ctx: OpContext) -> None:
    """The detached kick: start the core unless another kick is at it."""
    try:
        with ctx.lock(KICK_LOCK, shared=False, wait_s=0.0):
            if not kick_due(ctx):
                return
            try:
                hc_bin = ctx.hc_binary()
                check_core_lock(ctx)
                try:
                    ctx.client().hello()
                    write_kick(ctx, KickRecord(at_ms=ctx.host.now_ms(), ok=True, detail="already running"))
                    return
                except HcUnreachable:
                    pass
                start_core(ctx, hc_bin)
            except (ConfigError, OpError, HcError, OSError) as err:
                write_kick(ctx, KickRecord(at_ms=ctx.host.now_ms(), ok=False, detail=ctx.request.redactor.redact(str(err))))
                raise
            write_kick(ctx, KickRecord(at_ms=ctx.host.now_ms(), ok=True, detail="started"))
    except LockTimeout:
        return
