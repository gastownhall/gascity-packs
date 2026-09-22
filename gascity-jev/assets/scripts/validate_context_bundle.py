#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

SECRET_NAMES = {
    ".env",
    ".ssh",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "cookies.txt",
    "cookie.txt",
}
SECRET_DIRECTORY_NAMES = {
    "secret",
    "secrets",
    "credential",
    "credentials",
    "token",
    "tokens",
    "cookie",
    "cookies",
}
SECRET_PATTERNS = {
    ".env.*",
    ".git/config",
    "*/.git/config",
    "*cookie*",
    "*credentials*",
    "*credential*",
    "*secret*",
    "*token*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "id_*",
}
ITEM_KEYS = {"name", "path", "description"}


class ValidationError(Exception):
    pass


YAML_ERROR_TYPES = (yaml.YAMLError,) if yaml is not None else ()
CLI_ERROR_TYPES = (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) + YAML_ERROR_TYPES


@dataclass(frozen=True)
class ContextItem:
    name: str
    path: str
    description: str
    resolved_path: Path


@dataclass(frozen=True)
class ContextBundle:
    path: Path
    items: list[ContextItem]


def load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        if yaml is None:
            raise ValidationError("PyYAML is required to parse YAML context bundles")
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: context bundle must be a mapping")
    return data


def validate_bundle(path: Path, *, allowed_roots: list[Path] | None = None, max_bytes: int = 1_000_000) -> ContextBundle:
    bundle_path = path.resolve()
    data = load_mapping(bundle_path)
    unknown_top = set(data) - {"items"}
    if unknown_top:
        raise ValidationError(f"{bundle_path}: unknown top-level fields: {sorted(unknown_top)}")
    raw_items = data.get("items", [])
    if raw_items is None:
        raw_items = []
    if not isinstance(raw_items, list):
        raise ValidationError(f"{bundle_path}: items must be a list")

    roots = [root.resolve() for root in (allowed_roots or [bundle_path.parent])]
    items: list[ContextItem] = []
    for index, raw in enumerate(raw_items):
        item_name = f"items[{index}]"
        if not isinstance(raw, dict):
            raise ValidationError(f"{bundle_path}: {item_name} must be a mapping")
        unknown = set(raw) - ITEM_KEYS
        if unknown:
            raise ValidationError(f"{bundle_path}: {item_name} unknown fields: {sorted(unknown)}")
        name = required_string(raw, "name", bundle_path, item_name)
        item_path = required_string(raw, "path", bundle_path, item_name)
        description = required_string(raw, "description", bundle_path, item_name)
        resolved = resolve_item_path(bundle_path, item_path)
        validate_item_path(bundle_path, name, item_path, resolved, roots, max_bytes=max_bytes)
        items.append(ContextItem(name=name, path=item_path, description=description, resolved_path=resolved))
    return ContextBundle(path=bundle_path, items=items)


def required_string(raw: dict[str, Any], key: str, bundle_path: Path, item_name: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{bundle_path}: {item_name}.{key} must be a non-empty string")
    return value.strip()


def resolve_item_path(bundle_path: Path, item_path: str) -> Path:
    path = Path(item_path)
    if path.is_absolute():
        return path.resolve()
    return (bundle_path.parent / path).resolve()


def validate_item_path(
    bundle_path: Path,
    item_name: str,
    original_path: str,
    resolved: Path,
    allowed_roots: list[Path],
    *,
    max_bytes: int,
) -> None:
    if is_secret_path(Path(original_path), resolved, allowed_roots):
        raise ValidationError(
            f"{bundle_path}: {item_name} path {original_path!r} resolves to known secret location {resolved}"
        )
    if not any(path_is_relative_to(resolved, root) for root in allowed_roots):
        raise ValidationError(
            f"{bundle_path}: {item_name} path {original_path!r} resolves outside allowed roots: {resolved}"
        )
    try:
        info = resolved.stat()
    except FileNotFoundError as exc:
        raise ValidationError(f"{bundle_path}: {item_name} path {original_path!r} does not exist: {resolved}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValidationError(f"{bundle_path}: {item_name} path {original_path!r} is not a regular file: {resolved}")
    if info.st_size > max_bytes:
        raise ValidationError(
            f"{bundle_path}: {item_name} path {original_path!r} exceeds max size {max_bytes}: {resolved}"
        )
    with resolved.open("rb") as handle:
        sample = handle.read(min(info.st_size, 8192))
    if b"\x00" in sample:
        raise ValidationError(f"{bundle_path}: {item_name} path {original_path!r} appears binary: {resolved}")


def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def is_secret_path(original: Path, resolved: Path, allowed_roots: list[Path] | None = None) -> bool:
    part_sets = path_part_sets(original, allowed_roots) + path_part_sets(resolved, allowed_roots)
    names = {part for parts in part_sets for part in parts}
    if names & SECRET_NAMES:
        return True
    if any(
        part in SECRET_DIRECTORY_NAMES
        for parts in part_sets
        for part in parts[:-1]
    ):
        return True

    path_values = set()
    for parts in part_sets:
        path_values.update(adjacent_paths(parts))
        if parts:
            path_values.add("/".join(parts))
    leaf_patterns = {pattern for pattern in SECRET_PATTERNS if "/" not in pattern}
    path_patterns = {pattern for pattern in SECRET_PATTERNS if "/" in pattern}
    return any(fnmatch.fnmatch(value, pattern) for value in names for pattern in leaf_patterns) or any(
        fnmatch.fnmatch(value, pattern) for value in path_values for pattern in path_patterns
    )


def path_part_sets(path: Path, allowed_roots: list[Path] | None) -> list[list[str]]:
    if not path.is_absolute() or not allowed_roots:
        return [normalized_parts(path)]
    for root in allowed_roots:
        try:
            return [normalized_parts(path.relative_to(root))]
        except ValueError:
            continue
    return [normalized_parts(path)]


def normalized_parts(path: Path) -> list[str]:
    return [part.lower() for part in path.parts if part not in {"", path.anchor, "/", "\\"}]


def adjacent_paths(parts: list[str]) -> set[str]:
    return {"/".join(parts[index : index + 2]) for index in range(len(parts) - 1)}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a gc context bundle")
    parser.add_argument("path", type=Path)
    parser.add_argument("--allow-root", action="append", type=Path, default=[])
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        bundle = validate_bundle(args.path, allowed_roots=args.allow_root or None, max_bytes=args.max_bytes)
    except CLI_ERROR_TYPES as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "items": len(bundle.items)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
