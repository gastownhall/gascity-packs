#!/usr/bin/env python3
"""Small registry.toml sanity check for the wave-1 migration branch."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse


PACK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(/[a-z0-9][a-z0-9-]*)?$")
RELEASE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUIRED_WAVE_1 = {
    "cass",
    "discord",
    "gascity",
    "gastown",
    "github",
    "slack-channel",
    "slack-full",
    "slack-mini",
}
FORBIDDEN_WAVE_1 = {"bd", "core", "dolt", "maintenance"}


def inside_git_worktree(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_object_exists(root: Path, object_name: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", object_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(root),
            *args,
        ]
    )


def relative_pack_content_path(git_path: str, pack_path: str) -> str:
    if not pack_path:
        return git_path
    prefix = pack_path + "/"
    if not git_path.startswith(prefix):
        raise ValueError(f"git path {git_path!r} is outside pack path {pack_path!r}")
    rel = git_path[len(prefix) :]
    if not rel:
        raise ValueError(f"empty relative path for {git_path!r}")
    return rel


def manifest_perm(mode: str) -> str:
    if mode == "100644":
        return "0644"
    if mode == "100755":
        return "0755"
    if mode == "120000":
        return "0777"
    raise ValueError(f"unsupported git file mode {mode!r}")


def git_pack_content_hash(root: Path, commit: str, pack_path: str) -> str | None:
    pack_toml_object = f"{commit}:{pack_path}/pack.toml" if pack_path else f"{commit}:pack.toml"
    if not git_object_exists(root, pack_toml_object):
        return None
    args = ["ls-tree", "-r", "-z", "--full-tree", commit]
    if pack_path:
        args.extend(["--", pack_path])
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(root),
            *args,
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    entries: list[str] = []
    for record in result.stdout.rstrip(b"\0").split(b"\0"):
        if not record:
            continue
        fields, _, raw_path = record.partition(b"\t")
        parts = fields.decode("utf-8").split()
        if len(parts) != 3:
            raise ValueError(f"unexpected git ls-tree metadata {fields!r}")
        mode, object_type, object_id = parts
        if object_type != "blob":
            raise ValueError(f"unsupported git object type {object_type!r} for {raw_path!r}")
        rel = relative_pack_content_path(raw_path.decode("utf-8"), pack_path)
        data = git_bytes(root, "cat-file", "blob", object_id)
        entries.append(f"{rel} {manifest_perm(mode)} {hashlib.sha256(data).hexdigest()}")
    if not entries:
        return None
    manifest = "\n".join(sorted(entries)).encode("utf-8")
    return "sha256:" + hashlib.sha256(manifest).hexdigest()


def source_pack_path(source: str) -> str:
    git_subdir = re.search(r"\.git//([^#]+)", source)
    if git_subdir:
        return git_subdir.group(1).strip("/")
    tree_path = re.search(r"/tree/[^/]+/([^#]+)", source)
    if tree_path:
        return tree_path.group(1).strip("/")
    return ""


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    git_checks_enabled = inside_git_worktree(path.parent)

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

            commit = release.get("commit", "")
            if git_checks_enabled and (pack_path := source_pack_path(pack.get("source", ""))):
                pack_toml_object = f"{commit}:{pack_path}/pack.toml"
                if COMMIT_RE.fullmatch(commit) and not git_object_exists(path.parent, pack_toml_object):
                    errors.append(f"{label}: release {version!r} commit does not contain {pack_path}/pack.toml")
                expected_hash = git_pack_content_hash(path.parent, commit, pack_path) if COMMIT_RE.fullmatch(commit) else None
                if expected_hash and release.get("hash", "") != expected_hash:
                    errors.append(f"{label}: release {version!r} hash {release.get('hash', '')!r} does not match {expected_hash!r}")

        source = pack.get("source", "")
        parsed = urlparse(source)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{label}: source must be an HTTPS git locator")
            continue
        if parsed.fragment:
            errors.append(f"{label}: source must not embed a ref fragment; use [[pack.release]].ref")
            continue

        pack_path = source_pack_path(source)
        if pack_path:
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
