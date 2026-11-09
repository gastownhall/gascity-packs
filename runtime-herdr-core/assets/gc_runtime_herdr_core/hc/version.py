"""hc versions and the hello gate.

hc ships behaviour changes in patch releases (in 0.1.19, programs a terminal
detaches started to outlive it: herdr-core CHANGELOG, #136), so the pack
drives only cores it knows: protocol generation 1, at least the policy's
minimum version. A newer version outside the tested list
still runs, with a warning for doctor to surface.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from typing import Final, Optional, Tuple

from .errors import HcGateError
from .types import HelloResult

GENERATION: Final = 1
"""The hc protocol generation this pack speaks; a real break needs a new one."""

_IDENT = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_SEMVER: Final = re.compile(
    r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    rf"(?:-({_IDENT}(?:\.{_IDENT})*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


@functools.total_ordering
@dataclass(frozen=True, eq=True)
class Version:
    """A semantic version; build metadata is dropped, as precedence ignores it."""

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()

    @classmethod
    def parse(cls, text: str) -> Version:
        """Parse ``[v]MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]``; ValueError otherwise."""
        match = _SEMVER.fullmatch(text)
        if match is None:
            raise ValueError(f"not a semantic version: {text!r}")
        pre = match.group(4)
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=tuple(pre.split(".")) if pre else (),
        )

    def _key(self) -> Tuple[int, int, int, int, Tuple[Tuple[int, int, str], ...]]:
        # A release outranks its pre-releases; numeric identifiers rank
        # numerically and below alphanumeric ones (semver.org, precedence rule 11).
        identifiers = tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in self.prerelease)
        return (self.major, self.minor, self.patch, 0 if self.prerelease else 1, identifiers)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() < other._key()

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        return f"{core}-{'.'.join(self.prerelease)}" if self.prerelease else core


@dataclass(frozen=True)
class VersionPolicy:
    """Which cores the pack drives: at least ``min_version``; ``tested`` run without a warning."""

    min_version: Version
    tested: Tuple[Version, ...]


@dataclass(frozen=True)
class GateResult:
    hello: HelloResult
    version: Version
    warnings: Tuple[str, ...]


def gate(hello: HelloResult, policy: VersionPolicy) -> GateResult:
    """Admit the core behind ``hello`` or raise :class:`HcGateError`."""
    if hello.generation != GENERATION:
        raise HcGateError(
            "hello",
            f"hc version unsupported: the core speaks protocol generation {hello.generation}, "
            f"this pack generation {GENERATION} (run gc doctor)",
        )
    version: Optional[Version]
    try:
        version = Version.parse(hello.version)
    except ValueError:
        version = None
    if version is None:
        raise HcGateError("hello", "hc version unsupported: the core reports an unreadable version (run gc doctor)")
    if version < policy.min_version:
        raise HcGateError(
            "hello",
            f"hc version unsupported: {version} is older than the minimum {policy.min_version} (run gc doctor)",
        )
    warnings: Tuple[str, ...] = ()
    if version not in policy.tested:
        tested = ", ".join(str(v) for v in policy.tested)
        warnings = (f"hc {version} is not a tested version (tested: {tested})",)
    return GateResult(hello=hello, version=version, warnings=warnings)
