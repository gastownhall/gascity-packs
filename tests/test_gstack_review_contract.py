from __future__ import annotations

import hashlib
import pathlib
import tomllib

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GSTACK_ROOT = REPO_ROOT / "gstack"
UPSTREAM_COMMIT = "1626d4857bfe30da2690dd6a3217961934aa3192"
UPSTREAM_SKILL_BLOB = "e7a2fa4f23ae62823e83473ee5717501b521aeba"
UPSTREAM_RESOURCES = {
    "checklist.md": "16aa111bb00fe128320ab66a99714361f2a49232",
    "design-checklist.md": "e9d2b7117c039f82b78daec8f7db63998ee1480c",
    "greptile-triage.md": "3cb6e8d597fd04462b5c2fe18174be2c9ce75c8f",
    "specialists/api-contract.md": "01a649b1b0f47bb1af78e1614924b80cddbd48fa",
    "specialists/data-migration.md": "effc11469c12ec14975cc12036f0e28570d39019",
    "specialists/maintainability.md": "a2a036f9ca4c77ea4d9b9b38233444772a9eccfc",
    "specialists/performance.md": "612aa285d69a3c73da37e766a8da6de489c41a6d",
    "specialists/red-team.md": "12654da877f4f036e7f994fbd587b8cafe1e1d62",
    "specialists/security.md": "b1d2e30c1ff0cc83d5d4e4e4f4fe5b1f4bd581e2",
    "specialists/testing.md": "b2ea12e57c882ef307daee1abaa7066429b4425f",
}


def git_blob_id(path: pathlib.Path) -> str:
    payload = path.read_bytes()
    framed = b"blob " + str(len(payload)).encode() + b"\0" + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity


def test_review_resources_match_pinned_upstream_and_installed_copy() -> None:
    provenance = tomllib.loads(
        (GSTACK_ROOT / "vendor/gstack/upstream.toml").read_text(encoding="utf-8")
    )
    assert provenance["upstream"]["commit"] == UPSTREAM_COMMIT
    assert git_blob_id(GSTACK_ROOT / "vendor/gstack/skills/review/SKILL.md") == (
        UPSTREAM_SKILL_BLOB
    )

    for relative, expected_blob in UPSTREAM_RESOURCES.items():
        vendor = GSTACK_ROOT / "vendor/gstack/review" / relative
        installed = GSTACK_ROOT / "skills/review" / relative
        assert vendor.is_file(), relative
        assert installed.is_file(), relative
        assert vendor.read_bytes() == installed.read_bytes(), relative
        assert git_blob_id(vendor) == expected_blob, relative


def test_installed_review_skill_is_self_contained_and_uses_adjacent_resources() -> None:
    skill_root = GSTACK_ROOT / "skills/review"
    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == "review"
    assert len(text.splitlines()) < 500
    for forbidden in (
        ".claude/",
        "~/.claude",
        "gstack/bin/",
        "gstack-update-check",
        "provider-native runtime",
        "bun ",
    ):
        assert forbidden not in text
    for relative in UPSTREAM_RESOURCES:
        assert (skill_root / relative).is_file(), relative
        assert f"`{relative}`" in text, relative
    assert "## Review boundary" in text
    assert "one independent Gstack Lite review pass" in text
    assert "external review bot" in text
    assert "never a\n  prerequisite for review or delivery" in text
    assert "parallel subagents or specialist agents are overridden" in text
    assert "post replies, resolve threads, or change PR state" in text
    assert "immutable candidate head" in text


def test_formula_staff_lane_is_absent_from_pack_discovery() -> None:
    assert not (GSTACK_ROOT / "agents").exists()
    assert not (GSTACK_ROOT / "assets").exists()
    assert not (GSTACK_ROOT / "formulas").exists()
