from __future__ import annotations

import hashlib
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
from unittest import mock

import tomllib

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

CANONICAL_ENFORCEMENTS = {
    "artifact",
    "check",
    "expansion",
    "graph-invariant",
    "review",
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

def test_method_formulas_use_formula_identity() -> None:
    for formula in (
        "pstack-how",
        "pstack-why",
        "pstack-architect",
        "pstack-investigation",
    ):
        collect = next(step for step in load_formula(formula)["steps"] if step["id"] == "collect")
        assert collect["metadata"]["gc.run_target"] == "pstack.investigator"
        assert "pstack.skill" not in collect["metadata"]


def test_pack_runtime_schema_context_is_documented() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for fragment in (
        "GC_PACK_DIR",
        "GC_BUILD_SCHEMA_ROOTS",
        "shared Gas City schema root",
        "must not set",
        "GC_RIG_ROOT",
        "GC_BEADS_SCOPE_ROOT",
        "GC_DIR",
        "GC_WORK_DIR",
    ):
        assert fragment in text


def test_producer_gate_resolves_pstack_schema_from_pack_context() -> None:
    gate = GAS_CITY / "assets/scripts/checks/build-artifact-valid.sh"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        fake_gc = bin_dir / "gc"
        fake_gc.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "bd" ] && [ "$2" = "show" ] && [ "$4" = "--json" ]; then\n'
            "  printf '%s\\n' "
            "'{\"id\":\"step-1\",\"metadata\":{\"gc.build.artifact_schema\":"
            "\"pstack.program-status.v1\",\"gc.build.artifact_path_keys\":"
            "\"pstack.artifact_path\",\"pstack.artifact_path\":\"artifacts/status.md\"}}'\n"
            "  exit 0\n"
            "fi\n"
            "exit 2\n",
            encoding="utf-8",
        )
        fake_gc.chmod(0o755)
        artifact = tmp_path / "artifacts/status.md"
        artifact.parent.mkdir()
        artifact.write_text(
            """---
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
""",
            encoding="utf-8",
        )
        env = {**os.environ}
        for key in ("GC_BUILD_SCHEMA_ROOTS", "GC_RIG_ROOT", "GC_BEADS_SCOPE_ROOT", "GC_DIR"):
            env.pop(key, None)
        env.update(
            {
                "GC_BEAD_ID": "step-1",
                "GC_PACK_DIR": str(ROOT),
                "GC_WORK_DIR": str(tmp_path),
                "PATH": f"{bin_dir}:/usr/bin:/bin",
            }
        )
        result = subprocess.run(
            [str(gate)], capture_output=True, text=True, env=env, check=False
        )

    assert result.returncode == 0, result.stderr
    assert "schema=pstack.program-status.v1" in result.stdout
    assert "artifacts/status.md" in result.stdout


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

def test_principle_enforcement_contract_has_one_vocabulary() -> None:
    manifest = tomllib.loads((ROOT / "principles/manifest.toml").read_text())
    mapping = tomllib.loads((ROOT / "mappings/principles.toml").read_text())["principles"]
    declared = {value for item in manifest["principle"] for value in item["enforcement"]}
    mapped = {value for item in mapping.values() for value in item["enforcement"]}
    assert declared == mapped == CANONICAL_ENFORCEMENTS

    schema = (ROOT / "schemas/principle-application.v1.yaml").read_text()
    expected = "allowed_enforcements:\n" + "".join(f"  - {value}\n" for value in sorted(CANONICAL_ENFORCEMENTS))
    assert expected in schema

    prompt = (ROOT / "assets/workflows/pstack-build/principles.md").read_text()
    for field in ("effect", "enforcement", "required_artifacts", "evidence"):
        assert field in prompt
    assert "enforcement class" not in prompt



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
    data = tomllib.loads((ROOT / "vendor/pstack/upstream.toml").read_text())
    source = data["upstream"]
    assert source["source"] == "https://github.com/cursor/plugins"
    assert source["path"] == "pstack"
    assert source["commit"] == "6fecddba65801f9b9c08b8b328d998ee5b09d290"
    assert source["license"] == "MIT"
    assert "tommy-ca" not in source["source"]
    assert data["vendor"]["paths"] == [
        "vendor/pstack/skills",
        "vendor/pstack/agents",
        "vendor/pstack/README.md",
        "vendor/pstack/LICENSE",
    ]
    assert (ROOT / "vendor/pstack/LICENSE").is_file()
    vendor_agents = {path.name for path in (ROOT / "vendor/pstack/agents").iterdir()}
    assert vendor_agents == {"comment-sicko.md", "poteto-agent.md"}
    pack_agents = {path.name for path in (ROOT / "agents").iterdir() if path.is_dir()}
    assert "architect" in pack_agents
    assert vendor_agents.isdisjoint(pack_agents)
    assert not (ROOT / "agents/comment-sicko.md").is_file()
    assert not (ROOT / "agents/poteto-agent.md").is_file()
    assert data["runtime_adaptation"]["skills_copy"] == ["skills"]
    assert "agents" in data["runtime_adaptation"]["pack_owned"]
    assert "agents" not in data["runtime_adaptation"]["skills_copy"]
    for extra in ("docs", "automations"):
        assert not (ROOT / "vendor/pstack" / extra).exists()


