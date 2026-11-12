"""The hc build the pack drives, where its binary is, and the hc config the
city's core runs with.

* **Version policy.** ``assets/hc-pin.json`` (:mod:`.pin`): the pack drives
  hc at least the pin's ``min_version``; its ``tested`` versions run without a
  warning. A missing or malformed pin fails every op that needs hc.
* **Binary.** The pinned install
  ``<password-database home>/.local/share/gc-runtime-herdr-core/hc/<version>/herdr-core``
  (``gc herdr-core install`` puts it there), unless the city's pack config
  (``<pack state>/config.json``) names ``hc_bin`` *and* sets
  ``allow_unpinned``: an explicit operator choice to drive another build. A
  ``herdr-core`` or ``hc`` on ``PATH`` is never used: hc changes behaviour in
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
from typing import Callable, Final, Literal, Mapping, Optional

from ..hc.paths import HcPaths
from ..hc.version import VersionPolicy
from ..rpp.jsonval import JsonObject, JsonShapeError, loads
from ..rpp.statedir import StateDirError, ensure_private_dir, user_home
from .pin import PinError, load_pin

INSTALL_LEAF: Final = os.path.join(".local", "share", "gc-runtime-herdr-core", "hc")
BINARY_NAME: Final = "herdr-core"
PACK_CONFIG_FILE: Final = "config.json"

TEST_ENV: Final = "GC_HC_TEST"
TEST_BIN_ENV: Final = "GC_HC_TEST_BIN"
"""Test-only: the hc binary to drive (fake-hc), honoured only under ``GC_HC_TEST=1``."""
TEST_HOME_ENV: Final = "GC_HC_TEST_HOME"
"""Test-only: the home the pinned install lives under, honoured only under
``GC_HC_TEST=1`` by the pack commands and doctor checks."""

AppVisibility = Literal["off", "labels"]
APP_VISIBILITY_VALUES: Final = ("off", "labels")

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


def pin_policy() -> VersionPolicy:
    """The hello gate from the pin; :class:`ConfigError` when the pack is unpinned."""
    try:
        return load_pin().policy
    except PinError as err:
        raise ConfigError(str(err)) from None


def pinned_version() -> str:
    """The pinned hc version; :class:`ConfigError` when the pack is unpinned."""
    try:
        return str(load_pin().version)
    except PinError as err:
        raise ConfigError(str(err)) from None


def install_root(home: Callable[[], str] = user_home) -> str:
    """Where ``gc herdr-core install`` keeps hc builds, one directory per version."""
    return os.path.join(home(), INSTALL_LEAF)


def pinned_binary(home: Callable[[], str] = user_home, version: Optional[str] = None) -> str:
    """Where ``gc herdr-core install`` puts the binary of ``version`` (default: the pin's)."""
    return os.path.join(install_root(home), version or pinned_version(), BINARY_NAME)


@dataclass(frozen=True)
class PackConfig:
    """``<pack state>/config.json``: operator choices for one city."""

    hc_bin: Optional[str] = None
    allow_unpinned: bool = False
    """``hc_bin`` is honoured only with this set: it drives a build the pin does not name."""
    app_visibility: AppVisibility = "off"
    """``labels``: label each session so the Herdr app shows it (:mod:`.appvis`)."""


def read_pack_config(pack_state: str) -> PackConfig:
    """The city's pack config; an absent file is the default config. It names
    the binary the pack executes, so it must be a regular file of this user,
    never a symlink."""
    path = os.path.join(pack_state, PACK_CONFIG_FILE)
    try:
        data = read_private_file(path, limit=1 << 16)
    except StateDirError as err:
        raise ConfigError(str(err)) from None
    if data is None:
        return PackConfig()
    try:
        doc = JsonObject.of(loads(data))
        hc_bin = doc.opt_str("hc_bin")
        allow_unpinned = doc.bool_or("allow_unpinned", False)
        visibility = doc.str_or("app_visibility", "off")
    except JsonShapeError as err:
        raise ConfigError(f"{path}: {err}") from None
    if hc_bin is not None and not os.path.isabs(hc_bin):
        raise ConfigError(f"{path}: hc_bin must be an absolute path")
    if visibility == "labels":
        app: AppVisibility = "labels"
    elif visibility == "off":
        app = "off"
    else:
        raise ConfigError(f"{path}: app_visibility must be one of {', '.join(APP_VISIBILITY_VALUES)}")
    return PackConfig(hc_bin=hc_bin or None, allow_unpinned=allow_unpinned, app_visibility=app)


def resolve_hc_binary(
    env: Mapping[str, str], pack_state: str, *, home: Callable[[], str] = user_home
) -> str:
    """The hc binary for this city; :class:`ConfigError` when none is usable."""
    if test_mode(env) and env.get(TEST_BIN_ENV, ""):
        candidate = env[TEST_BIN_ENV]
        source = TEST_BIN_ENV
    else:
        config = read_pack_config(pack_state)
        config_path = os.path.join(pack_state, PACK_CONFIG_FILE)
        if config.hc_bin and not config.allow_unpinned:
            raise ConfigError(
                f"hc_bin in {config_path} names an unpinned hc: set allow_unpinned to drive it, "
                "or remove hc_bin and run `gc herdr-core install`"
            )
        candidate = config.hc_bin or pinned_binary(home)
        source = "hc_bin in " + config_path if config.hc_bin else "the pinned install"
    if not os.path.isabs(candidate):
        raise ConfigError(f"{source}: the hc binary must be an absolute path")
    if not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
        raise ConfigError(
            f"hc not installed: no executable herdr-core at {candidate} ({source}): run `gc herdr-core install`"
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
