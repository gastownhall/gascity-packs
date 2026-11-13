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
permissive: they report what the core holds.

A read that finds the core down answers unknown and **kicks** a detached
start, at most one at a time per city and none for five minutes after a
failed one; ``kick.json`` records the last attempt and its outcome, never
liveness (always probed live).

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
from dataclasses import dataclass
from typing import Callable, Dict, Final, FrozenSet, Mapping, Optional

from ..hc.errors import HcError, HcUnreachable
from ..hc.paths import ensure_dirs
from ..rpp.flock import LockTimeout
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.ops import OpError
from ..rpp.statedir import StateDirError
from .attach import ATTACH_TERMINAL_KEYS
from .command import run_bounded
from .config import ConfigError, read_private_file, write_hc_config, write_private_file
from .context import OpContext
from .corescan import listener_elsewhere, nothing_runs
from .procs import ProcError

CORE_START_WAIT_S: Final = 15.0
"""hc's own wait for a starting core (``client.rs`` START_WAIT)."""

KICK_FILE: Final = "kick.json"
PARK_FILE: Final = "parked.json"
KICK_BACKOFF_MS: Final = 5 * 60 * 1000
KICK_OP: Final = "x-kick-core"
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

TEST_RUNTIME_DIR_ENV: Final = "GC_HC_TEST_RUNTIME_DIR"
"""Test-only (``GC_HC_TEST=1``): the runtime directory handed to the core
instead of ``/run/user/<uid>``."""

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
    settings too (:data:`.attach.ATTACH_TERMINAL_KEYS`)."""
    return frozenset(env) | {"LANG", HC_RUNTIME_KEY, "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", *ATTACH_TERMINAL_KEYS}


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


def foreign_reason(
    actual: Mapping[str, str],
    expected: Mapping[str, str],
    *,
    unit_environment: Callable[[str], Optional[Dict[str, str]]] = read_unit_environment,
) -> Optional[str]:
    """Why a core running with environment ``actual`` is not the pack's, or None.

    A core hc placed under systemd runs with the user manager's environment
    block, systemd's service variables and its unit's EnvironmentFile (the
    starter's environment): the starter is judged by that file, never by the
    manager's block, which the pack does not control and which changes. A
    core spawned without systemd is judged by its own environment. Only key
    names are reported, never values.
    """
    for key in DISCOVERY_KEYS:
        if actual.get(key) != expected.get(key):
            return f"its {key} differs from the pack's"
    allowed = set(allowed_core_keys(expected)) | SERVICE_KEYS
    started = actual
    runtime_directory = actual.get("RUNTIME_DIRECTORY")
    if runtime_directory is not None:
        run_user = expected.get("XDG_RUNTIME_DIR", "")
        if not run_user or os.path.dirname(os.path.normpath(runtime_directory)) != os.path.normpath(run_user):
            return "it runs as a systemd unit outside the user's runtime directory"
        unit_env = unit_environment(runtime_directory)
        if unit_env is None:
            return "it runs as a systemd unit whose environment file cannot be read"
        for key in DISCOVERY_KEYS:
            if unit_env.get(key) != expected.get(key):
                return f"its unit was started with another {key}"
        started = unit_env
        allowed = set(allowed_core_keys(expected))
    stray = sorted(key for key in started if key not in allowed and not key.startswith("LC_"))
    if stray:
        return "it carries variables the pack never sets: " + ", ".join(stray[:8])
    return None


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


def start_core(ctx: OpContext, hc_bin: str) -> None:
    """``hc server start`` under the allowlist, then wait for the core's hello."""
    ensure_dirs(ctx.paths)
    write_hc_config(ctx.paths)
    budget = ctx.request.deadline.budget(CORE_START_WAIT_S)
    if budget <= 0:
        raise OpError("no time left to start the city's core")
    done = run_bounded(
        [hc_bin, "server", "start"],
        env=core_env(ctx, hc_bin),
        cwd=ctx.paths.state_root,
        timeout_s=budget,
        cancel=ctx.request.cancel,
    )
    if not done.ok:
        detail = done.output.splitlines()[-1] if done.output else "no output"
        state = "timed out" if done.returncode is None else f"exited {done.returncode}"
        raise OpError(f"cannot start the city's core: hc server start {state}: {detail}")
    end = time.monotonic() + ctx.request.deadline.budget(CORE_START_WAIT_S)
    while True:
        try:
            ctx.client().hello()
            return
        except HcUnreachable:
            if time.monotonic() >= end:
                raise OpError("the city's core did not answer after hc server start") from None
            ctx.request.cancel.pause(0.05)


# --- parking ---------------------------------------------------------------------------


def parked(ctx: OpContext) -> bool:
    """Whether ``server-stop`` stopped the city's core and no start has come
    since. An unreadable mark reads as not parked: reads kick, as before.
    It creates no state (doctor reads it too), as :func:`read_kick` does."""
    try:
        return read_private_file(os.path.join(ctx.pack_state, PARK_FILE)) is not None
    except StateDirError:
        return False


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


def check_foreign(ctx: OpContext, hc_bin: str) -> None:
    """Refuse the running core unless the pack started it with its allowlist."""
    status = ctx.client().server_status()
    try:
        actual = ctx.host.procs.environ(status.pid)
    except ProcError as err:
        raise OpError(f"cannot read the city core's environment ({err}); {FOREIGN_FIX}") from None
    if actual is None:
        raise OpError(f"cannot read the city core's environment (pid {status.pid}); {FOREIGN_FIX}")
    reason = foreign_reason(actual, core_env(ctx, hc_bin))
    if reason is not None:
        raise OpError(f"{FOREIGN_FIX} ({reason})")


def ensure_core(ctx: OpContext) -> str:
    """The city's core, started if down and checked as the pack's own.
    Returns the hc binary. It clears the stopped mark first, whatever then
    becomes of the start: a start is the way out of a parked city."""
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
    return hc_bin


# --- kick ------------------------------------------------------------------------------


@dataclass(frozen=True)
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
    """Whether a kick may start the core: never while it is parked and
    nothing of it runs, nor within the backoff after a failed one. A parked
    city whose holder or core still runs is kicked: gc reads unknown while
    it runs and never sends the start that unparks, so the core comes back
    to adopt what runs (``server-stop`` holds the kick lock, so none starts
    while it sweeps)."""
    if parked(ctx) and nothing_runs(ctx):
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