def test_vendor_script_refuses_pack_owned_dest() -> None:
    path = ROOT / "scripts/vendor_canonical_pstack.py"
    spec = importlib.util.spec_from_file_location("pstack_vendor_canonical", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load vendor_canonical_pstack")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.assert_safe_paths(ROOT, ROOT / "skills")
    except SystemExit:
        pass
    else:
        raise AssertionError("pack root dest must be refused")
    try:
        module.assert_safe_paths(ROOT / "vendor" / "pstack", ROOT / "agents")
    except SystemExit:
        return
    raise AssertionError("pack agents runtime dest must be refused")


def test_pack_owned_surface_does_not_prescribe_cursor_host_clis() -> None:
    forbidden = ("scripts/watch-pr", "scripts/orch/orch.ts", "orchestrate/<project-slug>/")
    roots = (ROOT / "formulas", ROOT / "assets", ROOT / "agents")
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                assert needle not in text, (path, needle)


def test_every_pstack_formula_declares_formula_compiler_requirement() -> None:
    for path in sorted((ROOT / "formulas").glob("*.formula.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        assert data.get("requires", {}).get("formula_compiler") == ">=2.0.0", path


def test_decision_schema_accepts_no_removal_status_and_rejects_empty_fields() -> None:
    validator = load_build_artifact_validator()
    rendered = """---
schema: pstack.decision.v1
workflow:
  id: build-001
  formula: pstack-build
producer:
  formula: pstack-build
  stage: subtract
  attempt: 1
status: no_removal_opportunity
trace:
  upstream:
    - path: requirements.md
      hash: git:decision-revision
  coverage: []
problem: No removable complexity was found.
options:
  - Keep the existing structure.
chosen_path: Keep the existing structure.
subtraction: Reviewed existing paths; none can be removed safely.
rationale: The requested behavior already has the smallest viable surface.
---

## Decision
"""
    with mock.patch.dict(os.environ, {"GC_BUILD_SCHEMA_ROOTS": str(ROOT / "schemas")}):
        artifact = validator.validate_artifact_text(rendered, expected_schema="pstack.decision.v1")
        assert artifact.front_matter["status"] == "no_removal_opportunity"

        for field in ("subtraction", "rationale"):
            invalid = rendered.replace(
                f"{field}: " + ("Reviewed existing paths; none can be removed safely." if field == "subtraction" else "The requested behavior already has the smallest viable surface."),
                f"{field}: \"\"",
                1,
            )
            with mock.patch.dict(os.environ, {"GC_BUILD_SCHEMA_ROOTS": str(ROOT / "schemas")}):
                try:
                    validator.validate_artifact_text(invalid, expected_schema="pstack.decision.v1")
                except validator.ValidationError as exc:
                    assert "required fields must be non-empty" in str(exc)
                else:
                    raise AssertionError(f"blank {field} was accepted")



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

def test_delivery_checks_cover_pstack() -> None:
    ci = (PACKS_ROOT / ".github/workflows/ci.yml").read_text()
    assert "pstack/tests/test_pstack_pack.py" in ci
    assert "slack-full pstack slack-mini; do" in ci

    traceability = (ROOT / "TRACEABILITY.md").read_text()
    assert "dev-env/openspec/specs/pstack-gascity-pack/spec.md" in traceability
    assert "openspec/changes/pstack-gascity-pack/" not in traceability
    assert "not silently imported" in traceability
    assert "README.md" in traceability
    assert "https://github.com/cursor/plugins" in traceability
    assert "tommy-ca/pstack" not in (ROOT / "vendor/pstack/upstream.toml").read_text()
    assert "moving maintained SHA" in traceability
    assert "no separate graph-cook script" in traceability
    assert "https://github.com/cursor/plugins/tree/main/pstack" in traceability
    assert "6fecddba65801f9b9c08b8b328d998ee5b09d290" in traceability
    architecture = (ROOT / "ARCHITECTURE.md").read_text()
    assert "build-base" in architecture
    assert "bmad" in architecture
    assert "6fecddba65801f9b9c08b8b328d998ee5b09d290" in architecture


def test_method_formulas_keep_unconsumed_graph_operator_metadata() -> None:
    expected = {
        "pstack-swarm": (("fanout", "gc.graph_operator", "fanout"), ("fanin", "gc.graph_operator", "fanin")),
        "pstack-arena": (("trigger", "pstack.graph_operator", "gate"), ("candidates", "gc.graph_operator", "fanout")),
        "pstack-interrogate": (("select", "pstack.graph_operator", "selector"), ("review", "gc.graph_operator", "fanout")),
    }
    for formula_name, steps in expected.items():
        by_id = {step["id"]: step for step in load_formula(formula_name)["steps"]}
        for step_id, key, value in steps:
            assert by_id[step_id]["metadata"][key] == value, (formula_name, step_id, key)

    text = (ROOT / "TRACEABILITY.md").read_text()
    assert "gc.graph_operator" in text
    assert "no Gas City consumer" in text
    for path in (ROOT / "formulas").glob("*.formula.toml"):
        body = path.read_text(encoding="utf-8")
        assert "spawn_subagent" not in body
        assert "cursor/agents" not in body


def test_optional_pack_catalog_matches_declared_names() -> None:
    names = {
        "compound-engineering",
        "superpowers",
        "bmad",
        "gstack",
    }
    data = tomllib.loads((ROOT / "mappings/optional-packs.toml").read_text())
    assert set(data["optional_packs"]) == names
    assert data["policy"]["missing_pack"] == "skip-with-reason"
    for item in data["optional_packs"].values():
        assert item["required"] is False
    for path in sorted((ROOT / "formulas").glob("*.formula.toml")):
        text = path.read_text(encoding="utf-8")
        for name in names:
            assert name not in text, path.name


def test_gascity_has_no_graph_operator_consumer() -> None:
    hits: list[str] = []
    for path in GAS_CITY.rglob("*"):
        if not path.is_file() or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "graph_operator" in text:
            hits.append(str(path.relative_to(GAS_CITY)))
    assert hits == []


def test_method_prompts_state_single_node_graph_operator() -> None:
    for relative in (
        "assets/workflows/pstack-methods/fanout.md",
        "assets/workflows/pstack-methods/arena-candidates.md",
        "assets/workflows/pstack-methods/interrogate-review.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "does not expand" in text
        assert "gc.graph_operator" in text


def test_selector_formulas_override_pack_local_assets() -> None:
    planning = {step["id"]: step for step in load_formula("pstack-planning")["steps"]}
    assert planning["requirements"]["metadata"]["gc.run_target"] == "pstack.investigator"
    assert planning["requirements"]["description_file"].endswith("pstack-build/requirements.md")
    assert planning["plan"]["metadata"]["gc.run_target"] == "pstack.architect"
    assert planning["plan"]["description_file"].endswith("pstack-build/plan.md")
    assert planning["plan-review"]["metadata"]["gc.run_target"] == "pstack.review-synthesizer"
    build = {step["id"]: step for step in load_formula("pstack-build")["steps"]}
    assert build["requirements"]["metadata"]["gc.run_target"] == planning["requirements"]["metadata"]["gc.run_target"]
    assert build["plan-review"]["metadata"]["gc.run_target"] == planning["plan-review"]["metadata"]["gc.run_target"]
    decomposition = {step["id"]: step for step in load_formula("pstack-decomposition")["steps"]}
    assert "lever-decision" in decomposition
    assert decomposition["decompose"]["needs"] == ["lever-decision"]
    assert decomposition["decompose"]["description_file"].endswith("pstack-build/decompose.md")


def test_migration_formula_declares_ungated_callers_and_delete() -> None:
    by_id = {step["id"]: step for step in load_formula("pstack-migration")["steps"]}
    assert "callers" in by_id and "delete" in by_id and "verify" in by_id
    assert "check" not in by_id["callers"]
    assert "check" not in by_id["delete"]
    text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "schemas").glob("*.yaml"))
    assert "remaining_callers" not in text


def test_intent_change_validates_against_dev_env_specs() -> None:
    spec_root = pathlib.Path("/home/tommyk/projects/dev-env/openspec")
    if not (spec_root / "config.yaml").is_file():
        return
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/apply_intent_change.py"),
            "--validate-only",
            "--spec-root",
            str(spec_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


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
        assert "contract" not in data
        assert data["requires"]["formula_compiler"] == ">=2.0.0"
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
