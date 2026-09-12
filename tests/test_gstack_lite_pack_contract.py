from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
GSTACK_ROOT = REPO_ROOT / "gstack"
AUDIT_PATH = GSTACK_ROOT / "skills/gstack-lite/scripts/audit_city.py"


def load_audit_module():
    spec = importlib.util.spec_from_file_location("gstack_lite_audit", AUDIT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gstack_pack_is_skills_only() -> None:
    manifest = tomllib.loads((GSTACK_ROOT / "pack.toml").read_text(encoding="utf-8"))

    assert manifest["pack"]["name"] == "gstack"
    assert "imports" not in manifest
    for retired_surface in ("agents", "commands", "formulas"):
        assert not (GSTACK_ROOT / retired_surface).exists()
    assert (GSTACK_ROOT / "skills/gstack-lite/SKILL.md").is_file()
    assert (
        REPO_ROOT / "deprecated/gstack-graph/formulas/gstack-build.formula.toml"
    ).is_file()


def test_gc_roles_pack_is_standalone() -> None:
    roles = REPO_ROOT / "gascity/roles"
    manifest = tomllib.loads((roles / "pack.toml").read_text(encoding="utf-8"))

    assert manifest["pack"]["name"] == "gc-roles"
    assert "imports" not in manifest
    for fragment in ("gc-role-worker", "gstack-lite-policy"):
        assert (roles / f"template-fragments/{fragment}.template.md").is_file()


def test_complete_delivery_tombstone_has_no_runnable_surface() -> None:
    tombstone = REPO_ROOT / "complete-delivery"
    assert (tombstone / "pack.toml").is_file()
    for retired_surface in ("agents", "commands", "formulas", "skills"):
        assert not (tombstone / retired_surface).exists()
    assert (REPO_ROOT / "deprecated/complete-delivery/pack.toml").is_file()


def test_gstack_lite_records_owner_and_candidate_leases() -> None:
    text = (GSTACK_ROOT / "skills/gstack-lite/SKILL.md").read_text(encoding="utf-8")

    for required in (
        "gc.delivery.owner_session",
        "gc.delivery.source_head",
        "gc.delivery.phase",
        "gc runtime drain-check",
        "gc session close",
        "immutable candidate head",
        "four minutes",
        "structured artifact",
    ):
        assert required in text


def test_gstack_lite_consolidates_every_review_surface_before_repair() -> None:
    skill = (GSTACK_ROOT / "skills/gstack-lite/SKILL.md").read_text(encoding="utf-8")
    requirements = (GSTACK_ROOT / "REQUIREMENTS.md").read_text(encoding="utf-8")
    readme = (GSTACK_ROOT / "README.md").read_text(encoding="utf-8")

    for text in (skill, requirements, readme):
        normalized = " ".join(text.split())
        assert "required CI" in normalized
        assert "external PR" in normalized
        assert (
            "different-family" in normalized
            or "different model family" in normalized
        )
        assert (
            "exact repaired head" in normalized
            or "exact-repaired-head" in normalized
        )
        assert (
            "Safety findings always block" in normalized
            or "safety always blocks" in normalized
        )

    assert skill.index("external PR review bots") < skill.index(
        "single repair allowance"
    )
    assert "never repair serially" in skill
    assert "bounded explicit timeout or\nunavailable result" in skill


def test_gstack_lite_preserves_rejected_candidates_for_successors() -> None:
    skill = (GSTACK_ROOT / "skills/gstack-lite/SKILL.md").read_text(encoding="utf-8")

    assert "exact commit/diff and review evidence" in skill
    assert "carries the failed candidate forward by default" in skill
    assert "Rebuild from\nprotected `main` only" in skill
    assert "delete any protection-required PR branch after\n  merge" not in skill


def test_audit_rejects_retired_formula_names(monkeypatch, tmp_path: Path) -> None:
    audit = load_audit_module()
    city = tmp_path / "city"
    city.mkdir()
    (city / "pack.toml").write_text(
        "[pack]\nname='city'\nschema=2\n[imports.gstack]\nsource='gstack'\n",
        encoding="utf-8",
    )
    (city / "city.toml").write_text(
        "[agent_defaults]\nappend_fragments=['gstack-lite-policy']\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        audit,
        "active_formula_names",
        lambda _city: ({"mol-do-work", "gstack-build", "build-basic"}, None),
    )

    errors, _notes = audit.audit(city, False)

    assert any(
        "strict Gstack Lite profile excludes active formulas" in error
        for error in errors
    )
