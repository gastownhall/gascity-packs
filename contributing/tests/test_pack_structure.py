from __future__ import annotations

import os
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PackStructureTests(unittest.TestCase):
    def test_pack_declares_pr_pipeline_import(self) -> None:
        """The contributing pack composes pr-pipeline; the pairing must be declared."""
        text = (ROOT / "pack.toml").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\[imports\.pr-pipeline\]")
        self.assertRegex(text, r"(?m)^\s*source\s*=")

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
