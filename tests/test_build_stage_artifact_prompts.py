"""Pin the artifact contract on the expansion prompts that close checked build stages.

When a build stage `expand`s into a methodology flow, gc drops the stage's own
prompt: only the expansion's step prompts reach agents. The flow's `{target}`
step is the one gated by `build-artifact-valid.sh`, and the build gate's final
artifact check reads the same workflow-root keys. So the instruction to write
the artifact and record its path has to live in the `{target}` prompt, not in
the stage override.

Two contract gaps surfaced in the gc v1.5.0 RC inference runs:

* bmad and superpowers (and, by inspection, compound-engineering and gstack)
  code-review flows never told the agent to record
  `gc.build.review_report_path` on the workflow root, so the review artifact
  check passed or failed depending on whether the model happened to do it.
* superpowers' requirements artifact lacked YAML front matter, and the
  requirements `{target}` repair attempts never read the validator errors in
  `gc.attempt_log`, so every repair closed without touching the file.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path
from typing import Any, Iterator

import yaml

from scripts import gascity_pack_inference_gate

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_REPORT_KEY = "gc.build.review_report_path"
CHECK_SCRIPT = "build-artifact-valid.sh"

# (pack, build formula) whose `review` stage expands into a code-review flow.
REVIEW_BUILDS = (
    ("bmad", "bmad-build"),
    ("compound-engineering", "compound-build"),
    ("gstack", "gstack-build"),
    ("superpowers", "superpowers-build"),
)

# Every fragment is matched lowercased with whitespace collapsed.
REVIEW_TARGET_FRAGMENTS = (
    f'gc bd update "<workflow-root-id>" --set-metadata "{REVIEW_REPORT_KEY}=<absolute path>"',
    "on the workflow root bead, not on the claimed step bead",
    f"use workflow root metadata `{REVIEW_REPORT_KEY}` when it is set",
    'cp -f "<',
    f"gc_bead_id=<claimed-step-id> .gc/scripts/checks/{CHECK_SCRIPT}",
    "fix any error before setting `gc.outcome=pass`",
    "read the validator errors from `gc.attempt_log` on the validation loop control bead",
)

REVIEW_OVERRIDE_FRAGMENTS = (
    f'gc bd update "<workflow-root-id>" --set-metadata "{REVIEW_REPORT_KEY}=<absolute path>"',
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
    "schema: gc.build.requirements.v1",
    "an `id` column and a `status` column",
)

REQUIREMENTS_FEEDBACK_FRAGMENTS = ("preserve its yaml front matter",)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


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


def prompt_text(formula_path: Path, step: dict[str, Any]) -> str:
    return normalize((formula_path.parent / step["description_file"]).read_text(encoding="utf-8"))


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


class ReviewReportPathContractTests(unittest.TestCase):

    def test_gate_checks_review_report_path(self) -> None:
        keys = [key for key, _ in gascity_pack_inference_gate.BUILD_BASIC_ARTIFACT_CONTRACTS]
        self.assertIn(REVIEW_REPORT_KEY, keys)

    def test_review_stages_check_review_report_path(self) -> None:
        for pack, build in REVIEW_BUILDS:
            with self.subTest(pack=pack):
                _, _, stage_step, _ = expansion_target(pack, build, "review")
                keys = stage_step["expand_vars"]["artifact_path_keys"].split(",")
                self.assertIn(REVIEW_REPORT_KEY, [key.strip() for key in keys])

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


class SuperpowersRequirementsContractTests(unittest.TestCase):

    def setUp(self) -> None:
        self.exp_path, self.exp_data, _, self.target = expansion_target(
            "superpowers", "superpowers-build", "requirements"
        )

    def child_prompt(self, suffix: str) -> str:
        return prompt_text(self.exp_path, find_step(self.exp_data, f"{{target}}.{suffix}", "template"))

    def test_requirements_target_repairs_from_validator_errors(self) -> None:
        text = prompt_text(self.exp_path, self.target)
        for fragment in REQUIREMENTS_TARGET_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(normalize(fragment), text)

    def test_requirements_writer_emits_schema_front_matter_and_sections(self) -> None:
        text = self.child_prompt("write-requirements-spec")
        for fragment in REQUIREMENTS_WRITER_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(normalize(fragment), text)
        schema = yaml.safe_load(
            (REPO_ROOT / "gascity" / "schemas" / "build" / "requirements.v1.yaml").read_text(encoding="utf-8")
        )
        for field in schema["required_front_matter"]:
            with self.subTest(front_matter=field):
                for part in field.split("."):
                    self.assertIn(f"{part}:", text)
        for section in schema["required_sections"]:
            with self.subTest(section=section):
                self.assertIn(normalize(section), text)

    def test_spec_feedback_preserves_front_matter(self) -> None:
        text = self.child_prompt("apply-spec-feedback")
        for fragment in REQUIREMENTS_FEEDBACK_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(normalize(fragment), text)


if __name__ == "__main__":
    unittest.main()
