"""Pin the artifact contract on the expansion prompts that close checked build stages.

When a build stage `expand`s into a methodology flow, gc drops the stage's own
prompt: only the expansion's step prompts reach agents. The flow's `{target}`
step is the one gated by `build-artifact-valid.sh`, and the build gate's final
artifact check reads the same workflow-root keys. So the instruction to write
the artifact and record its path has to live in the `{target}` prompt, not in
the stage override.

Contract gaps surfaced in the gc v1.5.0 RC inference runs:

* bmad and superpowers (and, by inspection, compound-engineering and gstack)
  code-review flows never told the agent to record
  `gc.build.review_report_path` on the workflow root, so the review artifact
  check passed or failed depending on whether the model happened to do it.
  compound-resolution had the same gap for `gc.build.final_report_path`.
* superpowers' requirements artifact lacked YAML front matter, and the
  requirements `{target}` repair attempts never read the validator errors in
  `gc.attempt_log`, so every repair closed without touching the file.
* gstack's apply-plan-review-findings lane set the plan's front-matter status
  to `reviewed`, which gc.build.plan.v1 rejects, and closed without running the
  validator; nothing re-validated the plan until the gate's final check. Every
  apply-findings lane that edits a build artifact in place had the same gap,
  and the plan-review `{target}` steps were unchecked.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

import yaml

from scripts import gascity_pack_inference_gate

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_REPORT_KEY = "gc.build.review_report_path"
FINAL_REPORT_KEY = "gc.build.final_report_path"
CHECK_SCRIPT = "build-artifact-valid.sh"
YAML_BLOCK_RE = re.compile(r"^```yaml\n(?P<body>.*?)^```$", re.DOTALL | re.MULTILINE)

# (pack, build formula) whose `review` stage expands into a code-review flow.
REVIEW_BUILDS = (
    ("bmad", "bmad-build"),
    ("compound-engineering", "compound-build"),
    ("gstack", "gstack-build"),
    ("superpowers", "superpowers-build"),
)

# Shared by every checked `{target}` prompt: validate before passing, and on a
# repair attempt start from the validator errors.
VALIDATION_FRAGMENTS = (
    "on the workflow root bead, not on the claimed step bead",
    f"gc_bead_id=<claimed-step-id> .gc/scripts/checks/{CHECK_SCRIPT}",
    "fix any error before setting `gc.outcome=pass`",
    "read the validator errors from `gc.attempt_log` on the validation loop control bead",
)

# Every fragment is matched lowercased with whitespace collapsed.
REVIEW_TARGET_FRAGMENTS = VALIDATION_FRAGMENTS + (
    f'gc bd update "<workflow-root-id>" --set-metadata "{REVIEW_REPORT_KEY}=<absolute path>"',
    f"use workflow root metadata `{REVIEW_REPORT_KEY}` when it is set",
    "resolve it against `$gc_rig_root` before copying",
    'cp -f "<',
)

REVIEW_OVERRIDE_FRAGMENTS = (
    f'gc bd update "<workflow-root-id>" --set-metadata "{REVIEW_REPORT_KEY}=<absolute path>"',
)

FINAL_TARGET_FRAGMENTS = VALIDATION_FRAGMENTS + (
    f'gc bd update "<workflow-root-id>" --set-metadata "{FINAL_REPORT_KEY}=<absolute path>"',
    f"use workflow root metadata `{FINAL_REPORT_KEY}` when it is set",
    "resolve it against `$gc_rig_root`",
    "schema `gc.build.final-report.v1`",
)

REQUIREMENTS_TARGET_FRAGMENTS = (
    "read the validator errors from `gc.attempt_log` on the validation loop control bead",
    "repair the requirements artifact in place",
    "build artifact must start with yaml front matter",
    f"gc_bead_id=<claimed-step-id> .gc/scripts/checks/{CHECK_SCRIPT}",
    "approval metadata alone does not satisfy it",
)

REQUIREMENTS_WRITER_FRAGMENTS = (
    "must start with yaml front matter on its first line",
    "an `id` column and a `status` column",
)

REQUIREMENTS_FEEDBACK_FRAGMENTS = ("preserve its yaml front matter",)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def load_validator() -> ModuleType:
    path = REPO_ROOT / "gascity" / "assets" / "scripts" / "validate_build_artifact.py"
    spec = importlib.util.spec_from_file_location("validate_build_artifact", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules.
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator()


def load_formula(pack: str, name: str) -> tuple[Path, dict[str, Any]]:
    path = REPO_ROOT / pack / "formulas" / f"{name}.formula.toml"
    return path, tomllib.loads(path.read_text(encoding="utf-8"))


def iter_steps(steps: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for step in steps:
        yield step
        yield from iter_steps(step.get("children") or [])


def find_step(data: dict[str, Any], step_id: str, section: str) -> dict[str, Any]:
    matches = [step for step in iter_steps(data.get(section) or []) if step.get("id") == step_id]
    if len(matches) != 1:
        raise AssertionError(f"expected one {section} entry {step_id!r}, found {len(matches)}")
    return matches[0]


def raw_prompt(formula_path: Path, step: dict[str, Any]) -> str:
    return (formula_path.parent / step["description_file"]).read_text(encoding="utf-8")


def prompt_text(formula_path: Path, step: dict[str, Any]) -> str:
    return normalize(raw_prompt(formula_path, step))


def expansion_target(pack: str, build: str, stage: str) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build stage -> (expansion path, expansion data, stage step, checked `{target}` template)."""
    build_path, build_data = load_formula(pack, build)
    stage_step = find_step(build_data, stage, "steps")
    expansion = stage_step.get("expand")
    if not expansion:
        raise AssertionError(f"{build_path} stage {stage!r} no longer expands into a flow")
    exp_path, exp_data = load_formula(pack, expansion)
    target = find_step(exp_data, "{target}", "template")
    if CHECK_SCRIPT not in str(target.get("check")):
        raise AssertionError(f"{exp_path} {{target}} is no longer gated by {CHECK_SCRIPT}")
    return exp_path, exp_data, stage_step, target


