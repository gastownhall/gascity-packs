"""Behavioral tests for the ``rename-symbol`` write-side op.

The op (``astlens/ops/rename_symbol.py``) is a *compile-aware* cross-file
symbol rename — a thin wrapper over gopls's type-aware ``textDocument/rename``,
per "The AST as LLM Lens" sec 5.D. These tests validate its CONTRACT:

  * ``compute_change(file_path, args) -> {relpath: new_content} | None``
  * On a 2-file Go package where ``Foo`` is defined in one file and called in
    another, renaming ``Foo`` -> ``Bar`` returns BOTH files' new content with
    the definition and the call site updated, and both stay ``gofmt -e`` clean.
  * Compile-awareness / safety: a shadowing local variable that merely shares
    the symbol's name is left untouched (a naive textual rename would corrupt
    it).
  * Purity: the op never mutates the real files on disk.
  * Graceful ``None``: non-Go input, missing/invalid args, unknown symbol,
    same-name no-op, and (when gopls is absent) every Go case.

The gopls-backed cases are SKIPPED with a clear message when gopls is not
installed (a best-effort ``go install`` is attempted first). The op import and
the pure ``None`` cases that never reach gopls always run.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess

import pytest

# ---- Import the op by file path (cwd-independent) --------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK = os.path.dirname(_HERE)
_OP_PY = os.path.join(_PACK, "astlens", "ops", "rename_symbol.py")
_FIX = os.path.join(_HERE, "write_fixtures", "rename_symbol")

_spec = importlib.util.spec_from_file_location("ast_lens_rename_symbol", _OP_PY)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


# ---- gopls / go availability ------------------------------------------------
def _ensure_gopls() -> str | None:
    """Path to gopls, attempting a best-effort install if go is present."""
    found = shutil.which("gopls")
    if found:
        return found
    if shutil.which("go"):
        try:
            subprocess.run(
                ["go", "install", "golang.org/x/tools/gopls@latest"],
                capture_output=True,
                text=True,
                timeout=600,
            )
        except (OSError, subprocess.SubprocessError):
            pass
        return shutil.which("gopls")
    return None


_GOPLS = _ensure_gopls()
_HAVE_GOFMT = shutil.which("gofmt") is not None

requires_gopls = pytest.mark.skipif(
    _GOPLS is None,
    reason="gopls not installed and could not be installed (need Go + network); "
    "the gopls-backed Go rename cases are skipped.",
)


# ---- fixture helper ---------------------------------------------------------
@pytest.fixture
def twofile_repo(tmp_path):
    """Copy the 2-file Go package fixture into an isolated git repo.

    git-init'ing the temp dir makes the op's repo-root (git root above the
    file) equal the Go module root, so emitted relpaths are clean basenames
    (``foo.go``, ``caller.go``) and the test is hermetic — independent of the
    pack's own git state. Returns the repo directory path.
    """
    src = os.path.join(_FIX, "twofile_pkg")
    dst = tmp_path / "twofile"
    shutil.copytree(src, dst)
    subprocess.run(["git", "init", "-q"], cwd=dst, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dst, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=dst,
        check=True,
    )
    return dst


def _gofmt_clean(content: str, tmp_path) -> bool:
    """True iff ``content`` is valid Go AND already gofmt-canonical."""
    p = tmp_path / "snippet.go"
    p.write_text(content)
    proc = subprocess.run(
        ["gofmt", "-e", str(p)], capture_output=True, text=True
    )
    return proc.returncode == 0 and proc.stdout == content


# =========================================================================== #
# The headline case: cross-file rename, both files updated, gofmt-clean
# =========================================================================== #
@requires_gopls
def test_cross_file_rename_updates_definition_and_call_site(twofile_repo, tmp_path):
    foo = str(twofile_repo / "foo.go")
    res = rs.compute_change(foo, {"symbol": "Foo", "new-name": "Bar"})

    assert res is not None, "rename of an exported func used cross-file must succeed"
    # BOTH files are returned — the definition file and the caller file.
    assert set(res.keys()) == {"foo.go", "caller.go"}, res.keys()

    # Definition site updated (func + its doc comment), call site updated.
    assert "func Bar(name string) string" in res["foo.go"]
    assert "func Foo" not in res["foo.go"]
    assert 'return Bar("world")' in res["caller.go"]
    assert "Foo(" not in res["caller.go"]

    # Both produced files are gofmt-clean (and gofmt-stable).
    if _HAVE_GOFMT:
        assert _gofmt_clean(res["foo.go"], tmp_path)
        assert _gofmt_clean(res["caller.go"], tmp_path)


@requires_gopls
def test_rename_is_pure_does_not_touch_disk(twofile_repo):
    foo = str(twofile_repo / "foo.go")
    before_foo = (twofile_repo / "foo.go").read_text()
    before_caller = (twofile_repo / "caller.go").read_text()

    res = rs.compute_change(foo, {"symbol": "Foo", "new-name": "Bar"})
    assert res is not None

    # The op returns new content but must NOT have written anything.
    assert (twofile_repo / "foo.go").read_text() == before_foo
    assert (twofile_repo / "caller.go").read_text() == before_caller
    assert "func Foo" in before_foo  # sanity: original still defines Foo


@requires_gopls
def test_new_name_underscore_alias_accepted(twofile_repo):
    """The contract names the arg ``new-name``; ``new_name`` is also accepted."""
    foo = str(twofile_repo / "foo.go")
    res = rs.compute_change(foo, {"symbol": "Foo", "new_name": "Bar"})
    assert res is not None
    assert "func Bar(name string) string" in res["foo.go"]


@requires_gopls
def test_explicit_line_col_disambiguates(twofile_repo):
    """An explicit (line, col) pins the symbol without the name-resolution step."""
    foo = str(twofile_repo / "foo.go")
    # `func Foo` starts at foo.go:4:6 (1-based).
    res = rs.compute_change(
        foo, {"symbol": "Foo", "new-name": "Baz", "line": 4, "col": 6}
    )
    assert res is not None
    assert set(res.keys()) == {"foo.go", "caller.go"}
    assert "func Baz(name string) string" in res["foo.go"]
    assert 'return Baz("world")' in res["caller.go"]


# =========================================================================== #
# Compile-awareness / semantic safety: shadowing local var is NOT renamed
# =========================================================================== #
@requires_gopls
def test_shadowing_local_var_is_not_renamed(tmp_path):
    """Renaming a package-level func must leave a same-named LOCAL var intact.

    This is the property a naive textual rename cannot guarantee and the whole
    reason the op delegates to a type-aware language server.
    """
    repo = tmp_path / "amb"
    repo.mkdir()
    (repo / "go.mod").write_text("module example.com/amb\n\ngo 1.21\n")
    (repo / "s.go").write_text(
        "package amb\n\n"
        "// Count returns a fixed package-level value.\n"
        "func Count() int { return 7 }\n\n"
        "func Total() int {\n"
        "\tCount := 100\n"
        "\treturn Count + 1\n"
        "}\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        cwd=repo,
        check=True,
    )

    res = rs.compute_change(str(repo / "s.go"), {"symbol": "Count", "new-name": "Tally"})
    assert res is not None
    out = res["s.go"]
    assert "func Tally() int" in out, "the package-level func must be renamed"
    assert "func Count" not in out
    # The shadowing local variable and its use must be UNTOUCHED.
    assert "Count := 100" in out
    assert "return Count + 1" in out
    if _HAVE_GOFMT:
        assert _gofmt_clean(out, tmp_path)


# =========================================================================== #
# Graceful None cases (these exercise the contract's "can't do safely -> None")
# =========================================================================== #
@requires_gopls
def test_same_name_is_noop_none(twofile_repo):
    foo = str(twofile_repo / "foo.go")
    assert rs.compute_change(foo, {"symbol": "Foo", "new-name": "Foo"}) is None


@requires_gopls
def test_unknown_symbol_returns_none(twofile_repo):
    foo = str(twofile_repo / "foo.go")
    assert rs.compute_change(foo, {"symbol": "Nope", "new-name": "Bar"}) is None


@requires_gopls
def test_invalid_new_identifier_returns_none(twofile_repo):
    foo = str(twofile_repo / "foo.go")
    # Not a valid Go identifier.
    assert rs.compute_change(foo, {"symbol": "Foo", "new-name": "2bad"}) is None
    # A reserved keyword — gopls itself rejects this; op surfaces it as None.
    assert rs.compute_change(foo, {"symbol": "Foo", "new-name": "func"}) is None


# --- These need no gopls (they short-circuit before invoking it) -------------
def test_non_go_file_returns_none(tmp_path):
    py = tmp_path / "x.py"
    py.write_text("def f():\n    return 1\n")
    assert rs.compute_change(str(py), {"symbol": "f", "new-name": "g"}) is None


def test_missing_symbol_arg_returns_none(tmp_path):
    go = tmp_path / "a.go"
    go.write_text("package a\n\nfunc Foo() {}\n")
    assert rs.compute_change(str(go), {"new-name": "Bar"}) is None


def test_missing_new_name_arg_returns_none(tmp_path):
    go = tmp_path / "a.go"
    go.write_text("package a\n\nfunc Foo() {}\n")
    assert rs.compute_change(str(go), {"symbol": "Foo"}) is None


def test_invalid_symbol_identifier_returns_none(tmp_path):
    go = tmp_path / "a.go"
    go.write_text("package a\n\nfunc Foo() {}\n")
    assert rs.compute_change(str(go), {"symbol": "1bad", "new-name": "Bar"}) is None


def test_empty_args_returns_none(tmp_path):
    go = tmp_path / "a.go"
    go.write_text("package a\n\nfunc Foo() {}\n")
    assert rs.compute_change(str(go), {}) is None


def test_nonexistent_file_returns_none(tmp_path):
    missing = str(tmp_path / "ghost.go")
    assert rs.compute_change(missing, {"symbol": "Foo", "new-name": "Bar"}) is None


def test_no_go_mod_returns_none(tmp_path):
    """A loose .go file with no enclosing go.mod is out of scope -> None."""
    if _GOPLS is None:
        pytest.skip("gopls not installed; the go.mod gate is exercised regardless "
                    "but assert the safe None either way")
    go = tmp_path / "loose.go"
    go.write_text("package loose\n\nfunc Foo() {}\n")
    # No go.mod anywhere above tmp_path -> _module_root is None -> None.
    assert rs.compute_change(str(go), {"symbol": "Foo", "new-name": "Bar"}) is None


# ---- unit coverage of the diff-application core (no gopls needed) -----------
def test_apply_hunks_roundtrip():
    """The unified-diff applier reconstructs the post-edit file from originals."""
    original = "package p\n\nfunc Foo() int {\n\treturn 1\n}\n"
    body = [
        "@@ -1,5 +1,5 @@",
        " package p",
        " ",
        "-func Foo() int {",
        "+func Bar() int {",
        "\treturn 1",   # context line (gopls omits the leading space on some)
        " }",
    ]
    # Normalise: the line above is genuine context; mark it as such.
    body[5] = " \treturn 1"
    out = rs._apply_hunks(original, body)
    assert out == "package p\n\nfunc Bar() int {\n\treturn 1\n}\n"


def test_apply_hunks_rejects_mismatched_context():
    """If the diff's context does not match the original, refuse (return None)."""
    original = "package p\n\nfunc Foo() {}\n"
    body = [
        "@@ -1,3 +1,3 @@",
        " package DIFFERENT",   # context that does NOT match the original
        " ",
        "-func Foo() {}",
        "+func Bar() {}",
    ]
    assert rs._apply_hunks(original, body) is None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
