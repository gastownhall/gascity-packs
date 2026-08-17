"""Every registered pack must exist inside a published release tag (#137).

The failure this guards against is the one three separate users reported, and
it is silent on our side: `gc import add <repo-url>//<pack>` with no version
constraint resolves against this repository's **git tags**, not against
`registry.toml`. When a pack is added to `main` and no newer tag is cut, the
resolver checks out the newest existing tag, finds no `<pack>/pack.toml` there,
fails validation, and then deletes the cache directory it names in the error.
The user sees `cached pack ... is missing pack.toml at <path that no longer
exists>` and has no way to tell that the pack simply is not in any release.

Nothing in this repository noticed. `superpowers`, `contributing`,
`gascity/roles`, `pr-pipeline`, `oversight-rig`, `bmad`, `compound-engineering`
and `runtime-cloudflare` were all registered and installable-looking while
being absent from every tag, for weeks. `v0.4.0` (2026-07-24) closed that gap;
this test is what keeps the next pack from reopening it.

The check is deliberately against the real tree and the real tags rather than a
fixture. A fixture-based version of this test would have passed on every day
the repository was broken.

Refute the current state with:

    git tag -l 'v*' | sort -V | tail -1
    git cat-file -e "$(git tag -l 'v*' | sort -V | tail -1):superpowers/pack.toml"
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import tomllib

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "registry.toml"

# A release tag, as this repository cuts them: v0.2.0, v0.3.0, v0.4.0.
# Non-release tags exist (backup/*, pr109-head, keep-*) and must not be
# mistaken for releases.
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# The pack's directory is the path segment after /tree/<ref>/ in its source URL.
SOURCE_PATH = re.compile(r"/tree/[^/]+/(?P<path>.+?)/?$")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def release_tags() -> list[str]:
    """Release tags, oldest first by version rather than by string."""
    tags = [t for t in _git("tag", "-l").split() if RELEASE_TAG.match(t)]
    return sorted(tags, key=lambda t: tuple(int(g) for g in RELEASE_TAG.match(t).groups()))


def registry_pack_paths() -> dict[str, str]:
    """Registered pack name -> its directory in this repository."""
    data = tomllib.loads(REGISTRY.read_text(encoding="utf-8"))
    paths: dict[str, str] = {}
    for pack in data.get("pack", []):
        name = pack.get("name")
        source = pack.get("source", "")
        match = SOURCE_PATH.search(source)
        if name and match:
            paths[name] = match.group("path")
    return paths


def packs_absent_from(tag: str) -> list[str]:
    """Registered packs whose pack.toml does not exist at `tag`."""
    absent = []
    for name, path in sorted(registry_pack_paths().items()):
        blob = f"{tag}:{path}/pack.toml"
        exists = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "cat-file", "-e", blob],
            capture_output=True,
        )
        if exists.returncode != 0:
            absent.append(f"{name} ({path}/pack.toml absent at {tag})")
    return absent


def test_the_registry_and_the_tags_are_both_readable() -> None:
    """Discovery control: neither input may be silently empty.

    Without this, a shallow clone with no tags, or a registry the parser
    returned nothing for, would make every assertion below vacuously true —
    the check would report a clean repository precisely when it could see
    nothing at all.
    """
    packs = registry_pack_paths()
    assert len(packs) >= 16, (
        f"registry.toml yielded only {len(packs)} packs with a resolvable "
        "directory; the registry parse has broken rather than the repository "
        "having shrunk"
    )

    tags = release_tags()
    assert tags, (
        "no vX.Y.Z release tags are visible. In CI this means the checkout did "
        "not fetch tags (actions/checkout needs fetch-depth: 0); locally, run "
        "`git fetch --tags`. This test fails rather than skips, because a "
        "tagless checkout cannot tell a released pack from an unreleased one."
    )


def test_every_registered_pack_exists_in_the_newest_release_tag() -> None:
    """The property users depend on: a registered pack is importable by tag."""
    newest = release_tags()[-1]
    absent = packs_absent_from(newest)
    assert not absent, (
        f"{len(absent)} registered pack(s) are absent from the newest release "
        f"tag {newest}, so `gc import add <url>//<pack>` with no version "
        "constraint fails for them with a misleading 'missing pack.toml' "
        "error (gastownhall/gascity-packs#137). Cut a release tag that "
        "includes them:\n  " + "\n  ".join(absent)
    )


def test_the_check_detects_a_tag_that_really_is_missing_packs() -> None:
    """Mutation control: the assertion above can go red.

    v0.3.0 is a real tag that predates eight registered packs. If
    `packs_absent_from` reports it as clean, the detector is broken and the
    green above means nothing.
    """
    tags = release_tags()
    if "v0.3.0" not in tags:
        pytest.skip("v0.3.0 is not in this checkout; no known-bad tag to test against")

    absent = packs_absent_from("v0.3.0")
    assert len(absent) >= 8, (
        "v0.3.0 predates at least eight registered packs, so the detector must "
        f"report them missing; it reported {len(absent)}. The detector, not the "
        "repository, is what changed."
    )
