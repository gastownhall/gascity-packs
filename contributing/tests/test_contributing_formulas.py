from __future__ import annotations

import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FORMULAS = ROOT / "formulas"
SKILLS = ROOT / "skills"

# Each thin wrapper formula delegates ALL standards to exactly one sibling
# skill, which stays the single source of truth. The formula adds only gc
# orchestration. write-issue is intentionally absent: issue authoring sits
# upstream of the PR flow, so it has no formula peer (use the skill directly).
FORMULA_TO_SKILL = {
    "mol-contributing-find-work": "find-work",
    "mol-contributing-plan-implementation": "plan-implementation",
    "mol-contributing-map-blast-radius": "map-blast-radius",
    "mol-contributing-review": "review",
    "mol-contributing-fine-tune": "fine-tune",
}


def _formula_files() -> list[pathlib.Path]:
    return sorted(FORMULAS.glob("*.formula.toml"))


class FormulaSetTests(unittest.TestCase):
    """The pack ships exactly the five thin wrappers — no more, no fewer."""

    def test_formulas_directory_exists(self) -> None:
        self.assertTrue(FORMULAS.is_dir(), "contributing/formulas/ must exist")

    def test_exactly_the_expected_formulas_are_present(self) -> None:
        names = {p.name[: -len(".formula.toml")] for p in _formula_files()}
        self.assertEqual(
            names,
            set(FORMULA_TO_SKILL),
            "formulas/ must contain exactly the five mol-contributing-* wrappers",
        )

    def test_write_issue_has_no_formula_peer(self) -> None:
        # Out of scope by design — guard against a future drive-by addition.
        self.assertFalse(
            (FORMULAS / "mol-contributing-write-issue.formula.toml").exists(),
            "write-issue authoring is upstream of the PR flow; it must have no formula",
        )


class FormulaWellFormednessTests(unittest.TestCase):
    """Every formula parses and has the plain step-formula shape its peers use."""

    def test_each_formula_parses_and_is_well_formed(self) -> None:
        for path in _formula_files():
            with self.subTest(formula=path.name):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                stem = path.name[: -len(".formula.toml")]
                self.assertEqual(
                    data.get("formula"),
                    stem,
                    "formula name must match the filename",
                )
                self.assertIn(stem, FORMULA_TO_SKILL, "unexpected formula")
                self.assertEqual(data.get("version"), 1)
                self.assertTrue(data.get("description"), "formula needs a description")
                steps = data.get("steps", [])
                self.assertTrue(steps, "formula must declare at least one step")

    def test_step_needs_reference_real_step_ids(self) -> None:
        for path in _formula_files():
            with self.subTest(formula=path.name):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                ids = {step["id"] for step in data["steps"]}
                for step in data["steps"]:
                    for need in step.get("needs", []):
                        self.assertIn(
                            need,
                            ids,
                            f"{path.name}: step {step['id']!r} needs unknown step {need!r}",
                        )


class FormulaSkillDelegationTests(unittest.TestCase):
    """The whole point: each wrapper references a REAL sibling skill, and the
    skill — not the formula — carries the standards."""

    def test_each_formula_references_its_real_sibling_skill(self) -> None:
        for stem, skill in FORMULA_TO_SKILL.items():
            with self.subTest(formula=stem):
                self.assertTrue(
                    (SKILLS / skill / "SKILL.md").exists(),
                    f"{stem} delegates to skills/{skill}, which must exist",
                )
                text = (FORMULAS / f"{stem}.formula.toml").read_text(encoding="utf-8")
                self.assertIn(
                    f"${{GC_PACK_DIR}}/skills/{skill}/SKILL.md",
                    text,
                    f"{stem} must reference its skill pack-relative via GC_PACK_DIR",
                )


class FormulaSelfContainmentTests(unittest.TestCase):
    """Formulas keep the pack standalone: no sibling-pack imports, no author
    host paths. Mirrors the pr-pipeline config-purity guard."""

    def test_no_sibling_pack_imports(self) -> None:
        for path in _formula_files():
            with self.subTest(formula=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("[imports.", text)
                self.assertNotIn(
                    "pr-pipeline",
                    text,
                    "formulas must reference the pack's own skills, not pr-pipeline",
                )

    def test_no_author_absolute_paths(self) -> None:
        for path in _formula_files():
            with self.subTest(formula=path.name):
                self.assertNotIn("/home/", path.read_text(encoding="utf-8"))


class FineTuneStopGuardTests(unittest.TestCase):
    """mol-contributing-fine-tune must carry the explicit STOP guard — its
    load-bearing safety contract is that it ends at the readiness report and
    never pushes."""

    def test_fine_tune_formula_declares_the_stop_guard(self) -> None:
        text = (FORMULAS / "mol-contributing-fine-tune.formula.toml").read_text(encoding="utf-8")
        self.assertIn(
            "MUST NOT run `git push` or `gh pr create`",
            text,
            "the ship wrapper must state the no-push / no-PR guard verbatim",
        )


if __name__ == "__main__":
    unittest.main()
