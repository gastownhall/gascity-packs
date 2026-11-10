"""Installing the pinned herdr-core build.

``gc herdr-core install`` puts the pin's build at
``<install root>/<version>/herdr-core``, where the install root is
``<password-database home>/.local/share/gc-runtime-herdr-core/hc`` (never
``$HOME`` or ``XDG_DATA_HOME``: the supervisor, cron and ssh must all find
the same binary). In order:

1. The release manifest must name the pin's version and generation, and the
   sha256 the pin records for this platform's asset.
2. The asset is downloaded into memory and its sha256 checked against the
   pin **before anything is written**.
3. The binary is read out of the archive (one regular file of the pinned
   name; nothing else in the archive is extracted, and nothing is run), into
   a staging directory beside the version directories, with ``install.json``
   recording what was installed. The file and its directory are made
   read-only, so ``hc update`` refuses to replace the binary.
4. The staging directory is renamed into place: a reader sees the old
   version directory or the new one, never a partial one.

Older versions are garbage-collected afterwards: the pinned version stays,
the most recently installed other version stays (to roll back to), and so
does every version a process of this user still runs. Nothing is removed
when the process table cannot be read. The install root's lock serialises
installs and collections.
"""

from __future__ import annotations

import hashlib
import http.client
import io
import os
import shutil
import ssl
import stat
import tarfile
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Final, FrozenSet, List, Mapping, Optional, Set, Tuple

from ..hc.version import Version
from ..rpp.cancel import CancelToken
from ..rpp.flock import FileLock
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError, ensure_private_dir
from .config import BINARY_NAME, read_private_file
from .pin import HcPin
from .procs import ProcError, ProcSource

RECORD_FILE: Final = "install.json"
LOCK_FILE: Final = ".install.lock"
MANIFEST_FILE: Final = "manifest.json"

MANIFEST_LIMIT: Final = 1 << 16
ARCHIVE_LIMIT: Final = 256 << 20
BINARY_LIMIT: Final = 512 << 20
FETCH_TIMEOUT_S: Final = 60.0
LOCK_WAIT_S: Final = 30.0

TEST_RELEASES_ENV: Final = "GC_HC_TEST_RELEASES"
"""Test-only (``GC_HC_TEST=1``): a directory standing in for the release
server; ``<releases>/<version>/<file>`` is read from ``<dir>/<version>/<file>``."""

Fetch = Callable[[str, int], bytes]
"""Reads a URL, at most ``limit`` bytes (more is an error)."""


class InstallError(Exception):
    """The pinned build cannot be installed; nothing was changed."""


@dataclass(frozen=True)
class InstallRecord:
    """``<version>/install.json``: what ``install`` put there."""

    version: str
    target: str
    archive_sha256: str
    binary_sha256: str
    installed_ms: int


@dataclass(frozen=True)
class InstallOutcome:
    version: str
    binary: str
    installed: bool
    """False when the pinned build was already in place."""
    kept: Tuple[str, ...]
    removed: Tuple[str, ...]
    gc_note: str = ""
    """Why nothing was collected, when nothing could be."""