def stage_path_keys(stage_step: dict[str, Any], target: dict[str, Any]) -> list[str]:
    raw = (stage_step.get("expand_vars") or {}).get("artifact_path_keys") or target["metadata"][
        "gc.build.artifact_path_keys"
    ]
    return [key.strip() for key in raw.split(",")]


def assert_prompt_example_validates(case: unittest.TestCase, prompt: str, schema_id: str) -> None:
    """The prompt's YAML front-matter example must pass the real validator.

    The example is wrapped in the body a compliant agent would write: every
    required section as a `##` heading in schema order, plus the ID/Status
    coverage table built from the example's own `trace.coverage`.
    """
    blocks = [m.group("body") for m in YAML_BLOCK_RE.finditer(prompt) if f"schema: {schema_id}" in m.group("body")]
    case.assertEqual(len(blocks), 1, f"expected one {schema_id} YAML example")
    front = blocks[0].strip()
    case.assertTrue(front.startswith("---\n") and front.endswith("\n---"), "example must be a --- fenced block")
    data = yaml.safe_load(front.strip("-\n"))
    case.assertIsInstance(data, dict)
    schema = VALIDATOR.load_schema(schema_id)
    for section in schema["required_sections"]:
        case.assertIn(normalize(section), normalize(prompt), f"prompt does not name section {section!r}")
    rows = "\n".join(f"| {row['id']} | {row['status']} |" for row in data["trace"]["coverage"])
    sections = "\n\n".join(f"## {section}\n\ntext" for section in schema["required_sections"])
    artifact = f"{front}\n\n| ID | Status |\n| --- | --- |\n{rows}\n\n{sections}\n"
    VALIDATOR.validate_artifact_text(artifact, expected_schema=schema_id)


