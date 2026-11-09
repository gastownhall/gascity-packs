"""Pack-level guards: the manifest gc composes, and the runtime's discipline
(stdlib only, Python 3.9 syntax, env read in one place)."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Iterator, Tuple

import pytest

from gc_runtime_herdr_core import PACK_NAME, PACK_VERSION, RUNTIME_NAME

PACK_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = PACK_ROOT / "assets" / "gc_runtime_herdr_core"
ENTRY = PACK_ROOT / "assets" / "bin" / "gc-runtime-herdr-core"


def runtime_sources() -> Iterator[Tuple[Path, ast.Module]]:
    for path in sorted(PACKAGE.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    yield ENTRY, ast.parse(ENTRY.read_text(encoding="utf-8"), filename=str(ENTRY))


def test_manifest_declares_the_herdr_core_runtime() -> None:
    tomllib = pytest.importorskip("tomllib")  # 3.11+; the 3.12 lanes run it
    manifest = tomllib.loads((PACK_ROOT / "pack.toml").read_text(encoding="utf-8"))
    assert manifest["pack"] == {"name": PACK_NAME, "version": PACK_VERSION, "schema": 2}
    assert PACK_ROOT.name == PACK_NAME
    runtimes = manifest["runtimes"]
    # `herdr` is a gc builtin: declaring it is a composition error (RUNTIME-SEL-007).
    assert list(runtimes) == [RUNTIME_NAME] == ["herdr-core"]
    assert runtimes["herdr-core"] == {
        "command": "assets/bin/gc-runtime-herdr-core",
        "protocol": 0,
        "prompt_delivery": "nudge-fallback",
    }
    assert (PACK_ROOT / runtimes["herdr-core"]["command"]).resolve() == ENTRY.resolve()


def test_no_top_level_scripts_dir() -> None:
    # gascity docs/reference/specs/pack-spec.md "Directory Rules" bans a
    # top-level scripts/ in new packs.
    assert not (PACK_ROOT / "scripts").exists()


def test_runtime_imports_only_the_standard_library() -> None:
    names = getattr(sys, "stdlib_module_names", None)  # 3.10+
    if names is None:
        pytest.skip("sys.stdlib_module_names is 3.10+; the 3.12 lanes run this")
    stdlib = set(names)
    offenders = []
    for path, tree in runtime_sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                if top not in stdlib and top != "gc_runtime_herdr_core":
                    offenders.append(f"{path.relative_to(PACK_ROOT)}: {name}")
    assert offenders == []


def test_runtime_parses_as_python_3_9() -> None:
    for path, _ in runtime_sources():
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))


def test_every_module_postpones_annotations() -> None:
    missing = []
    for path, tree in runtime_sources():
        if path == ENTRY:
            continue
        futures = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "__future__"
            for alias in node.names
        }
        if "annotations" not in futures:
            missing.append(str(path.relative_to(PACK_ROOT)))
    assert missing == []


def test_only_main_reads_the_process_environment() -> None:
    # Handlers take an OpRequest that the per-op runner builds from
    # os.environ once. Anything else reading the environment would answer
    # differently under a transport that builds requests another way.
    readers = []
    for path, tree in runtime_sources():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in ("environ", "environb", "getenv", "putenv", "unsetenv")
            ):
                readers.append(str(path.relative_to(PACK_ROOT)))
    assert sorted(set(readers)) == [os.path.join("assets", "gc_runtime_herdr_core", "main.py")]