def https_fetch(url: str, limit: int, *, timeout_s: float = FETCH_TIMEOUT_S) -> bytes:
    """GET ``url`` over https with certificate checks; a redirect is an error."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise InstallError(f"refusing a non-https URL: {url}")
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    conn = http.client.HTTPSConnection(parts.hostname, parts.port or 443, timeout=timeout_s, context=ssl.create_default_context())
    try:
        conn.request("GET", path or "/", headers={"User-Agent": "gc-runtime-herdr-core"})
        response = conn.getresponse()
        if response.status != 200:
            raise InstallError(f"cannot fetch {url}: HTTP {response.status} {response.reason}")
        data = response.read(limit + 1)
    except (OSError, http.client.HTTPException) as err:
        raise InstallError(f"cannot fetch {url}: {err}") from None
    finally:
        conn.close()
    if len(data) > limit:
        raise InstallError(f"{url} is larger than {limit} bytes")
    return data


def directory_fetch(pin: HcPin, directory: str) -> Fetch:
    """A fetch that reads ``<pin.releases>/<rest>`` from ``directory/<rest>`` (tests)."""
    prefix = pin.releases + "/"

    def fetch(url: str, limit: int) -> bytes:
        if not url.startswith(prefix):
            raise InstallError(f"no test release for {url}")
        path = os.path.join(directory, *url[len(prefix) :].split("/"))
        try:
            with open(path, "rb") as handle:
                data = handle.read(limit + 1)
        except OSError as err:
            raise InstallError(f"cannot fetch {url}: {err.strerror}") from None
        if len(data) > limit:
            raise InstallError(f"{url} is larger than {limit} bytes")
        return data

    return fetch


def fetch_for(pin: HcPin, env: Mapping[str, str], *, test: bool) -> Fetch:
    """The release server, or the test stand-in under ``GC_HC_TEST=1``."""
    if test and env.get(TEST_RELEASES_ENV, ""):
        return directory_fetch(pin, env[TEST_RELEASES_ENV])
    return lambda url, limit: https_fetch(url, limit)


def check_manifest(pin: HcPin, target: str, data: bytes) -> None:
    """The release manifest must agree with the pin on everything the pin records."""
    entry = pin.target(target)
    try:
        doc = JsonObject.of(loads(data))
        version = doc.req_str("version")
        generation = doc.req_int("generation")
        listed = doc.obj_map("targets").get(target)
        if listed is None:
            raise InstallError(f"the {pin.version} release manifest has no build for {target}")
        sha = listed.req_str("sha256")
        url = listed.req_str("url")
    except JsonShapeError as err:
        raise InstallError(f"the {pin.version} release manifest is malformed: {err}") from None
    if version != str(pin.version) or generation != pin.generation:
        raise InstallError(f"the release manifest describes {version} (generation {generation}), not the pinned {pin.version}")
    if sha != entry.sha256:
        raise InstallError(f"the release manifest's sha256 for {target} differs from the pin's: refusing to install")
    if url.split("?", 1)[0].rsplit("/", 1)[-1] != entry.asset:
        raise InstallError(f"the release manifest names another asset for {target} than the pin's {entry.asset}")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_binary(archive: bytes, name: str) -> bytes:
    """The one regular file called ``name`` at the archive's top level; nothing
    else is read and nothing is written."""
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            found = [
                member
                for member in tar.getmembers()
                if os.path.normpath(member.name) == name
            ]
            if len(found) != 1 or not found[0].isreg():
                raise InstallError(f"the release archive does not hold exactly one regular file {name!r}")
            if found[0].size > BINARY_LIMIT:
                raise InstallError(f"{name} in the release archive is larger than {BINARY_LIMIT} bytes")
            handle = tar.extractfile(found[0])
            if handle is None:
                raise InstallError(f"cannot read {name} from the release archive")
            with handle:
                return handle.read()
    except (tarfile.TarError, OSError, EOFError) as err:
        raise InstallError(f"the release archive cannot be read: {err}") from None


def read_record(version_dir: str) -> Optional[InstallRecord]:
    """``install.json`` of a version directory; None when absent or unreadable."""
    try:
        raw = read_private_file(os.path.join(version_dir, RECORD_FILE), limit=1 << 16)
    except StateDirError:
        return None
    if raw is None:
        return None
    try:
        doc = JsonObject.of(loads(raw))
        return InstallRecord(
            version=doc.req_str("version"),
            target=doc.req_str("target"),
            archive_sha256=doc.req_str("archive_sha256"),
            binary_sha256=doc.req_str("binary_sha256"),
            installed_ms=doc.req_int("installed_ms"),
        )
    except JsonShapeError:
        return None


def file_sha256(path: str) -> Optional[str]:
    """sha256 of the file at ``path``; None when it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def verify_installed(pin: HcPin, root: str, target: str) -> Optional[str]:
    """Why the pinned build at ``root`` is not the pin's, or None when it is."""
    version_dir = os.path.join(root, str(pin.version))
    binary = os.path.join(version_dir, BINARY_NAME)
    if not os.path.isfile(binary):
        return f"hc {pin.version} is not installed at {binary}"
    record = read_record(version_dir)
    if record is None:
        return f"{binary} was not installed by `gc herdr-core install` (no {RECORD_FILE}): it cannot be checked against the pin"
    entry = pin.target(target)
    if record.version != str(pin.version) or record.archive_sha256 != entry.sha256:
        return f"{binary} came from another release than the pin's"
    if file_sha256(binary) != record.binary_sha256:
        return f"{binary} changed since it was installed"
    return None


def _make_writable(path: str) -> None:
    for here, dirs, files in os.walk(path):
        os.chmod(here, 0o700)
        for name in dirs:
            os.chmod(os.path.join(here, name), 0o700)


def remove_tree(path: str) -> None:
    """Remove an install directory, read-only ones included."""
    if not os.path.lexists(path):
        return
    if os.path.islink(path) or not os.path.isdir(path):
        os.unlink(path)
        return
    _make_writable(path)
    shutil.rmtree(path)


def ensure_root(root: str) -> None:
    """The install root and its pack directory are 0700 directories of this user."""
    parent = os.path.dirname(root)
    os.makedirs(os.path.dirname(parent), mode=0o755, exist_ok=True)
    ensure_private_dir(parent)
    ensure_private_dir(root)


