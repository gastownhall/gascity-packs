"""The agent launcher: the program ``start`` asks hc to run.

    <python> -I -S gc-herdr-core-launch <spawn file>

It opens the spawn file without following links, unlinks it, then reads it
from the open descriptor, so the session's secrets are gone from the
filesystem before anything parses them. It then builds the agent's
environment (:mod:`.envplan`) and execs the agent, so the pid hc reports
stays the agent's. A launcher that cannot start the agent says why on the
terminal's screen and exits 127; the box then reads dead with that screen.
"""

from __future__ import annotations

import os
import pwd
import stat
import sys
from typing import Mapping, Sequence, TextIO

from .envplan import agent_env, launch_argv, scoped_env, unusable
from .spawnfile import SpawnSpec, decode

EXIT_CANNOT_LAUNCH = 127
_MAX_SPAWN_BYTES = 8 << 20


def read_spawn_file(path: str) -> SpawnSpec:
    """Open, unlink, then read and parse the spawn file at ``path``."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.unlink(path)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
            raise ValueError("the spawn file is not a private regular file of this user")
        chunks = []
        size = 0
        while True:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            size += len(chunk)
            if size > _MAX_SPAWN_BYTES:
                raise ValueError("the spawn file is too large")
            chunks.append(chunk)
    finally:
        os.close(fd)
    return decode(b"".join(chunks))


def _login_shell() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_shell or "/bin/sh"
    except KeyError:
        return "/bin/sh"


def main(argv: Sequence[str], environ: Mapping[str, str], *, stderr: TextIO = sys.stderr) -> int:
    """Exec the agent the spawn file describes; returns only on failure."""
    if len(argv) != 2:
        stderr.write("usage: gc-herdr-core-launch <spawn file>\n")
        return EXIT_CANNOT_LAUNCH
    try:
        spec = read_spawn_file(argv[1])
    except (OSError, ValueError) as err:
        stderr.write(f"gc-herdr-core-launch: cannot read the session's spawn file: {err}\n")
        return EXIT_CANNOT_LAUNCH
    env = agent_env(environ, spec.env, spec.shim_dir)
    scope = spec.scope
    if scope is not None:
        why = unusable(scope)
        if why is not None:
            stderr.write(f"gc-herdr-core-launch: the agent is not re-scoped out of the holder's cgroup: {why}\n")
            scope = None
    args = launch_argv(spec.command, scope, _login_shell())
    exec_env = env if scope is None else scoped_env(env, scope)
    try:
        if spec.work_dir:
            os.chdir(spec.work_dir)
        stderr.flush()
        os.execve(args[0], args, exec_env)
    except OSError as err:
        stderr.write(f"gc-herdr-core-launch: cannot start the agent: {err}\n")
    return EXIT_CANNOT_LAUNCH
