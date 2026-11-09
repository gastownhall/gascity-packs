"""hc version parsing and the hello gate."""

from __future__ import annotations

import pytest

from gc_runtime_herdr_core.hc.errors import HcGateError
from gc_runtime_herdr_core.hc.types import CoreInfo, HelloResult
from gc_runtime_herdr_core.hc.version import GENERATION, Version, VersionPolicy, gate

POLICY = VersionPolicy(min_version=Version.parse("0.1.19"), tested=(Version.parse("0.1.19"),))


def hello(version: str, generation: int = 1) -> HelloResult:
    return HelloResult(
        generation=generation,
        version=version,
        core=CoreInfo(id="c0ffee", name="host"),
        framed=False,
        methods=("hello", "terminal.run"),
        features=("status",),
    )


@pytest.mark.parametrize(
    ("text", "parts"),
    [("0.1.19", (0, 1, 19)), ("v0.1.19", (0, 1, 19)), ("10.20.30", (10, 20, 30)), ("0.1.20-rc.1", (0, 1, 20))],
)
def test_parse(text: str, parts: tuple[int, int, int]) -> None:
    v = Version.parse(text)
    assert (v.major, v.minor, v.patch) == parts


@pytest.mark.parametrize("text", ["", "0.1", "0.1.19.4", "01.1.1", "x.y.z", "0.1.19-", "0.1.-1"])
def test_parse_refuses_non_semver(text: str) -> None:
    with pytest.raises(ValueError):
        Version.parse(text)


def test_semver_precedence() -> None:
    order = ["0.1.18", "0.1.19", "0.1.20-alpha", "0.1.20-alpha.1", "0.1.20-beta", "0.1.20-rc.2", "0.1.20-rc.10", "0.1.20", "0.2.0", "1.0.0"]
    parsed = [Version.parse(text) for text in order]
    assert sorted(reversed(parsed)) == parsed
    assert Version.parse("0.1.19+build.7") == Version.parse("0.1.19")
    assert str(Version.parse("v0.1.20-rc.1")) == "0.1.20-rc.1"


def test_generation_is_one() -> None:
    assert GENERATION == 1


def test_gate_passes_the_pinned_version_silently() -> None:
    assert gate(hello("0.1.19"), POLICY).warnings == ()


def test_gate_warns_on_a_newer_untested_version() -> None:
    warnings = gate(hello("0.1.21"), POLICY).warnings
    assert len(warnings) == 1
    assert "0.1.21" in warnings[0]


def test_gate_refuses_an_older_core() -> None:
    with pytest.raises(HcGateError, match="0.1.18"):
        gate(hello("0.1.18"), POLICY)


def test_gate_refuses_another_generation() -> None:
    with pytest.raises(HcGateError, match="generation"):
        gate(hello("0.1.19", generation=2), POLICY)


def test_gate_refuses_an_unparseable_version() -> None:
    with pytest.raises(HcGateError):
        gate(hello("nightly"), POLICY)
