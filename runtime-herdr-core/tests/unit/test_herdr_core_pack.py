"""Pack-level guards: the manifest gc composes, and the runtime's discipline
(stdlib only, Python 3.9 syntax, env read in one place)."""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

import pytest

from gc_runtime_herdr_core import PACK_NAME, PACK_VERSION, RUNTIME_NAME

PACK_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = PACK_ROOT / "assets" / "gc_runtime_herdr_core"
ENTRY = PACK_ROOT / "assets" / "bin" / "gc-runtime-herdr-core"
SCRIPTS = (ENTRY,)


def source_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def runtime_sources() -> Iterator[Tuple[Path, ast.Module]]:
    for path in [*sorted(PACKAGE.rglob("*.py")), *SCRIPTS]:
        yield path, ast.parse(source_text(path), filename=str(path))


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
        ast.parse(source_text(path), filename=str(path), feature_version=(3, 9))


def test_every_module_postpones_annotations() -> None:
    missing = []
    for path, tree in runtime_sources():
        if path in SCRIPTS:
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


CODE_SCANNING_PASSWORD_NAME = re.compile(
    r"(?is).*(pass(wd|word|code|.?phrase)(?!.*question)|(auth(entication|ori[sz]ation)?).?key|oauth|"
    r"api.?(key|tok)|([_-]|\b)mfa([_-]|\b)).*"
)
"""CodeQL's ``maybePassword`` name heuristic (codeql ``SensitiveDataHeuristics.qll``)."""


def test_no_name_looks_like_a_password_to_code_scanning() -> None:
    # The runtime hashes paths and keys with SHA-256 (city id, hc session).
    # Code scanning classifies as a password whatever comes from a function,
    # parameter, variable or attribute whose name matches its heuristic, or
    # from a lookup by such a string key, and a password reaching SHA-256 is
    # a merge-blocking alert (py/weak-sensitive-data-hashing). It follows
    # function references, so even a default argument naming such a function
    # counts. No name in the runtime may match.
    found: List[str] = []
    for path, tree in runtime_sources():
        for node in ast.walk(tree):
            names: List[str] = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
            elif isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
            elif isinstance(node, ast.arg):
                names.append(node.arg)
            elif isinstance(node, ast.keyword) and node.arg:
                names.append(node.arg)
            elif isinstance(node, ast.alias):
                names.append(node.asname or node.name)
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                names.append(str(node.slice.value))
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                names.append(str(node.args[0].value))
            found.extend(
                f"{path.relative_to(PACK_ROOT)}:{getattr(node, 'lineno', 0)}: {name}"
                for name in names
                if CODE_SCANNING_PASSWORD_NAME.fullmatch(name)
            )
    assert found == []


def test_the_password_heuristic_is_live() -> None:
    # The guard above is only as good as its pattern: it must catch the name
    # that raised the alert, and the near misses an innocent rename could pick.
    for name in ("password_home", "passwd_home_dir", "get_passphrase", "api_token", "oauth_dir", "auth_key"):
        assert CODE_SCANNING_PASSWORD_NAME.fullmatch(name), name
    for name in ("user_home", "state_root", "session_name", "machine_identity", "city_key", "bypass_cache"):
        assert not CODE_SCANNING_PASSWORD_NAME.fullmatch(name), name


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
