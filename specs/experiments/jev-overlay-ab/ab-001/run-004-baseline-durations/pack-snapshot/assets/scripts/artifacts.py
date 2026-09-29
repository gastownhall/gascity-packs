#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


class ArtifactError(Exception):
    pass


_GC_PLAN_MARKER = ".gc-plans"
_GC_PLAN_ARTIFACTS = {"requirements.md", "implementation-plan.md", "tasks.md", "context.yaml"}
_GC_PLAN_OWNED_DIRS = {"github"}


def resolve_artifact_root(override: str, *, rig_root: str = "") -> Path:
    raw_override = override.strip()
    if raw_override:
        return Path(raw_override).expanduser().resolve()

    raw_rig_root = rig_root.strip() or first_env("GC_RIG_ROOT", "GC_DIR", "GC_BEADS_SCOPE_ROOT")
    if not raw_rig_root:
        raise ArtifactError("artifact root override is empty and no rig root environment is available")
    rig = Path(raw_rig_root).expanduser().resolve()
    plans = rig / "plans"
    if plans.exists() and plans.is_dir() and _plans_root_is_foreign(plans):
        return (rig / "gc-plans").resolve()
    return plans.resolve()


def _plans_root_is_foreign(plans: Path) -> bool:
    marker = plans / _GC_PLAN_MARKER
    if marker.exists():
        return False
    try:
        children = list(plans.iterdir())
    except OSError:
        return True
    if not children:
        return False
    for child in children:
        if child.is_dir() and child.name in _GC_PLAN_OWNED_DIRS:
            return False
        if child.name in _GC_PLAN_ARTIFACTS:
            return False
        if child.is_dir() and any((child / artifact).exists() for artifact in _GC_PLAN_ARTIFACTS):
            return False
    return True


def mark_owned_artifact_root(root: Path, override: str, *, rig_root: str = "") -> None:
    if override.strip():
        return
    raw_rig_root = rig_root.strip() or first_env("GC_RIG_ROOT", "GC_DIR", "GC_BEADS_SCOPE_ROOT")
    if not raw_rig_root:
        return
    plans = Path(raw_rig_root).expanduser().resolve() / "plans"
    if root.resolve() == plans.resolve():
        try:
            (root / _GC_PLAN_MARKER).touch(exist_ok=True)
        except OSError as exc:
            raise ArtifactError(f"failed to mark artifact root {root}: {exc}") from exc


def resolve_artifact_path(override: str, relative: str, *, rig_root: str = "") -> Path:
    root = resolve_artifact_root(override, rig_root=rig_root)
    cleaned = relative.strip()
    if not cleaned:
        raise ValueError("artifact relative path must not be empty")
    cleaned = cleaned.lstrip("/")
    if not cleaned:
        raise ValueError("artifact relative path must name a file or directory")

    target = (root / cleaned).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes root: {relative}") from exc
    return target


def first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve gc workflow artifact paths")
    subparsers = parser.add_subparsers(dest="command", required=True)

    root_parser = subparsers.add_parser("root")
    root_parser.add_argument("--override", default="")
    root_parser.add_argument("--rig-root", default="")
    root_parser.add_argument("--mkdir", action="store_true")

    path_parser = subparsers.add_parser("path")
    path_parser.add_argument("--override", default="")
    path_parser.add_argument("--rig-root", default="")
    path_parser.add_argument("--relative", required=True)
    path_parser.add_argument("--mkdir-parents", action="store_true")
    path_parser.add_argument("--directory", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "root":
            path = resolve_artifact_root(args.override, rig_root=args.rig_root)
            if args.mkdir:
                path.mkdir(parents=True, exist_ok=True)
                mark_owned_artifact_root(path, args.override, rig_root=args.rig_root)
        elif args.command == "path":
            root = resolve_artifact_root(args.override, rig_root=args.rig_root)
            path = resolve_artifact_path(args.override, args.relative, rig_root=args.rig_root)
            if args.mkdir_parents:
                mkdir_target = path if args.directory else path.parent
                mkdir_target.mkdir(parents=True, exist_ok=True)
                mark_owned_artifact_root(root, args.override, rig_root=args.rig_root)
        else:  # pragma: no cover
            raise ArtifactError(f"unsupported command {args.command}")
    except (ArtifactError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
