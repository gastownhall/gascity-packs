"""Behavioral suite for the pattern-DSL engine (paper §4.E / "Subsystem E").

Covers the YAML-intent authoring path end-to-end:

  - the active backend resolves to a real ast-grep surface (or, when absent,
    the fallback) and is reported.
  - each bundled example intent transforms a fixture exactly as intended AND
    the rewritten content still passes the compile gate (it parses).
  - a file with no matches -> None; an unsupported language -> None.
  - a malformed YAML intent is rejected cleanly (PatternError), and one bad
    intent file never sinks the registry's discovery of the good ones.
  - the minimal fallback matcher handles its pattern subset and declines
    anything outside it.
  - the intents are registered as ops and run plan->execute through `bin/op`.

Run via the pack venv:
    .venv/bin/python -m pytest tests/test_pattern_dsl.py -q
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

from astlens import pattern as P  # noqa: E402
from astlens import registry as registry_mod  # noqa: E402
from astlens.gate import gate  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "write_fixtures", "pattern")
INTENTS_DIR = P.DEFAULT_INTENTS_DIR
BIN_OP = os.path.join(PACK_ROOT, "bin", "op")

HAVE_GOFMT = shutil.which("gofmt") is not None
HAVE_NODE = shutil.which("node") is not None


def _read(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def _intent(intent_id: str) -> P.Intent:
    intents = {i.id: i for i in P.load_intents_dir(INTENTS_DIR)}
    assert intent_id in intents, f"missing bundled intent {intent_id!r}"
    return intents[intent_id]


# --------------------------------------------------------------------------- #
# backend
# --------------------------------------------------------------------------- #
def test_active_backend_is_known():
    assert P.active_backend() in ("ast-grep-py", "ast-grep-bin", "fallback")


def test_ast_grep_py_is_the_active_backend_when_installed():
    # The pack pins ast-grep-py in requirements, so in the pack venv it should be
    # the live backend (this guards the install + the preference order).
    try:
        import ast_grep_py  # noqa: F401
    except Exception:  # pragma: no cover - only when the wheel is unavailable
        pytest.skip("ast-grep-py not installed")
    assert P.active_backend() == "ast-grep-py"


# --------------------------------------------------------------------------- #
# bundled intents load + are well-formed
# --------------------------------------------------------------------------- #
def test_all_bundled_intents_load():
    intents = P.load_intents_dir(INTENTS_DIR)
    ids = {i.id for i in intents}
    assert {"remove-console", "no-var", "go-interface-any"} <= ids
    for i in intents:
        assert i.description.strip()
        assert i.exts  # language expanded to at least one extension


# --------------------------------------------------------------------------- #
# remove-console
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAVE_NODE, reason="node not available for the gate")
def test_remove_console_drops_standalone_logs_only():
    intent = _intent("remove-console")
    src = _read("console_demo.js")
    out = intent.apply_text(src, ".js")
    assert out is not None
    # The two standalone debug/log statements are gone...
    assert 'console.log("starting");' not in out
    assert 'console.debug("item", it);' not in out
    # ...but the braceless-if body and the value-producing console.count survive.
    assert 'if (out.length === 0) console.log("empty");' in out
    assert "console.count" in out
    # And the rewrite still parses (gate ACCEPT on a host with node).
    verdict = gate({"console_demo.js": out}, "/tmp")
    assert verdict["verdict"] == "accept"


def test_remove_console_no_blank_line_residue():
    intent = _intent("remove-console")
    src = "function f() {\n  console.log('a');\n  return 1;\n}\n"
    out = intent.apply_text(src, ".js")
    assert out == "function f() {\n  return 1;\n}\n"


# --------------------------------------------------------------------------- #
# no-var
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAVE_NODE, reason="node not available for the gate")
def test_no_var_rewrites_keyword_preserving_structure():
    intent = _intent("no-var")
    src = _read("vars_demo.js")
    out = intent.apply_text(src, ".js")
    assert out is not None
    # `var` keywords became `let`; no `var ` declaration remains.
    assert "var total" not in out
    assert "let total = 0;" in out
    # Multi-declarator and its semicolon are intact.
    assert "let a = 1, b = 2;" in out
    # for-loop initialiser rewritten in place, structure preserved.
    assert "for (let i = 0; i < 3; i++) {" in out
    # const/let left untouched.
    assert "const FACTOR = 2;" in out
    assert "let result = total + a + b;" in out
    verdict = gate({"vars_demo.js": out}, "/tmp")
    assert verdict["verdict"] == "accept"


def test_no_var_preserves_trailing_semicolon_single():
    out = _intent("no-var").apply_text("var x = 1;\n", ".js")
    assert out == "let x = 1;\n"


# --------------------------------------------------------------------------- #
# go-interface-any
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAVE_GOFMT, reason="gofmt not available for the gate")
def test_go_interface_any_rewrites_all_empty_interfaces():
    intent = _intent("go-interface-any")
    src = _read("iface_demo.go")
    out = intent.apply_text(src, ".go")
    assert out is not None
    assert "interface{}" not in out
    assert "func Wrap(x any) any {" in out
    assert "map[string]any" in out
    # AST-aware, not regex: the literal "interface{}" inside the `//` comment is
    # NOT an interface_type node and so is left untouched.
    assert "empty-interface type appears" in out
    verdict = gate({"iface_demo.go": out}, "/tmp")
    assert verdict["verdict"] == "accept"


# --------------------------------------------------------------------------- #
# no-match / unsupported language -> None
# --------------------------------------------------------------------------- #
def test_no_match_returns_none():
    src = _read("clean.js")
    assert _intent("remove-console").apply_text(src, ".js") is None
    assert _intent("no-var").apply_text(src, ".js") is None


def test_unsupported_language_returns_none_via_op():
    # The go intent on a .py file: the op must decline (None), not error.
    op = P.make_op(_intent("go-interface-any"))
    py_path = os.path.join(FIXTURES, "sample.py")
    assert op(py_path, {}) is None


def test_op_declines_clean_file():
    op = P.make_op(_intent("remove-console"))
    assert op(os.path.join(FIXTURES, "clean.js"), {}) is None


# --------------------------------------------------------------------------- #
# malformed intents are rejected cleanly
# --------------------------------------------------------------------------- #
def test_malformed_intent_file_is_rejected():
    bad = os.path.join(FIXTURES, "malformed_intent.yaml")
    with pytest.raises(P.PatternError):
        P.load_intent(bad)


def test_intent_missing_id_rejected():
    with pytest.raises(P.PatternError):
        P._intent_from_dict({"language": "js", "description": "x", "pattern": "a"})


def test_intent_both_rule_and_pattern_rejected():
    with pytest.raises(P.PatternError):
        P._intent_from_dict(
            {"id": "x", "language": "js", "description": "d", "rule": {"kind": "k"}, "pattern": "p"}
        )


def test_intent_unknown_language_rejected():
    with pytest.raises(P.PatternError):
        P._intent_from_dict({"id": "x", "language": "cobol", "description": "d", "pattern": "p"})


def test_invalid_yaml_rejected(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("id: x\n  bad: : :\n", encoding="utf-8")
    with pytest.raises(P.PatternError):
        P.load_intent(str(bad))


# --------------------------------------------------------------------------- #
# fallback matcher (forced; independent of whether ast-grep is installed)
# --------------------------------------------------------------------------- #
@pytest.fixture
def force_fallback(monkeypatch):
    monkeypatch.setattr(P, "_have_ast_grep_py", lambda: False)
    monkeypatch.setattr(P, "_have_ast_grep_bin", lambda: None)
    assert P.active_backend() == "fallback"


def test_fallback_deletes_pattern(force_fallback):
    intent = P._intent_from_dict(
        {
            "id": "rm-print",
            "language": "python",
            "description": "drop print",
            "pattern": "print($$$ARGS)",
            "strip_statement": True,
        }
    )
    out = intent.apply_text("print('hi')\nx = 1\nprint('again', x)\nkeep()\n", ".py")
    assert out == "x = 1\nkeep()\n"


def test_fallback_strip_statement_swallows_semicolon(force_fallback):
    # A `call(...)` pattern stops before the `;`; strip_statement must still
    # remove the whole statement line (terminator + indentation) cleanly.
    intent = P._intent_from_dict(
        {
            "id": "rm-log",
            "language": "js",
            "description": "drop log",
            "pattern": "console.log($$$ARGS)",
            "strip_statement": True,
        }
    )
    src = "function f() {\n  console.log('x', y);\n  return 1;\n}\n"
    assert intent.apply_text(src, ".js") == "function f() {\n  return 1;\n}\n"


def test_fallback_rewrites_with_metavars(force_fallback):
    intent = P._intent_from_dict(
        {"id": "f2b", "language": "python", "description": "foo->bar", "pattern": "foo($ARG)", "fix": "bar($ARG)"}
    )
    out = intent.apply_text("y = foo(42)\nz = foo(q)\n", ".py")
    assert out == "y = bar(42)\nz = bar(q)\n"


def test_fallback_declines_rule_based(force_fallback):
    intent = P._intent_from_dict(
        {"id": "ru", "language": "js", "description": "d", "rule": {"kind": "variable_declaration"}, "select": "var", "fix": "let"}
    )
    assert intent.apply_text("var a = 1;\n", ".js") is None


def test_fallback_declines_multiline_pattern(force_fallback):
    intent = P._intent_from_dict(
        {"id": "ml", "language": "python", "description": "d", "pattern": "a\nb"}
    )
    assert intent.apply_text("a\nb\n", ".py") is None


# --------------------------------------------------------------------------- #
# registry integration
# --------------------------------------------------------------------------- #
def test_registry_lists_intents_as_ops():
    names = registry_mod.listing_names()
    for intent_id in ("remove-console", "no-var", "go-interface-any"):
        assert intent_id in names
        assert registry_mod.is_intent(intent_id) is True
        assert registry_mod.available().get(intent_id) is True
        assert registry_mod.describe(intent_id)


def test_intents_excluded_from_canonical_op_names():
    # The auto-load is additive but scoped: intents live in `listing_names`, not
    # in the spine's canonical `all_op_names` (the four Python ops).
    canonical = registry_mod.all_op_names()
    assert "remove-console" not in canonical
    assert set(canonical) == {
        "strip-trailing-ws",
        "fix-imports",
        "rename-symbol",
        "extract-to-package",
    }


def test_registry_resolves_intent_to_compute_change():
    fn = registry_mod.resolve("remove-console")
    assert callable(fn)
    # It honours the op contract: None on an already-clean file.
    assert fn(os.path.join(FIXTURES, "clean.js"), {}) is None


def test_registry_still_has_python_ops():
    # The auto-load is additive: the hand-written ops are untouched.
    names = registry_mod.listing_names()
    assert "strip-trailing-ws" in names
    assert registry_mod.is_intent("strip-trailing-ws") is False


def test_registry_tolerates_a_malformed_intent_in_dir(tmp_path, monkeypatch):
    # Point the engine at a temp intents dir holding one good + one broken
    # intent, reset the registry cache, and assert: the good one loads, the bad
    # one is listed-but-unavailable (and raises a clear OpError on resolve),
    # while the rest of discovery keeps working.
    good = tmp_path / "good.yaml"
    good.write_text(
        "id: tmp-good\nlanguage: js\ndescription: d\npattern: var $N = $V\nrule: null\n",
        encoding="utf-8",
    )
    # (rule: null keeps it a pure-pattern intent; pyyaml maps it to None.)
    bad = tmp_path / "bad.yaml"
    bad.write_text("language: [js]\nfix: let\n", encoding="utf-8")

    monkeypatch.setattr(P, "DEFAULT_INTENTS_DIR", str(tmp_path))
    monkeypatch.setattr(registry_mod, "_INTENTS", None)
    monkeypatch.setattr(registry_mod, "_INTENT_ERRORS", {})
    monkeypatch.setattr(registry_mod, "_RESOLVED", {})

    names = registry_mod.listing_names()
    assert "tmp-good" in names
    assert "bad" in names  # listed by file stem
    assert registry_mod.available()["tmp-good"] is True
    assert registry_mod.available()["bad"] is False
    with pytest.raises(registry_mod.OpError):
        registry_mod.resolve("bad")


# --------------------------------------------------------------------------- #
# end-to-end through bin/op (plan -> execute -> gated write)
# --------------------------------------------------------------------------- #
def _run_op(*args: str):
    return subprocess.run(
        [BIN_OP, *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def _token_from_plan(stdout: str) -> str:
    import re

    m = re.search(r"^- `([0-9a-f]{64})`", stdout, re.MULTILINE)
    assert m, f"no plan token in:\n{stdout}"
    return m.group(1)


def test_bin_op_list_shows_intents():
    res = _run_op("--list")
    assert res.returncode == 0
    assert "remove-console" in res.stdout
    assert "no-var" in res.stdout
    assert "go-interface-any" in res.stdout
    assert "pattern-DSL backend:" in res.stdout


@pytest.mark.skipif(not HAVE_NODE, reason="node not available for the gate")
def test_bin_op_plan_and_execute_remove_console(tmp_path):
    f = tmp_path / "demo.js"
    f.write_text(
        "function f() {\n  console.log('a');\n  const x = 1;\n  console.debug('b', x);\n  return x;\n}\n",
        encoding="utf-8",
    )
    plan = _run_op("remove-console", str(f))
    assert plan.returncode == 0, plan.stdout + plan.stderr
    assert "ACCEPT" in plan.stdout
    token = _token_from_plan(plan.stdout)

    ex = _run_op("remove-console!", str(f), token)
    assert ex.returncode == 0, ex.stdout + ex.stderr
    assert "ACCEPT" in ex.stdout
    after = f.read_text(encoding="utf-8")
    assert "console.log" not in after
    assert "console.debug" not in after
    assert "return x;" in after

    # Re-executing the same (now stale) token writes nothing.
    ex2 = _run_op("remove-console!", str(f), token)
    assert ex2.returncode == 3
    assert "stale plan" in ex2.stdout


@pytest.mark.skipif(not HAVE_GOFMT, reason="gofmt not available for the gate")
def test_bin_op_execute_go_interface_any(tmp_path):
    f = tmp_path / "g.go"
    f.write_text("package main\n\nfunc f(x interface{}) interface{} {\n\treturn x\n}\n", encoding="utf-8")
    plan = _run_op("go-interface-any", str(f))
    assert plan.returncode == 0, plan.stdout + plan.stderr
    token = _token_from_plan(plan.stdout)
    ex = _run_op("go-interface-any!", str(f), token)
    assert ex.returncode == 0, ex.stdout + ex.stderr
    after = f.read_text(encoding="utf-8")
    assert "interface{}" not in after
    assert "func f(x any) any {" in after
