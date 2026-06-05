from __future__ import annotations

import hashlib
import subprocess
import textwrap

import validate_registry


def run_git(root, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_source_pack_path_accepts_tree_urls() -> None:
    source = "https://github.com/gastownhall/gascity-packs/tree/main/cass"

    assert validate_registry.source_pack_path(source) == "cass"


def test_validate_tree_url_source_checks_pack_toml_name(tmp_path) -> None:
    pack_dir = tmp_path / "cass"
    pack_dir.mkdir()
    (pack_dir / "pack.toml").write_text(
        textwrap.dedent(
            """\
            [pack]
            name = "wrong"
            schema = 2
            """
        ),
        encoding="utf-8",
    )
    registry = tmp_path / "registry.toml"
    registry.write_text(
        textwrap.dedent(
            """\
            schema = 1

            [[pack]]
            name = "cass"
            description = "CASS session search pack."
            source = "https://github.com/gastownhall/gascity-packs/tree/main/cass"
            source_kind = "git"

              [[pack.release]]
              version = "0.1.0"
              ref = "main"
              commit = "d3617d1319a1206ac85f69ba024ec395c49c6f4b"
              hash = "sha256:9849675daa3ba8a792fc1c68c727542936400687d529e5d4d231afde29d4a341"
              description = "Initial CASS session-search pack release."
            """
        ),
        encoding="utf-8",
    )

    errors = validate_registry.validate(registry)

    assert "cass: registry name does not match cass/pack.toml name 'wrong'" in errors


def test_pack_content_hash_uses_relative_paths_modes_and_blob_hashes(tmp_path) -> None:
    run_git(tmp_path, "init")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test User")
    pack_dir = tmp_path / "cass"
    pack_dir.mkdir()
    pack_toml = b'[pack]\nname = "cass"\nschema = 2\n'
    readme = b"CASS docs\n"
    (pack_dir / "pack.toml").write_bytes(pack_toml)
    (pack_dir / "README.md").write_bytes(readme)
    run_git(tmp_path, "add", "cass")
    run_git(tmp_path, "commit", "-m", "add cass")
    commit = run_git(tmp_path, "rev-parse", "HEAD")

    manifest = "\n".join(
        sorted(
            [
                f"README.md 0644 {hashlib.sha256(readme).hexdigest()}",
                f"pack.toml 0644 {hashlib.sha256(pack_toml).hexdigest()}",
            ]
        )
    ).encode("utf-8")

    expected = "sha256:" + hashlib.sha256(manifest).hexdigest()

    assert validate_registry.git_pack_content_hash(tmp_path, commit, "cass") == expected
