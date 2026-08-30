from __future__ import annotations

import hashlib
import pathlib
import tomllib


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKS_ROOT = ROOT.parent
GAS_CITY = PACKS_ROOT / "gascity"
EXPECTED_PRINCIPLES = {
    "laziness-protocol",
    "foundational-thinking",
    "redesign-from-first-principles",
    "subtract-before-you-add",
    "minimize-reader-load",
    "outcome-oriented-execution",
    "experience-first",
    "exhaust-the-design-space",
    "build-the-lever",
    "model-the-domain",
    "boundary-discipline",
    "type-system-discipline",
    "make-operations-idempotent",
    "migrate-callers-then-delete-legacy-apis",
    "separate-before-serializing-shared-state",
    "prove-it-works",
    "fix-root-causes",
    "sequence-verifiable-units",
    "guard-the-context-window",
    "never-block-on-the-human",
    "encode-lessons-in-structure",
}


def load_formula(name: str) -> dict:
    return tomllib.loads((ROOT / "formulas" / f"{name}.formula.toml").read_text())


def file_digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pack_metadata_and_import() -> None:
    data = tomllib.loads((ROOT / "pack.toml").read_text())
    assert data["pack"] == {
        "name": "pstack",
        "version": "0.1.0",
        "schema": 2,
        "requires_gc": ">=0.13.0",
    }
    assert data["imports"]["gc"]["source"] == "../gascity"


def test_vendor_source_binding_is_immutable() -> None:
    source = tomllib.loads((ROOT / "vendor/pstack/upstream.toml").read_text())["upstream"]
    assert source["source"] == "https://github.com/tommy-ca/pstack"
    assert len(source["commit"]) == 40
    assert source["license"] == "MIT"
    assert (ROOT / "vendor/pstack/LICENSE").is_file()


def test_all_21_principles_have_runtime_skills_and_enforcement() -> None:
    manifest = tomllib.loads((ROOT / "principles/manifest.toml").read_text())
    principles = manifest["principle"]
    assert {item["id"] for item in principles} == EXPECTED_PRINCIPLES
    assert len(principles) == len(EXPECTED_PRINCIPLES)
    for item in principles:
        assert (ROOT / item["skill"]).is_file()
        assert item["triggers"]
        assert item["applies_to"]
        assert item["enforcement"]
        assert item["required_artifacts"]


def test_runtime_skills_match_vendored_source() -> None:
    runtime = ROOT / "skills"
    vendor = ROOT / "vendor/pstack/skills"
    runtime_files = sorted(path.relative_to(runtime) for path in runtime.rglob("*") if path.is_file())
    vendor_files = sorted(path.relative_to(vendor) for path in vendor.rglob("*") if path.is_file())
    assert runtime_files == vendor_files
    assert all(file_digest(runtime / relative) == file_digest(vendor / relative) for relative in runtime_files)


def test_build_extends_base_and_preserves_anchors() -> None:
    base = tomllib.loads((GAS_CITY / "formulas/build-base.formula.toml").read_text())
    build = load_formula("pstack-build")
    assert build["extends"] == ["build-base"]
    assert build["catalog"]["name"] == "pstack-build"
    assert build["vars"]["planning_formula"]["default"] == "pstack-planning"
    assert build["vars"]["decomposition_formula"]["default"] == "pstack-decomposition"
    assert build["vars"]["implementation_formula"]["default"] == "pstack-implementation"
    assert build["vars"]["implementation_item_formula"]["default"] == "pstack-work-item"
    assert build["vars"]["code_review_formula"]["default"] == "pstack-review"
    assert build["vars"]["review_fix_formula"]["default"] == "pstack-fix-loop"
    ids = [step["id"] for step in base["steps"]]
    by_id = {step["id"]: step for step in base["steps"]}
    by_id.update({step["id"]: step for step in build["steps"]})
    for step_id in ids:
        assert step_id in by_id
    assert by_id["plan"]["needs"] == ["foundation"]
    assert by_id["decompose"]["needs"] == ["lever-decision"]
    assert by_id["implement"]["drain"]["context"] == "separate"
    assert by_id["implement-same-session"]["drain"]["context"] == "shared"
    assert by_id["review"]["expand"] == "pstack-build-review"


def test_pstack_specific_schemas_are_declared_and_referenced() -> None:
    expected = {
        "source-binding",
        "principle-application",
        "foundation",
        "lever-decision",
        "reproduction",
        "root-cause",
        "verification",
        "arena-candidate",
        "arena-synthesis",
        "swarm-result",
        "decision",
        "frontier",
        "standing-orders",
        "program-status",
    }
    paths = sorted((ROOT / "schemas").glob("*.yaml"))
    assert {path.stem for path in paths} == {f"{name}.v1" for name in expected}
    for path in paths:
        text = path.read_text()
        assert f"schema_id: pstack.{path.stem}" in text
        assert "required_front_matter:" in text
        assert "evidence_fields:" in text


def test_methods_programs_and_variants_are_providerless_and_asset_complete() -> None:
    formulas = sorted((ROOT / "formulas").glob("*.formula.toml"))
    assert len(formulas) >= 28
    forbidden = ("Task tool (general-purpose):", "Dispatch implementer subagent", "claude -p")
    for path in formulas:
        data = tomllib.loads(path.read_text())
        assert data["contract"] == "graph.v2"
        for node in data.get("steps", []):
            description = node.get("description_file")
            if description:
                assert (path.parent / description).resolve().is_file()
        text = path.read_text()
        assert not any(fragment in text for fragment in forbidden)
    for path in (ROOT / "assets" / "workflows").rglob("*.md"):
        text = path.read_text()
        relative = path.relative_to(ROOT / "assets" / "workflows")
        if relative.parts[0].startswith("pstack"):
            assert "Gas City" in text
            assert "provider-native subagents" not in text or "Do not invoke provider-native subagents" in text


def test_review_expansion_and_role_routes() -> None:
    expansion = load_formula("pstack-build-review")
    nodes = expansion["template"]
    children = [child for node in nodes for child in node.get("children", [])]
    all_nodes = nodes + children
    assert len(all_nodes) >= 4
    assert any(node["id"].endswith(".gap-analysis-review") for node in children)
    targets = {node.get("metadata", {}).get("gc.run_target") for node in all_nodes}
    assert "pstack.review-synthesizer" in targets
    assert (ROOT / "agents/implementation-worker/agent.toml").is_file()
    assert (ROOT / "agents/review-synthesizer/prompt.template.md").is_file()


def test_migration_bug_and_durable_program_ordering() -> None:
    bug = load_formula("pstack-bug-fix")
    bug_ids = [step["id"] for step in bug["steps"]]
    assert bug_ids[:4] == ["reproduce", "root-cause", "build", "verify"]
    migration = load_formula("pstack-migration")
    migration_ids = [step["id"] for step in migration["steps"]]
    assert migration_ids == ["callers", "lever", "migrate", "delete", "verify", "finalize"]
    program = load_formula("pstack-orchestrate")
    assert [step["id"] for step in program["steps"]] == ["orders", "brief", "pilot", "frontier", "reconcile", "finalize"]
    assert "scheduler" not in program["description"].lower()


def test_optional_pack_policy_is_non_blocking() -> None:
    data = tomllib.loads((ROOT / "mappings/optional-packs.toml").read_text())
    assert all(not item["required"] for item in data["optional_packs"].values())
    assert data["policy"]["missing_pack"] == "skip-with-reason"
