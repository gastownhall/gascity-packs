#!/usr/bin/env python3
"""Small registry.toml sanity check for the wave-1 migration branch."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse


PACK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(/[a-z0-9][a-z0-9-]*)?$")
RELEASE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUIRED_WAVE_1 = {"discord", "gascity", "gastown", "github-intake", "slack-full"}
FORBIDDEN_WAVE_1 = {"bd", "core", "dolt", "maintenance"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    if data.get("schema", 1) != 1:
        errors.append("schema must be 1")

    packs = data.get("pack", [])
    if not isinstance(packs, list):
        errors.append("[[pack]] entries are required")
        return errors

    seen: set[str] = set()
    for index, pack in enumerate(packs, start=1):
        name = pack.get("name", "")
        label = name or f"entry #{index}"
        if not PACK_NAME_RE.fullmatch(name):
            errors.append(f"{label}: invalid pack name")
        if name in seen:
            errors.append(f'{label}: duplicate pack "{name}"')
        seen.add(name)

        if not pack.get("description"):
            errors.append(f"{label}: description is required")
        if pack.get("source_kind") != "git":
            errors.append(f"{label}: source_kind must be git")

        releases = pack.get("release", [])
        if not isinstance(releases, list) or len(releases) == 0:
            errors.append(f"{label}: at least one [[pack.release]] is required")
        seen_releases: set[str] = set()
        for release in releases if isinstance(releases, list) else []:
            version = release.get("version", "")
            if not RELEASE_VERSION_RE.fullmatch(version):
                errors.append(f"{label}: release version {version!r} must be semver major.minor[.patch]")
            if version in seen_releases:
                errors.append(f"{label}: duplicate release {version!r}")
            seen_releases.add(version)
            if not release.get("ref"):
                errors.append(f"{label}: release {version!r} ref is required")
            if not COMMIT_RE.fullmatch(release.get("commit", "")):
                errors.append(f"{label}: release {version!r} commit must be a full lowercase SHA")
            if not HASH_RE.fullmatch(release.get("hash", "")):
                errors.append(f"{label}: release {version!r} hash must be sha256:<64 lowercase hex>")
            if not release.get("description"):
                errors.append(f"{label}: release {version!r} description is required")

        source = pack.get("source", "")
        parsed = urlparse(source)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{label}: source must be an HTTPS git locator")
            continue
        if parsed.fragment:
            errors.append(f"{label}: source must not embed a ref fragment; use [[pack.release]].ref")
            continue

        match = re.search(r"\.git//([^#]+)", source)
        if match:
            pack_path = match.group(1)
            pack_toml = path.parent / pack_path / "pack.toml"
            if not pack_toml.exists():
                errors.append(f"{label}: source path {pack_path!r} does not contain pack.toml")
                continue
            try:
                with pack_toml.open("rb") as handle:
                    pack_data = tomllib.load(handle)
            except tomllib.TOMLDecodeError as exc:
                errors.append(f"{label}: source path {pack_path!r} pack.toml is invalid: {exc}")
                continue
            actual_name = pack_data.get("pack", {}).get("name", "")
            if actual_name != name:
                errors.append(f"{label}: registry name does not match {pack_path}/pack.toml name {actual_name!r}")

    missing = REQUIRED_WAVE_1 - seen
    if missing:
        errors.append("missing wave-1 entries: " + ", ".join(sorted(missing)))

    forbidden = FORBIDDEN_WAVE_1 & seen
    if forbidden:
        errors.append("wave-1 registry must not include: " + ", ".join(sorted(forbidden)))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", nargs="?", default="registry.toml")
    args = parser.parse_args()

    errors = validate(Path(args.registry))
    if errors:
        for error in errors:
            print(f"registry validation failed: {error}", file=sys.stderr)
        return 1

    print(f"{args.registry}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
