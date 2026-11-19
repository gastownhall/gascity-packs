"""Provision records: ``<pack state>/provision/<terminal name>.json``.

``provision`` creates no terminal (:mod:`.unwelded`): what it leaves for
``launch`` is this small record, written under the name's exclusive lock,
mode 0600 in a 0700 directory. It holds the identity to seed the launch's
metadata with (the start env's :data:`~..rpp.wire.LAUNCH_KEYS`, nothing
else of the env: secrets reach the agent only through the spawn file
``launch`` writes) and, only when ``provision``'s config carried them, the
session steps deferred until the agent runs (``session_setup``,
``session_setup_script``) and the work dir they run in.

A record is good for :data:`TTL_MS` after it was written; an older one reads
as absent, and the next ``provision`` of any name removes it. ``launch``
consumes the record once the new incarnation's metadata is written;
``stop`` drops the name's record, even with the core down, so a stop
between ``provision`` and ``launch`` wins; ``server-stop`` drops the city's.

This module is tiny on purpose: ``stop`` and ``server-stop`` import it and
nothing of ``launch``.
"""

from __future__ import annotations

import errno
import os
from typing import TYPE_CHECKING, Dict, Final, List, Mapping, Optional, Tuple

from ..rpp.frozen import field, frozen
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError
from ..rpp.wire import LAUNCH_KEYS, StartConfig
from .config import read_private_file, write_private_file
from .naming import terminal_name

if TYPE_CHECKING:
    from .context import OpContext

SUBDIR: Final = "provision"
SUFFIX: Final = ".json"
TTL_MS: Final = 600_000
"""How long a provision record stays good: the grace inventory gives
metadata no record carries (:data:`.reads.META_GC_AGE_S`). gc launches right
after it provisions, so only a crash between the two leaves one this old."""


@frozen
class SessionSteps:
    """The session steps ``provision``'s config carried, run once the agent does."""

    session_setup: Tuple[str, ...]
    session_setup_script: str
    work_dir: str


@frozen
class Provisioned:
    """A name ``provision`` prepared and no ``launch`` has started yet."""

    session: str
    at_ms: int
    values: Mapping[str, str] = field(default_factory=dict)
    steps: Optional[SessionSteps] = None

    def encode(self) -> bytes:
        doc: Dict[str, object] = {"session": self.session, "at_ms": self.at_ms, "values": dict(self.values)}
        if self.steps is not None:
            doc["session_setup"] = list(self.steps.session_setup)
            doc["session_setup_script"] = self.steps.session_setup_script
            doc["work_dir"] = self.steps.work_dir
        return (dumps(doc) + "\n").encode("ascii")


def launch_values(env: Mapping[str, str]) -> Dict[str, str]:
    """The seed a launch's metadata takes from ``env``: its non-empty :data:`LAUNCH_KEYS`."""
    return {key: env[key] for key in LAUNCH_KEYS if env.get(key, "")}


def steps_of(cfg: StartConfig) -> Optional[SessionSteps]:
    """The session steps ``cfg`` carries; None when it carries none."""
    if not cfg.session_setup and not cfg.session_setup_script:
        return None
    return SessionSteps(session_setup=cfg.session_setup, session_setup_script=cfg.session_setup_script, work_dir=cfg.work_dir)


def of_config(name: str, cfg: StartConfig, at_ms: int) -> Provisioned:
    """The record ``provision`` writes for ``cfg``."""
    return Provisioned(session=name, at_ms=at_ms, values=launch_values(cfg.env), steps=steps_of(cfg))


def _directory(ctx: "OpContext") -> str:
    return os.path.join(ctx.pack_state, SUBDIR)


def record_path(ctx: "OpContext", name: str) -> str:
    """Where ``name``'s record lives (one file per name, by its terminal name)."""
    return os.path.join(_directory(ctx), terminal_name(ctx.paths.city_id, name) + SUFFIX)


def write(ctx: "OpContext", record: Provisioned) -> None:
    """Write ``record``, replacing the name's earlier one (call under the name's lock)."""
    ctx.state_dir(SUBDIR)
    write_private_file(record_path(ctx, record.session), record.encode())


def _parse(data: bytes, name: str) -> Provisioned:
    try:
        doc = JsonObject.of(loads(data))
        steps = None
        if doc.has("session_setup") or doc.has("session_setup_script"):
            steps = SessionSteps(
                session_setup=doc.str_tuple("session_setup"),
                session_setup_script=doc.str_or("session_setup_script", ""),
                work_dir=doc.str_or("work_dir", ""),
            )
        record = Provisioned(session=doc.req_str("session"), at_ms=doc.req_int("at_ms"), values=doc.str_map("values"), steps=steps)
    except JsonShapeError as err:
        raise StateDirError(f"the provision record of {name!r} is malformed: {err}") from None
    if record.session != name:
        raise StateDirError(f"the provision record of {name!r} names another session")
    return record


def expired(record: Provisioned, now_ms: int) -> bool:
    return now_ms - record.at_ms > TTL_MS


def read(ctx: "OpContext", name: str, now_ms: int) -> Optional[Provisioned]:
    """``name``'s record while it is good; None when there is none or it expired."""
    data = read_private_file(record_path(ctx, name))
    if data is None:
        return None
    record = _parse(data, name)
    return None if expired(record, now_ms) else record


def drop(ctx: "OpContext", name: str) -> None:
    """Remove ``name``'s record, if any."""
    _unlink(record_path(ctx, name))


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as err:
        raise StateDirError(f"cannot remove {path}: {err.strerror}") from None


def _entries(ctx: "OpContext") -> List[str]:
    try:
        names = os.listdir(_directory(ctx))
    except OSError as err:
        if err.errno in (errno.ENOENT, errno.ENOTDIR):
            return []
        raise StateDirError(f"cannot list {_directory(ctx)}: {err.strerror}") from None
    return [os.path.join(_directory(ctx), entry) for entry in names if entry.endswith(SUFFIX) and not entry.startswith(".")]


def drop_all(ctx: "OpContext") -> None:
    """Remove every record of the city (``server-stop``)."""
    for path in _entries(ctx):
        _unlink(path)


def sweep(ctx: "OpContext", now_ms: int) -> None:
    """Remove the city's expired records; one that cannot be read is left alone."""
    for path in _entries(ctx):
        try:
            data = read_private_file(path)
            if data is None:
                continue
            doc = JsonObject.of(loads(data))
            at_ms = doc.req_int("at_ms")
        except (StateDirError, JsonShapeError):
            continue
        if now_ms - at_ms > TTL_MS:
            _unlink(path)