class ReviewReportPathContractTests(unittest.TestCase):

    def test_gate_checks_review_and_final_report_paths(self) -> None:
        keys = [key for key, _ in gascity_pack_inference_gate.BUILD_BASIC_ARTIFACT_CONTRACTS]
        self.assertIn(REVIEW_REPORT_KEY, keys)
        self.assertIn(FINAL_REPORT_KEY, keys)

    def test_review_stages_check_review_report_path(self) -> None:
        for pack, build in REVIEW_BUILDS:
            with self.subTest(pack=pack):
                _, _, stage_step, target = expansion_target(pack, build, "review")
                self.assertIn(REVIEW_REPORT_KEY, stage_path_keys(stage_step, target))

    def test_review_target_prompts_publish_the_review_report(self) -> None:
        for pack, build in REVIEW_BUILDS:
            exp_path, _, _, target = expansion_target(pack, build, "review")
            text = prompt_text(exp_path, target)
            for fragment in REVIEW_TARGET_FRAGMENTS:
                with self.subTest(pack=pack, fragment=fragment):
                    self.assertIn(normalize(fragment), text)

    def test_review_stage_overrides_keep_the_build_base_contract(self) -> None:
        for pack, build in REVIEW_BUILDS:
            build_path, build_data = load_formula(pack, build)
            text = prompt_text(build_path, find_step(build_data, "review", "steps"))
            for fragment in REVIEW_OVERRIDE_FRAGMENTS:
                with self.subTest(pack=pack, fragment=fragment):
                    self.assertIn(normalize(fragment), text)


class CompoundFinalReportContractTests(unittest.TestCase):

    def setUp(self) -> None:
        self.exp_path, _, self.stage_step, self.target = expansion_target(
            "compound-engineering", "compound-build", "finalize"
        )

    def test_finalize_stage_checks_final_report_path(self) -> None:
        self.assertIn(FINAL_REPORT_KEY, stage_path_keys(self.stage_step, self.target))

    def test_finalize_target_writes_and_records_the_final_report(self) -> None:
        text = prompt_text(self.exp_path, self.target)
        for fragment in FINAL_TARGET_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(normalize(fragment), text)

    def test_finalize_target_front_matter_example_validates(self) -> None:
        assert_prompt_example_validates(self, raw_prompt(self.exp_path, self.target), "gc.build.final-report.v1")


class SuperpowersRequirementsContractTests(unittest.TestCase):

    def setUp(self) -> None:
        self.exp_path, self.exp_data, _, self.target = expansion_target(
            "superpowers", "superpowers-build", "requirements"
        )

    def child_step(self, suffix: str) -> dict[str, Any]:
        return find_step(self.exp_data, f"{{target}}.{suffix}", "template")

    def test_requirements_target_repairs_from_validator_errors(self) -> None:
        text = prompt_text(self.exp_path, self.target)
        for fragment in REQUIREMENTS_TARGET_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(normalize(fragment), text)

    def test_requirements_writer_states_the_front_matter_contract(self) -> None:
        text = prompt_text(self.exp_path, self.child_step("write-requirements-spec"))
        for fragment in REQUIREMENTS_WRITER_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(normalize(fragment), text)

    def test_requirements_writer_front_matter_example_validates(self) -> None:
        prompt = raw_prompt(self.exp_path, self.child_step("write-requirements-spec"))
        assert_prompt_example_validates(self, prompt, "gc.build.requirements.v1")

    def test_spec_feedback_preserves_front_matter(self) -> None:
        text = prompt_text(self.exp_path, self.child_step("apply-spec-feedback"))
        for fragment in REQUIREMENTS_FEEDBACK_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(normalize(fragment), text)


# (pack, build formula, build stage, lane suffix under the stage's expansion,
# schemas of the build artifacts that lane may edit in place).
APPLY_LANES = (
    ("gstack", "gstack-build", "plan-review", "apply-plan-review-findings", ("plan",)),
    ("compound-engineering", "compound-build", "plan-review", "apply-plan-findings", ("requirements", "plan")),
    ("superpowers", "superpowers-build", "plan-review", "apply-plan-feedback", ("requirements", "plan")),
    ("superpowers", "superpowers-build", "requirements", "apply-spec-feedback", ("requirements",)),
    ("bmad", "bmad-build", "review", "apply-bmad-review-findings", ("implementation-summary", "review")),
    ("compound-engineering", "compound-build", "review", "apply-review-findings", ("implementation-summary", "review")),
    ("gstack", "gstack-build", "review", "apply-review-findings", ("implementation-summary", "review")),
)

