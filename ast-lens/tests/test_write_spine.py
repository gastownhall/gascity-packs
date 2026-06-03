"""Behavioral suite for the ast-lens write-side spine.

Covers the shared write-side contract end-to-end:

  - gate ACCEPTS a syntactically-clean change (py / go / js).
  - gate REJECTS a change that introduces a syntax error (broken .py and .go).
  - gate REJECTS when no checker is available for the language (false-negative
    -only: unknown extension, and .ts when tsc is absent).
  - gate NEVER touches the real tree (a reject leaves disk untouched).
  - plan token detects drift: editing the file after planning makes execute
    abort "stale plan" and write nothing.
  - execute WRITES iff verdict == accept (file modified on accept, untouched on
    reject).
  - bin/op CLI prints a plan and executes the demo op end-to-end on a temp file.

Run via the pack venv:  .venv/bin/python -m pytest tests/test_write_spine.py -q
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

# Make the pack root importable when pytest is invoked from anywhere.
PACK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACK_ROOT not in sys.path:
    sys.path.insert(0, PACK_ROOT)

from astlens import gate as gate_mod  # noqa: E402
from astlens import plan as plan_mod  # noqa: E402
from astlens import registry as registry_mod  # noqa: E402
from astlens.gate import gate  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "write_fixtures", "spine")
BIN_OP = os.path.join(PACK_ROOT, "bin", "op")

HAVE_GOFMT = shutil.which("gofmt") is not None
HAVE_NODE = shutil.which("node") is not None
HAVE_TSC = shutil.which("tsc") is not None


# --------------------------------------------------------------------------- #
# gate: accepts clean changes
# --------------------------------------------------------------------------- #


def test_gate_accepts_clean_python():
    res = gate({"a.py": "def f(x):\n    return x\n"}, "/tmp")
    assert res["verdict"] == "accept"
    assert "passed" in res["reason"]


@pytest.mark.skipif(not HAVE_GOFMT, reason="gofmt not available")
def test_gate_accepts_clean_go():
    res = gate({"a.go": "package main\n\nfunc X() {}\n"}, "/tmp")
    assert res["verdict"] == "accept"


@pytest.mark.skipif(not HAVE_NODE, reason="node not available")
def test_gate_accepts_clean_js():
    res = gate({"a.js": "const x = 1;\nfunction f() { return x; }\n"}, "/tmp")
    assert res["verdict"] == "accept"


def test_gate_accepts_multi_file_all_clean():
    res = gate(
        {"pkg/a.py": "x = 1\n", "pkg/sub/b.py": "y = 2\n"},
        "/tmp",
    )
    assert res["verdict"] == "accept"
    assert "2 touched files" in res["reason"]


# --------------------------------------------------------------------------- #
# gate: rejects syntax errors
# --------------------------------------------------------------------------- #


def test_gate_rejects_broken_python():
    res = gate({"a.py": "def x(:\n    pass\n"}, "/tmp")
    assert res["verdict"] == "reject"
    assert "py_compile" in res["reason"]


@pytest.mark.skipif(not HAVE_GOFMT, reason="gofmt not available")
def test_gate_rejects_broken_go():
    res = gate({"a.go": "package main\nfunc x( {\n"}, "/tmp")
    assert res["verdict"] == "reject"
    assert "gofmt" in res["reason"]


@pytest.mark.skipif(not HAVE_NODE, reason="node not available")
def test_gate_rejects_broken_js():
    res = gate({"a.js": "function x( {\n"}, "/tmp")
    assert res["verdict"] == "reject"


def test_gate_rejects_one_bad_file_among_clean():
    res = gate({"good.py": "x = 1\n", "bad.py": "def (:\n"}, "/tmp")
    assert res["verdict"] == "reject"


# --------------------------------------------------------------------------- #
# gate: false-negative-only — no checker => reject
# --------------------------------------------------------------------------- #


def test_gate_rejects_unknown_language():
    res = gate({"a.rb": "puts 'hi'\n"}, "/tmp")
    assert res["verdict"] == "reject"
    assert "no syntax checker" in res["reason"]


def test_gate_rejects_extensionless_file():
    res = gate({"Makefile": "all:\n\techo hi\n"}, "/tmp")
    assert res["verdict"] == "reject"
    assert "no syntax checker" in res["reason"]


def test_gate_rejects_empty_changeset():
    res = gate({}, "/tmp")
    assert res["verdict"] == "reject"
    assert "empty" in res["reason"]


@pytest.mark.skipif(HAVE_TSC, reason="tsc IS available; this asserts the no-tsc reject path")
def test_gate_rejects_typescript_when_tsc_absent():
    # Even a perfectly valid .ts file must reject when no checker exists.
    res = gate({"a.ts": "const x: number = 1;\n"}, "/tmp")
    assert res["verdict"] == "reject"
    assert "tsc" in res["reason"] or "syntax check failed" in res["reason"]


def test_checker_matrix_shape():
    # Sanity on the published matrix: the floor languages map to their checkers.
    assert ".py" in gate_mod.CHECKER_MATRIX
    assert ".go" in gate_mod.CHECKER_MATRIX
    for ext in (".js", ".jsx", ".mjs", ".cjs"):
        assert gate_mod.CHECKER_MATRIX[ext][0] == "node --check"
    # Unknown extension has no checker.
    assert gate_mod.checker_for("x.rb") is None
    assert gate_mod.checker_for("x.py") is not None
    # The human-readable matrix mentions the false-negative-only stance.
    desc = gate_mod.describe_matrix()
    assert "false-negative-only" in desc
    assert "REJECT (no checker)" in desc


# --------------------------------------------------------------------------- #
# gate: never touches the real tree
# --------------------------------------------------------------------------- #


def test_gate_does_not_write_real_tree_on_reject(tmp_path):
    # A path that, if the gate wrote relative to repo_root, would clobber a real
    # file. The reject must leave it absent.
    target = tmp_path / "should_not_exist.py"
    res = gate({"should_not_exist.py": "def (:\n"}, str(tmp_path))
    assert res["verdict"] == "reject"
    assert not target.exists(), "gate wrote into the real tree on reject"


def test_gate_does_not_write_real_tree_on_accept(tmp_path):
    target = tmp_path / "also_not_here.py"
    res = gate({"also_not_here.py": "x = 1\n"}, str(tmp_path))
    assert res["verdict"] == "accept"
    # The gate materialises into scratch ONLY; even on accept it writes nothing
    # to repo_root — writing is execute()'s job, not the gate's.
    assert not target.exists(), "gate wrote into the real tree on accept"


# --------------------------------------------------------------------------- #
# demo op: strip_trailing_ws
# --------------------------------------------------------------------------- #


def test_strip_op_returns_none_when_clean(tmp_path):
    f = tmp_path / "clean.py"
    f.write_text("x = 1\ny = 2\n")
    from astlens.ops import strip_trailing_ws

    assert strip_trailing_ws.compute_change(str(f), {}) is None


def test_strip_op_strips_and_preserves_eol(tmp_path):
    f = tmp_path / "dirty.py"
    f.write_text("x = 1   \ny = 2\t\n")
    from astlens.ops import strip_trailing_ws

    changes = strip_trailing_ws.compute_change(str(f), {})
    assert changes is not None
    (relpath, content), = changes.items()
    assert content == "x = 1\ny = 2\n"
    # File itself is NOT written by the op.
    assert f.read_text() == "x = 1   \ny = 2\t\n"


def test_strip_op_returns_none_on_binary(tmp_path):
    f = tmp_path / "blob.py"
    f.write_bytes(b"\x00\x01\xff\xfe trailing  ")
    from astlens.ops import strip_trailing_ws

    assert strip_trailing_ws.compute_change(str(f), {}) is None


# --------------------------------------------------------------------------- #
# plan / token / execute
# --------------------------------------------------------------------------- #


def _make_dirty(tmp_path, name="t.py", body="def f(x):   \n    return x  \n"):
    f = tmp_path / name
    f.write_text(body)
    return f


def test_make_plan_has_token_and_predicted_accept(tmp_path):
    f = _make_dirty(tmp_path)
    plan = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    assert plan["no_change"] is False
    assert plan["token"] and len(plan["token"]) == 64
    assert plan["verdict"]["verdict"] == "accept"


def test_render_plan_five_sections(tmp_path):
    f = _make_dirty(tmp_path)
    plan = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    md = plan_mod.render_plan(plan)
    for section in ("## Target", "## Scope", "## Diff", "## Predicted verdict", "## Plan token"):
        assert section in md, f"missing section {section}"
    assert plan["token"] in md
    assert "```diff" in md


def test_plan_on_clean_file_is_no_change(tmp_path):
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n")
    plan = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    assert plan["no_change"] is True
    assert plan["token"] is None
    md = plan_mod.render_plan(plan)
    assert "no change" in md.lower()


def test_execute_writes_on_accept(tmp_path):
    f = _make_dirty(tmp_path)
    plan = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    res = plan_mod.execute("strip-trailing-ws", str(f), {}, plan["token"])
    assert res["verdict"] == "accept"
    assert f.read_text() == "def f(x):\n    return x\n"
    assert str(f) in [os.path.realpath(p) for p in res["written"]] or any(
        os.path.samefile(p, str(f)) for p in res["written"]
    )


def test_execute_aborts_on_drift_and_writes_nothing(tmp_path):
    f = _make_dirty(tmp_path)
    plan = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    token = plan["token"]
    # Drift: change the file to DIFFERENT dirty content after planning.
    f.write_text("def f(x):   \n    return x  \n    z = 9  \n")
    res = plan_mod.execute("strip-trailing-ws", str(f), {}, token)
    assert res["verdict"] == "reject"
    assert "stale plan" in res["reason"]
    # The drifted file is untouched (still has its trailing whitespace).
    assert f.read_text() == "def f(x):   \n    return x  \n    z = 9  \n"


def test_execute_stale_when_file_becomes_clean(tmp_path):
    f = _make_dirty(tmp_path)
    plan = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    token = plan["token"]
    # Someone else already cleaned the file -> op now declines -> stale.
    f.write_text("def f(x):\n    return x\n")
    res = plan_mod.execute("strip-trailing-ws", str(f), {}, token)
    assert res["verdict"] == "reject"
    assert "stale plan" in res["reason"]


def test_execute_rejects_bad_token(tmp_path):
    f = _make_dirty(tmp_path)
    plan_mod.make_plan("strip-trailing-ws", str(f), {})
    res = plan_mod.execute("strip-trailing-ws", str(f), {}, "deadbeef" * 8)
    assert res["verdict"] == "reject"
    assert "stale plan" in res["reason"]
    # File unchanged.
    assert f.read_text() == "def f(x):   \n    return x  \n"


def test_token_is_content_addressed_and_stable(tmp_path):
    f = _make_dirty(tmp_path)
    p1 = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    p2 = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    assert p1["token"] == p2["token"], "token must be stable for identical state"
    # Token incorporates the op name.
    changes = {"t.py": "x = 1\n"}
    current = {"t.py": b"x = 1   \n"}
    t_a = plan_mod.compute_token("strip-trailing-ws", changes, current)
    t_b = plan_mod.compute_token("some-other-op", changes, current)
    assert t_a != t_b, "token must depend on the op name"


def test_execute_gate_reject_does_not_write(tmp_path, monkeypatch):
    # Force the op to produce a SYNTACTICALLY BROKEN change, so the token
    # matches but the gate rejects; execute must write nothing.
    f = tmp_path / "v.py"
    f.write_text("x = 1\n")

    broken = {"v.py": "def (:\n"}

    def fake_compute(file_path, args):
        return dict(broken)

    monkeypatch.setattr(registry_mod, "resolve", lambda name: fake_compute)
    # Recompute the token the way plan would, then execute.
    plan = plan_mod.make_plan("strip-trailing-ws", str(f), {})
    assert plan["verdict"]["verdict"] == "reject"  # predicted reject
    res = plan_mod.execute("strip-trailing-ws", str(f), {}, plan["token"])
    assert res["verdict"] == "reject"
    assert res["written"] == []
    assert f.read_text() == "x = 1\n", "gate-rejected execute wrote to the tree"


# --------------------------------------------------------------------------- #
# registry: guarded imports
# --------------------------------------------------------------------------- #


def test_registry_resolves_demo_op():
    fn = registry_mod.resolve("strip-trailing-ws")
    assert callable(fn)


def test_registry_unknown_op_raises():
    with pytest.raises(registry_mod.OpError):
        registry_mod.resolve("no-such-op")


def test_registry_missing_sibling_is_not_fatal():
    # A sibling op module that does not exist must NOT raise on `available()`,
    # and must NOT prevent the demo op from resolving.
    avail = registry_mod.available()
    assert "strip-trailing-ws" in avail
    assert avail["strip-trailing-ws"] is True
    # All four canonical names are listed regardless of presence.
    assert set(registry_mod.all_op_names()) == {
        "strip-trailing-ws",
        "fix-imports",
        "rename-symbol",
        "extract-to-package",
    }


# --------------------------------------------------------------------------- #
# bin/op CLI end-to-end
# --------------------------------------------------------------------------- #


def _run_op(*args):
    return subprocess.run(
        [BIN_OP, *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_list():
    res = _run_op("--list")
    assert res.returncode == 0
    assert "strip-trailing-ws" in res.stdout
    assert "available" in res.stdout


def test_cli_matrix():
    res = _run_op("--matrix")
    assert res.returncode == 0
    assert "py_compile" in res.stdout
    assert "false-negative-only" in res.stdout


def test_cli_help():
    res = _run_op("--help")
    assert res.returncode == 0
    assert "PLAN" in res.stdout


def test_cli_plan_then_execute_end_to_end(tmp_path):
    f = tmp_path / "cli.py"
    f.write_text("def g(y):   \n    return y  \n")

    # PLAN (read-only).
    plan_res = _run_op("strip-trailing-ws", str(f))
    assert plan_res.returncode == 0, plan_res.stderr
    assert "## Plan token" in plan_res.stdout
    # File untouched by planning.
    assert f.read_text() == "def g(y):   \n    return y  \n"

    # Extract the 64-hex token from the rendered plan.
    import re

    m = re.search(r"\b([0-9a-f]{64})\b", plan_res.stdout)
    assert m, "no token in plan output"
    token = m.group(1)

    # EXECUTE.
    exec_res = _run_op("strip-trailing-ws!", str(f), token)
    assert exec_res.returncode == 0, exec_res.stderr
    assert "ACCEPT" in exec_res.stdout
    assert f.read_text() == "def g(y):\n    return y\n"

    # Re-executing with the same (now stale) token rejects and writes nothing.
    exec2 = _run_op("strip-trailing-ws!", str(f), token)
    assert exec2.returncode == 3
    assert "REJECT" in exec2.stdout
    assert f.read_text() == "def g(y):\n    return y\n"


def test_cli_plan_no_change_exits_3(tmp_path):
    f = tmp_path / "already_clean.py"
    f.write_text("x = 1\n")
    res = _run_op("strip-trailing-ws", str(f))
    # No change => exit 3 (nothing executable).
    assert res.returncode == 3
    assert "no change" in res.stdout.lower()


def test_cli_unknown_op_errors():
    res = _run_op("definitely-not-an-op", "/tmp/whatever.py")
    assert res.returncode == 2
    assert "unknown op" in res.stderr.lower()
