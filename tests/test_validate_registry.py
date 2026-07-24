from __future__ import annotations

import hashlib
import subprocess
import sys
import textwrap
import tomllib

import pytest

import validate_registry

_PACK_TOML_BYTES = b'[pack]\nname = "cass"\nschema = 2\n'
_README_BYTES = b"CASS docs\n"


def run_git(root, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _init_pack_repo(root) -> str:
    run_git(root, "init")
    run_git(root, "config", "user.email", "test@example.com")
    run_git(root, "config", "user.name", "Test User")
    pack_dir = root / "cass"
    pack_dir.mkdir()
    (pack_dir / "pack.toml").write_bytes(_PACK_TOML_BYTES)
    (pack_dir / "README.md").write_bytes(_README_BYTES)
    run_git(root, "add", "cass")
    run_git(root, "commit", "-m", "add cass")
    return run_git(root, "rev-parse", "HEAD")


def test_parse_source_accepts_canonical_tree_url() -> None:
    spec = validate_registry.parse_source(
        "https://github.com/gastownhall/gascity-packs/tree/main/cass"
    )

    assert spec == validate_registry.SourceSpec(ref="main", pack_path="cass")


def test_parse_source_accepts_bare_repo_url_as_root_pack() -> None:
    spec = validate_registry.parse_source("https://github.com/gastownhall/gascity-packs")

    assert spec == validate_registry.SourceSpec(ref=None, pack_path="")


def test_parse_source_tolerates_trailing_slash_and_host_case() -> None:
    spec = validate_registry.parse_source(
        "https://GITHUB.COM/gastownhall/gascity-packs/tree/main/cass/"
    )

    assert spec == validate_registry.SourceSpec(ref="main", pack_path="cass")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # The headline bug: a foreign source must be refused, not silently unverified.
        ("https://github.com/eve/packs", "external pack sources are not accepted"),
        ("https://github.com/eve/packs/tree/main/x", "external pack sources are not accepted"),
        ("https://evil.com/gastownhall/gascity-packs/tree/main/x", "external pack sources are not accepted"),
        # Legacy forms that used to skip every check.
        ("https://github.com/gastownhall/gascity-packs//cass", "legacy '<repo>//<dir>' source form"),
        ("https://github.com/gastownhall/gascity-packs.git//cass", "legacy '<repo>//<dir>' source form"),
        # Plausible-but-wrong shapes previously mis-read as "repository root".
        ("https://github.com/gastownhall/gascity-packs/packs/cass", "unrecognized source URL form"),
        ("https://github.com/gastownhall/gascity-packs/blob/main/cass", "source uses /blob/"),
        ("https://github.com/gastownhall/gascity-packs/tree/main", "missing the pack directory"),
        ("https://github.com/gastownhall/gascity-packs/tree/main/../etc", "invalid segment"),
        # Transport / identity.
        ("http://github.com/gastownhall/gascity-packs/tree/main/cass", "must be an HTTPS URL"),
        ("git@github.com:gastownhall/gascity-packs.git", "must be an HTTPS URL"),
        ("https://github.com/GasTownHall/gascity-packs/tree/main/cass", "canonical repository URL"),
        ("https://github.com/gastownhall/gascity-packs/tree/main/cass#v1", "must not embed a ref fragment"),
        ("https://github.com/gastownhall/gascity-packs/tree/main/cass?x=1", "no query, credentials, or port"),
    ],
)
def test_parse_source_rejects_unverifiable_sources(source: str, expected: str) -> None:
    with pytest.raises(validate_registry.SourceError) as excinfo:
        validate_registry.parse_source(source)

    assert expected in str(excinfo.value)


def test_validate_rejects_foreign_source_with_bogus_hash(tmp_path) -> None:
    """Regression: this exact entry validated "ok" before the fail-closed fix."""
    commit = _init_pack_repo(tmp_path)
    registry = tmp_path / "registry.toml"
    registry.write_text(
        textwrap.dedent(
            f"""\
            schema = 1

            [[pack]]
              name = "evil-pack"
              description = "d"
              source = "https://github.com/eve/packs"
              source_kind = "git"

              [[pack.release]]
                version = "0.1.0"
                ref = "main"
                commit = "{"a" * 40}"
                hash = "sha256:{"0" * 64}"
                description = "d"
            """
        )
    )
    del commit

    errors = validate_registry.validate(registry)

    assert any("external pack sources are not accepted" in e for e in errors)


def test_validate_reports_uncomputable_hash_instead_of_passing(tmp_path) -> None:
    """A canonical source whose commit is absent must error, not silently verify."""
    _init_pack_repo(tmp_path)
    registry = tmp_path / "registry.toml"
    registry.write_text(
        textwrap.dedent(
            f"""\
            schema = 1

            [[pack]]
              name = "cass"
              description = "d"
              source = "https://github.com/gastownhall/gascity-packs/tree/main/cass"
              source_kind = "git"

              [[pack.release]]
                version = "0.1.0"
                ref = "main"
                commit = "{"a" * 40}"
                hash = "sha256:{"0" * 64}"
                description = "d"
            """
        )
    )

    errors = validate_registry.validate(registry)

    assert any("content hash could not be computed" in e for e in errors)


