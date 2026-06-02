from __future__ import annotations

import textwrap

from scripts import registry_release


def test_withdraw_adds_release_metadata(tmp_path) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_text(
        textwrap.dedent(
            """\
            schema = 1

            [[pack]]
            name = "demo"
            description = "Demo pack."
            source = "https://example.com/repo/tree/main/demo"
            source_kind = "git"

              [[pack.release]]
              version = "0.1.0"
              ref = "main"
              commit = "0123456789abcdef0123456789abcdef01234567"
              hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
              description = "Initial release."
            """
        ),
        encoding="utf-8",
    )

    registry_release.withdraw(registry, "demo", "0.1.0", "Superseded by 0.1.1.")

    assert (
        '  description = "Initial release."\n'
        "  withdrawn = true\n"
        '  withdrawn_reason = "Superseded by 0.1.1."\n'
    ) in registry.read_text(encoding="utf-8")


def test_set_source_updates_only_requested_pack(tmp_path) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_text(
        textwrap.dedent(
            """\
            schema = 1

            [[pack]]
            name = "demo"
            description = "Demo pack."
            source = "/tmp/local/demo"
            source_kind = "git"

            [[pack]]
            name = "other"
            description = "Other pack."
            source = "/tmp/local/other"
            source_kind = "git"
            """
        ),
        encoding="utf-8",
    )

    registry_release.set_source(registry, "demo", "https://example.com/repo/tree/main/demo")

    text = registry.read_text(encoding="utf-8")
    assert 'source = "https://example.com/repo/tree/main/demo"' in text
    assert 'source = "/tmp/local/other"' in text
