"""The agent's environment and argv, as the launcher builds them in the
terminal hc started it in.

hc gives a program the core's environment (the pack's allowlist), its own
variables, and ``HC_SCOPE``: the token hc's holder-loss sweep kills every
carrier of, with all its descendants. So at the agent's root the launcher:

1. removes ``HC_SCOPE``, ``HC_SOCKET`` and ``HC_SESSION`` (in-agent ``hc`` gets
   the core's exact tuple from the pack's shim instead), and the core's own
   state and config directories unless the session sets them (gc's session
   environment does: the agent sees gc's values). The user's runtime
   directory and session bus stay, as a tmux pane has them: keyrings,
   ``systemctl --user`` and rootless containers need them;
2. applies the session environment: a value sets, ``""`` unsets
   (exec-session-provider.md "Session environment"). ``start`` adds gc's
   own ``HOME`` to it when the session does not set one
   (:func:`with_gc_home`): under ``fs.host`` gc reads the agent's
   transcripts below its own home, while the core runs with the
   password-database one;
3. puts the pack's ``hc`` shim first on ``PATH``, and keeps
   ``HC_TERMINAL_ID`` and ``HC_TERMINAL_SOCKET`` for in-agent ``hc`` use.

When ``start``'s probe admitted it, the agent then runs in its own transient
scope under ``GC_AGENT_SLICE`` (``systemd-run --user --scope`` moves the
calling process and execs, so the pid hc reports is unchanged): out of the
holder's cgroup, which an OOM kill or ``systemctl kill`` of the holder takes
down whole. ``systemd-run`` reaches the manager through the runtime
directory and bus the probe used, and gets a generic description so the
agent's command line stays out of the journal. A scope the launcher cannot
run (no ``systemd-run``, no runtime directory) falls back to an unwrapped
launch: the agent is never lost to its cgroup escape.
"""

from __future__ import annotations

import os
from typing import Dict, Final, List, Mapping, Optional, Sequence, Tuple

from .spawnfile import Scope

STRIPPED: Final = ("HC_SCOPE", "HC_SOCKET", "HC_SESSION")
CORE_STATE: Final = ("XDG_STATE_HOME", "XDG_CONFIG_HOME")
DEFAULT_PATH: Final = "/usr/local/bin:/usr/bin:/bin"
SHELL: Final = "/bin/sh"
SCOPE_DESCRIPTION: Final = "gascity agent"


HOME_KEY: Final = "HOME"


def with_gc_home(session: Mapping[str, str], op_env: Mapping[str, str]) -> Dict[str, str]:
    """The session environment the spawn file carries: ``session``, with gc's
    ``HOME`` (from the op's environment) unless the session sets or unsets it."""
    out = dict(session)
    home = op_env.get(HOME_KEY, "")
    if HOME_KEY not in out and home:
        out[HOME_KEY] = home
    return out


def agent_env(base: Mapping[str, str], session: Mapping[str, str], shim_dir: str) -> Dict[str, str]:
    """The agent's environment from the launcher's own (``base``) and the session's."""
    env = {k: v for k, v in base.items() if k not in STRIPPED}
    for key in CORE_STATE:
        if key not in session:
            env.pop(key, None)
    for key, value in session.items():
        if value == "":
            env.pop(key, None)
        else:
            env[key] = value
    for key in STRIPPED:
        env.pop(key, None)
    path = [part for part in env.get("PATH", DEFAULT_PATH).split(":") if part and part != shim_dir]
    env["PATH"] = ":".join([shim_dir] + path)
    return env


def scope_prefix(scope: Scope) -> Tuple[str, ...]:
    """``systemd-run`` up to its ``--``: the probe runs ``/bin/true`` after it,
    the launcher the agent."""
    return (
        scope.systemd_run,
        "--user",
        "--scope",
        f"--slice={scope.slice}",
        "--collect",
        "--quiet",
        f"--description={SCOPE_DESCRIPTION}",
        "--",
    )


def scope_env(scope: Scope) -> Dict[str, str]:
    """What ``systemd-run`` needs to reach the user manager."""
    env = {"XDG_RUNTIME_DIR": scope.runtime_dir}
    if scope.bus:
        env["DBUS_SESSION_BUS_ADDRESS"] = scope.bus
    return env


def scoped_env(env: Mapping[str, str], scope: Scope) -> Dict[str, str]:
    """``env`` with the manager ``scope`` was probed against."""
    out = dict(env)
    out.update(scope_env(scope))
    return out


def unusable(scope: Scope) -> Optional[str]:
    """Why the launcher cannot run ``scope`` here, or None."""
    if not os.access(scope.systemd_run, os.X_OK):
        return f"{scope.systemd_run} is not executable"
    if not os.path.isdir(scope.runtime_dir):
        return f"the runtime directory {scope.runtime_dir} is gone"
    return None


def launch_argv(command: str, scope: Optional[Scope], login_shell: str) -> List[str]:
    """The argv the launcher execs (its first element is an absolute path)."""
    inner: Sequence[str] = [SHELL, "-c", command] if command else [login_shell or SHELL]
    if scope is None:
        return list(inner)
    return [*scope_prefix(scope), *inner]
