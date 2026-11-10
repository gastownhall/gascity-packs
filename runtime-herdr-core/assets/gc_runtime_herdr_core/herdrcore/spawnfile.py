"""Spawn files: how a session's environment reaches its agent without
touching persistent disk.

gc's session environment carries provider credentials and identity tokens
(exec-session-provider.md "Session environment"). hc persists every
``terminal.run`` environment in plaintext in ``terminals.json`` for a day
after the terminal ends, so the pack never passes it there. ``start`` writes
it, with the command and work directory, to a spawn file the launcher opens,
unlinks, then reads, before it execs the agent:

* the directory is ``/run/user/<uid>/gc-herdr-core/<city id>/`` when the
  user's runtime directory exists, else
  ``/dev/shm/gc-herdr-core-<uid>/<city id>/`` (both tmpfs), else (macOS) a
  directory under the per-user temporary directory, which is on disk; every
  level the pack creates is 0700, the user's, and never a symlink;
* the file is ``<gc.obj>.json``, created ``O_CREAT|O_EXCL|O_NOFOLLOW`` with
  mode 0600;
* ``start`` removes it on any failure or cancel, and every op removes spawn
  files older than two minutes from its city's directory, so one left by a
  killed ``start`` lives at most one op cycle.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, Final, Mapping, Optional

from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError, ensure_private_dir
from .naming import is_object_nonce

MAX_AGE_S: Final = 120.0
SUFFIX: Final = ".json"
ROOT_ENV: Final = "GC_HC_TEST_SPAWN_ROOT"
"""Test-only: the directory spawn files go under (``GC_HC_TEST=1`` only)."""


@dataclass(frozen=True)
class Scope:
    """Run the agent in its own transient systemd scope under ``slice``,
    reaching the user manager through ``runtime_dir`` and ``bus`` (what the
    probe that admitted the scope used)."""

    systemd_run: str
    slice: str
    runtime_dir: str
    bus: str


@dataclass(frozen=True)
class SpawnSpec:
    """What the launcher needs: the session environment, command and work dir."""

    env: Mapping[str, str]
    command: str
    work_dir: str
    shim_dir: str
    scope: Optional[Scope]

    def encode(self) -> bytes:
        doc: Dict[str, object] = {
            "env": dict(self.env),
            "command": self.command,
            "work_dir": self.work_dir,
            "shim_dir": self.shim_dir,
            "scope": None
            if self.scope is None
            else {
                "systemd_run": self.scope.systemd_run,
                "slice": self.scope.slice,
                "runtime_dir": self.scope.runtime_dir,
                "bus": self.scope.bus,
            },
        }
        return dumps(doc).encode("ascii")


def decode(data: bytes) -> SpawnSpec:
    try:
        doc = JsonObject.of(loads(data))
        scope_doc = doc.opt_obj("scope")
        return SpawnSpec(
            env=doc.str_map("env"),
            command=doc.str_or("command", ""),
            work_dir=doc.str_or("work_dir", ""),
            shim_dir=doc.req_str("shim_dir"),
            scope=None
            if scope_doc is None
            else Scope(
                systemd_run=scope_doc.req_str("systemd_run"),
                slice=scope_doc.req_str("slice"),
                runtime_dir=scope_doc.req_str("runtime_dir"),
                bus=scope_doc.str_or("bus", ""),
            ),
        )
    except JsonShapeError as err:
        raise ValueError(f"malformed spawn file: {err}") from None


def directory(
    city_id: str,
    *,
    override: Optional[str] = None,
    uid: Optional[int] = None,
    run_user: Optional[str] = None,
    shm: str = "/dev/shm",
) -> str:
    """Where this city's spawn files go, created private on demand."""
    owner = os.getuid() if uid is None else uid
    if override:
        base = override
        ensure_private_dir(base)
    else:
        runtime_dir = run_user if run_user is not None else f"/run/user/{owner}"
        if os.path.isdir(runtime_dir):
            base = os.path.join(runtime_dir, "gc-herdr-core")
        elif os.path.isdir(shm):
            base = os.path.join(shm, f"gc-herdr-core-{owner}")
        else:
            temp = _darwin_user_temp()
            if temp is None:
                raise StateDirError("no tmpfs for spawn files: neither /run/user/<uid> nor /dev/shm exists")
            base = os.path.join(temp, "gc-herdr-core")
        ensure_private_dir(base)
    city_dir = os.path.join(base, city_id)
    ensure_private_dir(city_dir)
    return city_dir


def _darwin_user_temp(platform: str = sys.platform) -> Optional[str]:
    if platform != "darwin":
        return None
    try:
        value = os.confstr("CS_DARWIN_USER_TEMP_DIR")
    except (ValueError, OSError):
        return None
    return value or None


def create(city_dir: str, obj: str, spec: SpawnSpec) -> str:
    """Write ``spec`` to a new private spawn file; returns its path."""
    if not is_object_nonce(obj):
        raise StateDirError("not an incarnation nonce")
    path = os.path.join(city_dir, obj + SUFFIX)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(spec.encode())
        while view:
            view = view[os.write(fd, view) :]
    except BaseException:
        os.close(fd)
        remove(path)
        raise
    os.close(fd)
    return path


def remove(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def sweep(city_dir: str, *, now: Optional[float] = None, max_age_s: float = MAX_AGE_S) -> int:
    """Remove spawn files older than ``max_age_s``; returns how many."""
    current = time.time() if now is None else now
    removed = 0
    try:
        entries = os.listdir(city_dir)
    except FileNotFoundError:
        return 0
    for entry in entries:
        if not entry.endswith(SUFFIX):
            continue
        path = os.path.join(city_dir, entry)
        try:
            if current - os.lstat(path).st_mtime > max_age_s:
                os.unlink(path)
                removed += 1
        except FileNotFoundError:
            continue
    return removed
