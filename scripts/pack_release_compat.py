#!/usr/bin/env python3
"""Smoke test latest released packs against a Gas City CLI binary.

The runner intentionally exercises the consumer path from registry metadata:
it writes pack imports plus packs.lock entries from registry.toml, then asks
`gc` to install, check, and resolve the resulting city config.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
BARE_TOML_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
IMPORT_BINDING_RE = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Release:
    name: str
    binding: str
    source: str
    version: str
    commit: str


def semver_key(version: str) -> tuple[int, int, int]:
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"invalid semver release {version!r}")
    parts = [int(part) for part in version.split(".")]
    if len(parts) == 2:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def toml_key(value: str) -> str:
    if BARE_TOML_KEY_RE.fullmatch(value):
        return value
    return toml_string(value)


def import_binding(name: str) -> str:
    binding = IMPORT_BINDING_RE.sub("-", name).strip("-")
    if not binding:
        raise ValueError(f"pack name {name!r} cannot be converted to an import binding")
    return binding


def unique_bindings(names: Iterable[str]) -> dict[str, str]:
    bindings: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        base = import_binding(name)
        binding = base
        suffix = 2
        while binding in used:
            binding = f"{base}-{suffix}"
            suffix += 1
        bindings[name] = binding
        used.add(binding)
    return bindings


def require_string(mapping: dict, key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: {key} is required")
    return value


def load_latest_releases(
    registry_path: Path,
    *,
    pack_filters: Sequence[str] | None = None,
    include_withdrawn: bool = False,
) -> list[Release]:
    with registry_path.open("rb") as handle:
        registry = tomllib.load(handle)

    packs = registry.get("pack", [])
    if not isinstance(packs, list):
        raise ValueError("[[pack]] entries are required")

    requested = set(pack_filters or [])
    selected_names: list[str] = []
    selected_pack_data: list[dict] = []
    for pack in packs:
        if not isinstance(pack, dict):
            raise ValueError("registry pack entries must be tables")
        name = require_string(pack, "name", "registry pack")
        if requested and name not in requested:
            continue
        selected_names.append(name)
        selected_pack_data.append(pack)

    missing = requested - set(selected_names)
    if missing:
        raise ValueError("requested pack(s) not found in registry: " + ", ".join(sorted(missing)))

    bindings = unique_bindings(selected_names)
    releases: list[Release] = []
    for pack in selected_pack_data:
        name = require_string(pack, "name", "registry pack")
        source = require_string(pack, "source", name)
        pack_releases = pack.get("release", [])
        if not isinstance(pack_releases, list) or not pack_releases:
            raise ValueError(f"{name}: at least one [[pack.release]] entry is required")
        active_releases = [
            release
            for release in pack_releases
            if isinstance(release, dict) and (include_withdrawn or not release.get("withdrawn", False))
        ]
        if not active_releases:
            raise ValueError(f"{name}: no active releases found")
        latest = max(active_releases, key=lambda release: semver_key(require_string(release, "version", name)))
        releases.append(
            Release(
                name=name,
                binding=bindings[name],
                source=source,
                version=require_string(latest, "version", name),
                commit=require_string(latest, "commit", f"{name} {latest.get('version', '')}"),
            )
        )
    return releases


def write_compat_city(city_dir: Path, releases: Sequence[Release]) -> None:
    city_dir.mkdir(parents=True, exist_ok=False)
    (city_dir / ".gc").mkdir()
    (city_dir / "city.toml").write_text(
        """\
[workspace]
provider = "codex"

[providers.codex]
base = "builtin:codex"
ready_delay_ms = 0

