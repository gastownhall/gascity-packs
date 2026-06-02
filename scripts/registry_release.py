#!/usr/bin/env python3
"""Line-preserving helpers for registry release maintenance."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PACK_HEADER_RE = re.compile(r"^\[\[pack\]\]\s*$")
RELEASE_HEADER_RE = re.compile(r"^\s*\[\[pack\.release\]\]\s*$")
FIELD_RE = re.compile(r"^(\s*)([A-Za-z_]+)\s*=")


def set_source(registry: Path, pack_name: str, source: str) -> None:
    lines = registry.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = find_pack(lines, pack_name)
    changed = replace_field(lines, start, end, "source", toml_string(source), "  ")
    if not changed:
        raise ValueError(f'{pack_name}: missing "source" field')
    registry.write_text("".join(lines), encoding="utf-8")


def withdraw(registry: Path, pack_name: str, version: str, reason: str) -> None:
    lines = registry.read_text(encoding="utf-8").splitlines(keepends=True)
    pack_start, pack_end = find_pack(lines, pack_name)
    release_start, release_end = find_release(lines, pack_start, pack_end, version)
    release_lines = lines[release_start:release_end]
    release_lines = upsert_field(release_lines, "withdrawn_reason", toml_string(reason), "  ")
    release_lines = upsert_field(release_lines, "withdrawn", "true", "  ")
    lines[release_start:release_end] = release_lines
    registry.write_text("".join(lines), encoding="utf-8")


def find_pack(lines: list[str], pack_name: str) -> tuple[int, int]:
    pack_starts = [index for index, line in enumerate(lines) if PACK_HEADER_RE.match(line)]
    for offset, start in enumerate(pack_starts):
        end = pack_starts[offset + 1] if offset + 1 < len(pack_starts) else len(lines)
        name = field_value(lines[start:end], "name")
        if name == pack_name:
            return start, end
    raise ValueError(f'pack "{pack_name}" not found')


def find_release(lines: list[str], pack_start: int, pack_end: int, version: str) -> tuple[int, int]:
    release_starts = [
        index for index in range(pack_start, pack_end) if RELEASE_HEADER_RE.match(lines[index])
    ]
    for offset, start in enumerate(release_starts):
        end = release_starts[offset + 1] if offset + 1 < len(release_starts) else pack_end
        actual = field_value(lines[start:end], "version")
        if actual == version:
            return start, end
    raise ValueError(f'release "{version}" not found')


def field_value(lines: list[str], key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*\"([^\"]*)\"")
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return None


def replace_field(lines: list[str], start: int, end: int, key: str, value: str, indent: str) -> bool:
    for index in range(start, end):
        match = FIELD_RE.match(lines[index])
        if match and match.group(2) == key:
            lines[index] = f"{indent}{key} = {value}\n"
            return True
    return False


def upsert_field(lines: list[str], key: str, value: str, indent: str) -> list[str]:
    next_lines = list(lines)
    if replace_field(next_lines, 0, len(next_lines), key, value, indent):
        return next_lines

    insert_at = len(next_lines)
    for index, line in enumerate(next_lines):
        match = FIELD_RE.match(line)
        if match and match.group(2) == "description":
            insert_at = index + 1
    next_lines.insert(insert_at, f"{indent}{key} = {value}\n")
    return next_lines


def toml_string(value: str) -> str:
    return json.dumps(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    set_source_parser = subcommands.add_parser("set-source")
    set_source_parser.add_argument("--registry", default="registry.toml")
    set_source_parser.add_argument("--pack", required=True)
    set_source_parser.add_argument("--source", required=True)

    withdraw_parser = subcommands.add_parser("withdraw")
    withdraw_parser.add_argument("--registry", default="registry.toml")
    withdraw_parser.add_argument("--pack", required=True)
    withdraw_parser.add_argument("--version", required=True)
    withdraw_parser.add_argument("--reason", required=True)

    args = parser.parse_args()
    if args.command == "set-source":
        set_source(Path(args.registry), args.pack, args.source)
    elif args.command == "withdraw":
        withdraw(Path(args.registry), args.pack, args.version, args.reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
