"""Behavioural tests for the ``extract-to-package`` write-side op.

The op (``astlens/ops/extract_to_package.py``) lifts a single exported top-level
Go declaration into a brand-new sibling package and qualifies references within
the original package. These tests validate the *contract* — what
``compute_change`` returns — not any reference implementation.

Method: each test copies a fixture (or a tiny inline source tree) into a
``tmp_path`` sandbox and calls ``compute_change`` on the copy. The op reads
sibling ``.go`` files and the enclosing ``go.mod`` from the real filesystem, so
the sandbox makes the test hermetic and side-effect-free (the op itself never
writes — it only returns ``{relpath: content}``).

Every emitted Go file is asserted ``gofmt -e`` clean (parses + is canonically
formatted). Where ``go`` is available the applied result is additionally
``go build``-checked, so the change is proven to compile, not merely parse.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess

import pytest

# ---- Import the op by file path (cwd-independent, mirrors test_outline.py) --
_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK = os.path.dirname(_HERE)
_OP_PY = os.path.join(_PACK, "astlens", "ops", "extract_to_package.py")
_FIX = os.path.join(_HERE, "write_fixtures", "extract_to_package")

_spec = importlib.util.spec_from_file_location("astlens_extract_to_package", _OP_PY)
ep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ep)


# --------------------------------------------------------------------------- #
# Tooling availability — gofmt is required by the op; go build is a bonus.
# --------------------------------------------------------------------------- #
def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


requires_gofmt = pytest.mark.skipif(
    not _have("gofmt"), reason="gofmt not on PATH (the op requires it)"
)


def _gofmt_clean(content: str) -> bool:
    """True if ``content`` is byte-for-byte what ``gofmt -e`` produces (i.e. it
    parses AND is already canonically formatted)."""
    proc = subprocess.run(
        ["gofmt"], input=content.encode("utf-8"), capture_output=True
    )
    return proc.returncode == 0 and proc.stdout.decode("utf-8") == content


def _go_build(root: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["go", "build", "./..."], cwd=root, capture_output=True, text=True
    )
    return proc.returncode, proc.stderr.strip()


# --------------------------------------------------------------------------- #
# Sandbox helpers
# --------------------------------------------------------------------------- #
def _copy_fixture(name: str, tmp_path) -> str:
    """Copy ``write_fixtures/extract_to_package/<name>`` into the sandbox and
    return the destination directory."""
    dst = os.path.join(str(tmp_path), name)
    shutil.copytree(os.path.join(_FIX, name), dst)
    return dst


def _write_tree(tmp_path, files: dict[str, str]) -> str:
    """Materialise an inline ``{relpath: content}`` Go source tree; return the
    root directory."""
    root = os.path.join(str(tmp_path), "tree")
    for rel, content in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
    return root


def _apply_and_build(src_root: str, result: dict[str, str], tmp_path,
                     tag: str) -> tuple[int, str]:
    """Copy ``src_root`` fresh, overlay the op's result, and ``go build`` it."""
    build = os.path.join(str(tmp_path), f"build-{tag}")
    shutil.copytree(src_root, build)
    for rel, content in result.items():
        p = os.path.join(build, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
    return _go_build(build)


_GOMOD = "module example.com/m\n\ngo 1.21\n"


# =====================================================================
# The headline supported case (from the task spec): move an exported
# free function `Helper` into a new `helpers` package.
# =====================================================================
@requires_gofmt
class TestBasicExtract:
    def _run(self, tmp_path):
        proj = _copy_fixture("basic", tmp_path)
        res = ep.compute_change(
            os.path.join(proj, "util.go"),
            {"symbol": "Helper", "target": "helpers"},
        )
        assert res is not None, f"expected a change, got None ({ep.last_reason})"
        return proj, res

    def test_returns_all_three_files(self, tmp_path):
        _, res = self._run(tmp_path)
        assert set(res.keys()) == {"util.go", "main.go", "helpers/helper.go"}, (
            f"unexpected file set: {sorted(res)}"
        )

    def test_new_package_file_has_moved_func_and_package_clause(self, tmp_path):
        _, res = self._run(tmp_path)
        new = res["helpers/helper.go"]
        assert new.startswith("package helpers\n"), new[:40]
        assert "func Helper(s string) string" in new
        # The import the func actually uses is carried over.
        assert '"strings"' in new
        # The func's doc comment travels with it.
        assert "Helper upper-cases" in new

    def test_source_file_shrinks(self, tmp_path):
        _, res = self._run(tmp_path)
        util = res["util.go"]
        # The moved declaration (and its doc) is gone...
        assert "func Helper" not in util
        assert "Helper upper-cases" not in util
        # ...but the unexported sibling that stays behind is untouched.
        assert "func stays()" in util
        # The now-orphaned import is pruned (else util.go would not compile).
        assert '"strings"' not in util

    def test_caller_is_qualified_and_imports_new_package(self, tmp_path):
        _, res = self._run(tmp_path)
        main = res["main.go"]
        assert "helpers.Helper(" in main, "call site not qualified"
        assert "Helper(" not in main.replace("helpers.Helper(", ""), (
            "an unqualified Helper( call survived"
        )
        # The new package is imported by its full module path.
        assert '"example.com/widget/helpers"' in main
        # The unexported sibling call is left alone (it stayed in-package).
        assert "stays()" in main and "helpers.stays" not in main

    def test_every_returned_file_is_gofmt_clean(self, tmp_path):
        _, res = self._run(tmp_path)
        for rel, content in res.items():
            assert _gofmt_clean(content), f"{rel} is not gofmt -e clean"

    @pytest.mark.skipif(not _have("go"), reason="go toolchain not on PATH")
    def test_applied_result_compiles(self, tmp_path):
        proj, res = self._run(tmp_path)
        rc, err = _apply_and_build(proj, res, tmp_path, "basic")
        assert rc == 0, f"applied change did not compile: {err}"

    def test_op_does_not_write_files(self, tmp_path):
        # The op is pure: calling it must not create the target package on disk
        # nor modify the source files.
        proj, _ = self._run(tmp_path)
        assert not os.path.exists(os.path.join(proj, "helpers")), (
            "compute_change must not create the target directory"
        )
        on_disk = open(os.path.join(proj, "util.go"), encoding="utf-8").read()
        assert "func Helper" in on_disk, "source file on disk was mutated"


# =====================================================================
# Additional supported shapes: a type+its methods, a const, a var.
# =====================================================================
@requires_gofmt
class TestSupportedShapes:
    def test_type_with_methods_moves_together(self, tmp_path):
        files = {
            "go.mod": _GOMOD,
            "a.go": (
                "package m\n\n"
                "import \"fmt\"\n\n"
                "// Widget is a thing.\n"
                "type Widget struct {\n\tName string\n}\n\n"
                "func (w *Widget) Show() string { return fmt.Sprintf(\"%s\", w.Name) }\n\n"
                "func (w Widget) Plain() string { return w.Name }\n"
            ),
            "b.go": (
                "package m\n\n"
                "func use() string {\n"
                "\tw := Widget{Name: \"x\"}\n"
                "\treturn w.Show() + w.Plain()\n"
                "}\n"
            ),
        }
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Widget", "target": "model"}
        )
        assert res is not None, ep.last_reason
        new = res["model/widget.go"]
        assert "type Widget struct" in new
        # Both methods on the type travel with it.
        assert "func (w *Widget) Show()" in new
        assert "func (w Widget) Plain()" in new
        # The composite-literal type reference is qualified...
        assert "model.Widget{Name:" in res["b.go"]
        # ...but the method-call selectors are NOT (they hang off the value `w`).
        assert "w.Show()" in res["b.go"] and "w.Plain()" in res["b.go"]
        for rel, content in res.items():
            assert _gofmt_clean(content), f"{rel} not gofmt clean"

    def test_const_moves(self, tmp_path):
        files = {
            "go.mod": _GOMOD,
            "a.go": "package m\n\nconst MaxSize = 1024\n",
            "b.go": "package m\n\nfunc cap2() int { return MaxSize * 2 }\n",
        }
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "MaxSize", "target": "consts"}
        )
        assert res is not None, ep.last_reason
        assert "const MaxSize = 1024" in res["consts/maxsize.go"]
        assert "consts.MaxSize" in res["b.go"]
        assert "const MaxSize" not in res["a.go"]
        for rel, content in res.items():
            assert _gofmt_clean(content), f"{rel} not gofmt clean"

    def test_var_moves_with_its_import(self, tmp_path):
        files = {
            "go.mod": _GOMOD,
            "a.go": "package m\n\nimport \"errors\"\n\nvar ErrNope = errors.New(\"nope\")\n",
            "b.go": "package m\n\nfunc f() error { return ErrNope }\n",
        }
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "ErrNope", "target": "errs"}
        )
        assert res is not None, ep.last_reason
        new = res["errs/errnope.go"]
        assert "var ErrNope = errors.New" in new
        assert '"errors"' in new, "the import the var uses must be carried"
        assert "errs.ErrNope" in res["b.go"]
        for rel, content in res.items():
            assert _gofmt_clean(content), f"{rel} not gofmt clean"

    @pytest.mark.skipif(not _have("go"), reason="go toolchain not on PATH")
    def test_supported_shapes_compile(self, tmp_path):
        files = {
            "go.mod": _GOMOD,
            "a.go": (
                "package m\n\nimport \"fmt\"\n\n"
                "type Widget struct{ Name string }\n\n"
                "func (w *Widget) Show() string { return fmt.Sprintf(\"%s\", w.Name) }\n"
            ),
            "b.go": "package m\n\nfunc use() string { return (&Widget{}).Show() }\n",
        }
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Widget", "target": "model"}
        )
        assert res is not None, ep.last_reason
        rc, err = _apply_and_build(root, res, tmp_path, "shapes")
        assert rc == 0, f"did not compile: {err}"