[daemon]
formula_v2 = true
""",
        encoding="utf-8",
    )

    pack_lines = [
        "[pack]",
        'name = "pack-release-compat"',
        "schema = 2",
        "",
    ]
    for release in releases:
        pack_lines.extend(
            [
                f"[imports.{toml_key(release.binding)}]",
                f"source = {toml_string(release.source)}",
                f"version = {toml_string(release.version)}",
                "",
            ]
        )
    (city_dir / "pack.toml").write_text("\n".join(pack_lines), encoding="utf-8")

    lock_lines = [
        "schema = 1",
        "",
    ]
    for release in releases:
        lock_lines.extend(
            [
                f"[packs.{toml_key(release.source)}]",
                f"version = {toml_string(release.version)}",
                f"commit = {toml_string(release.commit)}",
                "",
            ]
        )
    (city_dir / "packs.lock").write_text("\n".join(lock_lines), encoding="utf-8")


def run_checked(command: Sequence[str], *, cwd: Path | None = None, quiet: bool = False) -> None:
    print("+ " + shlex.join(command), flush=True)
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=quiet,
        check=False,
    )
    if result.returncode == 0:
        return
    if quiet:
        if result.stdout:
            print(result.stdout, file=sys.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
    raise subprocess.CalledProcessError(result.returncode, command)


def run_pack_release_validate(command: Sequence[str], *, cwd: Path) -> bool:
    print("+ " + shlex.join(command), flush=True)
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return True

    output = (result.stdout or "") + (result.stderr or "")
    if 'unknown command "release" for "gc pack"' in output:
        print(
            "gc pack release validate is unavailable in this gc binary; using local registry validator",
            file=sys.stderr,
        )
        return False

    if result.stdout:
        print(result.stdout, file=sys.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    raise subprocess.CalledProcessError(result.returncode, command)


def validate_registry_locally(registry_path: Path) -> None:
    validator = registry_path.parent / "validate_registry.py"
    if not validator.exists():
        print(
            "local validate_registry.py not found; skipping release hash validation fallback",
            file=sys.stderr,
        )
        return
    run_checked([sys.executable, str(validator)], cwd=registry_path.parent)


def validate_registry_hashes(gc_bin: str, registry_path: Path, pack_filters: Sequence[str] | None) -> None:
    commands: list[list[str]] = []
    if pack_filters:
        for pack in pack_filters:
            commands.append([gc_bin, "pack", "release", "validate", str(registry_path), "--pack", pack])
    else:
        commands.append([gc_bin, "pack", "release", "validate", str(registry_path)])

    for command in commands:
        if not run_pack_release_validate(command, cwd=registry_path.parent):
            validate_registry_locally(registry_path)
            return


def exercise_city(gc_bin: str, city_dir: Path) -> None:
    run_checked([gc_bin, "--city", str(city_dir), "import", "install"])
    run_checked([gc_bin, "--city", str(city_dir), "import", "check"])
    run_checked([gc_bin, "--city", str(city_dir), "config", "show"], quiet=True)
    run_checked([gc_bin, "--city", str(city_dir), "formula", "list"], quiet=True)
    run_checked([gc_bin, "--city", str(city_dir), "skill", "list"], quiet=True)


def exercise_releases(gc_bin: str, work_root: Path, releases: Sequence[Release], exercise: str) -> None:
    if exercise in {"combined", "both"}:
        city_dir = work_root / "combined"
        print(f"== combined: {len(releases)} latest release import(s) ==", flush=True)
        write_compat_city(city_dir, releases)
        exercise_city(gc_bin, city_dir)

    if exercise in {"each", "both"}:
        for release in releases:
            city_dir = work_root / release.binding
            print(f"== {release.name}: {release.version} @ {release.commit[:12]} ==", flush=True)
            write_compat_city(city_dir, [release])
            exercise_city(gc_bin, city_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("registry.toml"), help="pack registry to test")
    parser.add_argument("--gc-bin", default=os.environ.get("GC_BIN", "gc"), help="gc binary to exercise")
    parser.add_argument("--pack", dest="packs", action="append", help="pack name to test; repeat for multiple")
    parser.add_argument(
        "--exercise",
        choices=("each", "combined", "both"),
        default="both",
        help="test each latest release, one combined city, or both",
    )
    parser.add_argument("--include-withdrawn", action="store_true", help="allow withdrawn releases when selecting latest")
    parser.add_argument(
        "--skip-release-validation",
        action="store_true",
        help="skip gc pack release validate before import smoke tests",
    )
    parser.add_argument("--workdir", type=Path, help="directory for generated compatibility cities")
    parser.add_argument("--keep-workdir", action="store_true", help="keep generated compatibility cities after success")
    parser.add_argument("--list", action="store_true", help="print selected releases and exit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    registry_path = args.registry.resolve()
    gc_bin = shutil.which(args.gc_bin) if os.path.sep not in args.gc_bin else args.gc_bin
    if not gc_bin:
        parser.error(f"gc binary not found: {args.gc_bin}")

    releases = load_latest_releases(
        registry_path,
        pack_filters=args.packs,
        include_withdrawn=args.include_withdrawn,
    )
    if args.list:
        for release in releases:
            print(f"{release.name}\t{release.version}\t{release.commit}\t{release.source}")
        return 0

    if not args.skip_release_validation:
        validate_registry_hashes(gc_bin, registry_path, args.packs)

    if args.workdir:
        work_root = args.workdir.resolve()
        if work_root.exists() and any(work_root.iterdir()):
            parser.error(f"--workdir must be empty or absent: {work_root}")
        work_root.mkdir(parents=True, exist_ok=True)
        cleanup_work_root = False
    else:
        work_root = Path(tempfile.mkdtemp(prefix="gascity-pack-compat-"))
        cleanup_work_root = not args.keep_workdir

    try:
        exercise_releases(gc_bin, work_root, releases, args.exercise)
        print(f"compatibility smoke passed for {len(releases)} latest release(s)", flush=True)
        if args.keep_workdir or args.workdir:
            print(f"compatibility workdir: {work_root}", flush=True)
    finally:
        if cleanup_work_root:
            shutil.rmtree(work_root, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
