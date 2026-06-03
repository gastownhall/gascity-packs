"""Behavioral tests for the fix-imports write-side op.

These tests validate ``astlens/ops/fix_imports.py`` against the shared
write-side contract from "The AST as LLM Lens" (sec 5.5 plan/execute, sec 5.D
op catalogue):

    compute_change(file_path, args) -> {relpath: new_full_content} | None

The op re-canonicalises a single file's imports — dropping unused imports and
sorting the rest — by wrapping the language's battle-tested formatter
(goimports/gofmt for Go, ruff/autoflake+isort for Python), exactly as the
paper wraps the LSP for rename. This is a behavioral suite: it asserts the op
*behaves* as specified, not that it matches any reference byte-for-byte. It
never writes the real fixture files.

When the relevant formatter is not installed, the corresponding test SKIPS
with a clear reason rather than failing — the code path is still exercised for
correctness via the explicit tool-missing test below.
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import shutil
import subprocess

import pytest

# ---- Import the op by file path (cwd-independent, like the outline suite) -- #
_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK = os.path.dirname(_HERE)
_OP_PY = os.path.join(_PACK, "astlens", "ops", "fix_imports.py")
_FIX = os.path.join(_HERE, "write_fixtures", "fix_imports")

_spec = importlib.util.spec_from_file_location("astlens_ops_fix_imports", _OP_PY)
fi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fi)


def fx(name: str) -> str:
    return os.path.join(_FIX, name)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# Tool availability — drives skips so the suite is green on any machine while
# still exercising the real formatter when it is present.
_HAS_GO = shutil.which("goimports") is not None or shutil.which("gofmt") is not None
_HAS_GOIMPORTS = shutil.which("goimports") is not None
_HAS_RUFF = shutil.which("ruff") is not None
_HAS_PY = _HAS_RUFF or (
    shutil.which("autoflake") is not None or shutil.which("isort") is not None
)


# --------------------------------------------------------------------------- #
# Go: unused import removed, imports sorted, result still parses
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_GO, reason="no goimports/gofmt on PATH")
def test_go_unused_import_removed_and_sorted():
    src = fx("messy.go")
    original = _read(src)
    result = fi.compute_change(src, {})

    assert result is not None, "messy.go has an unused import; expected a change"
    assert list(result.keys()) == [_relpath(src)], "op must return exactly the one file"
    new = result[_relpath(src)]

    # The op is pure: the real fixture on disk is untouched.
    assert _read(src) == original, "compute_change must NOT mutate the real file"

    # goimports drops the unused `os` import; gofmt (fallback) only sorts, so we
    # only assert removal when goimports is the active tool.
    if _HAS_GOIMPORTS:
        assert '"os"' not in new, "unused `os` import should be removed"
    # `fmt` must sort before `strings` regardless of which tool ran.
    assert new.index('"fmt"') < new.index('"strings"'), "imports should be sorted"

    # The result still parses: gofmt -e returns 0 and emits the formatted file.
    rc = _gofmt_check(new)
    assert rc == 0, "rewritten Go must be gofmt -e clean (still parses)"


# --------------------------------------------------------------------------- #
# Python: unused import removed, imports sorted, result still compiles
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_PY, reason="no ruff/autoflake/isort available")
def test_py_unused_import_removed_and_sorted(tmp_path):
    src = fx("messy.py")
    original = _read(src)
    result = fi.compute_change(src, {})

    assert result is not None, "messy.py has unused imports; expected a change"
    assert list(result.keys()) == [_relpath(src)], "op must return exactly the one file"
    new = result[_relpath(src)]

    # Purity: the real fixture is untouched.
    assert _read(src) == original, "compute_change must NOT mutate the real file"

    # Unused `sys` and `OrderedDict` import statements are gone; the used `os`
    # survives. Match on import *statements* (the names also appear in the
    # fixture's docstring prose, which must remain untouched).
    import_lines = [
        ln for ln in new.splitlines() if ln.startswith(("import ", "from "))
    ]
    joined = "\n".join(import_lines)
    assert "import sys" not in joined, "unused `sys` import should be removed"
    assert "OrderedDict" not in joined, "unused `OrderedDict` import should be removed"
    assert "import os" in joined, "the used `os` import must be retained"

    # Still compiles: write the *returned* content to a temp file and byte-compile.
    out = tmp_path / "out.py"
    out.write_text(new, encoding="utf-8")
    py_compile.compile(str(out), doraise=True)  # raises PyCompileError on failure


# --------------------------------------------------------------------------- #
# Already-canonical files → None (nothing to change)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_GO, reason="no goimports/gofmt on PATH")
def test_go_canonical_returns_none():
    assert fi.compute_change(fx("canonical.go"), {}) is None


@pytest.mark.skipif(not _HAS_PY, reason="no ruff/autoflake/isort available")
def test_py_canonical_returns_none():
    assert fi.compute_change(fx("canonical.py"), {}) is None


# --------------------------------------------------------------------------- #
# Unsupported language → None (op only handles Go + Python)
# --------------------------------------------------------------------------- #
def test_unsupported_language_returns_none(tmp_path):
    ts = tmp_path / "thing.ts"
    ts.write_text("import {a} from 'b'\nimport {z} from 'y'\n", encoding="utf-8")
    assert fi.compute_change(str(ts), {}) is None


def test_missing_file_returns_none(tmp_path):
    assert fi.compute_change(str(tmp_path / "nope.py"), {}) is None


# --------------------------------------------------------------------------- #
# Tool-missing path → None gracefully (simulate by hiding tools from PATH so
# shutil.which() finds nothing, without depending on whether a tool is really
# installed).
# --------------------------------------------------------------------------- #
def test_go_tool_missing_returns_none(monkeypatch):
    monkeypatch.setattr(fi.shutil, "which", lambda _name: None)
    # With no goimports/gofmt discoverable, a messy Go file yields no change.
    assert fi.compute_change(fx("messy.go"), {}) is None


def test_py_tool_missing_returns_none(monkeypatch):
    monkeypatch.setattr(fi.shutil, "which", lambda _name: None)
    # With no ruff/autoflake/isort discoverable, a messy Python file yields none.
    assert fi.compute_change(fx("messy.py"), {}) is None


def test_args_is_ignored(monkeypatch):
    """args is accepted and ignored — a bogus args dict changes nothing."""
    monkeypatch.setattr(fi.shutil, "which", lambda _name: None)
    # Whatever junk is in args, with no tool the op returns None (and never
    # raises on the args shape).
    assert fi.compute_change(fx("messy.py"), {"anything": [1, 2, 3]}) is None


# --------------------------------------------------------------------------- #
# relpath: returned key is relative to the git root above the file.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_PY, reason="no ruff/autoflake/isort available")
def test_relpath_is_repo_relative():
    src = fx("messy.py")
    result = fi.compute_change(src, {})
    assert result is not None
    (key,) = result.keys()
    # The pack is a git repo; the key must be the path of the fixture relative
    # to the git root, using forward slashes, and must round-trip back to the
    # same file on disk.
    assert key == "tests/write_fixtures/fix_imports/messy.py"
    assert not os.path.isabs(key)


@pytest.mark.skipif(not _HAS_PY, reason="no ruff/autoflake/isort available")
def test_relpath_falls_back_to_dir_outside_git(tmp_path):
    """Outside any git repo, relpath is taken against the file's own dir.

    pytest's ``tmp_path`` lives under the system temp dir, which is not a git
    worktree, so ``_repo_root`` cannot find a ``--show-toplevel`` and falls
    back to the file's own directory — making the returned relpath the bare
    basename.
    """
    if subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    ).returncode == 0:
        pytest.skip("temp dir is unexpectedly inside a git repo")

    target = tmp_path / "messy.py"
    target.write_text(_read(fx("messy.py")), encoding="utf-8")
    result = fi.compute_change(str(target), {})
    assert result is not None
    (key,) = result.keys()
    # File's own dir is the root, so the relpath is just the basename.
    assert key == "messy.py"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _relpath(path: str) -> str:
    """The relpath the op should return for a fixture inside this git repo."""
    root = subprocess.run(
        ["git", "-C", os.path.dirname(os.path.abspath(path)),
         "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    ).stdout.strip()
    return os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")


def _gofmt_check(content: str) -> int:
    """Run `gofmt -e` over content via stdin; return the exit code."""
    tool = shutil.which("gofmt") or shutil.which("goimports")
    proc = subprocess.run([tool, "-e"], input=content, capture_output=True, text=True)
    return proc.returncode
