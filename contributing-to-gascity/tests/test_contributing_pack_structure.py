from __future__ import annotations

import os
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


EXPECTED_SKILLS = {
    "start-contribution",
    "orchestrate-contribution",
    "find-work",
    "fine-tune",
    "map-blast-radius",
    "plan-implementation",
    "review",
    "write-issue",
}


class PackStructureTests(unittest.TestCase):
    def test_pack_is_self_contained(self) -> None:
        """0.2.0 is END-TO-END self-contained: it must declare no imports."""
        text = (ROOT / "pack.toml").read_text(encoding="utf-8")
        # Only `[pack]` tables are allowed; any `[imports.*]` table breaks the
        # self-contained contract the 0.2.0 directive requires.
        self.assertNotRegex(
            text,
            r"(?m)^\[imports\.",
            "contributing 0.2.0 must not import any pack — it bakes the standards in",
        )

    def test_expected_skills_present(self) -> None:
        skills = {p.parent.name for p in ROOT.glob("skills/*/SKILL.md")}
        self.assertEqual(
            skills,
            EXPECTED_SKILLS,
            "the self-contained lifecycle requires exactly these eight skills",
        )

    def test_skill_name_matches_directory(self) -> None:
        for skill in sorted(ROOT.glob("skills/*/SKILL.md")):
            text = skill.read_text(encoding="utf-8")
            match = re.search(r"(?m)^name:\s*(\S+)", text)
            self.assertIsNotNone(match, f"{skill} missing name")
            self.assertEqual(
                match.group(1),
                skill.parent.name,
                f"{skill} frontmatter name must match its directory",
            )

    def test_doctor_check_scripts_are_executable(self) -> None:
        scripts = sorted(ROOT.glob("doctor/check-*.sh"))
        self.assertTrue(scripts, "expected at least one doctor check script")
        for script in scripts:
            self.assertTrue(
                os.access(script, os.X_OK),
                f"{script} must be executable (release hashes depend on the +x bit)",
            )


if __name__ == "__main__":
    unittest.main()
