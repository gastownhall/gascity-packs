#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGE = "audit-pstack-gascity-pack-contracts"


def source_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    pack = PACK_ROOT.resolve()
    if resolved == pack or pack in resolved.parents:
        raise SystemExit("OpenSpec payloads do not live inside the pack")
    if not resolved.is_dir():
        raise SystemExit(f"missing change payload {path}")
    return resolved


def copy_change(src: Path, dest_changes: Path) -> None:
    dest_changes.parent.mkdir(parents=True, exist_ok=True)
    if dest_changes.exists():
        shutil.rmtree(dest_changes)
    shutil.copytree(src, dest_changes)


def validate(spec_root: Path, src: Path, name: str) -> int:
    if not (spec_root / "config.yaml").is_file():
        raise SystemExit(f"missing OpenSpec config at {spec_root}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        root = tmp_path / "openspec"
        root.mkdir()
        shutil.copy2(spec_root / "config.yaml", root / "config.yaml")
        shutil.copytree(spec_root / "schemas", root / "schemas")
        shutil.copytree(spec_root / "specs", root / "specs")
        (root / "changes").mkdir()
        copy_change(src, root / "changes" / name)
        return subprocess.run(
            ["openspec", "validate", name, "--type", "change", "--strict"],
            cwd=tmp_path,
            check=False,
        ).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--change", default=DEFAULT_CHANGE)
    parser.add_argument("--spec-root", type=Path, help="OpenSpec root with config.yaml, schemas, and specs")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="OpenSpec change directory outside this pack",
    )
    parser.add_argument("--dest", type=Path, help="tree root that contains openspec/")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--archive", action="store_true", help="openspec archive after a successful dest copy")
    args = parser.parse_args()
    src = source_dir(args.source)
    if args.validate_only:
        spec_root = args.spec_root
        if spec_root is None and args.dest is not None:
            spec_root = args.dest / "openspec"
        if spec_root is None:
            raise SystemExit("pass --spec-root <openspec-dir> or --dest")
        return validate(spec_root, src, args.change)
    if args.dest is None:
        raise SystemExit("pass --dest <openspec-tree-root> or --validate-only")
    dest_changes = args.dest / "openspec" / "changes" / args.change
    try:
        copy_change(src, dest_changes)
    except OSError as exc:
        raise SystemExit(f"cannot write {dest_changes}: {exc}") from exc
    rc = validate(args.dest / "openspec", src, args.change)
    if rc != 0 or not args.archive:
        return rc
    return subprocess.run(
        ["openspec", "archive", args.change, "-y"],
        cwd=args.dest,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
