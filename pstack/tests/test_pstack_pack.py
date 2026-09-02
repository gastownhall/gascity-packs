from __future__ import annotations

import hashlib
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

import pytest
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

CURSOR_PLAYBOOK_FORMULAS = {
    "investigation": "pstack-investigation",
    "bug-fix": "pstack-bug-fix",
    "perf-issue": "pstack-perf",
    "hillclimb": "pstack-hillclimb",
    "runtime-forensics": "pstack-runtime-forensics",
    "trace-forensics": "pstack-trace-forensics",
    "feature": "pstack-feature",
    "refactoring": "pstack-refactor",
    "prototype": "pstack-prototype",
    "visual-parity": "pstack-visual-parity",
    "authoring-a-skill": "pstack-authoring-a-skill",
    "eval": "pstack-eval",
    "babysit": "pstack-babysit",
    "shipping": "pstack-shipping",
    "autonomous-run": "pstack-autonomous-run",
    "orchestrate": "pstack-orchestrate",
    "autopilot-full": "pstack-autopilot-full",
    "autopilot-stack": "pstack-autopilot-stack",
    "session-pickup": "pstack-session-pickup",
    "multi-phase-plan": "pstack-multi-phase-plan",
}
CURSOR_PLAYBOOKS_UNSUPPORTED = frozenset(
    {"opening-a-pr", "pause-safely", "worktree-cleanup"}
)


def test_cursor_playbooks_have_formulas_or_are_named_unsupported() -> None:
    playbooks = {
        path.stem
        for path in (ROOT / "vendor/pstack/skills/poteto-mode/playbooks").glob("*.md")
    }
    assert playbooks == set(CURSOR_PLAYBOOK_FORMULAS) | CURSOR_PLAYBOOKS_UNSUPPORTED
    for formula in CURSOR_PLAYBOOK_FORMULAS.values():
        assert (ROOT / "formulas" / f"{formula}.formula.toml").is_file()
    assert (ROOT / "formulas/pstack-perf-issue.formula.toml").is_file()
    assert (ROOT / "formulas/pstack-refactoring.formula.toml").is_file()
    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for name in CURSOR_PLAYBOOKS_UNSUPPORTED:
        assert f"`{name}`" in architecture
    assert "not `pstack-<playbook>`" in architecture


def load_playbook_map() -> tuple[dict[str, str], set[str], dict[str, str]]:
    data = tomllib.loads((ROOT / "mappings/playbooks.toml").read_text(encoding="utf-8"))
    formulas = {
        stem: str(entry["formula"])
        for stem, entry in data["playbooks"].items()
    }
    classes = {
        stem: str(entry["class"])
        for stem, entry in data["playbooks"].items()
    }
    unsupported = set(data["unsupported"]["stems"])
    return formulas, unsupported, classes


def test_poteto_mode_router_table_matches_playbook_map() -> None:
    formulas, unsupported, classes = load_playbook_map()
    assert formulas == CURSOR_PLAYBOOK_FORMULAS
    assert unsupported == CURSOR_PLAYBOOKS_UNSUPPORTED
    assert set(classes) == set(formulas)
    assert set(classes.values()) <= {"method-report", "build-factory"}
    formula = load_formula("pstack-poteto-mode")
    classify = next(step for step in formula["steps"] if step["id"] == "classify")
    write = next(step for step in formula["steps"] if step["id"] == "write")
    assert classify["metadata"]["gc.run_target"] == "pstack.coordinator"
    assert "gc.graph_operator" not in classify.get("metadata", {})
    assert "gc.graph_operator" not in write.get("metadata", {})
    assert write["metadata"]["pstack.artifact_schema"] == "pstack.route.v1"
    assert (ROOT / "assets/workflows/pstack-methods/classify.md").is_file()


def test_playbook_map_excludes_method_skill_stems() -> None:
    formulas, unsupported, _classes = load_playbook_map()
    method_stems = {"how", "why", "swarm", "arena", "interrogate"}
    assert method_stems.isdisjoint(formulas)
    assert method_stems.isdisjoint(unsupported)
    data = tomllib.loads((ROOT / "mappings/playbooks.toml").read_text())
    assert "methods" not in data


def test_corpus_only_skills_are_named() -> None:
    data = tomllib.loads((ROOT / "mappings/playbooks.toml").read_text())
    corpus = set(data["corpus"]["skills"])
    formula_names = {path.stem.replace(".formula", "") for path in (ROOT / "formulas").glob("*.formula.toml")}
    expected: set[str] = set()
    for path in (ROOT / "vendor/pstack/skills").iterdir():
        if not path.is_dir():
            continue
        name = path.name
        if name.startswith("principle-") or name == "poteto-mode":
            continue
        if f"pstack-{name}" in formula_names:
            continue
        expected.add(name)
    assert corpus == expected
    assert corpus.isdisjoint({f"pstack-{name}" for name in corpus} & formula_names)
    for name in corpus:
        assert f"pstack-{name}" not in formula_names


