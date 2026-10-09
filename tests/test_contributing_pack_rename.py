from __future__ import annotations

import pathlib
import tomllib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACK_NAME = "contributing-to-gascity"


def test_contributing_pack_uses_scoped_identity() -> None:
    pack_dir = REPO_ROOT / PACK_NAME

    assert pack_dir.is_dir()
    assert not (REPO_ROOT / "contributing").exists()

    with (pack_dir / "pack.toml").open("rb") as file:
        pack = tomllib.load(file)["pack"]

    assert pack["name"] == PACK_NAME
    assert pack["version"] == "0.5.0"


def test_repository_consumers_use_scoped_pack_path() -> None:
    expected_path = f"{PACK_NAME}/tests"
    consumers = (
        REPO_ROOT / ".github/workflows/ci.yml",
        REPO_ROOT / "README.md",
        REPO_ROOT / "registry.toml",
        REPO_ROOT / "tests/test_default_branch_resolution.py",
    )

    for consumer in consumers:
        text = consumer.read_text(encoding="utf-8")
        assert "contributing/tests" not in text
        assert "tree/main/contributing\"" not in text
        assert "./contributing)" not in text

    assert expected_path in consumers[0].read_text(encoding="utf-8")
