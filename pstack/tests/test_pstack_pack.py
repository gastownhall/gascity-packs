from __future__ import annotations

import hashlib
import importlib.util
import os
import pathlib
import sys
import tomllib
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKS_ROOT = ROOT.parent
GAS_CITY = PACKS_ROOT / "gascity"

def load_build_artifact_validator():
    path = GAS_CITY / "assets/scripts/validate_build_artifact.py"
    spec = importlib.util.spec_from_file_location("pstack_build_artifact_validator", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load build artifact validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
def load_any_formula(name: str) -> dict:
    for root in (ROOT, GAS_CITY):
        path = root / "formulas" / f"{name}.formula.toml"
        if path.is_file():
            return tomllib.loads(path.read_text())
    raise AssertionError(f"formula {name!r} not found")


def resolve_formula(name: str, seen: tuple[str, ...] = ()) -> dict:
    if name in seen:
        raise AssertionError(f"circular formula extends: {' -> '.join((*seen, name))}")
    data = load_any_formula(name)
    parents = data.get("extends", [])
    if not parents:
        return data
    resolved = dict(data)
    steps: list[dict] = []
    positions: dict[str, int] = {}
    for parent in parents:
        parent_data = resolve_formula(parent, (*seen, name))
        for step in parent_data.get("steps", []):
            positions[step["id"]] = len(steps)
            steps.append(step)
    for step in data.get("steps", []):
        index = positions.get(step["id"])
        if index is None:
            positions[step["id"]] = len(steps)
            steps.append(step)
        else:
            steps[index] = step
    resolved["steps"] = steps
    return resolved


def depends_on(steps: list[dict], target: str, prerequisite: str) -> bool:
    by_id = {step["id"]: step for step in steps}
    pending = [target]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        for dependency in by_id[current].get("needs", []):
            if dependency == prerequisite:
                return True
            pending.append(dependency)
    return False


def test_variant_evidence_gates_inherited_implementation() -> None:
    gates = {
        "pstack-feature": "experience",
        "pstack-perf": "baseline",
        "pstack-prototype": "experience",
        "pstack-refactor": "lever",
        "pstack-migration": "lever",
        "pstack-bug-fix": "root-cause",
    }
    for formula, gate in gates.items():
        steps = resolve_formula(formula)["steps"]
        by_id = {step["id"]: step for step in steps}
        assert gate in by_id["principle-selection"]["needs"], (
            f"{formula} must gate principle selection on {gate}"
        )
        for implementation in ("implement", "implement-same-session"):
            assert depends_on(steps, implementation, gate), (
                f"{formula} must gate {implementation} on {gate}"
            )


def test_variant_prompt_bindings_and_shipping_publish_route() -> None:
    expected_prompts = {
        ("pstack-autonomous-run", "check"): "../assets/workflows/pstack-variants/pstack-autonomous-run/check.md",
        ("pstack-autopilot-full", "ship"): "../assets/workflows/pstack-variants/pstack-autopilot-full/ship.md",
        ("pstack-autopilot-stack", "verify"): "../assets/workflows/pstack-variants/pstack-autopilot-stack/verify.md",
        ("pstack-babysit", "escalate"): "../assets/workflows/pstack-variants/pstack-babysit/escalate.md",
        ("pstack-orchestrate", "reconcile"): "../assets/workflows/pstack-variants/pstack-orchestrate/reconcile.md",
    }
    for (formula, step_id), description_file in expected_prompts.items():
        step = next(step for step in resolve_formula(formula)["steps"] if step["id"] == step_id)
        assert step["description_file"] == description_file
        assert "description_file" not in step.get("check", {}).get("check", {})

    shipping = {step["id"]: step for step in resolve_formula("pstack-shipping")["steps"]}
    assert shipping["review"]["expand"] == "pstack-build-review"
    assert shipping["finalize"]["metadata"]["gc.run_target"] == "gc.run-operator"
    assert shipping["publish"]["metadata"]["gc.run_target"] == "gc.publisher"

def test_babysit_escalation_declares_artifact_contract() -> None:
    step = next(step for step in resolve_formula("pstack-babysit")["steps"] if step["id"] == "escalate")
    assert step["needs"] == ["reconcile"]
    assert step["metadata"] == {
        "gc.run_target": "pstack.architect",
        "gc.build.artifact_schema": "pstack.program-status.v1",
        "gc.build.artifact_path_keys": "pstack.artifact_path",
        "pstack.artifact_schema": "pstack.program-status.v1",
        "pstack.artifact_path": "{{artifact_root}}/pstack/escalate.md",
    }
    assert step["description_file"] == "../assets/workflows/pstack-variants/pstack-babysit/escalate.md"
    assert "description_file" not in step["check"]["check"]
    assert step["check"]["check"] == {
        "mode": "exec",
        "path": ".gc/scripts/checks/build-artifact-valid.sh",
        "timeout": "5m",
    }
    asset = (ROOT / "assets/workflows/pstack-variants/pstack-babysit/escalate.md").read_text()
    for fragment in (
        "pstack.program-status.v1",
        "pstack.artifact_path",
        "goal",
        "phase",
        "predicate",
        "blockers",
        "restart_token",
        "evidence",
    ):
        assert fragment in asset
def test_babysit_escalation_artifact_validates_against_program_status() -> None:
    validator = load_build_artifact_validator()
    rendered = """---
schema: pstack.program-status.v1
workflow:
  id: babysit-001
  formula: pstack-babysit
producer:
  formula: pstack-babysit
  stage: escalate
  attempt: 1
status: blocked
trace:
  upstream:
    - path: pstack/reconcile.md
      hash: git:reconcile-revision
  coverage:
    - id: BLOCKER-001
      status: covered
goal: Keep the merge frontier actionable
phase: reconcile
predicate: Every blocker has an owner or next action
blockers:
  - id: BLOCKER-001
    summary: Owner rebase is required
restart_token: Re-run after the owner updates the branch
evidence:
  source_revision: git:reconcile-revision
  source_path: pstack/reconcile.md
  claim_refs:
    - bead:gc-6
  verification_status: observed
---

## Escalation

| ID | Status |
| --- | --- |
| BLOCKER-001 | covered |
"""
    with mock.patch.dict(os.environ, {"GC_BUILD_SCHEMA_ROOTS": str(ROOT / "schemas")}):
        artifact = validator.validate_artifact_text(
            rendered,
            expected_schema="pstack.program-status.v1",
        )
        assert artifact.front_matter["evidence"]["source_path"] == "pstack/reconcile.md"
        schema = validator.load_schema("pstack.program-status.v1")
        assert set(schema["evidence_fields"]) <= set(artifact.front_matter["evidence"])

        invalid = rendered.replace("      status: covered", "      status: waiting")
        try:
            validator.validate_artifact_text(
                invalid,
                expected_schema="pstack.program-status.v1",
            )
        except validator.ValidationError as exc:
            assert "coverage" in str(exc)
        else:
            raise AssertionError("invalid PStack coverage status was accepted")


def test_variant_steps_wait_for_both_implementation_drains() -> None:
    gated_steps = {
        "pstack-feature": "build",
        "pstack-bug-fix": "build",
        "pstack-migration": "migrate",
        "pstack-refactor": "build",
        "pstack-perf": "build",
        "pstack-prototype": "slice",
        "pstack-autonomous-run": "check",
        "pstack-autopilot-full": "ship",
        "pstack-autopilot-stack": "verify",
    }
    for formula, step_id in gated_steps.items():
        step = next(step for step in resolve_formula(formula)["steps"] if step["id"] == step_id)
        assert {"implement", "implement-same-session"} <= set(step["needs"])


def file_digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def test_pstack_build_assets_stamp_pstack_provenance() -> None:
    for name in ("requirements", "plan", "decompose", "finalize", "review", "publish", "plan-review"):
        text = (ROOT / "assets/workflows/pstack-build" / f"{name}.md").read_text()
        assert "build-basic" not in text
        assert "build-basic-review" not in text
        assert "factory_run_path" not in text
    assert "methodology: pstack-build" in (ROOT / "assets/workflows/pstack-build/finalize.md").read_text()


def test_principle_mapping_matches_manifest_enforcement() -> None:
    manifest = tomllib.loads((ROOT / "principles/manifest.toml").read_text())
    mapping = tomllib.loads((ROOT / "mappings/principles.toml").read_text())["principles"]
    expected = {item["id"]: item["enforcement"] for item in manifest["principle"]}
    assert {name: data["enforcement"] for name, data in mapping.items()} == expected


def test_principle_schema_captures_effect() -> None:
    text = (ROOT / "schemas/principle-application.v1.yaml").read_text()
    assert "  - effect" in text


def test_verification_schema_matches_verdict_contract() -> None:
    text = (ROOT / "schemas/verification.v1.yaml").read_text()
    for status in ("verified", "failed", "blocked", "insufficient"):
        assert f"  - {status}" in text
    for field in ("subject.kind", "subject.id", "revision", "checks", "evidence", "verdict"):
        assert f"  - {field}" in text
def test_source_binding_schema_matches_translation_contract() -> None:
    text = (ROOT / "schemas/source-binding.v1.yaml").read_text()
    for field in (
        "id",
        "source.path",
        "source.section",
        "source.commit",
        "target.formula",
        "target.node",
        "realization_type",
        "rationale",
    ):
        assert f"  - {field}" in text
def test_source_binding_formula_records_translation_metadata() -> None:
    formula = load_formula("pstack-source-binding")
    step = next(step for step in formula["steps"] if step["id"] == "record")
    assert step["metadata"]["gc.run_target"] == "pstack.investigator"
    assert step["metadata"]["pstack.artifact_schema"] == "pstack.source-binding.v1"
    assert step["metadata"]["pstack.artifact_path"] == "{{artifact_path}}"
    assert step["metadata"]["gc.build.artifact_schema"] == "pstack.source-binding.v1"
    assert step["metadata"]["gc.build.artifact_path_keys"] == "pstack.artifact_path"


def test_pack_metadata_and_import() -> None:
    data = tomllib.loads((ROOT / "pack.toml").read_text())
    assert data["pack"] == {
        "name": "pstack",
        "version": "0.1.0",
        "schema": 2,
        "requires_gc": ">=0.13.0",
    }
    assert data["imports"]["gc"]["source"] == "../gascity"


def test_readme_documents_required_gas_city_roles() -> None:
    text = (ROOT / "README.md").read_text()
    assert "[rigs.imports.gc]" in text
    assert "../gascity/roles" in text


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
        assert "  - producer.attempt" in text
        assert "coverage_statuses:" in text
        for status in ("covered", "not_applicable", "deferred", "blocked", "out_of_scope", "superseded"):
            assert f"  - {status}" in text
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
    build_step = next(step for step in resolve_formula("pstack-build")["steps"] if step["id"] == "review")
    review_step = next(step for step in load_formula("pstack-review")["steps"] if step["id"] == "write-report")
    assert build_step["expand"] == review_step["expand"] == "pstack-build-review"
    assert review_step["expand_vars"]["artifact_path_keys"] == "gc.build.review_report_path,gc.var.report_path"
    terminal = next(node for node in nodes if node["id"] == "{target}")
    assert terminal["metadata"]["gc.build.artifact_path_keys"] == "{artifact_path_keys}"


def test_migration_bug_and_durable_program_ordering() -> None:
    bug = load_formula("pstack-bug-fix")
    bug_ids = [step["id"] for step in bug["steps"]]
    assert bug_ids[:4] == ["reproduce", "root-cause", "build", "verify"]
    migration = load_formula("pstack-migration")
    migration_ids = [step["id"] for step in migration["steps"]]
    assert migration_ids == ["callers", "lever", "principle-selection", "migrate", "delete", "verify", "finalize"]
    program = load_formula("pstack-orchestrate")
    assert [step["id"] for step in program["steps"]] == ["orders", "brief", "pilot", "frontier", "reconcile", "finalize"]
    assert "scheduler" not in program["description"].lower()


def test_optional_pack_policy_is_non_blocking() -> None:
    data = tomllib.loads((ROOT / "mappings/optional-packs.toml").read_text())
    assert all(not item["required"] for item in data["optional_packs"].values())
    assert data["policy"]["missing_pack"] == "skip-with-reason"
