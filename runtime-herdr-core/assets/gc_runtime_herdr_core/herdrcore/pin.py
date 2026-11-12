"""The pinned herdr-core build: ``assets/hc-pin.json``.

The pin names the one hc version the pack installs and drives by default,
the oldest version it drives at all, the versions it was tested against,
and the release asset and sha256 of each platform's build. hc changes
behaviour in patch releases, so a missing or unreadable pin is an error,
never "whatever hc is on PATH". Moving the pin is a pack release.
"""

from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from typing import Dict, Final, Mapping, Optional, Tuple

from ..hc.version import GENERATION, Version, VersionPolicy
from ..rpp.jsonval import JsonObject, JsonShapeError, loads

PIN_FILE: Final = "hc-pin.json"

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_ASSET: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class PinError(Exception):
    """The pin is missing or malformed: the pack has no hc build to drive."""


@dataclass(frozen=True)
class PinTarget:
    """One platform's release asset (a ``.tar.gz`` holding the binary) and its sha256."""

    asset: str
    sha256: str


@dataclass(frozen=True)
class HcPin:
    """``hc-pin.json``."""

    version: Version
    generation: int
    min_version: Version
    tested: Tuple[Version, ...]
    releases: str
    """The release server's base URL; a version's files are under ``<releases>/<version>/``."""
    binary: str
    """The binary's name inside each asset."""
    targets: Mapping[str, PinTarget]

    @property
    def policy(self) -> VersionPolicy:
        """The hello gate: at least ``min_version``; ``tested`` without a warning."""
        return VersionPolicy(min_version=self.min_version, tested=self.tested)

    def target(self, name: str) -> PinTarget:
        """``name``'s asset; :class:`PinError` when the pin has no build for it."""
        found = self.targets.get(name)
        if found is None:
            raise PinError(f"hc {self.version} is not pinned for {name} (pinned: {', '.join(sorted(self.targets))})")
        return found

    def url(self, leaf: str) -> str:
        """The URL of ``leaf`` in the pinned version's release directory."""
        return f"{self.releases}/{self.version}/{leaf}"


def default_pin_path() -> str:
    """``assets/hc-pin.json`` beside the package."""
    here = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    return os.path.join(os.path.dirname(here), PIN_FILE)


def _version(doc: JsonObject, key: str) -> Version:
    try:
        return Version.parse(doc.req_str(key))
    except ValueError as err:
        raise JsonShapeError(f"{doc.path(key)}: {err}") from None


def parse_pin(data: bytes, where: str = PIN_FILE) -> HcPin:
    """Parse a pin document; :class:`PinError` when it is not one."""
    try:
        doc = JsonObject.of(loads(data))
        version = _version(doc, "version")
        min_version = _version(doc, "min_version")
        tested = tuple(Version.parse(v) for v in doc.str_tuple("tested", required=True))
        generation = doc.req_int("generation")
        releases = doc.req_str("releases").rstrip("/")
        binary = doc.req_str("binary")
        targets: Dict[str, PinTarget] = {}
        for name, entry in doc.obj_map("targets").items():
            asset = entry.req_str("asset")
            sha = entry.req_str("sha256")
            if not _ASSET.fullmatch(asset):
                raise JsonShapeError(f"{entry.path('asset')}: not a plain file name")
            if not _SHA256.fullmatch(sha):
                raise JsonShapeError(f"{entry.path('sha256')}: not a lowercase sha256")
            targets[name] = PinTarget(asset=asset, sha256=sha)
    except (JsonShapeError, ValueError) as err:
        raise PinError(f"{where}: {err}") from None
    if generation != GENERATION:
        raise PinError(f"{where}: pins protocol generation {generation}, this pack speaks {GENERATION}")
    if version < min_version:
        raise PinError(f"{where}: the pinned version {version} is older than min_version {min_version}")
    if not releases.startswith("https://"):
        raise PinError(f"{where}: releases must be an https URL")
    if not _ASSET.fullmatch(binary):
        raise PinError(f"{where}: binary must be a plain file name")
    if not targets:
        raise PinError(f"{where}: pins no platform")
    return HcPin(
        version=version,
        generation=generation,
        min_version=min_version,
        tested=tested,
        releases=releases,
        binary=binary,
        targets=targets,
    )


_LOADED: Dict[str, HcPin] = {}


def load_pin(path: Optional[str] = None) -> HcPin:
    """The pin at ``path`` (default: the pack's own); :class:`PinError` when unusable."""
    where = path or default_pin_path()
    cached = _LOADED.get(where)
    if cached is not None:
        return cached
    try:
        with open(where, "rb") as handle:
            data = handle.read(1 << 16)
    except OSError as err:
        raise PinError(f"hc is not pinned: cannot read {where}: {err.strerror}") from None
    pin = parse_pin(data, where)
    _LOADED[where] = pin
    return pin


_MACHINES: Final = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}
_SYSTEMS: Final = {"Linux": "linux", "Darwin": "macos"}


def host_target(system: Optional[str] = None, machine: Optional[str] = None) -> str:
    """This host's release target name (``linux-x86_64``, ``macos-aarch64``, ...),
    spelled as hc's release manifest spells it; :class:`PinError` for a host hc
    has no build for."""
    sys_name = platform.system() if system is None else system
    arch = platform.machine() if machine is None else machine
    os_part = _SYSTEMS.get(sys_name)
    arch_part = _MACHINES.get(arch.lower())
    if os_part is None or arch_part is None:
        raise PinError(f"herdr-core has no build for {sys_name} {arch}")
    return f"{os_part}-{arch_part}"
