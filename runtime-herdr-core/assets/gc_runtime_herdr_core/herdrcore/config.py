"""The hc build the pack drives, where its binary is, and the hc config the
city's core runs with.

* **Version policy.** The pack drives hc at least :data:`MIN_VERSION`; the
  versions in :data:`TESTED_VERSIONS` run without a warning.
* **Binary.** ``hc_bin`` in the city's pack config (``<pack state>/config.json``,
  an explicit operator choice), else the pinned install
  ``<password-database home>/.local/share/gc-runtime-herdr-core/hc/<version>/herdr-core``.
  A ``herdr-core`` or ``hc`` on ``PATH`` is never used: hc changes behaviour in
  patch releases, and the Herdr app updates the binary it installed.
* **hc config.** The core runs with ``XDG_CONFIG_HOME=R/hc-config``, so it
  reads the pack's ``config.toml`` and never the user's
  ``~/.config/herdr-core``: no typed notes into agents, a bounded history, and
  no personal shell, wait timeout or templates.
"""

from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass
from typing import Callable, Final, Mapping, Optional

from ..hc.paths import HcPaths
from ..hc.version import Version, VersionPolicy
from ..rpp.jsonval import JsonObject, JsonShapeError, loads
from ..rpp.statedir import StateDirError, ensure_private_dir, user_home

PINNED_VERSION: Final = "0.1.19"
MIN_VERSION: Final = "0.1.19"
"""0.1.19 stopped sweeping detached descendants on a normal kill, stop and
restart (herdr-core #136)."""
TESTED_VERSIONS: Final = ("0.1.19",)

POLICY: Final = VersionPolicy(
    min_version=Version.parse(MIN_VERSION),
    tested=tuple(Version.parse(v) for v in TESTED_VERSIONS),
)

INSTALL_LEAF: Final = os.path.join(".local", "share", "gc-runtime-herdr-core", "hc")
BINARY_NAME: Final = "herdr-core"
PACK_CONFIG_FILE: Final = "config.json"

TEST_ENV: Final = "GC_HC_TEST"
TEST_BIN_ENV: Final = "GC_HC_TEST_BIN"
"""Test-only: the hc binary to drive (fake-hc), honoured only under ``GC_HC_TEST=1``."""

HC_CONFIG_TOML: Final = """\
# Written by the runtime-herdr-core pack for this city's herdr-core.
# The core reads this file instead of ~/.config/herdr-core, so personal
# settings never change how the city's agents run. Edits are overwritten.
notes = false
notes_quiet = true
history_mb = 16
"""


class ConfigError(Exception):
    """The pack config or the hc binary cannot be used."""


def test_mode(env: Mapping[str, str]) -> bool:
    """Whether the test-only overrides are honoured (``GC_HC_TEST=1``)."""
    return env.get(TEST_ENV, "") == "1"


def pinned_binary(home: Callable[[], str] = user_home, version: str = PINNED_VERSION) -> str:
    """Where ``gc herdr-core install`` puts the pinned binary."""
    return os.path.join(home(), INSTALL_LEAF, version, BINARY_NAME)


@dataclass(frozen=True)
class PackConfig:
    """``<pack state>/config.json``: operator choices for one city."""

    hc_bin: Optional[str] = None


def read_pack_config(pack_state: str) -> PackConfig:
    """The city's pack config; an absent file is the default config."""
    path = os.path.join(pack_state, PACK_CONFIG_FILE)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return PackConfig()
    except OSError as err:
        raise ConfigError(f"cannot read {path}: {err.strerror}") from None
    with os.fdopen(fd, "rb") as handle:
        data = handle.read(1 << 16)
    try:
        doc = JsonObject.of(loads(data))
        hc_bin = doc.opt_str("hc_bin")
    except JsonShapeError as err:
        raise ConfigError(f"{path}: {err}") from None
    if hc_bin is not None and not os.path.isabs(hc_bin):
        raise ConfigError(f"{path}: hc_bin must be an absolute path")
    return PackConfig(hc_bin=hc_bin or None)


def resolve_hc_binary(
    env: Mapping[str, str], pack_state: str, *, home: Callable[[], str] = user_home
) -> str:
    """The hc binary for this city; :class:`ConfigError` when none is usable."""
    if test_mode(env) and env.get(TEST_BIN_ENV, ""):
        candidate = env[TEST_BIN_ENV]
        source = TEST_BIN_ENV
    else:
        configured = read_pack_config(pack_state).hc_bin
        candidate = configured or pinned_binary(home)
        source = "hc_bin in " + os.path.join(pack_state, PACK_CONFIG_FILE) if configured else "the pinned install"
    if not os.path.isabs(candidate):
        raise ConfigError(f"{source}: the hc binary must be an absolute path")
    if not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
        raise ConfigError(
            f"hc not installed: no executable herdr-core {PINNED_VERSION} at {candidate} ({source})"
        )
    return candidate


def write_hc_config(paths: HcPaths) -> None:
    """Write the pack-owned hc config and an empty templates directory, atomically.

    Rewritten only when its content differs, so a running core sees one
    file throughout.
    """
    directory = os.path.dirname(paths.config_file)
    ensure_private_dir(paths.config_home)
    ensure_private_dir(directory)
    ensure_private_dir(os.path.join(directory, "templates"))
    wanted = HC_CONFIG_TOML.encode("utf-8")
    if read_private_file(paths.config_file) != wanted:
        write_private_file(paths.config_file, wanted)


def write_private_file(path: str, data: bytes, *, mode: int = 0o600) -> None:
    """Replace ``path`` with ``data`` atomically: a private temp file, then rename."""
    directory = os.path.dirname(path)
    tmp = os.path.join(directory, f".{os.path.basename(path)}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, mode)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise
    os.close(fd)
    try:
        os.rename(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def read_private_file(path: str, *, limit: int = 1 << 20) -> Optional[bytes]:
    """``path``'s bytes; None when it does not exist. A symlink or another
    owner's file is refused."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as err:
        if err.errno == errno.ELOOP:
            raise StateDirError(f"{path} is a symlink") from None
        raise StateDirError(f"cannot read {path}: {err.strerror}") from None
    with os.fdopen(fd, "rb") as handle:
        st = os.fstat(handle.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise StateDirError(f"{path} is not a regular file owned by this user")
        return handle.read(limit)
