"""Check failure boundaries after native inheritance, expansion and checks."""

import json
from pathlib import Path

import pytest

from gc_live_city import REPO_ROOT, gc_test_bin, run_gc, write_city  # noqa: F401


FORMULAS = [
    "build-base", "build-basic",
    *[f"build-from-{stage}{suffix}"
      for stage in ("requirements", "plan", "decompose", "convoy", "review")
      for suffix in ("-base", "")],
    "bmad-build", "compound-build",
    "gstack-build", "superpowers-build",
]


@pytest.fixture(scope="module")
def build_city(tmp_path_factory):
    return write_city(tmp_path_factory.mktemp("build-failure-policy"), {
        "gc": REPO_ROOT / "gascity",
        **{pack: REPO_ROOT / pack for pack in (
            "bmad", "compound-engineering", "gstack", "superpowers"
        )},
    })


@pytest.mark.parametrize("formula", FORMULAS)
@pytest.mark.parametrize("drain", ("separate", "same-session"))
def test_native_compilation_preserves_required_stage_failure_boundaries(
    gc_test_bin: Path, build_city, formula, drain, record_property  # noqa: F811
):
    result = run_gc(gc_test_bin, build_city, "formula", "show", formula, "--json",
                    "--var", f"drain_policy={drain}")
    assert result.returncode == 0, result.stdout + result.stderr
    recipe = json.loads(result.stdout)
    assert recipe["schema_version"] == "1" and recipe["ok"] is True
    record_property("native_recipe", json.dumps(recipe, sort_keys=True))
    assert recipe["name"] == formula
    prefix = formula + "."
    roots = [step for step in recipe["steps"] if step.get("is_root", False)]
    assert len(roots) == 1 and roots[0]["id"] == formula
    children = [step for step in recipe["steps"] if not step.get("is_root", False)]
    assert all(step["id"].startswith(prefix) for step in children)
    steps = {step["id"].removeprefix(prefix): step for step in children}
    assert len(steps) == len(children)
    body = steps["build-body"]
    assert body["metadata"]["gc.kind"] == "scope"
    assert body["metadata"]["gc.scope_role"] == "body"
    assert "gc.run_target" not in body["metadata"]
    members = {name: step for name, step in steps.items()
               if step.get("metadata", {}).get("gc.scope_ref") == "build-body"}
    assert members
    # Expanded setup/finalization and logical check controllers must all be
    # scoped. Retry attempts belong to their native inner scope instead.
    for name, step in steps.items():
        meta = step.get("metadata", {})
        if meta.get("gc.run_target") and not meta.get("gc.attempt") and meta.get("gc.kind") != "spec":
            assert name in members, (name, meta)
    for name, member in members.items():
        meta = member["metadata"]
        assert meta["gc.on_fail"] == "abort_scope", (name, meta)
        assert meta["gc.scope_role"] in {"setup", "member", "control"}
        if meta.get("gc.kind") not in {"scope-check", "drain", "fanout"}:
            check = steps[name + "-scope-check"]
            assert check["metadata"]["gc.control_for"] == name
            assert check["metadata"]["gc.scope_ref"] == "build-body"
    assert any(dep["step_id"] == prefix + "workflow-finalize" and
               dep["depends_on_id"] == prefix + "build-body" for dep in recipe["deps"])
    record_property("compiled_policy", json.dumps({
        "formula": formula, "drain": drain,
        "members": {name: step["metadata"] for name, step in members.items()},
        "deps": recipe["deps"],
    }, sort_keys=True))


@pytest.mark.parametrize("formula", (
    "build-basic-review", "bmad-code-review-flow",
    "compound-plan-review", "compound-code-review",
    "compound-resolution", "gstack-plan-review",
    "gstack-code-review", "gstack-qa-review",
    "gstack-release-readiness", "superpowers-brainstorming",
    "superpowers-plan-review", "superpowers-code-review",
))
def test_standalone_expansions_do_not_reference_a_missing_build_scope(
    gc_test_bin: Path, build_city, formula, record_property  # noqa: F811
):
    result = run_gc(gc_test_bin, build_city, "formula", "show", formula, "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    recipe = json.loads(result.stdout)
    record_property("native_recipe", json.dumps(recipe, sort_keys=True))
    assert recipe["ok"] is True
    assert all(step.get("metadata", {}).get("gc.scope_ref") != "build-body"
               for step in recipe["steps"])
    assert not any("{failure_scope}" in json.dumps(step) for step in recipe["steps"])