# Stages whose expansion lets a fix lane edit the plan: the `{target}` must
# re-validate it before the stage passes.
PLAN_REVIEW_BUILDS = (
    ("compound-engineering", "compound-build"),
    ("gstack", "gstack-build"),
    ("superpowers", "superpowers-build"),
)

APPLY_LANE_FRAGMENTS = (
    "preserve its yaml front matter",
    "do not invent statuses such as `reviewed`",
    "before closing with `gc.outcome=pass`, from `$gc_rig_root`, re-run the validator",
    "read the validator errors from `gc.attempt_log`",
)

PLAN_TARGET_FRAGMENTS = (
    f"gc_bead_id=<claimed-step-id> .gc/scripts/checks/{CHECK_SCRIPT}",
    "fix any error before setting `gc.outcome=pass`",
    "read the validator errors from `gc.attempt_log` on the validation loop control bead",
    "keep its yaml front matter intact",
)


def allowed_statuses(artifact: str) -> list[str]:
    return VALIDATOR.load_schema(f"gc.build.{artifact}.v1")["allowed_statuses"]


def status_sentence(artifact: str) -> str:
    """The exact allowed-status sentence, in schema order, built from the schema file."""
    statuses = [f"`{status}`" for status in allowed_statuses(artifact)]
    return normalize(f"`status` must be one of {', '.join(statuses[:-1])}, or {statuses[-1]}.")


class ApplyFindingsFrontMatterTests(unittest.TestCase):

    def test_validator_ships_beside_the_check_script(self) -> None:
        # Prompts call `.gc/scripts/validate_build_artifact.py`; the check lives
        # at `.gc/scripts/checks/build-artifact-valid.sh`, both from gascity/assets/scripts.
        scripts = REPO_ROOT / "gascity" / "assets" / "scripts"
        self.assertTrue((scripts / "validate_build_artifact.py").is_file())
        self.assertTrue((scripts / "checks" / CHECK_SCRIPT).is_file())

    def test_apply_lanes_keep_edited_artifacts_schema_valid(self) -> None:
        for pack, build, stage, lane, artifacts in APPLY_LANES:
            build_path, build_data = load_formula(pack, build)
            exp_path, exp_data = load_formula(pack, find_step(build_data, stage, "steps")["expand"])
            text = prompt_text(exp_path, find_step(exp_data, f"{{target}}.{lane}", "template"))
            for fragment in APPLY_LANE_FRAGMENTS:
                with self.subTest(pack=pack, lane=lane, fragment=fragment):
                    self.assertIn(normalize(fragment), text)
            for artifact in artifacts:
                schema_id = f"gc.build.{artifact}.v1"
                with self.subTest(pack=pack, lane=lane, schema=schema_id):
                    self.assertIn(f"python3 .gc/scripts/validate_build_artifact.py --schema {schema_id} --path", text)
                with self.subTest(pack=pack, lane=lane, schema=schema_id, check="allowed statuses"):
                    self.assertIn(status_sentence(artifact), text)

    def test_plan_review_targets_revalidate_the_plan(self) -> None:
        for pack, build in PLAN_REVIEW_BUILDS:
            exp_path, _, _, target = expansion_target(pack, build, "plan-review")
            metadata = target["metadata"]
            with self.subTest(pack=pack, check="metadata"):
                self.assertEqual(metadata.get("gc.build.artifact_schema"), "gc.build.plan.v1")
                keys = [key.strip() for key in metadata.get("gc.build.artifact_path_keys", "").split(",")]
                self.assertEqual(keys[0], "gc.build.plan_path")
                self.assertIn("gc.build.plan_path", [k for k, _ in gascity_pack_inference_gate.BUILD_BASIC_ARTIFACT_CONTRACTS])
            text = prompt_text(exp_path, target)
            for fragment in PLAN_TARGET_FRAGMENTS:
                with self.subTest(pack=pack, fragment=fragment):
                    self.assertIn(normalize(fragment), text)
            with self.subTest(pack=pack, check="allowed statuses"):
                self.assertIn(status_sentence("plan"), text)


if __name__ == "__main__":
    unittest.main()
