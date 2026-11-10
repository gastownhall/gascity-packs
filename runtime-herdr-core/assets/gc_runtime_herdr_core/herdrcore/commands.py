"""The pack's commands: ``gc herdr-core install|status|upgrade|restart-core``
(``gc-runtime-herdr-core x-command <name> [args]``).

* ``install`` puts the pinned herdr-core build in place (:mod:`.install`).
* ``status`` reports the pin, what is installed and what the city's core
  runs; ``status --env`` prints the core's discovery tuple, for
  ``env $(gc herdr-core status --env) herdr-app``.
* ``upgrade`` installs the pinned build, then hands the city's core over to
  it with ``hc server restart`` under the pack's allowlist environment:
  hc keeps every program and its screen across a planned restart, so the
  city's sessions keep running. A core started outside the pack is refused
  (a planned restart would carry its environment over): ``restart-core``
  is its fix.
* ``restart-core`` stops the city's own core and starts a fresh one under
  the allowlist. Stopping a core ends every program on it, so it refuses
  while any terminal runs there (``gc stop`` the city first). It refuses a
  core that is not the city's (another user's, or one with another hc
  session or state root): the pack never stops a core it cannot tell is
  its own.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, Final, Mapping, Sequence, TextIO

from ..hc.client import HcClient
from ..hc.errors import HcError, HcUnreachable
from ..hc.version import Version
from ..rpp.cancel import CancelToken
from ..rpp.flock import LockTimeout
from ..rpp.ops import OpError
from ..rpp.redact import Redactor
from ..rpp.statedir import StateDirError
from .admin import (
    admin_context,
    admin_host,
    city_terminals,
    client_for,
    core_reachable,
    live_terminals,
    lock_socket,
    ownership,
)
from .command import run_bounded
from .config import ConfigError, install_root, pinned_binary, read_pack_config
from .context import Host, OpContext
from .core import CORE_START_WAIT_S, check_foreign, core_env, foreign_reason, start_core
from .install import InstallError, fetch_for, install, verify_installed
from .pin import HcPin, PinError, host_target, load_pin
from .procs import ProcError

COMMAND_DEADLINE_S: Final = 300.0
STOP_WAIT_S: Final = 10.0


class CommandError(Exception):
    """A command refused or failed; its message says why and what to do."""


Out = Callable[[str], None]


def _pin() -> HcPin:
    try:
        return load_pin()
    except PinError as err:
        raise CommandError(str(err)) from None


def _install(ctx: OpContext, pin: HcPin, out: Out) -> str:
    try:
        target = host_target()
        outcome = install(
            pin,
            root=install_root(ctx.host.home),
            target=target,
            fetch=fetch_for(pin, ctx.env, test=ctx.test),
            procs=ctx.host.procs,
            cancel=ctx.request.cancel,
            now_ms=ctx.host.now_ms,
        )
    except (InstallError, PinError, StateDirError, OSError) as err:
        raise CommandError(f"install failed: {err}") from None
    if outcome.installed:
        out(f"installed herdr-core {outcome.version} ({target}) at {outcome.binary}")
    else:
        out(f"herdr-core {outcome.version} is already installed at {outcome.binary}")
    if outcome.removed:
        out(f"removed older versions: {', '.join(outcome.removed)}")
    if outcome.gc_note:
        out(outcome.gc_note)
    return outcome.binary


def cmd_install(ctx: OpContext, args: Sequence[str], out: Out) -> None:
    if args:
        raise CommandError("usage: gc herdr-core install (installs the pinned version)")
    _install(ctx, _pin(), out)


def cmd_status(ctx: OpContext, args: Sequence[str], out: Out) -> None:
    if args == ["--env"]:
        for key, value in sorted(ctx.paths.discovery_env().items()):
            out(f"{key}={value}")
        return
    if args:
        raise CommandError("usage: gc herdr-core status [--env]")
    pin = _pin()
    tested = ", ".join(str(v) for v in pin.tested)
    out(f"pin:       herdr-core {pin.version} (min {pin.min_version}; tested {tested})")
    try:
        config = read_pack_config(ctx.pack_state)
    except ConfigError as err:
        raise CommandError(str(err)) from None
    if config.hc_bin:
        allowed = "allowed" if config.allow_unpinned else "NOT allowed: set allow_unpinned or remove it"
        out(f"installed: hc_bin {config.hc_bin} (unpinned, {allowed})")
    else:
        try:
            problem = verify_installed(pin, install_root(ctx.host.home), host_target())
        except PinError as err:
            problem = str(err)
        binary = pinned_binary(ctx.host.home, str(pin.version))
        out(f"installed: {problem}" if problem else f"installed: {binary} (matches the pin)")
    out(f"core:      session {ctx.paths.session}, socket {ctx.paths.socket}")
    client = client_for(ctx, ctx.paths.socket, any_version=True)
    try:
        hello = client.hello()
    except HcUnreachable:
        out("running:   no core")
        return
    except HcError as err:
        out(f"running:   a core that cannot be driven: {err}")
        return
    status = client.server_status()
    note = "" if hello.version == str(pin.version) else " (differs from the pin: run `gc herdr-core upgrade`)"
    try:
        if Version.parse(hello.version) < pin.min_version:
            note = f" (older than the minimum {pin.min_version}: the pack will not drive it; run `gc herdr-core upgrade`)"
    except ValueError:
        note = " (an unreadable version)"
    out(f"running:   herdr-core {hello.version}, pid {status.pid}, {status.live} live terminal(s){note}")
    try:
        env = ctx.host.procs.environ(status.pid)
    except ProcError:
        env = None
    if env is None:
        out("started:   cannot tell (its environment cannot be read)")
    else:
        hc_bin = _driving_binary(ctx, pin)
        reason = foreign_reason(env, core_env(ctx, hc_bin))
        out("started:   by the pack" if reason is None else f"started:   outside the pack ({reason}): run `gc herdr-core restart-core`")


def _driving_binary(ctx: OpContext, pin: HcPin) -> str:
    try:
        return ctx.hc_binary()
    except ConfigError:
        return pinned_binary(ctx.host.home, str(pin.version))


def _wait_gone(client: HcClient, cancel: CancelToken) -> None:
    end = time.monotonic() + STOP_WAIT_S
    while core_reachable(client):
        if time.monotonic() >= end:
            raise CommandError("the core still answers after server.stop")
        cancel.pause(0.05)


def cmd_restart_core(ctx: OpContext, args: Sequence[str], out: Out) -> None:
    if args:
        raise CommandError("usage: gc herdr-core restart-core")
    try:
        hc_bin = ctx.hc_binary()
    except ConfigError as err:
        raise CommandError(str(err)) from None
    target = ctx.paths.socket
    client = client_for(ctx, target, any_version=True)
    if not core_reachable(client):
        other = lock_socket(ctx)
        if other is not None:
            target = other
            client = client_for(ctx, other, any_version=True)
    if core_reachable(client):
        status = client.server_status()
        owner = ownership(ctx, status)
        if not owner.own:
            raise CommandError(
                f"refusing to stop the core at {target}: it is not this city's core ({owner.reason}); "
                "stop it yourself if it should not be there"
            )
        live = live_terminals(client)
        if live:
            mine = len(city_terminals(ctx, live))
            raise CommandError(
                f"{len(live)} terminal(s) run on the city's core ({mine} of them the city's sessions): "
                "stopping it would end them; stop the city first (`gc stop`), then run this again"
            )
        client.server_stop()
        _wait_gone(client, ctx.request.cancel)
        out(f"stopped the city's core (pid {status.pid})")
    try:
        start_core(ctx, hc_bin)
        check_foreign(ctx, hc_bin)
    except OpError as err:
        raise CommandError(err.message) from None
    out(f"started the city's core with {hc_bin} at {ctx.paths.socket}")


def cmd_upgrade(ctx: OpContext, args: Sequence[str], out: Out) -> None:
    if args:
        raise CommandError("usage: gc herdr-core upgrade (installs the pinned version and hands the core over)")
    pin = _pin()
    _install(ctx, pin, out)
    try:
        hc_bin = ctx.hc_binary()
    except ConfigError as err:
        raise CommandError(str(err)) from None
    client = client_for(ctx, ctx.paths.socket, any_version=True)
    try:
        hello = client.hello()
    except HcUnreachable:
        out("no core runs: the next session start uses the pinned build")
        return
    except HcError as err:
        raise CommandError(f"the city's core cannot be driven: {err}") from None
    if hello.version == str(pin.version):
        out(f"the city's core already runs herdr-core {pin.version}")
        return
    status = client.server_status()
    owner = ownership(ctx, status)
    if not owner.own:
        raise CommandError(f"refusing to restart the core at {ctx.paths.socket}: it is not this city's core ({owner.reason})")
    try:
        env = ctx.host.procs.environ(status.pid)
    except ProcError as err:
        raise CommandError(f"cannot read the core's environment ({err}): run `gc herdr-core restart-core`") from None
    expected = core_env(ctx, hc_bin)
    reason = None if env is None else foreign_reason(env, expected)
    if env is None or reason is not None:
        raise CommandError(
            f"the city's core was started outside the pack ({reason or 'its environment cannot be read'}); a planned "
            "restart would keep that environment: run `gc herdr-core restart-core` instead"
        )
    done = run_bounded(
        [hc_bin, "server", "restart"],
        env=expected,
        cwd=ctx.paths.state_root,
        timeout_s=ctx.request.deadline.budget(CORE_START_WAIT_S + STOP_WAIT_S),
        cancel=ctx.request.cancel,
    )
    if not done.ok:
        detail = done.output.splitlines()[-1] if done.output else "no output"
        raise CommandError(f"hc server restart failed ({detail}); herdr-core {hello.version} stays installed to roll back to")
    end = time.monotonic() + CORE_START_WAIT_S
    while True:
        try:
            now = ctx.client().hello()
            if now.version == str(pin.version):
                break
        except HcError:
            pass
        if time.monotonic() >= end:
            raise CommandError(f"the city's core does not run herdr-core {pin.version} after the restart")
        ctx.request.cancel.pause(0.1)
    out(f"handed the city's core over from herdr-core {hello.version} to {pin.version}; its sessions kept running")


COMMANDS: Final[Dict[str, Callable[[OpContext, Sequence[str], Out], None]]] = {
    "install": cmd_install,
    "status": cmd_status,
    "upgrade": cmd_upgrade,
    "restart-core": cmd_restart_core,
}


def run_command(name: str, args: Sequence[str], env: Mapping[str, str], host: Host, out: Out, err: Out) -> int:
    """Run command ``name``; exit 0 on success, 1 when it refused or failed, 2 on usage."""
    command = COMMANDS.get(name)
    if command is None:
        err(f"unknown command {name!r} (known: {', '.join(sorted(COMMANDS))})")
        return 2
    try:
        ctx = admin_context(env, host, name=name, deadline_s=COMMAND_DEADLINE_S, cancel=CancelToken())
        command(ctx, list(args), out)
    except CommandError as failure:
        err(f"gc herdr-core {name}: {ctx_redact(env, str(failure))}")
        return 1
    except (ConfigError, StateDirError, HcError, OpError, ProcError, LockTimeout, OSError) as failure:
        err(f"gc herdr-core {name}: {ctx_redact(env, str(failure))}")
        return 1
    return 0


def ctx_redact(env: Mapping[str, str], text: str) -> str:
    """``text`` with the sensitive values of the command's environment redacted."""
    redactor = Redactor()
    redactor.add_process_env(env)
    return redactor.redact(text)


def main(argv: Sequence[str], env: Mapping[str, str], python: str, stdout: TextIO, stderr: TextIO) -> int:
    """``x-command <name> [args]``."""
    if not argv:
        stderr.write(f"usage: x-command <{'|'.join(sorted(COMMANDS))}> [args]\n")
        return 2

    def out(line: str) -> None:
        stdout.write(line + "\n")
        stdout.flush()

    def err(line: str) -> None:
        stderr.write(line + "\n")
        stderr.flush()

    return run_command(argv[0], argv[1:], env, admin_host(env, python), out, err)

