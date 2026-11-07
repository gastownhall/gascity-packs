"""CI must run every test directory that exists in the repo.

``gastown/tests`` and ``oversight-rig/tests`` were on disk and absent from
the ``Run Python pack tests`` step's argument list, so those suites had
never executed in CI. Nothing failed; they were simply not run, which is
the quiet half of gastownhall/gascity-packs#307 (packs shipped without
being exercised).

The CI argument list stays explicit rather than switching to root
discovery, because discovery would also sweep fixture and vendored trees.
This test is what keeps an explicit list from drifting: add a pack with a
``tests/`` directory and forget the workflow, and CI goes red here instead
of silently skipping it.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
STEP_NAME = "Run Python pack tests"


def _pytest_paths_from_workflow() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    step = text.split(f"name: {STEP_NAME}", 1)
    assert len(step) == 2, f"workflow has no step named {STEP_NAME!r}"
    match = re.search(r"python3 -m pytest ([^\n]*)", step[1])
    assert match, f"step {STEP_NAME!r} does not invoke `python3 -m pytest`"
    return [
        token
        for token in match.group(1).split()
        if not token.startswith("-")
    ]


def _test_directories_on_disk() -> list[str]:
    found = []
    for path in sorted(REPO_ROOT.glob("*/tests")):
        if not path.is_dir() or path.name != "tests":
            continue
        if any(path.glob("test_*.py")):
            found.append(f"{path.parent.name}/tests")
    if any((REPO_ROOT / "tests").glob("test_*.py")):
        found.append("tests")
    return sorted(found)


def test_discovery_found_test_directories() -> None:
    # Control on the walk itself — an empty result would make the
    # comparison below vacuously true.
    on_disk = _test_directories_on_disk()
    assert len(on_disk) >= 5, f"suspiciously few test directories: {on_disk}"


def test_ci_runs_every_test_directory_on_disk() -> None:
    in_ci = set(_pytest_paths_from_workflow())
    on_disk = set(_test_directories_on_disk())
    missing = sorted(on_disk - in_ci)
    assert not missing, (
        "these test directories exist but CI never runs them; add them to "
        f"the {STEP_NAME!r} step in .github/workflows/ci.yml: {missing}"
    )


def test_ci_does_not_name_a_directory_that_is_gone() -> None:
    in_ci = set(_pytest_paths_from_workflow())
    on_disk = set(_test_directories_on_disk())
    stale = sorted(in_ci - on_disk)
    assert not stale, (
        f"the {STEP_NAME!r} step names directories with no tests on disk: "
        f"{stale}"
    )
