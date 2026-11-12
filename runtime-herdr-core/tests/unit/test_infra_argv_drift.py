"""The CI drift guard: the pack's infrastructure argv table against gc's
``IsCityInfrastructureArgv``, read from Go source."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from infra_argv_drift import ShapeError, compare, go_table

SCRIPT = Path(__file__).resolve().parents[1] / "infra_argv_drift.py"

# gascity internal/runtime/proctable/infrastructure_argv.go (the function and its constants).
GO = '''package proctable

const ManagedDoltScopeWatchdogVerb = "__gc-managed-dolt-scope-watchdog"

const BDProxyChildVerb = "db-proxy-child"

const (
	NudgePollerVerb    = "nudge"
	NudgePollerSubverb = "poll"
)

// IsCityInfrastructureArgv reports whether argv is city infrastructure.
func IsCityInfrastructureArgv(argv []string) bool {
	if len(argv) < 2 {
		return false
	}
	switch argv[1] {
	case ManagedDoltScopeWatchdogVerb, BDProxyChildVerb:
		return true
	case NudgePollerVerb:
		return len(argv) > 2 && argv[2] == NudgePollerSubverb
	}
	return false
}
'''


def test_the_pack_matches_gc() -> None:
    assert go_table(GO) == {("__gc-managed-dolt-scope-watchdog",), ("db-proxy-child",), ("nudge", "poll")}
    assert compare(GO) == []


def test_a_renamed_verb_is_drift() -> None:
    problems = compare(GO.replace('"db-proxy-child"', '"db-proxy-kid"'))
    assert problems == [
        "gc treats 'db-proxy-kid' as infrastructure; the pack does not",
        "the pack treats 'db-proxy-child' as infrastructure; gc does not",
    ]


def test_an_added_verb_is_drift() -> None:
    added = GO.replace("case NudgePollerVerb:", 'case "__gc-new-daemon":\n\t\treturn true\n\tcase NudgePollerVerb:')
    assert compare(added) == ["gc treats '__gc-new-daemon' as infrastructure; the pack does not"]


@pytest.mark.parametrize(
    "change",
    [
        ("return len(argv) > 2 && argv[2] == NudgePollerSubverb", "return strings.HasPrefix(argv[2], NudgePollerSubverb)"),
        ("if len(argv) < 2 {", "if len(argv) < 3 {"),
        ("func IsCityInfrastructureArgv(", "func IsInfrastructure("),
        ("case NudgePollerVerb:", "case UnknownVerb:"),
    ],
)
def test_a_shape_the_guard_does_not_understand_fails_closed(change: "tuple[str, str]") -> None:
    with pytest.raises(ShapeError):
        go_table(GO.replace(*change))


def test_the_script_fails_ci_on_a_deliberately_mismatched_list(tmp_path: Path) -> None:
    good = tmp_path / "good.go"
    good.write_text(GO)
    bad = tmp_path / "bad.go"
    bad.write_text(GO.replace('"nudge"', '"knock"'))
    ok = subprocess.run([sys.executable, str(SCRIPT), str(good)], capture_output=True, check=False)
    assert ok.returncode == 0, ok.stderr
    drift = subprocess.run([sys.executable, str(SCRIPT), str(bad)], capture_output=True, check=False)
    assert drift.returncode == 1 and b"knock" in drift.stderr
    missing = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "none.go")], capture_output=True, check=False)
    assert missing.returncode == 2
