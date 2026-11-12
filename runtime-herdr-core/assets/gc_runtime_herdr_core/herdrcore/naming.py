"""hc names and labels for gc sessions.

A gc session name is free text; an hc terminal name is 1-32 characters of
``[a-z0-9-_.]``, unique among live terminals, and never id-shaped like ``t7``
(hc ``crates/herdr-core/src/addr.rs``). The terminal name is therefore a
digest: ``g`` plus 20 base32 characters of ``sha256(city id, gc name)``.
``terminal.run`` is not idempotent, and a live name refusing a second run
(``name_taken``) is the only dedupe hc offers, so the digest is also the
start's dedupe key.

Labels carry what the pack needs to read a record back: the city, the exact
gc name, the incarnation (``gc.obj``, a fresh nonce per start, which also keys
the pack's metadata file) and the program's pid once ``run`` returned. A
record whose processes may survive its kill may also carry when starts
began to be refused over them, when its metadata cannot record it.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from typing import Dict, Final

LABEL_CITY: Final = "gc.city"
LABEL_SESSION: Final = "gc.session"
LABEL_OBJ: Final = "gc.obj"
LABEL_PID: Final = "gc.pid"
LABEL_REFUSED: Final = "gc.refused_since_ms"

CITY_LABEL_CHARS: Final = 12
TERMINAL_NAME_CHARS: Final = 20


def terminal_name(city_id: str, gc_name: str) -> str:
    """The hc terminal name of gc session ``gc_name`` in city ``city_id``."""
    digest = hashlib.sha256(os.fsencode(city_id) + b"\0" + os.fsencode(gc_name)).digest()
    return "g" + base64.b32encode(digest).decode("ascii").lower()[:TERMINAL_NAME_CHARS]


def city_label(city_id: str) -> str:
    """The ``gc.city`` label value of every terminal the city's sessions run in."""
    return city_id[:CITY_LABEL_CHARS]


def new_object_nonce() -> str:
    """A fresh incarnation nonce (``gc.obj``)."""
    return uuid.uuid4().hex


def session_labels(city_id: str, gc_name: str, obj: str) -> Dict[str, str]:
    """The labels ``terminal.run`` writes with the terminal."""
    return {LABEL_CITY: city_label(city_id), LABEL_SESSION: gc_name, LABEL_OBJ: obj}


def is_object_nonce(text: str) -> bool:
    """Whether ``text`` has the shape of a ``gc.obj`` nonce (it names a file)."""
    return len(text) == 32 and all(ch in "0123456789abcdef" for ch in text)
