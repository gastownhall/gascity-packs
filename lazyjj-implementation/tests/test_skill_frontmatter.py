from __future__ import annotations

import pathlib
import re
import unittest


class SkillFrontmatterTests(unittest.TestCase):
    def test_all_skills_have_name_and_description(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        skill_files = sorted(root.glob("skills/*/SKILL.md"))

        self.assertEqual([path.parent.name for path in skill_files], ["decompose", "design", "plan"])
        for path in skill_files:
            text = path.read_text(encoding="utf-8")
            match = re.match(r"\A---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
            self.assertIsNotNone(match, f"{path} missing YAML front matter")
            body = match.group("body") if match else ""
            self.assertRegex(body, r"(?m)^name:\s*\S+", f"{path} missing name")
            self.assertRegex(body, r"(?m)^description:\s*\S+", f"{path} missing description")


if __name__ == "__main__":
    unittest.main()
