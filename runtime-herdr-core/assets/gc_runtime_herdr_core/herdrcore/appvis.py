"""Opt-in labels that put a city's sessions on the Herdr app's screens.

The Herdr app shows a terminal only when it is labelled ``herdr.space=<id>``
(and ``herdr.tab=<id>``); it adopts unknown ids by creating the space or
tab. With ``"app_visibility": "labels"`` in the city's pack config
(``<pack state>/config.json``) the pack writes, with every session's
terminal:

* ``herdr.space`` = ``gc-<city label>``, or ``gc-<city label>-<rig>`` for a
  session of a rig (the session's ``GC_RIG``), so each rig is one space;
* ``herdr.tab`` = the session's hc terminal name (unique and stable per
  city and gc name).

It is **off by default**: the app sets ``keep=true`` on every terminal it
adopts, and keeps a shell after the program exits. The pack reads a kept
terminal's replacement shell as the session's death (gc restarts the
session), so turning it on is safe, but it changes what a person sees when
an agent exits. Only ``gc.*`` labels are ever read back; the app's own
(``herdr.seen``, ``herdr.pinned``) are ignored.
"""

from __future__ import annotations

import re
from typing import Dict, Final, Mapping

from .config import AppVisibility
from .naming import city_label, terminal_name

LABEL_SPACE: Final = "herdr.space"
LABEL_TAB: Final = "herdr.tab"
SPACE_PREFIX: Final = "gc-"
RIG_ENV: Final = "GC_RIG"
RIG_CHARS: Final = 32

_NOT_ID: Final = re.compile(r"[^a-z0-9]+")


def rig_slug(rig: str) -> str:
    """``rig`` as an id part: lowercase letters and digits, runs of anything
    else as one ``-``, at most :data:`RIG_CHARS` characters."""
    return _NOT_ID.sub("-", rig.lower()).strip("-")[:RIG_CHARS].strip("-")


def space_id(city_id: str, rig: str = "") -> str:
    """The app space of the city, or of one of its rigs."""
    base = SPACE_PREFIX + city_label(city_id)
    slug = rig_slug(rig)
    return f"{base}-{slug}" if slug else base


def app_labels(visibility: AppVisibility, city_id: str, gc_name: str, session_env: Mapping[str, str]) -> Dict[str, str]:
    """The labels that show the session in the app; none unless opted in."""
    if visibility != "labels":
        return {}
    return {
        LABEL_SPACE: space_id(city_id, session_env.get(RIG_ENV, "")),
        LABEL_TAB: terminal_name(city_id, gc_name),
    }
