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


def normalized_text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_gstack_pack_is_skills_only() -> None:
    manifest = tomllib.loads((GSTACK_ROOT / "pack.toml").read_text(encoding="utf-8"))

    assert manifest["pack"]["name"] == "gstack"
    assert "imports" not in manifest
    for retired_surface in ("agents", "commands", "formulas"):
        assert not (GSTACK_ROOT / retired_surface).exists()
    assert (GSTACK_ROOT / "skills/gstack-lite/SKILL.md").is_file()


def test_gc_roles_pack_inherits_public_worker_and_adds_lightweight_policy() -> None:
    roles = REPO_ROOT / "gascity/roles"
    manifest = tomllib.loads((roles / "pack.toml").read_text(encoding="utf-8"))

    assert manifest["pack"]["name"] == "gc-roles"
    assert manifest["imports"]["gc"]["source"] == ".."
    assert (
        REPO_ROOT / "gascity/template-fragments/gc-role-worker.template.md"
    ).is_file()
    assert (
        roles / "template-fragments/gstack-lite-policy.template.md"
    ).is_file()
    assert (roles / "agents/research-planner/agent.toml").is_file()
    assert (roles / "agents/research-planner/prompt.template.md").is_file()


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
        "repository-defined `gc.delivery.lane`",
        "same live reviewer conversation",
        "benchmarks outside delivery lineage",
    ):
        assert required in text


def test_delivery_schema_keeps_lanes_repository_defined_and_requires_safety_risk() -> None:
    schema = __import__("json").loads(
        (GSTACK_ROOT / "skills/gstack-lite/schemas/gc.delivery.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert "enum" not in schema["properties"]["repository_lane"]
    assert schema["properties"]["review_evidence"]["items"]["properties"]["head"]["minLength"] == 7
    assert schema["allOf"][0]["then"]["required"] == ["risk_reasons", "deployment_target"]


def test_gstack_lite_consolidates_every_review_surface_before_repair() -> None:
    skill = normalized_text(GSTACK_ROOT / "skills/gstack-lite/SKILL.md")
    requirements = normalized_text(GSTACK_ROOT / "REQUIREMENTS.md")
    readme = normalized_text(GSTACK_ROOT / "README.md")
    role_fragment = normalized_text(
        REPO_ROOT / "gascity/roles/template-fragments/gstack-lite-policy.template.md"
    )

    assert (
        "After deterministic checks, expose the same immutable candidate head to "
        "every applicable configured review surface: required CI, external PR review "
        "bots, and one direct `gstack.review` pass with a different model family for "
        "material code."
    ) in skill
    assert (
        "The same checked immutable candidate is exposed to required CI, configured "
        "external PR review bots, and one different-family review for material changes."
    ) in requirements
    assert (
        "expose one immutable candidate to required CI, external PR bots, and one "
        "independent different-family review for material changes;"
    ) in readme
    assert (
        "Every applicable review surface must evaluate the exact repaired head; "
        "aggregate that consolidated re-review before merge."
    ) in skill
    assert "All applicable surfaces evaluate the exact repaired head." in requirements
    assert (
        "require required CI, configured external PR bots, and the different-family "
        "reviewer to evaluate the exact repaired head, then consolidate the re-review "
        "findings;"
    ) in readme
    assert "one consolidated exact-head review round" in role_fragment
    assert "exact-repaired-head re-review" in role_fragment
    assert (
        "A surface skipped by its configuration (draft state, labels, or path filters) "
        "is not a valid timeout;"
    ) in skill
    assert (
        "Each bot has SHA-bound run/comment evidence; a configuration skip is not a "
        "timeout."
    ) in requirements
    assert (
        "Each configured bot needs run or comment evidence bound to the candidate SHA; "
        "a configuration skip is not a timeout, so use an explicit trigger or a "
        "merge-blocked ready-for-review PR."
    ) in readme
    assert "Any safety finding blocks merge regardless of repair accounting." in skill
    assert (
        "Only a blocking consolidated re-review fails upward; safety always blocks."
    ) in requirements
    assert (
        "Safety findings always block merge; other blocking findings fail upward only "
        "after the consolidated re-review."
    ) in readme
    assert (
        "The same bounded timeout/unavailable recording applies to re-review. An "
        "unavailable required surface blocks merge unless repository protection "
        "explicitly does not require it, and that exception is recorded."
    ) in skill
    assert (
        "The same bounded-result rule applies, and an unavailable required surface "
        "blocks merge unless repository protection explicitly exempts it and that is "
        "recorded."
    ) in requirements
    assert (
        "An unavailable required surface blocks merge unless repository protection "
        "explicitly does not require it and the exception is recorded."
    ) in readme

    raw_skill = (GSTACK_ROOT / "skills/gstack-lite/SKILL.md").read_text(encoding="utf-8")
    assert raw_skill.index("external PR review bots") < raw_skill.index(
        "single repair allowance"
    )
    assert "never repair serially" in raw_skill
    assert "bounded explicit timeout or unavailable result" in skill
    assert "skipped by its configuration" in skill
    assert "not a valid timeout" in skill
    assert "same bounded timeout/unavailable recording applies to re-review" in skill


def test_gstack_lite_preserves_rejected_candidates_for_successors() -> None:
    skill = normalized_text(GSTACK_ROOT / "skills/gstack-lite/SKILL.md")
    requirements = normalized_text(GSTACK_ROOT / "REQUIREMENTS.md")
    fragment = normalized_text(
        REPO_ROOT / "gascity/template-fragments/gstack-lite-policy.template.md"
    )

    assert (
        "Delete a rejected branch only after its exact commit, diff, and evidence are "
        "reachable from an approved successor or another durable remote reference; "
        "delete the accepted branch after merge."
    ) in skill
    assert (
        "Rejected branches remain durably reachable with their exact commit, diff, and "
        "evidence until an approved successor carries them or another durable remote "
        "reference preserves them."
    ) in requirements
    assert (
        "Preserve rejected branches until exact commits, diffs, and evidence are durably "
        "reachable. Rescue carries the failed candidate forward by default;"
    ) in fragment
    assert "Delete the accepted branch after merge." in fragment
    assert "delete any protection-required PR branch after merge" not in fragment


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