# =====================================================================
# Decline cases — the op returns None (safely) and records a reason.
# =====================================================================
class TestDeclines:
    def test_unexported_symbol_returns_none(self, tmp_path):
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nfunc helper() string { return \"x\" }\n"}
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "helper", "target": "h"}
        )
        assert res is None
        assert "unexported" in (ep.last_reason or "")

    def test_non_go_input_returns_none(self, tmp_path):
        p = os.path.join(str(tmp_path), "a.py")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("def helper():\n    return 'x'\n")
        res = ep.compute_change(p, {"symbol": "helper", "target": "h"})
        assert res is None
        assert "non-Go" in (ep.last_reason or "")

    def test_method_on_staying_type_returns_none(self, tmp_path):
        files = {
            "go.mod": _GOMOD,
            "a.go": "package m\n\ntype T struct{}\n\nfunc (t T) Show() string { return \"\" }\n",
        }
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Show", "target": "h"}
        )
        assert res is None
        assert "method" in (ep.last_reason or "")

    def test_unexported_dependency_returns_none(self, tmp_path):
        files = {
            "go.mod": _GOMOD,
            "a.go": (
                "package m\n\n"
                "func secret() int { return 1 }\n\n"
                "func Public() int { return secret() }\n"
            ),
        }
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Public", "target": "h"}
        )
        assert res is None
        assert "unexported package symbol" in (ep.last_reason or "")

    def test_symbol_not_found_returns_none(self, tmp_path):
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nfunc Other() {}\n"}
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Missing", "target": "h"}
        )
        assert res is None
        assert "not found" in (ep.last_reason or "")

    def test_grouped_const_block_returns_none(self, tmp_path):
        # A grouped `const (...)` is not a single-name decl → out of scope.
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nconst (\n\tA = 1\n\tB = 2\n)\n"}
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "A", "target": "h"}
        )
        assert res is None

    def test_target_directory_exists_returns_none(self, tmp_path):
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nfunc Pub() {}\n", "h/keep.go": "package h\n"}
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Pub", "target": "h"}
        )
        assert res is None
        assert "already exists" in (ep.last_reason or "")

    def test_target_with_path_separator_returns_none(self, tmp_path):
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nfunc Pub() {}\n"}
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Pub", "target": "sub/pkg"}
        )
        assert res is None
        assert "single new sibling package" in (ep.last_reason or "")

    def test_invalid_target_identifier_returns_none(self, tmp_path):
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nfunc Pub() {}\n"}
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Pub", "target": "2bad"}
        )
        assert res is None
        assert "valid Go package identifier" in (ep.last_reason or "")

    def test_missing_args_returns_none(self, tmp_path):
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nfunc Pub() {}\n"}
        root = _write_tree(tmp_path, files)
        assert ep.compute_change(os.path.join(root, "a.go"), {}) is None
        assert ep.compute_change(os.path.join(root, "a.go"), {"symbol": "Pub"}) is None
        assert ep.compute_change(os.path.join(root, "a.go"), {"target": "h"}) is None

    def test_parse_error_source_returns_none(self, tmp_path):
        files = {"go.mod": _GOMOD, "a.go": "package m\n\nfunc Pub( {\n"}  # broken
        root = _write_tree(tmp_path, files)
        res = ep.compute_change(
            os.path.join(root, "a.go"), {"symbol": "Pub", "target": "h"}
        )
        assert res is None