def test_validate_verifies_root_pack_hash(tmp_path) -> None:
    """A repo-root pack (pack_path == "") must be verified, not skipped."""
    run_git(tmp_path, "init")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "pack.toml").write_bytes(b'[pack]\nname = "rootpack"\nschema = 2\n')
    run_git(tmp_path, "add", "pack.toml")
    run_git(tmp_path, "commit", "-m", "root pack")
    commit = run_git(tmp_path, "rev-parse", "HEAD")
    registry = tmp_path / "registry.toml"

    def write(hash_value: str) -> None:
        registry.write_text(
            textwrap.dedent(
                f"""\
                schema = 1

                [[pack]]
                  name = "rootpack"
                  description = "d"
                  source = "https://github.com/gastownhall/gascity-packs"
                  source_kind = "git"

                  [[pack.release]]
                    version = "0.1.0"
                    ref = "main"
                    commit = "{commit}"
                    hash = "{hash_value}"
                    description = "d"
                """
            )
        )

    real = validate_registry.git_pack_content_hash(tmp_path, commit, "")
    write(real)
    assert not [e for e in validate_registry.validate(registry) if "rootpack" in e]

    write(f"sha256:{'0' * 64}")
    assert any("does not match" in e for e in validate_registry.validate(registry) if "rootpack" in e)


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
    commit = _init_pack_repo(tmp_path)

    manifest = "\n".join(
        sorted(
            [
                f"README.md 0644 {hashlib.sha256(_README_BYTES).hexdigest()}",
                f"pack.toml 0644 {hashlib.sha256(_PACK_TOML_BYTES).hexdigest()}",
            ]
        )
    ).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(manifest).hexdigest()

    assert validate_registry.git_pack_content_hash(tmp_path, commit, "cass") == expected


def test_resolve_commit_returns_full_lowercase_sha(tmp_path) -> None:
    head = _init_pack_repo(tmp_path)

    resolved = validate_registry.resolve_commit(tmp_path, "HEAD")

    assert validate_registry.COMMIT_RE.fullmatch(resolved)
    assert resolved == head


def test_git_pack_content_hash_raises_rather_than_returning_none(tmp_path) -> None:
    """The fail-closed contract: an uncomputable hash must raise, never be falsy."""
    commit = _init_pack_repo(tmp_path)

    computed = validate_registry.git_pack_content_hash(tmp_path, commit, "cass")

    assert validate_registry.HASH_RE.fullmatch(computed)
    with pytest.raises(ValueError, match="does not contain"):
        validate_registry.git_pack_content_hash(tmp_path, commit, "missing")
    with pytest.raises(ValueError, match="not present in this repository"):
        validate_registry.git_pack_content_hash(tmp_path, "a" * 40, "cass")


def test_render_pack_entry_parses_and_carries_computed_hash(tmp_path) -> None:
    commit = _init_pack_repo(tmp_path)
    content_hash = validate_registry.git_pack_content_hash(tmp_path, commit, "cass")

    block = validate_registry.render_pack_entry(
        name="cass",
        description="CASS session search pack.",
        source="https://github.com/gastownhall/gascity-packs/tree/main/cass",
        version="0.1.0",
        ref="main",
        commit=commit,
        content_hash=content_hash,
        release_description="Initial CASS session-search pack release.",
    )

    parsed = tomllib.loads(block)
    entry = parsed["pack"][0]
    release = entry["release"][0]
    assert entry["name"] == "cass"
    assert entry["source_kind"] == "git"
    assert release["commit"] == commit
    assert release["hash"] == content_hash
    assert validate_registry.HASH_RE.fullmatch(release["hash"])


def test_render_pack_entry_escapes_quotes_in_descriptions(tmp_path) -> None:
    commit = _init_pack_repo(tmp_path)
    content_hash = validate_registry.git_pack_content_hash(tmp_path, commit, "cass")

    description = 'Has a "quote" and a \\ backslash'
    block = validate_registry.render_pack_entry(
        name="cass",
        description=description,
        source="https://github.com/gastownhall/gascity-packs/tree/main/cass",
        version="0.1.0",
        ref="main",
        commit=commit,
        content_hash=content_hash,
        release_description="Initial release.",
    )

    parsed = tomllib.loads(block)
    assert parsed["pack"][0]["description"] == description


def test_cli_compute_happy_path(tmp_path, monkeypatch, capsys) -> None:
    commit = _init_pack_repo(tmp_path)
    registry = tmp_path / "registry.toml"
    registry.write_bytes(b"schema = 1\n")
    monkeypatch.setattr(sys, "argv", [
        "validate_registry", str(registry), "--compute", "cass", "--commit", commit,
    ])

    result = validate_registry.main()

    assert result == 0
    out, _ = capsys.readouterr()
    expected = validate_registry.git_pack_content_hash(tmp_path, commit, "cass")
    assert out.strip() == expected


def test_cli_emit_entry_missing_required_args_exit_2(tmp_path, monkeypatch, capsys) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_bytes(b"schema = 1\n")
    monkeypatch.setattr(sys, "argv", [
        "validate_registry", str(registry), "--emit-entry", "cass",
    ])

    result = validate_registry.main()

    assert result == 2
    _, err = capsys.readouterr()
    assert "emit-entry failed" in err


def test_cli_mutual_exclusion_guard(tmp_path, monkeypatch, capsys) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_bytes(b"schema = 1\n")
    monkeypatch.setattr(sys, "argv", [
        "validate_registry", str(registry), "--compute", "cass", "--emit-entry", "cass",
    ])

    result = validate_registry.main()

    assert result == 2
    _, err = capsys.readouterr()
    assert "mutually exclusive" in err


def test_cli_pack_name_traversal_rejected(tmp_path, monkeypatch, capsys) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_bytes(b"schema = 1\n")
    monkeypatch.setattr(sys, "argv", [
        "validate_registry", str(registry), "--compute", "../../x",
    ])

    result = validate_registry.main()

    assert result == 1
    _, err = capsys.readouterr()
    assert "invalid pack name" in err
