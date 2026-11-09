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
* the city id hashes the machine's identity with the key, so two machines
  sharing an NFS home never read each other's state. The identity is the one
  herdr-core itself keys a machine on: the machine id (``/etc/machine-id``),
  or on macOS the hardware UUID (IOPlatformUUID). A host name is not one:
  DHCP and Bonjour rename machines, and hc does not treat a rename as a new
  machine (``crates/herdr-core/src/server.rs`` ``load_identity``).

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
import sys
from typing import Callable, Final, Mapping, Optional, Sequence

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


def city_id(machine: str, key: str) -> str:
    """sha256 of the machine's identity and the city key, as hex."""
    return hashlib.sha256(os.fsencode(machine) + b"\0" + os.fsencode(key)).hexdigest()


MACHINE_ID_FILES: Final = ("/etc/machine-id", "/var/lib/dbus/machine-id")
"""Where systemd, then D-Bus, keep the machine id (hc reads the first)."""

_GETHOSTUUID_WAIT_S: Final = 1


def host_name() -> str:
    """This host's name, as ``uname -n`` prints it."""
    return os.uname().nodename


def read_machine_id_file(path: str) -> Optional[str]:
    """The id in a machine-id file; None when missing, empty or ``uninitialized``."""
    try:
        with open(path, encoding="ascii", errors="replace") as handle:
            value = handle.read(256).strip()
    except OSError:
        return None
    return value if value and value != "uninitialized" else None


def format_host_uuid(raw: bytes) -> str:
    """16 bytes as macOS writes IOPlatformUUID: upper-case 8-4-4-4-12 hex."""
    text = raw.hex().upper()
    return f"{text[:8]}-{text[8:12]}-{text[12:16]}-{text[16:20]}-{text[20:]}"


def darwin_host_uuid() -> Optional[str]:
    """macOS's hardware UUID (IOPlatformUUID) from gethostuuid(2), in process.

    None where libc has no gethostuuid (every other system) or the call fails.
    hc reads the same UUID through ioreg; this spawns nothing.
    """
    import ctypes

    class Timespec(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]

    try:
        gethostuuid = ctypes.CDLL(None).gethostuuid
    except (OSError, AttributeError):
        return None
    raw = (ctypes.c_ubyte * 16)()
    wait = Timespec(_GETHOSTUUID_WAIT_S, 0)
    status: object = gethostuuid(raw, ctypes.byref(wait))
    if status != 0:
        return None
    return format_host_uuid(bytes(raw))


def machine_identity(
    *,
    darwin: bool = sys.platform == "darwin",
    files: Sequence[str] = MACHINE_ID_FILES,
    host_uuid: Callable[[], Optional[str]] = darwin_host_uuid,
    host: Callable[[], str] = host_name,
) -> str:
    """What identifies this machine: what herdr-core keys a machine on.

    macOS: the hardware UUID. Elsewhere: the machine id, ``/etc/machine-id``
    then D-Bus's. The host name only when no id can be read.
    """
    if darwin:
        uuid = host_uuid()
        if uuid:
            return uuid
    else:
        for path in files:
            value = read_machine_id_file(path)
            if value:
                return value
    return host()


def user_home(uid: Optional[int] = None) -> str:
    """The home directory the password database gives ``uid`` (default: this user)."""
    who = os.getuid() if uid is None else uid
    try:
        home = pwd.getpwuid(who).pw_dir
    except KeyError:
        raise StateDirError(f"uid {who} has no entry in the password database") from None
    if not os.path.isabs(home):
        raise StateDirError(f"the password database gives uid {who} no absolute home")
    return home


def state_root(env: Mapping[str, str], *, leaf: str, home: Callable[[], str] = user_home) -> str:
    """``R``: ``GC_EXEC_STATE_DIR``, else ``<password-database home>/.local/state/<leaf>``.

    Normalized (``//`` and trailing ``/`` dropped), because the root keys the
    city's hc session: two spellings of one root must name one core.
    """
    configured = env.get(STATE_DIR_ENV, "")
    if configured:
        if not os.path.isabs(configured):
            raise StateDirError(f"{STATE_DIR_ENV} must be an absolute path")
        return os.path.normpath(configured)
    return os.path.normpath(os.path.join(home(), ".local", "state", leaf))


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
