from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "assets/scripts/has-undelivered-escalates.sh"


@pytest.fixture(scope="session")
def gc_test_bin() -> Path:
    configured = os.environ.get("GC_TEST_BIN")
    if not configured:
        pytest.skip("set GC_TEST_BIN to run real Gas City CLI integration tests")

    binary = Path(configured).expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        pytest.fail(f"GC_TEST_BIN is not an executable file: {binary}")
    return binary


def write_tool_link(bin_dir: Path, name: str) -> None:
    executable = shutil.which(name)
    assert executable is not None
    bin_dir.joinpath(name).symlink_to(executable)


def run_with_fake_gc(
    tmp_path: Path,
    *,
    stdout: str,
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_gc = bin_dir / "gc"
    fake_gc.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            printf '%s' {json.dumps(stdout)}
            exit {returncode}
            """
        ),
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(bin_dir), env.get("PATH", "")))
    return subprocess.run(
        [str(SCRIPT)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_fires_for_an_undelivered_escalation(tmp_path: Path) -> None:
    beads = [
        {
            "id": "rollup-1",
            "status": "open",
            "labels": ["rollup", "severity:escalate"],
        }
    ]

    result = run_with_fake_gc(tmp_path, stdout=json.dumps(beads))

    assert result.returncode == 0, result.stderr


def test_reports_no_work_for_an_empty_result(tmp_path: Path) -> None:
    result = run_with_fake_gc(tmp_path, stdout="[]")

    assert result.returncode == 1, result.stderr


def test_reports_no_work_when_the_escalation_was_delivered(tmp_path: Path) -> None:
    beads = [
        {
            "id": "rollup-1",
            "status": "open",
            "labels": ["rollup", "severity:escalate", "delivered"],
        }
    ]

    result = run_with_fake_gc(tmp_path, stdout=json.dumps(beads))

    assert result.returncode == 1, result.stderr


def test_cannot_decide_when_gc_query_fails(tmp_path: Path) -> None:
    result = run_with_fake_gc(tmp_path, stdout="[]", returncode=1)

    assert result.returncode == 2
    assert result.stderr


def test_cannot_decide_when_gc_returns_invalid_json(tmp_path: Path) -> None:
    result = run_with_fake_gc(tmp_path, stdout="not JSON")

    assert result.returncode == 2
    assert result.stderr


def test_cannot_decide_when_gc_returns_no_output(tmp_path: Path) -> None:
    result = run_with_fake_gc(tmp_path, stdout="")

    assert result.returncode == 2
    assert result.stderr


def test_cannot_decide_when_gc_is_absent(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_tool_link(bin_dir, "bash")
    write_tool_link(bin_dir, "jq")
    env = os.environ.copy()
    env["PATH"] = str(bin_dir)

    result = subprocess.run(
        [str(SCRIPT)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr


def test_cannot_decide_with_real_gc_and_no_beads_provider(
    tmp_path: Path,
    gc_test_bin: Path,
) -> None:
    city = tmp_path / "city"
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    (city / ".gc").mkdir(parents=True)
    home.mkdir()
    bin_dir.mkdir()
    bin_dir.joinpath("gc").symlink_to(gc_test_bin)
    write_tool_link(bin_dir, "bash")
    write_tool_link(bin_dir, "jq")
    city.joinpath("pack.toml").write_text(
        textwrap.dedent(
            """\
            [pack]
            name = "condition-contract-test"
            schema = 2
            """
        ),
        encoding="utf-8",
    )
    city.joinpath("city.toml").write_text(
        textwrap.dedent(
            """\
            [workspace]
            provider = "codex"

            [providers.codex]
            base = "builtin:codex"
            """
        ),
        encoding="utf-8",
    )
    city.joinpath(".gc", "site.toml").write_text(
        'workspace_name = "condition-contract-test"\n',
        encoding="utf-8",
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GC_", "BEADS_", "XDG_"))
    }
    env.update(
        {
            "HOME": str(home),
            "PATH": str(bin_dir),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
        }
    )

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=city,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    assert result.stderr
