"""Required build stages stop the pipeline after their own retries exhaust."""

from pathlib import Path

import pytest

from test_formula_assets import load_formula, resolve_formula_from_dirs


ROOT = Path(__file__).resolve().parents[2]
BUILD_FORMULAS = [
    ("gascity", "build-base"),
    ("gascity", "build-basic"),
    *[("gascity", f"build-from-{stage}{suffix}")
      for stage in ("requirements", "plan", "decompose", "convoy", "review")
      for suffix in ("-base", "")],
    ("bmad", "bmad-build"),
    ("compound-engineering", "compound-build"),
    ("gstack", "gstack-build"),
    ("superpowers", "superpowers-build"),
]


@pytest.mark.parametrize("pack,name", BUILD_FORMULAS)
def test_every_required_build_stage_belongs_to_the_fail_closed_scope(pack, name):
    formula = resolve_formula_from_dirs(
        [ROOT / "gascity/formulas", ROOT / pack / "formulas"], name
    )
    steps = {step["id"]: step for step in formula["steps"]}
    body = steps.pop("build-body")
    assert body["metadata"] == {
        "gc.kind": "scope", "gc.scope_name": "build", "gc.scope_role": "body"
    }
    assert set(body["needs"]) == set(steps)
    assert "gc.run_target" not in body["metadata"]
    for step_id, step in steps.items():
        metadata = step["metadata"]
        assert metadata["gc.scope_ref"] == "build-body", step_id
        assert metadata["gc.on_fail"] == "abort_scope", step_id
        assert metadata["gc.scope_role"] == (
            "setup" if step_id.startswith("prepare") else "member"
        ), step_id


@pytest.mark.parametrize("pack,name", BUILD_FORMULAS)
def test_child_step_replacements_declare_their_own_failure_policy(pack, name):
    # Native inheritance replaces a complete step, including its metadata.
    for step in load_formula(ROOT / pack, name).get("steps", []):
        if step["id"] != "build-body":
            assert step["metadata"]["gc.on_fail"] == "abort_scope", step["id"]
            assert step["metadata"]["gc.scope_ref"] == "build-body", step["id"]
            if "expand" in step:
                assert step["expand_vars"]["failure_scope"] == "build-body"
                expansion = load_formula(ROOT / pack, step["expand"])
                assert expansion["vars"]["failure_scope"]["default"] == ""
                for template in expansion["template"]:
                    assert template["metadata"]["gc.scope_ref"] == "{failure_scope}"
                    assert template["metadata"]["gc.scope_role"] == "member"
                    assert template["metadata"]["gc.on_fail"] == "abort_scope"
                    # An unsuccessful repair attempt must remain inside its
                    # own check loop, rather than abort the entire build.
                    for child in template.get("children", []):
                        assert child.get("metadata", {}).get("gc.scope_ref") not in {
                            "{failure_scope}", "build-body"
                        }, child["id"]
