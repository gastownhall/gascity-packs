"""Where a city's core lives.

Its hc session, socket, state and config come from the uid, the
password-database home (or ``GC_EXEC_STATE_DIR``), the host name and the raw
city key, and from nothing in the caller's environment: hc itself resolves
its socket and state from ``HC_SOCKET``, ``HC_SESSION``, ``XDG_RUNTIME_DIR`` and
``XDG_STATE_HOME`` (hc ``crates/herdr-core/src/paths.rs``), which differ
between the supervisor, cron, ssh and sudo. A process that resolved another
core would read the city's sessions as absent.

The tuple a core is started with (:meth:`HcPaths.discovery_env`) is the one
every client of that core uses: two state directories on one socket let a
second core take the first one's holders over (hc #200).

Layout under the state root ``R``::

    R/herdr-core/<session>/          hc's own state (the core's XDG_STATE_HOME is R)
    R/herdr-core/<session>/<session>.sock
    R/hc-config/herdr-core/config.toml   pack-owned (the core's XDG_CONFIG_HOME)

A socket path too long for ``sun_path`` moves to
``/tmp/gc-herdr-core-<uid>/``, a 0700 directory whose owner is checked
(gc's own ``controllerSocketPath`` fallback); it never depends on
``/run/user/<uid>``, which logind may remove.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable, Dict, Final, Mapping, Optional

from ..rpp.statedir import OP_CITY_ENV, city_id, city_key, ensure_private_dir, host_name, password_home, state_root

PACK_STATE_LEAF: Final = "gc-runtime-herdr-core"
"""The default state root is ``<password home>/.local/state/<leaf>``."""

HC_STATE_SUBDIR: Final = "herdr-core"
HC_CONFIG_SUBDIR: Final = "hc-config"
SESSION_PREFIX: Final = "gc-"
SESSION_ID_CHARS: Final = 10

SUN_PATH_MAX: Final = 108 if sys.platform.startswith("linux") else 104
"""``sizeof(sockaddr_un.sun_path)``; a bindable path is shorter (it needs its NUL)."""

HOLDER_SOCKET_SUFFIX_LEN: Final = len(".holder.") + 8 + len(".sock")
"""hc binds ``<session>.holder.<8hex>.sock`` beside the main socket, the
longest name it puts there; hc refuses a session whose longest socket path
does not fit ``sun_path`` (``crates/herdr-core/src/paths.rs``)."""

TMP_SOCKET_DIR_PREFIX: Final = "gc-herdr-core-"


@dataclass(frozen=True)
class HcPaths:
    """A city's core: its session, socket, state and config locations."""

    city_key: str
    city_id: str
    session: str
    state_root: str
    state_dir: str
    socket: str
    core_lock: str
    config_home: str
    config_file: str

    def discovery_env(self) -> Dict[str, str]:
        """The variables the core is started with and its clients use to find it."""
        return {
            "HC_SESSION": self.session,
            "HC_SOCKET": self.socket,
            "XDG_STATE_HOME": self.state_root,
            "XDG_CONFIG_HOME": self.config_home,
        }


def _sockets_fit(directory: str, session: str) -> bool:
    longest = len(os.fsencode(directory)) + 1 + len(session) + HOLDER_SOCKET_SUFFIX_LEN
    return longest < SUN_PATH_MAX


def resolve_paths(
    env: Mapping[str, str],
    *,
    host: Optional[str] = None,
    home: Callable[[], str] = password_home,
    uid: Optional[int] = None,
    city_var: str = OP_CITY_ENV,
    tmp_root: str = "/tmp",
) -> HcPaths:
    """Where the city named by ``env[city_var]`` keeps its core. Writes nothing.

    ``city_var`` is ``GC_EXEC_CITY_PATH`` for ops and ``GC_CITY_PATH`` for doctor
    checks and pack commands; both carry gc's absolute city path.
    """
    key = city_key(env, city_var)
    cid = city_id(host_name() if host is None else host, key)
    session = SESSION_PREFIX + cid[:SESSION_ID_CHARS]
    root = state_root(env, leaf=PACK_STATE_LEAF, home=home)
    state_dir = os.path.join(root, HC_STATE_SUBDIR, session)
    socket_dir = state_dir
    if not _sockets_fit(state_dir, session):
        owner = os.getuid() if uid is None else uid
        socket_dir = os.path.join(tmp_root, f"{TMP_SOCKET_DIR_PREFIX}{owner}")
    config_home = os.path.join(root, HC_CONFIG_SUBDIR)
    return HcPaths(
        city_key=key,
        city_id=cid,
        session=session,
        state_root=root,
        state_dir=state_dir,
        socket=os.path.join(socket_dir, f"{session}.sock"),
        core_lock=os.path.join(state_dir, "core.lock"),
        config_home=config_home,
        config_file=os.path.join(config_home, "herdr-core", "config.toml"),
    )


def ensure_dirs(paths: HcPaths) -> None:
    """Create the core's directories, each 0700 and owned by this user."""
    for directory in (
        paths.state_root,
        os.path.dirname(paths.state_dir),
        paths.state_dir,
        paths.config_home,
        os.path.dirname(paths.config_file),
        os.path.dirname(paths.socket),
    ):
        ensure_private_dir(directory)
