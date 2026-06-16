from __future__ import annotations

import subprocess
import textwrap

import pytest

from scripts import pack_release_compat


def test_latest_releases_ignore_withdrawn_and_sort_semver(tmp_path) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_text(
        textwrap.dedent(
            """\
            schema = 1

            [[pack]]
            name = "demo"
            description = "Demo pack."
            source = "https://example.com/gascity-packs/tree/main/demo"
            source_kind = "git"

              [[pack.release]]
              version = "0.1.9"
              ref = "main"
              commit = "1111111111111111111111111111111111111111"
              hash = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
              description = "Older release."

              [[pack.release]]
              version = "0.1.10"
              ref = "main"
              commit = "2222222222222222222222222222222222222222"
              hash = "sha256:2222222222222222222222222222222222222222222222222222222222222222"
              description = "Latest active release."

              [[pack.release]]
              version = "0.2.0"
              ref = "main"
              commit = "3333333333333333333333333333333333333333"
              hash = "sha256:3333333333333333333333333333333333333333333333333333333333333333"
              description = "Withdrawn release."
              withdrawn = true
              withdrawn_reason = "Bad release."
            """
        ),
        encoding="utf-8",
    )

    releases = pack_release_compat.load_latest_releases(registry)

    assert [release.name for release in releases] == ["demo"]
    assert releases[0].version == "0.1.10"
    assert releases[0].commit == "2222222222222222222222222222222222222222"


def test_write_compat_city_pins_latest_release_sources(tmp_path) -> None:
    releases = [
        pack_release_compat.Release(
            name="demo",
            binding="demo",
            source="https://example.com/gascity-packs/tree/main/demo",
            version="0.1.10",
            commit="2222222222222222222222222222222222222222",
        ),
        pack_release_compat.Release(
            name="vendor/nested",
            binding="vendor-nested",
            source="https://example.com/gascity-packs/tree/main/vendor/nested",
            version="1.2",
            commit="4444444444444444444444444444444444444444",
        ),
    ]

    city = tmp_path / "city"
    pack_release_compat.write_compat_city(city, releases)

    assert (city / "city.toml").read_text(encoding="utf-8") == textwrap.dedent(
        """\
        [workspace]
        provider = "codex"

        [providers.codex]
        base = "builtin:codex"
        ready_delay_ms = 0

        [daemon]
        formula_v2 = true
        """
    )
    assert (city / "pack.toml").read_text(encoding="utf-8") == textwrap.dedent(
        """\
        [pack]
        name = "pack-release-compat"
        schema = 2

        [imports.demo]
        source = "https://example.com/gascity-packs/tree/main/demo"
        version = "0.1.10"

        [imports.vendor-nested]
        source = "https://example.com/gascity-packs/tree/main/vendor/nested"
        version = "1.2"
        """
    )
    assert (city / "packs.lock").read_text(encoding="utf-8") == textwrap.dedent(
        """\
        schema = 1

        [packs."https://example.com/gascity-packs/tree/main/demo"]
        version = "0.1.10"
        commit = "2222222222222222222222222222222222222222"

        [packs."https://example.com/gascity-packs/tree/main/vendor/nested"]
        version = "1.2"
        commit = "4444444444444444444444444444444444444444"
        """
    )


def test_validate_registry_hashes_falls_back_when_gc_lacks_release_validate(tmp_path) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_text("schema = 1\npack = []\n", encoding="utf-8")
    marker = tmp_path / "validated"
    validator = tmp_path / "validate_registry.py"
    validator.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    gc_bin = tmp_path / "gc"
    gc_bin.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'gc: unknown command \"release\" for \"gc pack\"' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gc_bin.chmod(0o755)

    pack_release_compat.validate_registry_hashes(str(gc_bin), registry, None)

    assert marker.read_text(encoding="utf-8") == "ok"


def test_validate_registry_hashes_preserves_real_gc_validation_failures(tmp_path) -> None:
    registry = tmp_path / "registry.toml"
    registry.write_text("schema = 1\npack = []\n", encoding="utf-8")
    gc_bin = tmp_path / "gc"
    gc_bin.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'registry hash mismatch' >&2\n"
        "exit 2\n",
        encoding="utf-8",
    )
    gc_bin.chmod(0o755)

    with pytest.raises(subprocess.CalledProcessError):
        pack_release_compat.validate_registry_hashes(str(gc_bin), registry, None)