def _write_new(path: str, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view) :]
        os.fsync(fd)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def _place(root: str, version: str, binary: bytes, record: InstallRecord) -> str:
    """Stage the build beside the version directories and rename it into place."""
    staging = tempfile.mkdtemp(prefix=f".{version}.new-", dir=root)
    try:
        _write_new(os.path.join(staging, BINARY_NAME), binary, 0o555)
        doc = {
            "version": record.version,
            "target": record.target,
            "archive_sha256": record.archive_sha256,
            "binary_sha256": record.binary_sha256,
            "installed_ms": record.installed_ms,
        }
        _write_new(os.path.join(staging, RECORD_FILE), (dumps(doc) + "\n").encode("ascii"), 0o444)
        os.chmod(staging, 0o555)
        final = os.path.join(root, version)
        aside = ""
        if os.path.lexists(final):
            aside = os.path.join(root, f".{version}.old-{os.urandom(6).hex()}")
            os.rename(final, aside)
        try:
            os.rename(staging, final)
        except OSError:
            if aside:
                os.rename(aside, final)
            raise
        if aside:
            remove_tree(aside)
        return os.path.join(final, BINARY_NAME)
    except BaseException:
        if os.path.lexists(staging):
            remove_tree(staging)
        raise


def installed_versions(root: str) -> List[str]:
    """The version directories under ``root``."""
    try:
        names = os.listdir(root)
    except OSError:
        return []
    out = []
    for name in names:
        try:
            Version.parse(name)
        except ValueError:
            continue
        if os.path.isdir(os.path.join(root, name)) and not os.path.islink(os.path.join(root, name)):
            out.append(name)
    return sorted(out, key=Version.parse)


def versions_in_use(root: str, procs: ProcSource) -> FrozenSet[str]:
    """The versions whose binary a process of this user runs; :class:`ProcError`
    when that cannot be told."""
    prefix = os.path.realpath(root) + os.sep
    used: Set[str] = set()
    uid = os.getuid()
    for proc in procs.snapshot().values():
        if proc.uid != uid:
            continue
        exe = procs.exe(proc.pid)
        if not exe:
            continue
        if exe.endswith(" (deleted)"):
            exe = exe[: -len(" (deleted)")]
        if exe.startswith(prefix):
            used.add(exe[len(prefix) :].split(os.sep, 1)[0])
    return frozenset(used)


def collect(root: str, pin: HcPin, procs: ProcSource) -> Tuple[Tuple[str, ...], Tuple[str, ...], str]:
    """Remove version directories no longer needed; returns (kept, removed, note)."""
    versions = installed_versions(root)
    try:
        used = versions_in_use(root, procs)
    except ProcError as err:
        return tuple(versions), (), f"older versions kept: cannot tell which are running ({err})"
    pinned = str(pin.version)
    others = [v for v in versions if v != pinned]

    def installed_at(version: str) -> int:
        record = read_record(os.path.join(root, version))
        if record is not None:
            return record.installed_ms
        try:
            return int(os.stat(os.path.join(root, version)).st_mtime * 1000)
        except OSError:
            return 0

    keep: Set[str] = {pinned} | (set(used) & set(versions))
    if others:
        keep.add(max(others, key=installed_at))
    removed: List[str] = []
    for version in versions:
        if version not in keep:
            remove_tree(os.path.join(root, version))
            removed.append(version)
    for name in os.listdir(root):
        if name.startswith(".") and (".new-" in name or ".old-" in name):
            remove_tree(os.path.join(root, name))  # left by an install that died
    return tuple(v for v in versions if v in keep), tuple(removed), ""


def install(
    pin: HcPin,
    *,
    root: str,
    target: str,
    fetch: Fetch,
    procs: ProcSource,
    cancel: CancelToken,
    now_ms: Callable[[], int] = lambda: int(time.time() * 1000),
) -> InstallOutcome:
    """Install the pinned build under ``root`` (see the module docstring)."""
    entry = pin.target(target)
    version = str(pin.version)
    check_manifest(pin, target, fetch(pin.url(MANIFEST_FILE), MANIFEST_LIMIT))
    binary: Optional[bytes] = None
    if verify_installed(pin, root, target) is not None:
        archive = fetch(pin.url(entry.asset), ARCHIVE_LIMIT)
        got = sha256_hex(archive)
        if got != entry.sha256:
            raise InstallError(f"{entry.asset}: sha256 {got} is not the pinned {entry.sha256}: refusing to install")
        binary = extract_binary(archive, pin.binary)
    cancel.check()
    ensure_root(root)
    binary_path = os.path.join(root, version, BINARY_NAME)
    installed = False
    with FileLock(os.path.join(root, LOCK_FILE), shared=False, wait_s=LOCK_WAIT_S, cancel=cancel):
        if binary is not None and verify_installed(pin, root, target) is not None:
            record = InstallRecord(
                version=version,
                target=target,
                archive_sha256=entry.sha256,
                binary_sha256=sha256_hex(binary),
                installed_ms=now_ms(),
            )
            binary_path = _place(root, version, binary, record)
            installed = True
        kept, removed, note = collect(root, pin, procs)
    return InstallOutcome(
        version=version,
        binary=binary_path,
        installed=installed,
        kept=kept,
        removed=removed,
        gc_note=note,
    )


def writable(path: str) -> bool:
    """Whether the binary or its directory is writable by anyone (``hc update`` could replace it)."""
    try:
        file_mode = stat.S_IMODE(os.stat(path).st_mode)
        dir_mode = stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode)
    except OSError:
        return False
    return bool((file_mode | dir_mode) & 0o222)
