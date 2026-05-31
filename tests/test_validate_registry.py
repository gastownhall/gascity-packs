from __future__ import annotations

import textwrap

import validate_registry


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
