"""Behavior tests for scripts/install_bd_matching_gc.sh.

The script picks the bd that matches the beads module embedded in gc. These
tests stub `go` (build metadata and `go install`) and the gascity bd archive
installer, so they exercise the selection and verification logic offline.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "install_bd_matching_gc.sh"
BEADS = "github.com/steveyegge/beads"

# `go version -m <bin>` prints <bin>.meta; `go install <pkg>@<ver>` writes a
# bd whose metadata names that module and version.
FAKE_GO = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    set -euo pipefail
    echo "go $*" >> "$CALL_LOG"
    case "$1" in
      version) cat "$3.meta" ;;
      install)
        spec="$2"; pkg="${spec%@*}"; ver="${spec##*@}"
        mkdir -p "$GOBIN"
        touch "$GOBIN/bd"; chmod +x "$GOBIN/bd"
        printf '%s: go1.26.8\\n\\tpath\\t%s\\n\\tmod\\t%s\\t%s\\t\\n' "$GOBIN/bd" "$pkg" "${pkg%/cmd/bd}" "$ver" > "$GOBIN/bd.meta"
        ;;
      *) echo "unexpected go $*" >&2; exit 1 ;;
    esac
    """
)

# Mirrors install-bd-archive.sh without --cache: installs into
# BD_INSTALL_BIN_DIR. Release builds report a +dirty module version.
FAKE_ARCHIVE_INSTALLER = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    set -euo pipefail
    echo "archive $*" >> "$CALL_LOG"
    ver="${FAKE_ARCHIVE_VERSION:-$1}"
    mkdir -p "$BD_INSTALL_BIN_DIR"
    touch "$BD_INSTALL_BIN_DIR/bd"; chmod +x "$BD_INSTALL_BIN_DIR/bd"
    printf '%s: go1.26.8\\n\\tpath\\tgithub.com/steveyegge/beads/cmd/bd\\n\\tmod\\tgithub.com/steveyegge/beads\\t%s+dirty\\t\\n' \\
      "$BD_INSTALL_BIN_DIR/bd" "$ver" > "$BD_INSTALL_BIN_DIR/bd.meta"
    """
)


def gc_metadata(*dep_lines: str) -> str:
    lines = ["gc: go1.26.8", "\tpath\tgithub.com/gastownhall/gascity/cmd/gc", "\tmod\tgithub.com/gastownhall/gascity\tv1.4.2\th1:x="]
    lines.extend(dep_lines)
    return "\n".join(lines) + "\n"


def run_script(tmp_path: Path, metadata: str, **extra_env: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    stub_bin = tmp_path / "stub-bin"
    stub_bin.mkdir()
    (stub_bin / "go").write_text(FAKE_GO, encoding="utf-8")
    (stub_bin / "go").chmod(0o755)
    installer = tmp_path / "install-bd-archive.sh"
    installer.write_text(FAKE_ARCHIVE_INSTALLER, encoding="utf-8")
    installer.chmod(0o755)
    gc_bin = tmp_path / "gc"
    gc_bin.touch()
    (tmp_path / "gc.meta").write_text(metadata, encoding="utf-8")

    env = {
        "PATH": f"{stub_bin}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "CALL_LOG": str(tmp_path / "calls.log"),
        "BD_INSTALL_BIN_DIR": str(tmp_path / "bd-bin"),
        "GOBIN": str(tmp_path / "unused-gobin"),
        "GITHUB_ENV": str(tmp_path / "github_env"),
        "GITHUB_PATH": str(tmp_path / "github_path"),
        **extra_env,
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), str(gc_bin), str(installer)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, tmp_path


def calls(root: Path) -> list[str]:
    log = root / "calls.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


@pytest.mark.parametrize("version", ["v1.3.1", "v1.3.1-rc.2"])
def test_release_version_installs_matching_archive(tmp_path: Path, version: str) -> None:
    result, root = run_script(tmp_path, gc_metadata(f"\tdep\t{BEADS}\t{version}\th1:x="))

    assert result.returncode == 0, result.stderr
    assert f"archive {version}" in calls(root)
    assert not any(call.startswith("go install") for call in calls(root))
    bd_bin = root / "bd-bin" / "bd"
    assert (root / "github_env").read_text(encoding="utf-8") == f"GC_BEADS_BIN={bd_bin}\n"
    assert (root / "github_path").read_text(encoding="utf-8") == f"{root / 'bd-bin'}\n"


def test_pseudo_version_go_installs_exact_module_version(tmp_path: Path) -> None:
    pseudo = "v1.3.2-0.20261003210355-61d97acbbf34"
    result, root = run_script(tmp_path, gc_metadata(f"\tdep\t{BEADS}\t{pseudo}\th1:x="))

    assert result.returncode == 0, result.stderr
    assert f"go install {BEADS}/cmd/bd@{pseudo}" in calls(root)
    assert not any(call.startswith("archive") for call in calls(root))


def test_remote_replace_installs_the_replacement(tmp_path: Path) -> None:
    result, root = run_script(
        tmp_path,
        gc_metadata(
            f"\tdep\t{BEADS}\tv1.3.0\t",
            "\t=>\tgithub.com/example/beads-fork\tv1.3.0-fork.1\th1:y=",
        ),
    )

    assert result.returncode == 0, result.stderr
    assert "go install github.com/example/beads-fork/cmd/bd@v1.3.0-fork.1" in calls(root)


def test_local_replace_fails_without_installing(tmp_path: Path) -> None:
    result, root = run_script(tmp_path, gc_metadata(f"\tdep\t{BEADS}\tv1.3.0\t", "\t=>\t../beads\t"))

    assert result.returncode == 1
    assert "local path ../beads" in result.stderr
    assert not any(call.startswith(("archive", "go install")) for call in calls(root))


def test_gc_without_beads_fails(tmp_path: Path) -> None:
    result, root = run_script(tmp_path, gc_metadata("\tdep\tgithub.com/spf13/cobra\tv1.8.0\th1:x="))

    assert result.returncode == 1
    assert f"does not embed {BEADS}" in result.stderr
    assert not (root / "github_env").exists()


def test_installed_bd_with_wrong_beads_version_fails(tmp_path: Path) -> None:
    result, root = run_script(
        tmp_path,
        gc_metadata(f"\tdep\t{BEADS}\tv1.3.1\th1:x="),
        FAKE_ARCHIVE_VERSION="v1.3.0",
    )

    assert result.returncode == 1
    assert "embeds beads v1.3.0+dirty, but" in result.stderr
    assert not (root / "github_env").exists()