# =====================================================================
# Repo-relative path computation (git root above file_path, else its dir).
# =====================================================================
@requires_gofmt
class TestRelpaths:
    def test_paths_are_relative_to_git_root(self, tmp_path):
        # With a .git marker at the project root and the package one level down,
        # returned relpaths must be rooted at the git root (e.g. `pkg/util.go`).
        root = os.path.join(str(tmp_path), "repo")
        os.makedirs(os.path.join(root, ".git"))
        pkg = os.path.join(root, "pkg")
        os.makedirs(pkg)
        with open(os.path.join(root, "go.mod"), "w") as fh:
            fh.write("module example.com/r\n\ngo 1.21\n")
        with open(os.path.join(pkg, "util.go"), "w") as fh:
            fh.write("package pkg\n\nimport \"strings\"\n\nfunc Up(s string) string { return strings.ToUpper(s) }\n")
        with open(os.path.join(pkg, "main.go"), "w") as fh:
            fh.write("package pkg\n\nfunc Run() string { return Up(\"x\") }\n")
        res = ep.compute_change(
            os.path.join(pkg, "util.go"), {"symbol": "Up", "target": "strs"}
        )
        assert res is not None, ep.last_reason
        # Source + caller are under pkg/; the new package is pkg/strs/.
        assert "pkg/util.go" in res
        assert "pkg/main.go" in res
        assert "pkg/strs/up.go" in res
        # The import path reflects the package's position under the module.
        assert '"example.com/r/pkg/strs"' in res["pkg/main.go"]

    def test_paths_fall_back_to_file_dir_without_git(self, tmp_path):
        # No .git anywhere → relpaths are rooted at the source file's directory.
        root = os.path.join(str(tmp_path), "nogit")
        os.makedirs(root)
        with open(os.path.join(root, "go.mod"), "w") as fh:
            fh.write("module example.com/n\n\ngo 1.21\n")
        with open(os.path.join(root, "util.go"), "w") as fh:
            fh.write("package n\n\nfunc Pub() int { return 1 }\n")
        with open(os.path.join(root, "main.go"), "w") as fh:
            fh.write("package n\n\nfunc Run() int { return Pub() }\n")
        res = ep.compute_change(
            os.path.join(root, "util.go"), {"symbol": "Pub", "target": "p"}
        )
        assert res is not None, ep.last_reason
        assert "util.go" in res and "main.go" in res and "p/pub.go" in res
