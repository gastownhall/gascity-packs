"""The private state root and the city key.

exec-session-provider.md "Environment Variables": a script's state must not
depend on the caller's session environment. The supervisor, cron, ssh and
sudo differ in ``XDG_RUNTIME_DIR``, ``TMPDIR`` and even ``HOME``, and a box one
of them cannot find reads absent, so reconciler v2 starts a twin. Therefore:

* the state root ``R`` is ``GC_EXEC_STATE_DIR`` when set (an operator sets it
  alike for every gc process of the city), else a directory under the home
  from the password database, never ``$HOME``;
* the city key is the raw ``GC_EXEC_CITY_PATH`` (``GC_CITY_PATH`` for doctor
  checks and pack commands, which gc runs without the exec variables), and
  the fixed bucket :data:`UNSCOPED_CITY_KEY` when that is unset: never the
  cwd, which is whatever directory ``gc runtime check`` or ``gc runtime
  conformance`` was started from;
* the city id hashes the host name with the key, so two hosts sharing an NFS
  home never read each other's state.

``R`` and everything the pack creates under it is a 0700 directory owned by
the user, refused if it is a symlink or someone else's. Nothing here writes
under the city path or the cwd.
"""

from __future__ import annotations

import errno
import hashlib
import os
import pwd
import stat
from typing import Callable, Final, Mapping, Optional

STATE_DIR_ENV: Final = "GC_EXEC_STATE_DIR"
OP_CITY_ENV: Final = "GC_EXEC_CITY_PATH"
DOCTOR_CITY_ENV: Final = "GC_CITY_PATH"

UNSCOPED_CITY_KEY: Final = "unscoped"
"""The bucket for ops gc runs without a city (``gc runtime check``). gc only
ever sends absolute city paths, which cannot equal it."""


class StateDirError(Exception):
    """The state root or a directory under it cannot be used safely."""


def city_key(env: Mapping[str, str], var: str = OP_CITY_ENV) -> str:
    """The raw city path from ``var``, or :data:`UNSCOPED_CITY_KEY` when unset or empty."""
    raw = env.get(var, "")
    return raw if raw else UNSCOPED_CITY_KEY


def city_id(host: str, key: str) -> str:
    """sha256 of the host name and the city key, as hex."""
    return hashlib.sha256(os.fsencode(host) + b"\0" + os.fsencode(key)).hexdigest()


def host_name() -> str:
    """This host's name, as ``uname -n`` prints it."""
    return os.uname().nodename


def password_home(uid: Optional[int] = None) -> str:
    """The home directory the password database gives ``uid`` (default: this user)."""
    who = os.getuid() if uid is None else uid
    try:
        home = pwd.getpwuid(who).pw_dir
    except KeyError:
        raise StateDirError(f"uid {who} has no entry in the password database") from None
    if not os.path.isabs(home):
        raise StateDirError(f"the password database gives uid {who} no absolute home")
    return home


def state_root(env: Mapping[str, str], *, leaf: str, home: Callable[[], str] = password_home) -> str:
    """``R``: ``GC_EXEC_STATE_DIR``, else ``<password home>/.local/state/<leaf>``."""
    configured = env.get(STATE_DIR_ENV, "")
    if configured:
        if not os.path.isabs(configured):
            raise StateDirError(f"{STATE_DIR_ENV} must be an absolute path")
        return configured
    return os.path.join(home(), ".local", "state", leaf)


def ensure_private_dir(path: str, *, uid: Optional[int] = None) -> None:
    """Make ``path`` a 0700 directory owned by ``uid`` (default: this user).

    Missing parents are created. A symlink, a non-directory, or another
    owner's directory is refused; a loose mode on our own directory is
    repaired. Checks run on an fd opened without following links, so the
    path cannot be swapped between check and repair.
    """
    owner = os.getuid() if uid is None else uid
    if os.path.islink(path):
        raise StateDirError(f"{path} is a symlink; set {STATE_DIR_ENV} to keep state elsewhere")
    try:
        os.makedirs(path, mode=0o700, exist_ok=True)
    except FileExistsError:
        raise StateDirError(f"{path} exists and is not a directory") from None
    except OSError as err:
        raise StateDirError(f"cannot create {path}: {err.strerror}") from None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as err:
        if err.errno == errno.ELOOP:
            raise StateDirError(f"{path} is a symlink; set {STATE_DIR_ENV} to keep state elsewhere") from None
        raise StateDirError(f"cannot open {path}: {err.strerror}") from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode):
            raise StateDirError(f"{path} is not a directory")
        if st.st_uid != owner:
            raise StateDirError(f"{path} is owned by uid {st.st_uid}, not by uid {owner}")
        if stat.S_IMODE(st.st_mode) != 0o700:
            os.fchmod(fd, 0o700)
    finally:
        os.close(fd)