def test_interrogate_judgment_is_gated() -> None:
    by_id = {step["id"]: step for step in load_formula("pstack-interrogate")["steps"]}
    judgment = by_id["judgment"]
    assert judgment["metadata"]["gc.build.artifact_schema"] == "gc.build.review.v1"
    assert judgment["metadata"]["gc.build.artifact_path_keys"]
    assert judgment["metadata"]["pstack.artifact_path"] == ".gc/pstack/interrogate-judgment.md"
    assert judgment["check"]["check"]["path"] == ".gc/scripts/checks/build-artifact-valid.sh"


def test_pstack_work_inherits_do_work_worktree() -> None:
    data = load_formula("pstack-work")
    assert data["extends"] == ["do-work"]
    assert data["vars"]["implementation_target"]["default"] == "pstack.implementation-worker"
    by_id = {step["id"]: step for step in data.get("steps", [])}
    assert "prepare-worktree" not in by_id
    assert "close-source-anchor" not in by_id
    assert "implement" in by_id
    assert by_id["implement"]["description_file"].endswith("pstack-work/implement.md")


def test_route_schema_rejects_unknown_status() -> None:
    validator = load_build_artifact_validator()
    routed = """---
schema: pstack.route.v1
workflow:
  id: route-1
  formula: pstack-poteto-mode
producer:
  formula: pstack-poteto-mode
  stage: write
  attempt: 1
status: routed
trace:
  upstream:
    - path: pstack/mappings/playbooks.toml
      hash: git:playbooks
  coverage:
    - id: ROUTE-001
      status: covered
playbook: bug-fix
formula: pstack-bug-fix
class: build-factory
reason: Mapped Cursor bug-fix playbook
evidence:
  source_revision: git:playbooks
  source_path: pstack/mappings/playbooks.toml
  claim_refs:
    - bead:gc-1
  verification_status: observed
---

## Route

| ID | Status |
| --- | --- |
| ROUTE-001 | covered |
"""
    unsupported = routed.replace("status: routed", "status: unsupported").replace(
        "playbook: bug-fix",
        "playbook: opening-a-pr",
    ).replace(
        "formula: pstack-bug-fix",
        "formula: none",
    ).replace("class: build-factory", "class: unsupported")
    with mock.patch.dict(os.environ, {"GC_BUILD_SCHEMA_ROOTS": str(ROOT / "schemas")}):
        artifact = validator.validate_artifact_text(
            routed,
            expected_schema="pstack.route.v1",
        )
        assert artifact.front_matter["formula"] == "pstack-bug-fix"
        validator.validate_artifact_text(
            unsupported,
            expected_schema="pstack.route.v1",
        )
        try:
            validator.validate_artifact_text(
                routed.replace("status: routed", "status: waiting"),
                expected_schema="pstack.route.v1",
            )
        except validator.ValidationError as exc:
            assert "status" in str(exc)
        else:
            raise AssertionError("invalid route status was accepted")


