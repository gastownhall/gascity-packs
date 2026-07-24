#!/usr/bin/env python3
"""Small registry.toml sanity check for the wave-1 migration branch."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


# registry.toml describes packs that live in THIS repository, and nothing else.
# Community packs are published directly to the Gas City registry under a scoped
# <owner>/<pack> name; they never get an entry here. That keeps this validator a
# purely local, network-free, fail-closed check: every source it accepts is one
# whose content it can actually verify against the local object database.
CANONICAL_REPO_HOST = "github.com"
CANONICAL_REPO_OWNER = "gastownhall"
CANONICAL_REPO_NAME = "gascity-packs"
CANONICAL_REPO_URL = f"https://{CANONICAL_REPO_HOST}/{CANONICAL_REPO_OWNER}/{CANONICAL_REPO_NAME}"
PACK_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

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


def git_pack_content_hash(root: Path, commit: str, pack_path: str) -> str:
    """Content hash for a pack subtree at a commit.

    Raises ValueError with a reason rather than returning None: a hash that
    cannot be computed must surface as an error, never be mistaken for "verified".
    """
    if not git_object_exists(root, f"{commit}^{{commit}}"):
        raise ValueError(
            f"commit {commit} is not present in this repository "
            "(shallow clone? CI must check out with fetch-depth: 0)"
        )
    pack_toml_object = f"{commit}:{pack_path}/pack.toml" if pack_path else f"{commit}:pack.toml"
    if not git_object_exists(root, pack_toml_object):
        location = f"{pack_path}/pack.toml" if pack_path else "pack.toml at the repository root"
        raise ValueError(f"commit {commit} does not contain {location}")
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
        raise ValueError(f"git ls-tree failed for {commit} ({result.stderr.decode('utf-8', 'replace').strip()})")
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
        raise ValueError(f"no tracked files under {pack_path or 'the repository root'} at {commit}")
    manifest = "\n".join(sorted(entries)).encode("utf-8")
    return "sha256:" + hashlib.sha256(manifest).hexdigest()


class SourceError(ValueError):
    """A source URL this validator refuses to accept, with a human-readable reason."""


@dataclass(frozen=True)
class SourceSpec:
    """A parsed, accepted source URL.

    ref is the /tree/<ref> segment, or None for the bare repository URL.
    pack_path is "" if and only if the pack lives at the repository root — a
    distinct, fully-verified state, never a signal to skip checks.
    """

    ref: str | None
    pack_path: str


_FOREIGN_SOURCE_MESSAGE = (
    "external pack sources are not accepted in this registry, because this validator can "
    "only verify content hashes against this repository's own history. Your pack keeps "
    "living in your repo: publish it to the Gas City registry (registry.gascity.com/publish) "
    "under a scoped <owner>/<pack> name, where you stay its owner. No PR here is needed - "
    "drop this registry.toml change"
)


def parse_source(source: str) -> SourceSpec:
    """Parse a source URL, or raise SourceError explaining why it is unacceptable.

    Only URLs pointing at this repository are accepted, because only those can be
    verified against the local object database.
    """
    parsed = urlparse(source)
    if parsed.scheme != "https":
        raise SourceError(
            f"source must be an HTTPS URL of this repository ({CANONICAL_REPO_URL}); "
            f"got scheme {parsed.scheme!r}"
        )
    if parsed.fragment:
        raise SourceError("source must not embed a ref fragment; use [[pack.release]].ref")
    if parsed.query or parsed.username or parsed.password or parsed.port:
        raise SourceError("source must be a plain repository URL with no query, credentials, or port")
    if (parsed.hostname or "").lower() != CANONICAL_REPO_HOST:
        raise SourceError(_FOREIGN_SOURCE_MESSAGE)

    # Split before discarding empties so an interior "//" is caught rather than
    # silently collapsing into a valid-looking path.
    raw = parsed.path[:-1] if parsed.path.endswith("/") else parsed.path
    segments = raw.split("/")[1:] if raw.startswith("/") else raw.split("/")
    if segments == [""]:
        raise SourceError(f"source must use the canonical repository URL {CANONICAL_REPO_URL}")
    if any(segment == "" for segment in segments):
        raise SourceError(
            "legacy '<repo>//<dir>' source form is no longer accepted; use "
            f"{CANONICAL_REPO_URL}/tree/<ref>/<dir>"
        )
    if len(segments) < 2:
        raise SourceError(f"source must use the canonical repository URL {CANONICAL_REPO_URL}")

    owner, repo, *rest = segments
    if repo.endswith(".git"):
        raise SourceError(f"source must use the canonical repository URL {CANONICAL_REPO_URL}")
    if owner != CANONICAL_REPO_OWNER or repo != CANONICAL_REPO_NAME:
        # A different repo on github.com is still an external source.
        if (owner.lower(), repo.lower()) == (CANONICAL_REPO_OWNER, CANONICAL_REPO_NAME):
            raise SourceError(f"source must use the canonical repository URL {CANONICAL_REPO_URL}")
        raise SourceError(_FOREIGN_SOURCE_MESSAGE)

    if not rest:
        return SourceSpec(ref=None, pack_path="")

    if rest[0] == "blob":
        raise SourceError(f"source uses /blob/ (a file view); use {CANONICAL_REPO_URL}/tree/<ref>/<dir>")
    if rest[0] != "tree":
        raise SourceError(
            f"unrecognized source URL form {source!r}; expected "
            f"{CANONICAL_REPO_URL}/tree/<ref>/<dir> or the bare repository URL for a root pack"
        )

    ref, *dirs = rest[1:] or [""]
    if not ref:
        raise SourceError(f"source /tree/ URL is missing a ref; use {CANONICAL_REPO_URL}/tree/<ref>/<dir>")
    if not dirs:
        raise SourceError(
            "source /tree/ URL is missing the pack directory; for a repository-root pack "
            f"use the bare repository URL {CANONICAL_REPO_URL}"
        )
    for segment in dirs:
        if segment in {".", ".."} or not PACK_PATH_SEGMENT_RE.fullmatch(segment):
            raise SourceError(f"source pack path contains an invalid segment {segment!r}")
    return SourceSpec(ref=ref, pack_path="/".join(dirs))


def validate(path: Path, *, require_git: bool = False) -> list[str]:
    errors: list[str] = []
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    git_checks_enabled = inside_git_worktree(path.parent)
    if not git_checks_enabled:
        # Without git we can only check formatting — no commit or content-hash
        # verification happens at all. Never let that pass silently in CI.
        message = (
            "git content verification is unavailable "
            f"({path.parent} is not a git worktree); commit and hash checks were NOT performed"
        )
        if require_git:
            # Record and keep going: format errors are still worth reporting.
            errors.append(message + " (--require-git)")
        else:
            print(f"warning: {message}", file=sys.stderr)

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

        # Parse the source BEFORE validating releases: the release checks need the
        # pack path, and an unparseable source must never silently disable them.
        spec: SourceSpec | None = None
        try:
            spec = parse_source(pack.get("source", ""))
        except SourceError as exc:
            errors.append(f"{label}: {exc}")

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
            # No ref-vs-source-URL comparison: the source URL carries ONE /tree/<ref>
            # segment while releases are per-version, so any pack releasing from two
            # refs would be unsatisfiable. commit + content hash are the real anchor;
            # the ref segment is display metadata.
            if spec is not None and git_checks_enabled and COMMIT_RE.fullmatch(commit):
                # A hash that cannot be computed is an error, never a pass.
                try:
                    expected_hash = git_pack_content_hash(path.parent, commit, spec.pack_path)
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    errors.append(f"{label}: release {version!r} content hash could not be computed: {exc}")
                else:
                    if release.get("hash", "") != expected_hash:
                        errors.append(
                            f"{label}: release {version!r} hash {release.get('hash', '')!r} "
                            f"does not match {expected_hash!r}"
                        )

        # Worktree cross-check — runs for root packs too (pack_path == "").
        if spec is not None:
            pack_dir = path.parent / spec.pack_path if spec.pack_path else path.parent
            # "cass/pack.toml" for a subdir pack; "pack.toml" for a repo-root pack.
            toml_label = f"{spec.pack_path}/pack.toml" if spec.pack_path else "pack.toml"
            where = repr(spec.pack_path) if spec.pack_path else "the repository root"
            pack_toml = pack_dir / "pack.toml"
            if not pack_toml.exists():
                errors.append(f"{label}: source path {where} does not contain pack.toml")
                continue
            try:
                with pack_toml.open("rb") as handle:
                    pack_data = tomllib.load(handle)
            except tomllib.TOMLDecodeError as exc:
                errors.append(f"{label}: source path {where} pack.toml is invalid: {exc}")
                continue
            actual_name = pack_data.get("pack", {}).get("name", "")
            if actual_name != name:
                errors.append(f"{label}: registry name does not match {toml_label} name {actual_name!r}")

    missing = REQUIRED_WAVE_1 - seen
    if missing:
        errors.append("missing wave-1 entries: " + ", ".join(sorted(missing)))

    forbidden = FORBIDDEN_WAVE_1 & seen
    if forbidden:
        errors.append("wave-1 registry must not include: " + ", ".join(sorted(forbidden)))

    return errors


def resolve_commit(root: Path, ref: str) -> str:
    """Resolve a git ref to its full 40-char lowercase commit SHA."""
    return git_bytes(root, "rev-parse", "--verify", f"{ref}^{{commit}}").decode("utf-8").strip()


def _toml_escape(value: str) -> str:
    """Escape a string for embedding in a TOML basic (double-quoted) string."""
    result = []
    for ch in value:
        if ch == "\\":
            result.append("\\\\")
        elif ch == '"':
            result.append('\\"')
        elif ch == "\n":
            result.append("\\n")
        elif ch == "\r":
            result.append("\\r")
        elif ch == "\t":
            result.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise ValueError(f"control character U+{ord(ch):04X} in field value")
        else:
            result.append(ch)
    return "".join(result)


def render_pack_entry(
    *,
    name: str,
    description: str,
    source: str,
    version: str,
    ref: str,
    commit: str,
    content_hash: str,
    release_description: str,
) -> str:
    """Render a ready-to-paste [[pack]] block matching registry.toml style."""
    return (
        "[[pack]]\n"
        f'name = "{_toml_escape(name)}"\n'
        f'description = "{_toml_escape(description)}"\n'
        f'source = "{_toml_escape(source)}"\n'
        'source_kind = "git"\n'
        "\n"
        "  [[pack.release]]\n"
        f'  version = "{_toml_escape(version)}"\n'
        f'  ref = "{_toml_escape(ref)}"\n'
        f'  commit = "{commit}"\n'
        f'  hash = "{content_hash}"\n'
        f'  description = "{_toml_escape(release_description)}"\n'
    )


def _pack_toml_name(root: Path, pack: str) -> str:
    if not PACK_NAME_RE.fullmatch(pack):
        raise ValueError(f"invalid pack name {pack!r}")
    pack_toml = root / pack / "pack.toml"
    if not pack_toml.exists():
        raise ValueError(f"{pack}/pack.toml not found in working tree")
    with pack_toml.open("rb") as handle:
        name = tomllib.load(handle).get("pack", {}).get("name")
    if not name:
        raise ValueError(f"{pack}/pack.toml has no [pack].name key")
    return name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", nargs="?", default="registry.toml")
    parser.add_argument(
        "--require-git",
        action="store_true",
        help="fail instead of warning when git content verification is unavailable",
    )
    parser.add_argument(
        "--compute",
        metavar="PACK",
        help="compute and print the content hash for PACK at --commit, then exit",
    )
    parser.add_argument(
        "--emit-entry",
        metavar="PACK",
        help="print a ready-to-paste [[pack]] registry block for PACK, then exit",
    )
    parser.add_argument(
        "--commit",
        default="HEAD",
        metavar="REF",
        help="commit-ish whose pack content is hashed/pinned (default: HEAD)",
    )
    parser.add_argument(
        "--ref",
        default="main",
        metavar="REF",
        help="git ref label for the source URL and release ref field (default: main)",
    )
    parser.add_argument(
        "--repo-url",
        default="https://github.com/gastownhall/gascity-packs",
        help="repository base URL for the source field of --emit-entry",
    )
    parser.add_argument("--version", help="release version for --emit-entry (semver)")
    parser.add_argument(
        "--pack-description", help="catalog description for --emit-entry"
    )
    parser.add_argument(
        "--release-description", help="release description for --emit-entry"
    )
    args = parser.parse_args()

    root = Path(args.registry).resolve().parent

    if args.compute and args.emit_entry:
        print("--compute and --emit-entry are mutually exclusive", file=sys.stderr)
        return 2

    if args.compute:
        if not PACK_NAME_RE.fullmatch(args.compute):
            print(f"compute failed: invalid pack name {args.compute!r}", file=sys.stderr)
            return 1
        try:
            commit = resolve_commit(root, args.commit)
            print(git_pack_content_hash(root, commit, args.compute))
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"compute failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.emit_entry:
        pack = args.emit_entry
        problems = []
        if not args.version or not RELEASE_VERSION_RE.fullmatch(args.version):
            problems.append("--version must be semver major.minor[.patch]")
        if not args.pack_description:
            problems.append("--pack-description is required")
        if not args.release_description:
            problems.append("--release-description is required")
        if problems:
            for problem in problems:
                print(f"emit-entry failed: {problem}", file=sys.stderr)
            return 2
        try:
            actual_name = _pack_toml_name(root, pack)
            if actual_name != pack:
                raise ValueError(
                    f"{pack}/pack.toml name {actual_name!r} does not match {pack!r}"
                )
            commit = resolve_commit(root, args.commit)
            minted_source = f"{args.repo_url.rstrip('/')}/tree/{args.ref}/{pack}"
            try:
                parse_source(minted_source)
            except SourceError as exc:
                print(f"emit-entry failed: {exc}", file=sys.stderr)
                return 1
            content_hash = git_pack_content_hash(root, commit, pack)
            entry = render_pack_entry(
                name=pack,
                description=args.pack_description,
                source=minted_source,
                version=args.version,
                ref=args.ref,
                commit=commit,
                content_hash=content_hash,
                release_description=args.release_description,
            )
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"emit-entry failed: {exc}", file=sys.stderr)
            return 1
        print(entry, end="")
        return 0

    errors = validate(Path(args.registry), require_git=args.require_git)
    if errors:
        for error in errors:
            print(f"registry validation failed: {error}", file=sys.stderr)
        return 1

    print(f"{args.registry}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
