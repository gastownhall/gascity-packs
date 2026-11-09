"""Per-incarnation metadata: ``<pack state>/meta/<gc.obj>.json``.

``start`` writes the file, mode 0600, **before** it creates the terminal,
seeded with the session's identity (``GC_SESSION_ID``, ``GC_RUNTIME_EPOCH``,
``GC_INSTANCE_TOKEN``, ``GT_PROCESS_NAMES``), so identity is readable from
the first ``observe`` that sees the box (observe.v1 rule 5). ``set-meta``,
``get-meta`` and ``remove-meta`` read and write the same values, so
``get-meta`` of an identity key and ``observe``'s identity always agree
(rule 4). The file also keeps what the pack needs about the incarnation and
never puts on the wire: the base name of the session's gc binary (a process
name alias) and its work directory.

Writes are whole-file replacements (temp file, then rename) under the
name's exclusive lock; ``stop`` deletes the file.
"""

from __future__ import annotations

import errno
import os
from dataclasses import dataclass, field, replace
from typing import Dict, Final, List, Mapping, Optional

from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError
from ..rpp.wire import IDENTITY_KEYS
from .config import read_private_file, write_private_file
from .naming import is_object_nonce

META_SUFFIX: Final = ".json"


class MetaError(Exception):
    """A metadata file exists but cannot be read."""


@dataclass(frozen=True)
class Meta:
    session: str
    values: Mapping[str, str] = field(default_factory=dict)
    gc_bin: str = ""
    work_dir: str = ""

    def identity(self) -> Dict[str, str]:
        """The identity keys the incarnation has a value for."""
        return {key: self.values[key] for key in IDENTITY_KEYS if key in self.values}

    def process_names(self) -> List[str]:
        raw = self.values.get("GT_PROCESS_NAMES", "")
        return [part.strip() for part in raw.split(",") if part.strip()]

    def with_value(self, key: str, value: Optional[str]) -> Meta:
        values = dict(self.values)
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
        return replace(self, values=values)

    def encode(self) -> bytes:
        doc = {"session": self.session, "values": dict(self.values), "gc_bin": self.gc_bin, "work_dir": self.work_dir}
        return (dumps(doc) + "\n").encode("ascii")


def seed(session: str, env: Mapping[str, str], *, work_dir: str) -> Meta:
    """A new incarnation's metadata, from its start environment."""
    values = {key: env[key] for key in IDENTITY_KEYS if env.get(key, "")}
    return Meta(session=session, values=values, gc_bin=env.get("GC_BIN", ""), work_dir=work_dir)


class MetaStore:
    """The metadata files of one city."""

    def __init__(self, directory: str) -> None:
        self.directory = directory

    def path(self, obj: str) -> str:
        if not is_object_nonce(obj):
            raise MetaError("not an incarnation nonce")
        return os.path.join(self.directory, obj + META_SUFFIX)

    def read(self, obj: str) -> Optional[Meta]:
        """The incarnation's metadata; None when it has no file."""
        try:
            data = read_private_file(self.path(obj))
        except StateDirError as err:
            raise MetaError(str(err)) from None
        if data is None:
            return None
        try:
            doc = JsonObject.of(loads(data))
            return Meta(
                session=doc.req_str("session"),
                values=doc.str_map("values"),
                gc_bin=doc.str_or("gc_bin", ""),
                work_dir=doc.str_or("work_dir", ""),
            )
        except JsonShapeError as err:
            raise MetaError(f"metadata file for {obj}: {err}") from None

    def write(self, obj: str, meta: Meta) -> None:
        write_private_file(self.path(obj), meta.encode())

    def remove(self, obj: str) -> None:
        try:
            os.unlink(self.path(obj))
        except FileNotFoundError:
            pass

    def objects(self) -> Dict[str, float]:
        """Every incarnation with a file, and the file's modification time."""
        out: Dict[str, float] = {}
        try:
            entries = os.listdir(self.directory)
        except OSError as err:
            if err.errno == errno.ENOENT:
                return out
            raise
        for entry in entries:
            obj = entry[: -len(META_SUFFIX)] if entry.endswith(META_SUFFIX) else ""
            if is_object_nonce(obj):
                try:
                    out[obj] = os.lstat(os.path.join(self.directory, entry)).st_mtime
                except FileNotFoundError:
                    continue
        return out
