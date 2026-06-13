from __future__ import annotations

import os
import pathlib
import tomllib
import unittest


class FormulaAssetTests(unittest.TestCase):
    def test_implement_formula_shape(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        path = root / "formulas" / "implement-lazyjj.toml"

        data = tomllib.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["formula"], "implement-lazyjj")
        self.assertEqual(data["contract"], "graph.v2")
        self.assertIn("pack_root", data["vars"])
        self.assertTrue(data["vars"]["pack_root"]["required"])
        self.assertIn("base_revset", data["vars"])
        self.assertNotIn("base_ref", data["vars"])
        self.assertEqual(data["vars"]["lazyjj_work_formula"]["default"], "mol-polecat-lazyjj-work")

        step_ids = [step["id"] for step in data["steps"]]
        self.assertEqual(
            step_ids,
            [
                "prepare",
                "route-work",
                "wait-for-work",
                "prepare-gap-context",
                "gap-analysis-loop",
                "prepare-review-context",
                "review-loop",
                "finalize",
                "handoff-summary",
            ],
        )

        gap_loop = data["steps"][4]
        review_loop = data["steps"][6]
        self.assertEqual(gap_loop["ralph"]["check"]["path"], "{{pack_root}}/scripts/checks/gap-analysis-approved.sh")
        self.assertEqual(
            review_loop["ralph"]["check"]["path"],
            "{{pack_root}}/scripts/checks/implementation-review-approved.sh",
        )
        self.assertEqual([child["id"] for child in gap_loop["children"]], ["analyze-gaps", "apply-gap-fixes"])
        self.assertEqual(
            [child["id"] for child in review_loop["children"]],
            ["review-implementation", "apply-review-fixes"],
        )

    def test_check_scripts_are_executable_and_portable(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        scripts = sorted((root / "scripts" / "checks").glob("*.sh"))

        self.assertEqual(
            [script.name for script in scripts],
            ["gap-analysis-approved.sh", "implementation-review-approved.sh"],
        )
        for script in scripts:
            text = script.read_text(encoding="utf-8")
            self.assertTrue(os.access(script, os.X_OK), f"{script} must be executable")
            self.assertNotIn("/data/projects", text)
            self.assertNotIn("gascity-packs-worktrees", text)


if __name__ == "__main__":
    unittest.main()
