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
"""

from __future__ import annotations

import os
import pwd
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Dict, Final, FrozenSet, Mapping, Optional

from ..hc.errors import HcError, HcUnreachable
from ..hc.paths import ensure_dirs
from ..rpp.flock import LockTimeout
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.ops import OpError
from .command import run_bounded
from .config import ConfigError, read_private_file, write_hc_config, write_private_file
from .context import OpContext

CORE_START_WAIT_S: Final = 15.0
"""hc's own wait for a starting core (``client.rs`` START_WAIT)."""

KICK_FILE: Final = "kick.json"
KICK_BACKOFF_MS: Final = 5 * 60 * 1000
KICK_OP: Final = "x-kick-core"

BASE_PATH: Final = "/usr/local/bin:/usr/bin:/bin"

DISCOVERY_KEYS: Final = ("HC_SESSION", "HC_SOCKET", "XDG_STATE_HOME", "XDG_CONFIG_HOME")

SYSTEMD_UNIT_KEYS: Final[FrozenSet[str]] = frozenset(
    {
        "INVOCATION_ID",
        "JOURNAL_STREAM",
        "SYSTEMD_EXEC_PID",
        "MANAGERPID",
        "MEMORY_PRESSURE_WATCH",
        "MEMORY_PRESSURE_WRITE",
        "NOTIFY_SOCKET",
        "WATCHDOG_PID",
        "WATCHDOG_USEC",
    }
)
"""What systemd adds to a unit's environment, beside the user manager's own block."""

HC_RUNTIME_KEY: Final = "HC_RUNTIME"
"""hc marks its own cores and holders with ``HC_RUNTIME=1`` (sweep exemption)."""

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
    runtime_dir = run_user if run_user is not None else f"/run/user/{uid}"
    if os.path.isdir(runtime_dir):
        env["XDG_RUNTIME_DIR"] = runtime_dir
        bus = os.path.join(runtime_dir, "bus")
        if os.path.exists(bus):
            env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + bus
    return env


def allowed_core_keys(env: Mapping[str, str]) -> FrozenSet[str]:
    return frozenset(env) | {"LANG", HC_RUNTIME_KEY, "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"}


def manager_env_keys() -> Optional[FrozenSet[str]]:
    """The keys of the systemd user manager's environment block; None when unreadable."""
    try:
        done = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=1.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return frozenset(
        line.split("=", 1)[0] for line in done.stdout.decode("utf-8", "replace").splitlines() if "=" in line
    )


def foreign_reason(
    actual: Mapping[str, str],
    expected: Mapping[str, str],
    *,
    manager_keys: Callable[[], Optional[FrozenSet[str]]] = manager_env_keys,
) -> Optional[str]:
    """Why a core started with environment ``actual`` is not the pack's, or None.

    Only key names are reported, never values.
    """
    for key in DISCOVERY_KEYS:
        if actual.get(key) != expected.get(key):
            return f"its {key} differs from the pack's"
    allowed = set(allowed_core_keys(expected))
    if "INVOCATION_ID" in actual:
        allowed |= SYSTEMD_UNIT_KEYS
        extra = manager_keys()
        if extra is None:
            return "it runs as a systemd unit whose manager environment cannot be read"
        allowed |= extra
    stray = sorted(key for key in actual if key not in allowed and not key.startswith("LC_"))
    if stray:
        return "it carries variables the pack never sets: " + ", ".join(stray[:8])
    return None


def check_core_lock(ctx: OpContext) -> None:
    """Refuse a core of this session that listens on another socket (herdr-core #200)."""
    raw = read_private_file(ctx.paths.core_lock)
    if not raw:
        return
    listening = os.fsdecode(raw.strip())
    if listening == ctx.paths.socket:
        return
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(0.5)
        probe.connect(listening)
    except OSError:
        return  # a stale lock: nobody listens there
    finally:
        probe.close()
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


def check_foreign(ctx: OpContext, hc_bin: str, *, manager_keys: Callable[[], Optional[FrozenSet[str]]] = manager_env_keys) -> None:
    """Refuse the running core unless the pack started it with its allowlist."""
    status = ctx.client().server_status()
    actual = ctx.host.procs.environ(status.pid)
    if actual is None:
        raise OpError(f"cannot read the city core's environment (pid {status.pid}); {FOREIGN_FIX}")
    reason = foreign_reason(actual, core_env(ctx, hc_bin), manager_keys=manager_keys)
    if reason is not None:
        raise OpError(f"{FOREIGN_FIX} ({reason})")


def ensure_core(ctx: OpContext) -> str:
    """The city's core, started if down and checked as the pack's own.
    Returns the hc binary."""
    try:
        hc_bin = ctx.hc_binary()
    except ConfigError as err:
        raise OpError(str(err)) from None
    check_core_lock(ctx)
    try:
        ctx.client().hello()
    except HcUnreachable:
        if ctx.fault:
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
        raw = read_private_file(ctx.state_file(KICK_FILE))
        if raw is None:
            return None
        doc = JsonObject.of(loads(raw))
        return KickRecord(at_ms=doc.req_int("at_ms"), ok=doc.req_bool("ok"), detail=doc.str_or("detail", ""))
    except (JsonShapeError, OSError, ValueError):
        return None


def write_kick(ctx: OpContext, record: KickRecord) -> None:
    doc = {"at_ms": record.at_ms, "ok": record.ok, "detail": record.detail}
    write_private_file(ctx.state_file(KICK_FILE), (dumps(doc) + "\n").encode("ascii"))


def kick_due(ctx: OpContext) -> bool:
    record = read_kick(ctx)
    return record is None or record.ok or ctx.host.now_ms() - record.at_ms >= KICK_BACKOFF_MS


def kick(ctx: OpContext) -> bool:
    """Start the city's core in the background for the next pass. Returns
    whether a start was launched."""
    if ctx.fault or not kick_due(ctx):
        return False
    try:
        ctx.hc_binary()
        with ctx.lock("kick", shared=False, wait_s=0.0):
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
        with ctx.lock("kick", shared=False, wait_s=0.0):
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
