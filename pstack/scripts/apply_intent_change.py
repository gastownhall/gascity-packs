#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACK_ROOT.parent
DEFAULT_SPEC_ROOT = REPO_ROOT / "openspec"
_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def change_name(source: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    name = source.name
    stripped = _DATE_PREFIX.sub("", name, count=1)
    return stripped or name


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
    src_res = src.resolve()
    dest_res = dest_changes.expanduser().resolve()
    if src_res == dest_res:
        return
    if dest_res in src_res.parents or src_res in dest_res.parents:
        raise SystemExit("OpenSpec --source and dest change path overlap")
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
    parser.add_argument(
        "--change",
        default=None,
        help="OpenSpec change name. Default: --source directory name with a leading YYYY-MM-DD- prefix stripped",
    )
    parser.add_argument(
        "--spec-root",
        type=Path,
        default=DEFAULT_SPEC_ROOT,
        help="OpenSpec root with config.yaml, schemas, and specs",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="OpenSpec change directory outside pstack/",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=REPO_ROOT,
        help="tree root that contains openspec/",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--archive", action="store_true", help="openspec archive after a successful dest copy")
    args = parser.parse_args()
    src = source_dir(args.source)
    name = change_name(src, args.change)
    spec_root = args.spec_root.expanduser().resolve()
    if args.validate_only:
        return validate(spec_root, src, name)
    dest = args.dest.expanduser().resolve()
    dest_changes = dest / "openspec" / "changes" / name
    try:
        copy_change(src, dest_changes)
    except OSError as exc:
        raise SystemExit(f"cannot write {dest_changes}: {exc}") from exc
    rc = validate(dest / "openspec", src, name)
    if rc != 0 or not args.archive:
        return rc
    return subprocess.run(
        ["openspec", "archive", name, "-y"],
        cwd=dest,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