def load_route_checker():
    path = ROOT / "scripts/check_route_artifact.py"
    spec = importlib.util.spec_from_file_location("pstack_check_route_artifact", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load check_route_artifact")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_route_matches_map(front: dict) -> None:
    try:
        load_route_checker().check_route_front_matter(
            front,
            map_path=ROOT / "mappings/playbooks.toml",
        )
    except ValueError as exc:
        raise AssertionError(str(exc)) from exc


def test_routed_formula_must_exist_in_playbook_map() -> None:
    formulas, _unsupported, _classes = load_playbook_map()
    assert_route_matches_map(
        {
            "status": "routed",
            "playbook": "bug-fix",
            "formula": "pstack-bug-fix",
            "class": "build-factory",
        }
    )
    try:
        assert_route_matches_map(
            {
                "status": "routed",
                "playbook": "bug-fix",
                "formula": "pstack-missing",
                "class": "build-factory",
            }
        )
    except AssertionError:
        pass
    else:
        raise AssertionError("unknown formula was accepted")
    assert "pstack-missing" not in set(formulas.values())


def test_method_formulas_use_formula_identity() -> None:
    for formula in (
        "pstack-how",
        "pstack-why",
        "pstack-architect",
        "pstack-investigation",
        "pstack-hillclimb",
        "pstack-eval",
        "pstack-session-pickup",
    ):
        collect = next(step for step in load_formula(formula)["steps"] if step["id"] == "collect")
        assert collect["metadata"]["gc.run_target"] == "pstack.investigator"
        assert "pstack.skill" not in collect["metadata"]
        assert collect["metadata"]["pstack.playbook"]


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
    assert "gc import install" in text
    assert "gc import add https://github.com/gastownhall/gascity-packs.git//pstack" in text
    assert 'source = "../gascity-packs/pstack"' in text
    assert "not a slung production release" in text
    assert "does not expand `gc.graph_operator`" in text
    assert "sequential Gas City graphs" in text or "sequential annotated steps" in text
    assert "not multi-provider fanout" in text


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
    readme = (ROOT / "vendor/pstack/README.md").read_text(encoding="utf-8")
    assert readme.startswith("# pstack (Gas City vendor)")
    assert "listed subset" in readme
    assert "https://github.com/cursor/plugins/blob/" in readme
    assert "6fecddba65801f9b9c08b8b328d998ee5b09d290" in readme
    assert "(./docs/guide/README.md)" not in readme
    assert "(./automations/benny/" not in readme
    vendor_names = {path.name for path in (ROOT / "vendor/pstack").iterdir()}
    assert vendor_names == {
        "skills",
        "agents",
        "LICENSE",
        "README.md",
        "upstream.toml",
    }


def test_vendor_script_refuses_pack_owned_dest() -> None:
    path = ROOT / "scripts/vendor_canonical_pstack.py"
    spec = importlib.util.spec_from_file_location("pstack_vendor_canonical", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load vendor_canonical_pstack")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.LISTED == ("skills", "agents", "LICENSE", "README.md")
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
    assert "openspec/specs/pstack-gascity-pack/spec.md" in traceability
    assert "dest-env" not in traceability
    assert "dev-env/openspec" not in traceability
    assert "openspec/changes/pstack-gascity-pack/" not in traceability
    assert "intent/changes/audit-pstack-gascity-pack-contracts" not in traceability
    assert "unproven" in traceability
    assert "archive proven" not in traceability
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
    assert "not a slung production release" in traceability
    assert "without a host sling" in traceability
    packs_readme = (PACKS_ROOT / "README.md").read_text()
    assert "[pstack](./pstack)" in packs_readme
    assert "Not a slung production import" in packs_readme
    design = (ROOT / "DESIGN.md").read_text().lower()
    assert "dest-env" not in design
    specs = PACKS_ROOT / "openspec" / "specs"
    for relative in (
        "pstack-gascity-pack/spec.md",
        "gascity-provider-panel/spec.md",
        "pstack-delivery-evidence/spec.md",
    ):
        path = specs / relative
        assert path.is_file(), relative
        body = path.read_text().lower()
        assert "tbd" not in body
        assert "dest-env" not in body
    program = (PACKS_ROOT / "docs/pstack-program-plan.md").read_text()
    assert "pr-pstack-land-honesty" in program
    assert "pr-pstack-panel-stamp" in program
    assert "dest-env" not in program
    assert ".audit/" not in program
    assert "docs/pstack-program-plan.md" in traceability
    assert "origin/main:gascity/pack.toml" in program
    assert "origin/main:gascity/REQUIREMENTS.md" in program
    assert "origin/main:skills/" not in program
    repo = PACKS_ROOT
    for line in program.splitlines():
        marker = "git show origin/main:"
        if marker not in line:
            continue
        rel = line.split(marker, 1)[1].strip().strip("`")
        proc = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"origin/main:{rel}"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, rel


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
        assert "gc.provider_panel" not in body
        assert "gc.child_artifact_path_template" not in body


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


def test_pack_does_not_ship_openspec_change_payloads() -> None:
    assert not (ROOT / "intent").exists()
    assert not (PACKS_ROOT / "docs/openspec-changes").exists()
    requirements = (ROOT / "REQUIREMENTS.md").read_text()
    assert "intent/changes/audit-pstack-gascity-pack-contracts" not in requirements
    assert "unproven" in requirements
    assert "dest-env" not in requirements
    plan = (PACKS_ROOT / "docs/pstack-gascity-pack-apply-plan.md").read_text()
    assert "pstack/intent/changes/audit-pstack-gascity-pack-contracts" not in plan
    script = (ROOT / "scripts/apply_intent_change.py").read_text()
    assert 'PACK_ROOT / "intent"' not in script
    assert "/home/tommyk/projects/dev-env" not in script
    assert "dest-env" not in script
    assert "DEFAULT_SPEC_ROOT" in script


def test_apply_intent_change_rejects_pack_local_source() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/apply_intent_change.py"),
            "--validate-only",
            "--source",
            str(ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "do not live inside the pack" in proc.stdout + proc.stderr


def load_apply_intent_change():
    path = ROOT / "scripts/apply_intent_change.py"
    spec = importlib.util.spec_from_file_location("pstack_apply_intent_change", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load apply_intent_change")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_apply_intent_change_derives_change_name_from_source() -> None:
    script = (ROOT / "scripts/apply_intent_change.py").read_text()
    assert "DEFAULT_CHANGE" not in script
    apply_mod = load_apply_intent_change()
    dated = pathlib.Path("2026-09-02-pstack-program-arm-list")
    assert apply_mod.change_name(dated, None) == "pstack-program-arm-list"
    assert apply_mod.change_name(dated, "pstack-gherkin-restamp") == "pstack-gherkin-restamp"
    assert apply_mod.change_name(pathlib.Path("pstack-gherkin-restamp"), None) == "pstack-gherkin-restamp"
    with tempfile.TemporaryDirectory() as tmp:
        payload = pathlib.Path(tmp) / "pstack-gherkin-restamp"
        payload.mkdir()
        marker = payload / "proposal.md"
        marker.write_text("x\n")
        apply_mod.copy_change(payload, payload)
        assert marker.is_file()
        dest = pathlib.Path(tmp) / "outer"
        nested = dest / "inner"
        nested.mkdir(parents=True)
        (nested / "proposal.md").write_text("x\n")
        try:
            apply_mod.copy_change(nested, dest)
        except SystemExit as exc:
            assert "overlap" in str(exc)
        else:
            raise AssertionError("overlap was accepted")
        tree = pathlib.Path(tmp) / "tree"
        tree.mkdir()
        (tree / "proposal.md").write_text("x\n")
        inner_dest = tree / "changes" / "openspec"
        try:
            apply_mod.copy_change(tree, inner_dest)
        except SystemExit as exc:
            assert "overlap" in str(exc)
        else:
            raise AssertionError("dest inside source was accepted")
    if shutil.which("openspec") is None:
        pytest.skip("openspec CLI not installed")
    archive = PACKS_ROOT / "openspec/changes/archive/2026-09-02-pstack-program-arm-list"
    derived = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/apply_intent_change.py"),
            "--source",
            str(archive),
            "--validate-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    derived_out = derived.stdout + derived.stderr
    assert derived.returncode == 0, derived_out
    assert "Change 'pstack-program-arm-list' is valid" in derived_out
    assert "pstack-delegate-provider-panel" not in derived_out
    override = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/apply_intent_change.py"),
            "--change",
            "pstack-gherkin-restamp",
            "--source",
            str(archive),
            "--validate-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    override_out = override.stdout + override.stderr
    assert override.returncode == 0, override_out
    assert "Change 'pstack-gherkin-restamp' is valid" in override_out


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
        "route",
    }
    spec = importlib.util.spec_from_file_location(
        "pstack_validate_schemas",
        ROOT / "scripts/validate_pstack_schemas.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load validate_pstack_schemas")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    paths = module.validate_all(ROOT / "schemas", formulas_dir=ROOT / "formulas")
    assert {path.stem for path in paths} == {f"{name}.v1" for name in expected}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_pstack_schemas.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok route.v1.yaml" in proc.stdout
    valid = """schema_id: pstack.fixture.v1
artifact: fixture
allowed_statuses:
  - routed
coverage_statuses:
  - covered
  - not_applicable
  - deferred
  - blocked
  - out_of_scope
  - superseded
required_front_matter:
  - schema
  - workflow.id
  - workflow.formula
  - producer.formula
  - producer.stage
  - status
  - producer.attempt
  - trace
required_fields:
  - playbook
evidence_fields:
  - source_path
"""
    with tempfile.TemporaryDirectory() as tmp:
        dest = pathlib.Path(tmp)
        schemas = dest / "schemas"
        formulas = dest / "formulas"
        schemas.mkdir()
        formulas.mkdir()
        (schemas / "fixture.v1.yaml").write_text(valid, encoding="utf-8")
        module.validate_all(schemas, formulas_dir=formulas)
        broken = valid.replace("  - producer.attempt\n", "")
        (schemas / "fixture.v1.yaml").write_text(broken, encoding="utf-8")
        missing = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/validate_pstack_schemas.py"),
                "--schemas",
                str(schemas),
                "--formulas",
                str(formulas),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert missing.returncode != 0
        assert "producer.attempt" in missing.stderr
        (schemas / "fixture.v1.yaml").write_text(valid, encoding="utf-8")
        (formulas / "bad.formula.toml").write_text(
            """formula = "bad"
version = 1
[[steps]]
id = "write"
metadata = { "pstack.artifact_schema" = "pstack.nope.v1" }
""",
            encoding="utf-8",
        )
        unknown = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/validate_pstack_schemas.py"),
                "--schemas",
                str(schemas),
                "--formulas",
                str(formulas),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert unknown.returncode != 0
        assert "pstack.nope.v1" in unknown.stderr


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
